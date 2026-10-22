from ai_service import main
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage


class FakeAgent:
    async def ainvoke(self, inputs, config=None):
        return {
            'messages': [
                *inputs['messages'],
                AIMessage(content='Fake answer'),
            ]
        }


def test_health():
    with TestClient(main.app) as client:
        response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_chat_returns_answer_and_session(monkeypatch):
    monkeypatch.setattr(main, 'get_agent', lambda: FakeAgent())

    with TestClient(main.app) as client:
        response = client.post(
            '/chat',
            json={'message': 'Hello', 'session_id': 'session-1'},
            headers={'X-Request-Id': 'request-1'},
        )

    assert response.status_code == 200
    assert response.headers['X-Request-Id'] == 'request-1'

    body = response.json()
    assert body['answer'] == 'Fake answer'
    assert body['session_id'] == 'session-1'
    assert body['request_id'] == 'request-1'
    assert body['tools_used'] == []
