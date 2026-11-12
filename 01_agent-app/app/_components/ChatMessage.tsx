'use client'

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ErrorType, GeneratedFile, HistoryItem, RetrievedContext, SourceField, SourceItem, ToolSource } from '../_lib/api-client'
import FeedbackModal from './FeedbackModal'

interface ChatMessageProps {
  item: HistoryItem
  showFeedback: boolean
  rating: boolean | null
  errorTypes: ErrorType[]
  onFeedback: (traceId: string, isOk: boolean, errorTypeId?: number, observations?: string) => Promise<void>
}

// Deriva campos label/valor de la metadata de un chunk de Qdrant, para mostrarlo
// con la misma grilla que el resto de las fuentes en vez de un bloque de texto suelto.
function contextFields(ctx: RetrievedContext): SourceField[] {
  const documentName = ctx.metadata.document_name as string | undefined
  const sourceFile = ctx.metadata.source_file as string | undefined
  const section = (ctx.metadata['Header 2'] ?? ctx.metadata['Header 1']) as string | undefined

  const fields: SourceField[] = []
  if (documentName) fields.push({ label: 'Documento', value: documentName })
  if (section) fields.push({ label: 'Sección', value: section })
  if (sourceFile) fields.push({ label: 'Archivo', value: sourceFile })
  fields.push({ label: 'Score', value: ctx.score.toFixed(2) })
  return fields
}

// Muestra los valores del input de la tool (ej. {name_or_id: "pikachu"} -> "pikachu"),
// para dar contexto de qué se consultó sin tener que exponer los nombres de los parámetros.
function sourceInputSummary(input?: Record<string, unknown> | null): string | null {
  if (!input) return null
  const values = Object.values(input).filter(
    (v) => typeof v === 'string' || typeof v === 'number',
  )
  return values.length > 0 ? values.join(', ') : null
}

function FieldsGrid({ fields }: { fields: SourceField[] }) {
  if (fields.length === 0) return null
  return (
    <dl className="grid min-w-0 grid-cols-[auto_1fr] gap-x-2 gap-y-0.5">
      {fields.map((field, i) => (
        <div key={i} className="contents">
          <dt className="font-medium text-zinc-600">{field.label}</dt>
          <dd className="min-w-0 break-words text-zinc-500">{field.value}</dd>
        </div>
      ))}
    </dl>
  )
}

function StructuredItem({ item, fallbackAlt }: { item: SourceItem; fallbackAlt: string }) {
  return (
    <div className="flex gap-3">
      {item.image_url && (
        item.image_link_only ? (
          <a
            href={item.image_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex h-16 w-16 shrink-0 flex-col items-center justify-center gap-1 rounded-md border border-zinc-200 bg-white text-center text-[10px] font-medium text-zinc-500 transition-colors hover:border-zinc-400 hover:text-zinc-700"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 3h6v6" />
              <path d="M10 14 21 3" />
              <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            </svg>
            Ver imagen
          </a>
        ) : (
          <img
            src={item.image_url}
            alt={item.title ?? fallbackAlt}
            loading="lazy"
            className="h-16 w-16 shrink-0 rounded-md border border-zinc-200 bg-white object-contain"
            onError={(e) => { e.currentTarget.style.display = 'none' }}
          />
        )
      )}
      <div className="min-w-0 flex-1">
        {item.title && <p className="font-medium text-zinc-600">{item.title}</p>}
        <FieldsGrid fields={item.fields} />
      </div>
    </div>
  )
}

function FileAttachment({ file }: { file: GeneratedFile }) {
  return (
    <a
      href={`data:${file.mime_type};base64,${file.data_base64}`}
      download={file.filename}
      className="flex max-w-[75%] items-center gap-2.5 rounded-xl border border-zinc-200 bg-white px-3 py-2.5 text-sm text-zinc-800 transition-colors hover:border-zinc-400"
    >
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-zinc-400">
        <path d="M14 2v6h6" />
        <path d="M4 22h16a2 2 0 0 0 2-2V8l-6-6H6a2 2 0 0 0-2 2v4" />
        <path d="M12 12v6" />
        <path d="m9 15 3 3 3-3" />
      </svg>
      <span className="min-w-0 flex-1 truncate font-medium">{file.filename}</span>
      <span className="shrink-0 text-xs text-zinc-400">Descargar</span>
    </a>
  )
}

function SourceCard({ source }: { source: ToolSource }) {
  const inputSummary = sourceInputSummary(source.input)
  const hasContexts = source.contexts.length > 0
  const hasFields = source.fields.length > 0
  const hasItems = source.items.length > 0

  return (
    <li className="rounded-lg border border-zinc-100 bg-zinc-50 p-2">
      <p className="font-medium text-zinc-700">
        {source.label}
        {inputSummary && <span className="font-normal text-zinc-400"> · {inputSummary}</span>}
      </p>

      {/* RAG: contextos recuperados de la base de conocimiento, con su metadata como campos */}
      {hasContexts && (
        <ul className="mt-1.5 flex flex-col gap-2">
          {source.contexts.map((ctx, i) => (
            <li key={i} className="border-l-2 border-zinc-200 pl-2">
              <FieldsGrid fields={contextFields(ctx)} />
              <p className="mt-1 line-clamp-2 text-zinc-500">{ctx.page_content}</p>
            </li>
          ))}
        </ul>
      )}

      {/* Ficha única estructurada (ej. get_pokemon / get_superhero): imagen + campos */}
      {hasFields && (
        <div className="mt-1.5">
          {source.title && <p className="mb-1 font-medium text-zinc-600">{source.title}</p>}
          <StructuredItem
            item={{
              title: null,
              image_url: source.image_url,
              image_link_only: source.image_link_only,
              fields: source.fields,
            }}
            fallbackAlt={source.label}
          />
        </div>
      )}

      {/* Varias fichas estructuradas en una sola llamada (ej. search_superheroes) */}
      {hasItems && (
        <ul className="mt-1.5 flex flex-col gap-2">
          {source.items.map((sourceItem, i) => (
            <li key={i} className="border-l-2 border-zinc-200 pl-2">
              <StructuredItem item={sourceItem} fallbackAlt={source.label} />
            </li>
          ))}
        </ul>
      )}

      {/* Fallback: solo texto plano de salida de la tool */}
      {!hasContexts && !hasFields && !hasItems && source.content && (
        <p className="mt-0.5 line-clamp-2 text-zinc-500">{source.content}</p>
      )}
    </li>
  )
}

export default function ChatMessage({ item, showFeedback, rating, errorTypes, onFeedback }: ChatMessageProps) {
  const sources = item.sources ?? []
  const files = item.files ?? []
  const [modalOpen, setModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const isRated = rating !== null

  async function handleLike() {
    if (isRated || submitting) return
    setSubmitting(true)
    try {
      await onFeedback(item.trace_id, true)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Pregunta del usuario */}
      <div className="flex justify-end">
        <div className="max-w-[75%] rounded-2xl rounded-tr-sm bg-zinc-100 px-4 py-2.5 text-sm text-zinc-900">
          {item.question}
        </div>
      </div>

      {/* Respuesta del agente */}
      <div className="flex flex-col items-start gap-1.5">
        <div className="max-w-[75%] rounded-2xl rounded-tl-sm border border-zinc-200 bg-white px-4 py-2.5 text-sm text-zinc-800">
          {item.answer
            ? <div className="prose prose-sm prose-zinc max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{item.answer}</ReactMarkdown>
              </div>
            : <p className="text-zinc-400">Pensando…</p>
          }

          {showFeedback && (
            <div className="mt-2 flex gap-1 border-t border-zinc-100 pt-2">
              <button
                aria-label="Respuesta correcta"
                onClick={handleLike}
                disabled={isRated || submitting}
                className={`rounded-lg p-1.5 transition-colors disabled:cursor-not-allowed ${
                  rating === true
                    ? 'text-green-500'
                    : rating === false
                      ? 'text-zinc-200'
                      : 'text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600'
                }`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill={rating === true ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M7 10v12" />
                  <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
                </svg>
              </button>
              <button
                aria-label="Respuesta incorrecta"
                onClick={() => !isRated && !submitting && setModalOpen(true)}
                disabled={isRated || submitting}
                className={`rounded-lg p-1.5 transition-colors disabled:cursor-not-allowed ${
                  rating === false
                    ? 'text-red-500'
                    : rating === true
                      ? 'text-zinc-200'
                      : 'text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600'
                }`}
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill={rating === false ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 14V2" />
                  <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {files.map((file, i) => (
          <FileAttachment key={i} file={file} />
        ))}

        {sources.length > 0 && (
          <details className="group max-w-[75%] rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500 open:bg-white">
            <summary className="cursor-pointer list-none font-medium text-zinc-500 marker:hidden group-open:text-zinc-700">
              Fuentes ({sources.length})
            </summary>
            <ul className="mt-2 flex flex-col gap-2">
              {sources.map((source, i) => (
                <SourceCard key={i} source={source} />
              ))}
            </ul>
          </details>
        )}
      </div>

      {modalOpen && (
        <FeedbackModal
          traceId={item.trace_id}
          errorTypes={errorTypes}
          onSubmit={(errorTypeId, observations) =>
            onFeedback(item.trace_id, false, errorTypeId, observations)
          }
          onClose={() => setModalOpen(false)}
        />
      )}
    </div>
  )
}
