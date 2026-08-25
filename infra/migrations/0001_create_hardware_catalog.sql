BEGIN;

CREATE TYPE hardware_class AS ENUM (
  'gpu',
  'cpu',
  'npu',
  'integrated_gpu'
);

CREATE TABLE gpu_model (
  id TEXT PRIMARY KEY,
  vendor TEXT NOT NULL,
  marketing_name TEXT NOT NULL UNIQUE,
  vram_mib BIGINT NOT NULL CHECK (vram_mib > 0),
  memory_bandwidth_gib_s NUMERIC(12,2) NOT NULL CHECK (memory_bandwidth_gib_s > 0),
  fp16_tflops NUMERIC(10,2),
  int8_tops NUMERIC(10,2),
  tdp_watt INT NOT NULL CHECK (tdp_watt > 0),
  pcie_generation INT,
  pcie_lane_width INT,
  supports_nvlink BOOLEAN NOT NULL DEFAULT FALSE,
  released_at DATE
);

CREATE TABLE cpu_model (
  id TEXT PRIMARY KEY,
  vendor TEXT NOT NULL,
  marketing_name TEXT NOT NULL UNIQUE,
  physical_cores INT NOT NULL CHECK (physical_cores > 0),
  threads INT NOT NULL CHECK (threads > 0),
  memory_channels INT NOT NULL CHECK (memory_channels > 0),
  theoretical_memory_bandwidth_gib_s NUMERIC(12,2),
  tdp_watt INT
);

CREATE TABLE hardware_submission (
  id UUID PRIMARY KEY,
  owner_account_id UUID NOT NULL,
  gpu_model_id TEXT REFERENCES gpu_model(id),
  cpu_model_id TEXT REFERENCES cpu_model(id),
  gpu_count INT NOT NULL DEFAULT 1 CHECK (gpu_count > 0),
  ram_gib INT NOT NULL CHECK (ram_gib > 0),
  os_name TEXT NOT NULL,
  os_version TEXT NOT NULL,
  kernel_version TEXT,
  driver_version TEXT,
  cuda_version TEXT,
  rocm_version TEXT,
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  environment_snapshot JSONB NOT NULL
);

CREATE TABLE gpu_topology_link (
  id UUID PRIMARY KEY,
  hardware_submission_id UUID NOT NULL REFERENCES hardware_submission(id),
  gpu_index INT NOT NULL CHECK (gpu_index >= 0),
  numa_node INT,
  pcie_generation INT,
  pcie_lane_width INT,
  interconnect_type TEXT CHECK (interconnect_type IN ('pcie', 'nvlink', 'infinity_fabric', 'unknown')),
  peer_gpu_index INT
);

COMMIT;
