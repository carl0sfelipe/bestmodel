-- 0014_run_reports.sql — S28: denúncia de run irreal + proveniência do import.
-- Mecânica "fake pego": denúncia confirmada = +5 pontos ao denunciante
-- (identificado); denúncia NUNCA altera o alvo por si só — confirmar é ato
-- de moderação (MODERATOR_HANDLES).

BEGIN;

CREATE TABLE IF NOT EXISTS run_report (
    id uuid PRIMARY KEY,
    target_kind text NOT NULL CHECK (target_kind IN ('run_claim','benchmark_run')),
    run_claim_id uuid REFERENCES run_claim(id),
    benchmark_run_id uuid REFERENCES benchmark_run(id),
    reporter_user_id uuid REFERENCES app_user(id),
    reason_category text NOT NULL CHECK (reason_category IN
        ('numbers_unreal','wrong_hardware','wrong_model','duplicate','other')),
    reason_detail text CHECK (reason_detail IS NULL OR char_length(reason_detail) <= 1000),
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','confirmed','dismissed')),
    awarded_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    -- exatamente um alvo, casando com target_kind
    CONSTRAINT run_report_target_chk CHECK (
        (target_kind = 'run_claim' AND run_claim_id IS NOT NULL AND benchmark_run_id IS NULL)
        OR (target_kind = 'benchmark_run' AND benchmark_run_id IS NOT NULL AND run_claim_id IS NULL)
    )
);

-- Um reporter sem denúncia em aberto duplicada para o mesmo alvo.
CREATE UNIQUE INDEX IF NOT EXISTS run_report_open_unique_idx
    ON run_report (
        COALESCE(reporter_user_id::text, 'anon'),
        target_kind,
        COALESCE(run_claim_id::text, '-'),
        COALESCE(benchmark_run_id::text, '-')
    )
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS run_report_status_idx ON run_report (status);

-- Proveniência estruturada do import (S28): fonte, snapshot, sha do arquivo.
ALTER TABLE run_claim ADD COLUMN IF NOT EXISTS provenance jsonb;

COMMIT;
