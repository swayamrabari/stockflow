import os
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / '.env')

ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

DATABASE_URL = os.getenv('DATABASE_URL', '').strip()
if DATABASE_URL.startswith(('postgres://', 'postgresql://')):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)

if DATABASE_URL:
    parsed_database_url = urlsplit(DATABASE_URL)
    if (
        parsed_database_url.hostname
        and parsed_database_url.hostname.endswith('.supabase.co')
        and 'sslmode' not in dict(parse_qsl(parsed_database_url.query))
    ):
        database_query = parse_qsl(parsed_database_url.query)
        database_query.append(('sslmode', 'require'))
        DATABASE_URL = urlunsplit(
            parsed_database_url._replace(query=urlencode(database_query))
        )

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL') or None
AI_INTERNAL_TOKEN = os.getenv('AI_INTERNAL_TOKEN', '')
AI_MODEL = os.getenv('AI_MODEL', 'gpt-4o-mini')
AI_TEMPERATURE = float(os.getenv('AI_TEMPERATURE', '0'))
AI_REQUEST_TIMEOUT_SECONDS = int(os.getenv('AI_REQUEST_TIMEOUT_SECONDS', '45'))
AI_MAX_TOOL_CALLS = int(os.getenv('AI_MAX_TOOL_CALLS', '4'))
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '2'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '2'))
DB_POOL_RECYCLE_SECONDS = int(os.getenv('DB_POOL_RECYCLE_SECONDS', '1800'))
