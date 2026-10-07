import os
import sys

import pytest

# Point the app at a throwaway database *before* db.py reads DATABASE_URL
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://profrating:profrating@localhost:5432/profrating_test",
)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

from db import engine
from main import app

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session", autouse=True)
def schema():
    """Build the schema with the real migrations, so tests also cover them."""
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE reviews, professors RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client():
    return TestClient(app)
