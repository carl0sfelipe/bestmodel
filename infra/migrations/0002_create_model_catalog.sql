BEGIN;

CREATE TYPE model_architecture AS ENUM (
  'dense',
  'moe',
  'multimodal'
);

CREATE TYPE quant_format AS ENUM (
  'fp16',
  'bf16',
  'fp8',
  'int8',
  'int4',
  'awq',
  'gptq',
  'exl2',
  'gguf_q2',
  'gguf_q3',
  'gguf_q4',
  'gguf_q5',
  'gguf_q6',
  'gguf_q8'
);

CREATE TYPE kv_cache_format AS ENUM (
  'fp16',
  'bf16',
  'fp8',
  'int8',
  'int4'
);

CREATE TYPE runtime_engine AS ENUM (
  'llama_cpp',
  'ollama',
  'vllm',
  'sglang',
  'exllamav2',
  'tensorrt_llm',
  'mlx',
  'lmstudio'
);

CREATE TABLE model_release (
  id TEXT PRIMARY KEY,
  family TEXT NOT NULL,
  release_name TEXT NOT NULL UNIQUE,
  architecture model_architecture NOT NULL,
  parameter_count_billion NUMERIC(10,3) NOT NULL,
  active_parameter_count_billion NUMERIC(10,3),
  num_layers INT NOT NULL CHECK (num_layers > 0),
  hidden_size INT NOT NULL CHECK (hidden_size > 0),
  num_attention_heads INT NOT NULL CHECK (num_attention_heads > 0),
  num_kv_heads INT NOT NULL CHECK (num_kv_heads > 0),
  head_dim INT NOT NULL CHECK (head_dim > 0),
  expert_count INT,
  experts_per_token INT,
  max_context_tokens INT NOT NULL CHECK (max_context_tokens > 0),
  released_at DATE
);

CREATE TABLE quantization_profile (
  id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL UNIQUE,
  weight_format quant_format NOT NULL,
  weight_bits NUMERIC(4,2) NOT NULL CHECK (weight_bits BETWEEN 2 AND 16),
  kv_cache_format kv_cache_format NOT NULL DEFAULT 'fp16',
  kv_cache_bits NUMERIC(4,2) NOT NULL CHECK (kv_cache_bits BETWEEN 4 AND 16),
  group_size INT,
  calibration_set TEXT,
  expected_quality_retention NUMERIC(5,4)
);

CREATE TABLE inference_runtime (
  id TEXT PRIMARY KEY,
  engine runtime_engine NOT NULL,
  version TEXT NOT NULL,
  supports_tensor_parallel BOOLEAN NOT NULL DEFAULT FALSE,
  supports_kv_cache_quant BOOLEAN NOT NULL DEFAULT FALSE,
  supports_cpu_offload BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (engine, version)
);

COMMIT;
