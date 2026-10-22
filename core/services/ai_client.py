import httpx
from django.conf import settings


class AiServiceError(Exception):
    """Raised when the AI service cannot return an answer."""


def ask_ai(message: str, session_id: str) -> str:
    url = f'{settings.AI_SERVICE_URL.rstrip("/")}/chat'

    try:
        response = httpx.post(
            url,
            json={'message': message, 'session_id': session_id},
            timeout=settings.AI_TIMEOUT_SECONDS,
            headers={'X-Internal-Token': settings.AI_INTERNAL_TOKEN}
            if settings.AI_INTERNAL_TOKEN
            else {},
        )
        response.raise_for_status()
        data = response.json()
    except httpx.TimeoutException as exc:
        raise AiServiceError('The assistant took too long to respond.') from exc
    except httpx.RequestError as exc:
        raise AiServiceError('The assistant service is not running.') from exc
    except httpx.HTTPStatusError as exc:
        raise AiServiceError('The assistant could not answer right now.') from exc
    except ValueError as exc:
        raise AiServiceError('The assistant returned an invalid response.') from exc

    if not isinstance(data, dict):
        raise AiServiceError('The assistant returned an invalid response.')

    answer = data.get('answer')
    if not answer:
        raise AiServiceError('The assistant returned an empty answer.')

    return answer
