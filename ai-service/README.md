# StockFlow AI Service

FastAPI service for the StockFlow inventory assistant.

## Run

```bash
cd ai-service
uv run uvicorn ai_service.main:app --reload --port 8001
```

The service reads its settings from `ai-service/.env`. Do not reuse the Django
`.env` or the Django database user here.

## Endpoints

### `GET /health`

```json
{"status": "ok"}
```

### `POST /chat`

```json
{
  "message": "What is this app for?",
  "session_id": "optional-existing-session-id"
}
```

Response:

```json
{
  "answer": "StockFlow is an inventory management app...",
  "session_id": "generated-or-reused-session-id",
  "request_id": "request-id",
  "tools_used": []
}
```

Reuse the returned `session_id` for follow-up messages to keep conversation
memory. Memory is currently in-process; restarting the service clears it.

No tools are connected yet. The assistant will explain that live inventory data
is not available until the read-only data tools are added.
