import asyncio
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from ai_service.agent.graph import extract_answer, get_agent
from ai_service.config import (
    AI_MAX_TOOL_CALLS,
    AI_INTERNAL_TOKEN,
    AI_MODEL,
    AI_REQUEST_TIMEOUT_SECONDS,
    ENVIRONMENT,
    LOG_LEVEL,
)
from ai_service.db import engine
from ai_service.schemas import ChatRequest, ChatResponse, HealthResponse

logging.basicConfig(
    level=LOG_LEVEL.upper(),
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Starting StockFlow AI service')
    yield
    if engine is not None:
        await engine.dispose()
    logger.info('Stopping StockFlow AI service')


app = FastAPI(
    title='StockFlow AI Service',
    version='0.1.0',
    lifespan=lifespan,
    docs_url='/docs' if ENVIRONMENT == 'development' else None,
    redoc_url=None,
    openapi_url='/openapi.json' if ENVIRONMENT == 'development' else None,
)


@app.middleware('http')
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get('X-Request-Id') or str(uuid.uuid4())
    request.state.request_id = request_id

    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            'HTTP request failed request_id=%s method=%s path=%s elapsed_ms=%.1f',
            request_id,
            request.method,
            request.url.path,
            (time.perf_counter() - started) * 1000,
        )
        raise

    if request.url.path == '/chat':
        logger.info(
            'HTTP request completed request_id=%s status=%s elapsed_ms=%.1f',
            request_id,
            response.status_code,
            (time.perf_counter() - started) * 1000,
        )
    response.headers['X-Request-Id'] = request_id
    return response


@app.get('/health', response_model=HealthResponse)
async def health():
    return {'status': 'ok'}


@app.post('/chat', response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    x_internal_token: str | None = Header(default=None),
):
    if AI_INTERNAL_TOKEN and not secrets.compare_digest(
        x_internal_token or '', AI_INTERNAL_TOKEN
    ):
        raise HTTPException(status_code=403, detail='Forbidden.')

    request_id = request.state.request_id
    session_id = (payload.session_id or '').strip() or str(uuid.uuid4())
    message = payload.message.strip()

    if not message:
        raise HTTPException(status_code=422, detail='Message cannot be empty.')

    try:
        agent = get_agent()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception('Could not initialize agent request_id=%s', request_id)
        raise HTTPException(
            status_code=503,
            detail='The assistant is not configured correctly.',
        ) from exc

    try:
        agent_started = time.perf_counter()
        async with asyncio.timeout(AI_REQUEST_TIMEOUT_SECONDS):
            result = await agent.ainvoke(
                {'messages': [{'role': 'user', 'content': message}]},
                config={
                    'configurable': {'thread_id': session_id},
                    'recursion_limit': AI_MAX_TOOL_CALLS,
                    'metadata': {'request_id': request_id},
                },
            )
        agent_elapsed_ms = (time.perf_counter() - agent_started) * 1000
    except TimeoutError as exc:
        elapsed_ms = (time.perf_counter() - agent_started) * 1000
        logger.warning(
            'Chat timed out request_id=%s elapsed_ms=%.1f timeout_seconds=%s',
            request_id,
            elapsed_ms,
            AI_REQUEST_TIMEOUT_SECONDS,
        )
        raise HTTPException(
            status_code=504,
            detail='The assistant took too long to respond.',
        ) from exc
    except Exception as exc:
        logger.exception(
            'Chat failed request_id=%s session_id=%s elapsed_ms=%.1f',
            request_id,
            session_id,
            (time.perf_counter() - agent_started) * 1000,
        )
        raise HTTPException(
            status_code=502,
            detail='The assistant could not answer right now.',
        ) from exc

    answer, tools_used = extract_answer(result)
    if not answer:
        answer = 'I could not generate a response.'

    logger.info(
        'Chat completed request_id=%s session_id=%s model=%s agent_elapsed_ms=%.1f tools=%s',
        request_id,
        session_id,
        AI_MODEL,
        agent_elapsed_ms,
        tools_used,
    )

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        request_id=request_id,
        tools_used=tools_used,
    )
