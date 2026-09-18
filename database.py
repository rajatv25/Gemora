import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

database_url = os.getenv("DATABASE_URL", "sqlite:///test.db")

# CONNECT TO DATABASE
engine_options = {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def ensure_legacy_columns():
    """Add nullable columns needed by newer models to existing local databases."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    bill_columns = {column["name"] for column in inspector.get_columns("bills")} if "bills" in tables else set()
    new_bill_columns = {
        "customer_id": "INTEGER", "gross_weight": "FLOAT", "stone_weight": "FLOAT", "net_weight": "FLOAT",
        "metal_rate": "FLOAT", "purity_percentage": "FLOAT", "making_charge_percentage": "FLOAT",
        "wastage_amount": "FLOAT", "stone_charges": "FLOAT", "diamond_charges": "FLOAT",
        "discount_amount": "FLOAT", "gst_percent": "FLOAT",
    }
    missing = {name: sql_type for name, sql_type in new_bill_columns.items() if name not in bill_columns}
    if missing:
        with engine.begin() as connection:
            for name, sql_type in missing.items():
                connection.execute(text(f"ALTER TABLE bills ADD COLUMN {name} {sql_type} NOT NULL DEFAULT 0"))

# dependency database session function
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
