from sqlalchemy import create_engine, inspect, text

from app.migrations import TAG_COLUMNS, run_migrations


def _make_legacy_engine(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE invoices (id INTEGER PRIMARY KEY, material_type VARCHAR)"))
    return engine


def test_run_migrations_adds_missing_tag_columns(tmp_path):
    engine = _make_legacy_engine(tmp_path)
    run_migrations(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("invoices")}
    for column in TAG_COLUMNS:
        assert column in columns


def test_run_migrations_is_idempotent(tmp_path):
    engine = _make_legacy_engine(tmp_path)
    run_migrations(engine)
    run_migrations(engine)  # 두 번째 실행에서 에러가 나면 안 됨
    columns = {c["name"] for c in inspect(engine).get_columns("invoices")}
    for column in TAG_COLUMNS:
        assert column in columns


def test_run_migrations_skips_table_that_does_not_exist_yet(tmp_path):
    db_path = tmp_path / "empty.db"
    engine = create_engine(f"sqlite:///{db_path}")
    run_migrations(engine)  # invoices 테이블이 아예 없어도 에러 없이 통과해야 함


def _make_legacy_report_sequence_engine(tmp_path):
    db_path = tmp_path / "legacy_report_sequence.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            text("CREATE TABLE report_sequences (id INTEGER PRIMARY KEY, last_number INTEGER NOT NULL)")
        )
    return engine


def test_run_migrations_adds_missing_last_date_column(tmp_path):
    engine = _make_legacy_report_sequence_engine(tmp_path)
    run_migrations(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("report_sequences")}
    assert "last_date" in columns


def test_run_migrations_is_idempotent_for_report_sequences(tmp_path):
    engine = _make_legacy_report_sequence_engine(tmp_path)
    run_migrations(engine)
    run_migrations(engine)  # 두 번째 실행에서 에러가 나면 안 됨
    columns = {c["name"] for c in inspect(engine).get_columns("report_sequences")}
    assert "last_date" in columns
