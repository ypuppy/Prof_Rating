import os
import sys

import pytest

# Point the app at a throwaway database *before* db.py reads DATABASE_URL
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://profrating:profrating@localhost:5432/profrating_test",
)
os.environ["SECRET_KEY"] = "test-secret"
os.environ["EMAIL_BACKEND"] = "console"
os.environ["ALLOWED_EMAIL_DOMAINS"] = "u.nus.edu"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text

import auth
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
        conn.execute(text(
            "TRUNCATE deleted_reviews, reviews, professors, sessions, login_codes, users RESTART IDENTITY CASCADE"
        ))
    yield


@pytest.fixture
def sent_codes(monkeypatch):
    """Captures emailed codes instead of printing them: {email: latest code}."""
    codes = {}
    monkeypatch.setattr(auth, "send_login_code", lambda email, code, ttl: codes.__setitem__(email, code))
    return codes


@pytest.fixture
def login(sent_codes):
    def _login(client, email="e0000001@u.nus.edu"):
        assert client.post("/auth/request-code", json={"email": email}).status_code == 200
        res = client.post("/auth/verify", json={"email": email, "code": sent_codes[email]})
        assert res.status_code == 200, res.text
        return res.json()
    return _login


@pytest.fixture
def anon():
    """A client with no session cookie."""
    return TestClient(app)


@pytest.fixture
def client(login):
    """A logged-in client."""
    c = TestClient(app)
    login(c)
    return c
