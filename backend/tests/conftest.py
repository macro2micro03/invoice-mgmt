import os
import tempfile
from pathlib import Path

TEST_STORAGE_DIR = tempfile.mkdtemp(prefix="invoice_test_")
os.environ["STORAGE_DIR"] = TEST_STORAGE_DIR
os.environ["DATABASE_URL"] = f"sqlite:///{(Path(TEST_STORAGE_DIR) / 'test.db').as_posix()}"

import pytest  # noqa: E402

from app.database import Base, SessionLocal, engine  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
