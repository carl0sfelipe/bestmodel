pub mod collect_system_topology;
pub mod detect_runtime_installations;
pub mod execute_benchmark_scenario;
pub mod parse_runtime_output;
pub mod sign_submission_payload;
pub mod upload_benchmark_report;

#[derive(Clone, Copy)]
pub enum Runtime {
    LlamaCpp,
    Ollama,
    Mock,
}

impl Runtime {
    pub fn label(&self) -> &'static str {
        match self {
            Runtime::LlamaCpp => "llama.cpp",
            Runtime::Ollama => "Ollama",
            Runtime::Mock => "mock",
        }
    }

    pub fn engine_name(&self) -> &'static str {
        match self {
            Runtime::LlamaCpp => "llama_cpp",
            Runtime::Ollama => "ollama",
            Runtime::Mock => "mock",
        }
    }
}
