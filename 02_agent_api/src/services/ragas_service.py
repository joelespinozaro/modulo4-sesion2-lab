import json
import os
import uuid
from numbers import Number
from typing import Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.repositories.history_repository import HistoryRepository
from src.repositories.models.history import History
from src.repositories.models.ragas_evaluation import RagasEvaluation
from src.repositories.ragas_repository import RagasRepository
from src.utils.logger import get_logger

logger = get_logger(__name__)

LLM_JUDGE = "gpt-4o-mini"


def _aggregate_metric_values(values: List[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _normalize_ragas_scores(raw_scores) -> dict:
    scores: dict = {}

    if isinstance(raw_scores, dict):
        for metric_name, values in raw_scores.items():
            if isinstance(values, list):
                numeric_values = [float(v) for v in values if isinstance(v, Number)]
                scores[metric_name] = _aggregate_metric_values(numeric_values)
            elif isinstance(values, Number):
                scores[metric_name] = round(float(values), 4)
            else:
                scores[metric_name] = None
        return scores

    if isinstance(raw_scores, list):
        grouped: dict = {}
        for row in raw_scores:
            if not isinstance(row, dict):
                continue
            for metric_name, value in row.items():
                if not isinstance(value, Number):
                    continue
                grouped.setdefault(metric_name, []).append(float(value))

        for metric_name, values in grouped.items():
            scores[metric_name] = _aggregate_metric_values(values)

        return scores

    return scores


def _raise_ragas_dependency_error(exc: ModuleNotFoundError) -> None:
    logger.exception("Dependencia faltante/incompatible para RAGAS: %s", exc)
    raise HTTPException(
        status_code=503,
        detail=(
            "Dependencias de RAGAS incompletas o incompatibles. "
            "Reinstala dependencias del proyecto y asegúrate de tener "
            "langchain-community en versión compatible."
        ),
    ) from exc


def _extract_retrieved_contexts(record: History) -> List[str]:
    """Extrae los textos recuperados por RAG desde `History.sources`.

    `sources` guarda un JSON serializado de `List[ToolSource]` (ver
    dto/api_entities.py); sólo las tools de RAG llenan `contexts`, cada uno con
    `page_content` (no `text` como en el esquema plano de retrieved_contexts)."""
    sources_raw = getattr(record, "sources", None)
    if not sources_raw:
        return []

    try:
        sources = json.loads(sources_raw)
    except (TypeError, ValueError):
        return []

    if not isinstance(sources, list):
        return []

    return [
        context.get("page_content")
        for source in sources
        if isinstance(source, dict)
        for context in (source.get("contexts") or [])
        if isinstance(context, dict)
        and isinstance(context.get("page_content"), str)
        and context.get("page_content").strip()
    ]


class RagasService:
    def __init__(self, db: Session) -> None:
        self._history_repo = HistoryRepository(db)
        self._ragas_repo = RagasRepository(db)

    def evaluate(
        self,
        trace_ids: Optional[List[str]],
        session_id: Optional[str],
        ground_truths: Optional[Dict[str, str]],
    ) -> RagasEvaluation:
        """
        Orquesta la evaluación RAGAS:
        1. Recupera registros de History
        2. Construye el dataset
        3. Ejecuta la evaluación
        4. Exporta a LangSmith (si está configurado)
        5. Persiste y retorna el resultado
        """
        records = self._fetch_records(trace_ids, session_id)
        if not records:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron registros de historial para los criterios dados.",
            )

        dataset, valid_trace_ids, use_faithfulness = self._build_dataset(records, ground_truths)
        metrics_result = self._run_ragas(dataset, use_faithfulness=use_faithfulness)
        langsmith_url = self._export_to_langsmith(metrics_result, valid_trace_ids)

        evaluation = RagasEvaluation(
            id=str(uuid.uuid4()),
            trace_ids=valid_trace_ids,
            metrics=metrics_result,
            llm_judge=LLM_JUDGE,
            langsmith_run_url=langsmith_url,
        )
        return self._ragas_repo.save(evaluation)

    # ------------------------------------------------------------------
    # Métodos privados
    # ------------------------------------------------------------------

    def _fetch_records(
        self,
        trace_ids: Optional[List[str]],
        session_id: Optional[str],
    ) -> List[History]:
        if trace_ids:
            records = [
                self._history_repo.get_by_trace_id(tid)
                for tid in trace_ids
            ]
            return [r for r in records if r is not None]
        if session_id:
            return self._history_repo.get_all_by_session_id(session_id)
        raise HTTPException(
            status_code=422,
            detail="Debes proveer al menos 'trace_ids' o 'session_id'.",
        )

    def _build_dataset(
        self,
        records: List[History],
        ground_truths: Optional[Dict[str, str]],
    ):
        """Construye la lista de samples para RAGAS."""
        try:
            from ragas import EvaluationDataset, SingleTurnSample
        except ModuleNotFoundError as exc:
            _raise_ragas_dependency_error(exc)

        samples = []
        valid_trace_ids = []
        traces_with_contexts = 0

        for record in records:
            trace_id = str(record.trace_id)
            gt = (ground_truths or {}).get(trace_id)
            retrieved_contexts = _extract_retrieved_contexts(record)

            if retrieved_contexts:
                traces_with_contexts += 1

            sample = SingleTurnSample(
                user_input=record.question,
                response=record.answer,
                reference=gt,
                retrieved_contexts=retrieved_contexts,
            )
            samples.append(sample)
            valid_trace_ids.append(trace_id)

        use_faithfulness = traces_with_contexts == len(records)
        if not use_faithfulness:
            logger.info(
                "Omitiendo Faithfulness: %d/%d trace(s) con retrieved_contexts",
                traces_with_contexts,
                len(records),
            )

        return EvaluationDataset(samples=samples), valid_trace_ids, use_faithfulness

    def _run_ragas(self, dataset, use_faithfulness: bool) -> dict:
        """Ejecuta la evaluación RAGAS con GPT-4o-mini como LLM judge."""
        try:
            from langchain_openai import ChatOpenAI
            from ragas import evaluate
            from ragas.llms import LangchainLLMWrapper
            from ragas.metrics import AnswerRelevancy, Faithfulness
        except ModuleNotFoundError as exc:
            _raise_ragas_dependency_error(exc)

        logger.info("Iniciando evaluación RAGAS con %d sample(s)", len(dataset.samples))

        llm = LangchainLLMWrapper(ChatOpenAI(model=LLM_JUDGE, temperature=0))

        metrics = [AnswerRelevancy(llm=llm)]
        if use_faithfulness:
            metrics.append(Faithfulness(llm=llm))

        result = evaluate(dataset=dataset, metrics=metrics)

        scores = _normalize_ragas_scores(getattr(result, "scores", None))
        if not scores:
            logger.warning("No se pudieron normalizar métricas RAGAS desde result.scores=%s", type(getattr(result, "scores", None)).__name__)

        logger.info("Evaluación RAGAS completada: %s", scores)
        return scores

    def _export_to_langsmith(self, metrics: dict, trace_ids: List[str]) -> Optional[str]:
        """Exporta los resultados a LangSmith como feedback si está configurado."""
        langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
        langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

        if not langsmith_api_key:
            logger.info("LangSmith no configurado — omitiendo exportación")
            return None

        try:
            from langsmith import Client

            client = Client(api_url=langsmith_endpoint, api_key=langsmith_api_key)

            for trace_id in trace_ids:
                for metric_name, score in metrics.items():
                    if score is not None:
                        client.create_feedback(
                            run_id=trace_id,
                            key=f"ragas_{metric_name}",
                            score=score,
                            comment=f"RAGAS evaluation — judge: {LLM_JUDGE}",
                        )

            project = os.getenv("LANGSMITH_PROJECT", "default")
            url = f"{langsmith_endpoint}/o/default/projects/p/{project}"
            logger.info("Métricas exportadas a LangSmith: %s", url)
            return url

        except Exception as exc:
            logger.warning("Error exportando a LangSmith: %s", exc)
            return None
