pub mod collect_system_topology;
pub mod comfyui_adapter;
pub mod detect_runtime_installations;
pub mod execute_benchmark_scenario;
pub mod lab_recorder;
pub mod parse_runtime_output;
pub mod sign_submission_payload;
pub mod tuning_search;
pub mod upload_benchmark_report;

#[derive(Clone, Copy)]
pub enum Runtime {
    LlamaCpp,
    Ollama,
    Mock,
    ComfyUi,
}

impl Runtime {
    pub fn label(&self) -> &'static str {
        match self {
            Runtime::LlamaCpp => "llama.cpp",
            Runtime::Ollama => "Ollama",
            Runtime::Mock => "mock",
            Runtime::ComfyUi => "ComfyUI",
        }
    }

    pub fn engine_name(&self) -> &'static str {
        match self {
            Runtime::LlamaCpp => "llama_cpp",
            Runtime::Ollama => "ollama",
            Runtime::Mock => "mock",
            Runtime::ComfyUi => "comfyui",
        }
    }
}
