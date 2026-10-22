from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    request_id: str
    tools_used: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
