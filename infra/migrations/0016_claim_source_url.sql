-- 0016_claim_source_url.sql — S29 (rede de captura): o link da fonte onde
-- o run foi achado (reddit/twitter/github/blog). É a proveniência da
-- bagunça: claim nasce 'reported' apontando para o post original.
-- Null = run presenciado pelo próprio contribuidor (sem fonte externa).

BEGIN;
ALTER TABLE run_claim ADD COLUMN IF NOT EXISTS source_url text;
COMMIT;
