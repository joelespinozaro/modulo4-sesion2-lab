CREATE TABLE IF NOT EXISTS error_types (
    id SERIAL PRIMARY KEY,
    description VARCHAR(40) NOT NULL
);
INSERT INTO error_types(description)
SELECT * FROM (VALUES
    ('Sin respuesta a la pregunta'),
    ('Se inventó la respuesta'),
    ('Respuesta incompleta')
) AS v(description)
WHERE NOT EXISTS (SELECT 1 FROM error_types);

ALTER TABLE history ADD COLUMN IF NOT EXISTS is_ok BOOLEAN;
ALTER TABLE history ADD COLUMN IF NOT EXISTS error_type_id INTEGER REFERENCES error_types(id);
ALTER TABLE history ADD COLUMN IF NOT EXISTS observations TEXT;

CREATE TABLE IF NOT EXISTS ragas_evaluations (
    id                VARCHAR         PRIMARY KEY,
    trace_ids         JSONB           NOT NULL,
    metrics           JSONB           NOT NULL,
    llm_judge         VARCHAR         NOT NULL DEFAULT 'gpt-4o-mini',
    langsmith_run_url VARCHAR,
    evaluated_at      TIMESTAMP       NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ragas_evaluations_evaluated_at ON ragas_evaluations (evaluated_at DESC);
