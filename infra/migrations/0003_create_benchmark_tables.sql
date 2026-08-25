BEGIN;

CREATE TYPE benchmark_status AS ENUM (
  'submitted',
  'validated',
  'quarantined',
  'rejected'
);

CREATE TYPE metric_kind AS ENUM (
  'ttft_ms',
  'prefill_tok_s',
  'decode_tok_s',
  'peak_vram_mib',
  'peak_ram_mib',
  'power_watt_avg',
  'temperature_c_max',
  'energy_joule'
);

CREATE TYPE artifact_kind AS ENUM (
  'runtime_stdout',
  'runtime_stderr',
  'runtime_config',
  'gpu_smi_trace',
  'system_topology',
  'screenshot',
  'prompt_template'
);

CREATE TABLE benchmark_scenario (
  id UUID PRIMARY KEY,
  prompt_tokens INT NOT NULL CHECK (prompt_tokens >= 0),
  generated_tokens INT NOT NULL CHECK (generated_tokens > 0),
  context_tokens INT NOT NULL CHECK (context_tokens > 0),
  batch_size INT NOT NULL CHECK (batch_size > 0),
  tensor_parallel INT NOT NULL DEFAULT 1 CHECK (tensor_parallel > 0)
);

CREATE TABLE benchmark_run (
  id UUID PRIMARY KEY,
  hardware_submission_id UUID NOT NULL REFERENCES hardware_submission(id),
  model_release_id TEXT NOT NULL REFERENCES model_release(id),
  quantization_profile_id TEXT NOT NULL REFERENCES quantization_profile(id),
  inference_runtime_id TEXT NOT NULL REFERENCES inference_runtime(id),
  benchmark_scenario_id UUID NOT NULL REFERENCES benchmark_scenario(id),
  status benchmark_status NOT NULL DEFAULT 'submitted',
  client_version TEXT NOT NULL,
  signature TEXT NOT NULL,
  payload_digest TEXT NOT NULL,
  trust_score NUMERIC(5,4),
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX benchmark_run_lookup_idx
ON benchmark_run (
  hardware_submission_id,
  model_release_id,
  quantization_profile_id,
  inference_runtime_id,
  benchmark_scenario_id
);

CREATE TABLE benchmark_metric (
  benchmark_run_id UUID NOT NULL REFERENCES benchmark_run(id),
  kind metric_kind NOT NULL,
  p50_value NUMERIC(18,4),
  p90_value NUMERIC(18,4),
  unit TEXT NOT NULL,
  PRIMARY KEY (benchmark_run_id, kind)
);

CREATE TABLE benchmark_artifact (
  id UUID PRIMARY KEY,
  benchmark_run_id UUID NOT NULL REFERENCES benchmark_run(id),
  artifact_kind artifact_kind NOT NULL,
  sha256_digest TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
