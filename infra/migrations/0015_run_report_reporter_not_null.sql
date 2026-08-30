-- 0015_run_report_reporter_not_null.sql — S28 MELHORAR (veredito E6, Fable
-- 2026-08-31): "reporter_user_id é nullable no 0014 enquanto a API exige
-- auth; NOT NULL fecha o contrato DB=API antes que um segundo write path
-- apareça". Também trava re-denúncia do MESMO reporter sobre o MESMO alvo
-- após dismiss (risco 4 do E6: loop de re-report custa atenção do
-- moderador único). Confirmed não entra no índice: alvo confirmado vira
-- refuted, e novos denunciantes continuam podendo reportar.

BEGIN;

ALTER TABLE run_report ALTER COLUMN reporter_user_id SET NOT NULL;

DROP INDEX IF EXISTS run_report_open_unique_idx;

CREATE UNIQUE INDEX IF NOT EXISTS run_report_reporter_target_idx
    ON run_report (
        reporter_user_id,
        target_kind,
        COALESCE(run_claim_id::text, '-'),
        COALESCE(benchmark_run_id::text, '-')
    )
    WHERE status IN ('open', 'dismissed');

COMMIT;
