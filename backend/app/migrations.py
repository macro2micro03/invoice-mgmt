from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

TAG_COLUMNS = {
    "tag_photo_path": "VARCHAR",
    "tag_site_name": "VARCHAR",
    "tag_location": "VARCHAR",
    "tag_diameter": "VARCHAR",
    "tag_grade": "VARCHAR",
    "tag_length": "VARCHAR",
    "tag_quantity": "VARCHAR",
    "tag_shape": "VARCHAR",
    "tag_match_status": "VARCHAR",
}


def run_migrations(engine: Engine) -> None:
    inspector = inspect(engine)
    if "invoices" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("invoices")}
        missing = {name: col_type for name, col_type in TAG_COLUMNS.items() if name not in existing_columns}
        if missing:
            with engine.begin() as conn:
                for column, col_type in missing.items():
                    conn.execute(text(f"ALTER TABLE invoices ADD COLUMN {column} {col_type}"))

    if "report_sequences" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("report_sequences")}
        if "last_date" not in existing_columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE report_sequences ADD COLUMN last_date DATE"))
