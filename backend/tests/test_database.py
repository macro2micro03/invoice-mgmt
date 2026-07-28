from app.database import _connect_args


def test_connect_args_sqlite_disables_same_thread_check():
    assert _connect_args("sqlite:///test.db") == {"check_same_thread": False}


def test_connect_args_postgres_is_empty():
    assert _connect_args("postgresql://user:pass@host:5432/db") == {}
