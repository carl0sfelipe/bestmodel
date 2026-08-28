BEGIN;

-- Story 1.3 (Épico 1): recipe entity + video-aware run/scenario.
-- Idempotent by construction (IF NOT EXISTS + DO blocks): safe to re-run
-- even outside migrate.py's filename ledger.

-- Video runtime engine (comfyui) joins the catalog enum. ADD VALUE inside a
-- transaction is allowed on PG >= 12; the seed loader runs in its own
-- transaction afterwards, so the new value is usable there.
ALTER TYPE runtime_engine ADD VALUE IF NOT EXISTS 'comfyui';

CREATE TABLE IF NOT EXISTS recipe (
  recipe_id TEXT PRIMARY KEY,
  runtime TEXT NOT NULL,
  workflow_sha256 TEXT,
  params JSONB NOT NULL,
  model_release_id TEXT NOT NULL,
  quantization_profile_id TEXT,
  comfyui_version TEXT,
  author TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO recipe (recipe_id, runtime, params, model_release_id, comfyui_version, author)
VALUES (
  'wan22-flf2v-720p-81f-v1',
  'comfyui',
  '{"model":"wan22-i2v-flf2v","width":1280,"height":720,"frames":81,"steps":20,"cfg":3.5,"shift":5.0,"seed":42}'::jsonb,
  'model-wan22-i2v-flf2v-14b',
  '0.3.48',
  'seed'
)
ON CONFLICT (recipe_id) DO NOTHING;

ALTER TABLE benchmark_run ADD COLUMN IF NOT EXISTS recipe_id TEXT REFERENCES recipe(recipe_id);
ALTER TABLE benchmark_run ADD COLUMN IF NOT EXISTS source_class TEXT;
ALTER TABLE benchmark_run ADD COLUMN IF NOT EXISTS seconds_per_clip REAL;
ALTER TABLE benchmark_run ADD COLUMN IF NOT EXISTS it_per_s REAL;
ALTER TABLE benchmark_run ADD COLUMN IF NOT EXISTS frames_per_s REAL;
ALTER TABLE benchmark_run ADD COLUMN IF NOT EXISTS source_url TEXT;

-- Null-safe backfill: every pre-existing run is an owner-signed measurement.
UPDATE benchmark_run SET source_class = 'measured_signed' WHERE source_class IS NULL;
ALTER TABLE benchmark_run ALTER COLUMN source_class SET DEFAULT 'measured_signed';

-- benchmark_scenario becomes video-aware: token columns stay for LLM runs,
-- video runs carry their own fields (AD-1: never reuse token fields).
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS scenario_kind TEXT NOT NULL DEFAULT 'llm';
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS width INT;
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS height INT;
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS frames INT;
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS steps INT;
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS cfg REAL;
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS shift REAL;
ALTER TABLE benchmark_scenario ADD COLUMN IF NOT EXISTS seed BIGINT;

ALTER TABLE benchmark_scenario ALTER COLUMN prompt_tokens DROP NOT NULL;
ALTER TABLE benchmark_scenario ALTER COLUMN generated_tokens DROP NOT NULL;
ALTER TABLE benchmark_scenario ALTER COLUMN context_tokens DROP NOT NULL;
ALTER TABLE benchmark_scenario ALTER COLUMN batch_size DROP NOT NULL;

ALTER TABLE benchmark_scenario DROP CONSTRAINT IF EXISTS benchmark_scenario_prompt_tokens_check;
ALTER TABLE benchmark_scenario DROP CONSTRAINT IF EXISTS benchmark_scenario_generated_tokens_check;
ALTER TABLE benchmark_scenario DROP CONSTRAINT IF EXISTS benchmark_scenario_context_tokens_check;
ALTER TABLE benchmark_scenario DROP CONSTRAINT IF EXISTS benchmark_scenario_batch_size_check;

DO $$
BEGIN
  ALTER TABLE benchmark_scenario ADD CONSTRAINT scenario_llm_fields_check
    CHECK (
      scenario_kind <> 'llm'
      OR (
        prompt_tokens IS NOT NULL AND prompt_tokens >= 0
        AND generated_tokens IS NOT NULL AND generated_tokens > 0
        AND context_tokens IS NOT NULL AND context_tokens > 0
        AND batch_size IS NOT NULL AND batch_size > 0
      )
    );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
  ALTER TABLE benchmark_scenario ADD CONSTRAINT scenario_video_fields_check
    CHECK (
      scenario_kind <> 'video'
      OR (
        width IS NOT NULL AND width > 0
        AND height IS NOT NULL AND height > 0
        AND frames IS NOT NULL AND frames > 0
        AND steps IS NOT NULL AND steps > 0
      )
    );
EXCEPTION
  WHEN duplicate_object THEN NULL;
END $$;

COMMIT;
