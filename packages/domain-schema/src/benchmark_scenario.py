from pydantic import BaseModel, Field


class BenchmarkScenario(BaseModel):
    prompt_tokens: int = Field(ge=0)
    generated_tokens: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    context_tokens: int = Field(gt=0)
