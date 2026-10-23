from datetime import date
from functools import lru_cache

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from ai_service.config import (
    AI_MODEL,
    AI_REQUEST_TIMEOUT_SECONDS,
    AI_TEMPERATURE,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
)
from ai_service.agent.tools import READ_ONLY_TOOLS

SYSTEM_PROMPT = f"""You are StockFlow Assistant for an inventory management app.

Today is {date.today().strftime('%d/%m/%Y')}.

Rules:
- Only answer questions about inventory management, this app, or the data it contains.
- If a question is unrelated, politely say you can only help with inventory and app-related questions.
- You are read-only. Never claim to create, update, or delete records.
- Never invent numbers or live data.
- You have read-only live inventory tools. Use them for current stock, sales, purchases, suppliers, customers, and movements.
- Never claim a write action. You cannot create, update, delete, receive, dispatch, or adjust records.
- Use tools when the user asks about current data; never invent missing values.
- Keep answers short and clear.
- Use INR for money and d/m/Y for dates.
- Use plain text formatting. Do not use bold, italics, tables, or headings unless the user asks for them.
- For multiple results, use simple lines beginning with '-'.
- Avoid em dashes and decorative punctuation; use commas, colons, or parentheses instead.
- Keep each list item concise and put the most useful details on one line.
"""


@lru_cache(maxsize=1)
def get_agent():
    """Build the agent once and reuse its in-memory session store."""
    api_key = OPENAI_API_KEY
    base_url = OPENAI_BASE_URL

    if not api_key and not base_url:
        raise RuntimeError(
            'LLM is not configured. Set OPENAI_API_KEY or OPENAI_BASE_URL '
            'in ai-service/.env.'
        )

    model = ChatOpenAI(
        model=AI_MODEL,
        temperature=AI_TEMPERATURE,
        api_key=api_key or 'not-needed',
        base_url=base_url,
        timeout=AI_REQUEST_TIMEOUT_SECONDS,
        max_retries=1,
    )

    return create_agent(
        model=model,
        tools=READ_ONLY_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        checkpointer=InMemorySaver(),
    )


def extract_answer(result: dict) -> tuple[str, list[str]]:
    """Return the final assistant text and the tools it called."""
    messages = result.get('messages', [])

    tools_used: list[str] = []
    for message in messages:
        for call in getattr(message, 'tool_calls', None) or []:
            name = call.get('name')
            if name and name not in tools_used:
                tools_used.append(name)

    answer = ''
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            answer = message.text or ''
            if answer:
                break

    return answer.strip(), tools_used
