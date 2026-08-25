BEGIN;

CREATE TABLE trust_assessment (
  benchmark_run_id UUID PRIMARY KEY REFERENCES benchmark_run(id),
  environment_completeness NUMERIC(5,4) NOT NULL,
  statistical_plausibility NUMERIC(5,4) NOT NULL,
  reproducibility_score NUMERIC(5,4) NOT NULL,
  account_maturity NUMERIC(5,4) NOT NULL,
  peer_corroboration NUMERIC(5,4) NOT NULL,
  final_score NUMERIC(5,4) NOT NULL,
  outlier_flags TEXT[] NOT NULL DEFAULT '{}',
  assessed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE model_quality_evaluation (
  id UUID PRIMARY KEY,
  model_release_id TEXT NOT NULL REFERENCES model_release(id),
  quantization_profile_id TEXT NOT NULL REFERENCES quantization_profile(id),
  benchmark_name TEXT NOT NULL CHECK (benchmark_name IN ('mmlu', 'humaneval', 'gsm8k', 'mbpp', 'custom')),
  baseline_score NUMERIC(8,4) NOT NULL,
  quantized_score NUMERIC(8,4) NOT NULL,
  retention NUMERIC(5,4) NOT NULL,
  source TEXT NOT NULL,
  evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE price_quote (
  id UUID PRIMARY KEY,
  component_type TEXT NOT NULL CHECK (component_type IN ('gpu', 'cpu', 'memory', 'machine')),
  component_reference_id TEXT,
  vendor TEXT NOT NULL,
  price_usd NUMERIC(12,2) NOT NULL CHECK (price_usd >= 0),
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roi_assumption (
  id UUID PRIMARY KEY,
  electricity_usd_per_kwh NUMERIC(8,4) NOT NULL,
  hardware_amortization_months INT NOT NULL CHECK (hardware_amortization_months > 0),
  utilization_ratio NUMERIC(4,3) NOT NULL CHECK (utilization_ratio BETWEEN 0 AND 1),
  api_input_price_usd_per_mtok NUMERIC(10,4),
  api_output_price_usd_per_mtok NUMERIC(10,4),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;
