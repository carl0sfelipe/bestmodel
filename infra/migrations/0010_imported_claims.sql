BEGIN;

-- S22 (localmaxxing import): provenance for owner-less, community-imported
-- claims. A claim is either user-created (claimant set) or imported
-- (source + unique external_ref set); never both.

ALTER TABLE run_claim ALTER COLUMN claimant_id DROP NOT NULL;

ALTER TABLE run_claim ADD COLUMN source TEXT;
ALTER TABLE run_claim ADD COLUMN external_ref TEXT UNIQUE;

ALTER TABLE run_claim ADD CONSTRAINT run_claim_source_values_chk
  CHECK (source IS NULL OR source = 'localmaxxing');

ALTER TABLE run_claim ADD CONSTRAINT run_claim_provenance_chk
  CHECK (
    (claimant_id IS NOT NULL AND source IS NULL)
    OR (claimant_id IS NULL AND source IS NOT NULL AND external_ref IS NOT NULL)
  );

COMMIT;
