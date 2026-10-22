import asyncio
import logging
import secrets
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from ai_service.agent.graph import extract_answer, get_agent
from ai_service.config import (
    AI_MAX_TOOL_CALLS,
    AI_INTERNAL_TOKEN,
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

    response = await call_next(request)
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
        async with asyncio.timeout(AI_REQUEST_TIMEOUT_SECONDS):
            result = await agent.ainvoke(
                {'messages': [{'role': 'user', 'content': message}]},
                config={
                    'configurable': {'thread_id': session_id},
                    'recursion_limit': AI_MAX_TOOL_CALLS,
                },
            )
    except TimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail='The assistant took too long to respond.',
        ) from exc
    except Exception as exc:
        logger.exception(
            'Chat failed request_id=%s session_id=%s',
            request_id,
            session_id,
        )
        raise HTTPException(
            status_code=502,
            detail='The assistant could not answer right now.',
        ) from exc

    answer, tools_used = extract_answer(result)
    if not answer:
        answer = 'I could not generate a response.'

    logger.info(
        'Chat request_id=%s session_id=%s tools=%s',
        request_id,
        session_id,
        tools_used,
    )

    return ChatResponse(
        answer=answer,
        session_id=session_id,
        request_id=request_id,
        tools_used=tools_used,
    )
