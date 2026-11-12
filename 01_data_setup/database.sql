CREATE TABLE history (
    trace_id    UUID      NOT NULL,
    session_id  UUID      NOT NULL,
    question    TEXT      NOT NULL,
    answer      TEXT      NOT NULL,
    "user"            VARCHAR(255),
    input_tokens  INTEGER,
    output_tokens INTEGER,
    created_at  TIMESTAMP    NOT NULL DEFAULT NOW(),
    retrieved_contexts text,
    CONSTRAINT pk_history PRIMARY KEY (trace_id)
);
CREATE INDEX ix_history_session_id ON history (session_id);
