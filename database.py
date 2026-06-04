import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Default to SQLite local database, but allow overriding via environment variable
# e.g., DATABASE_URL=postgresql://user:pass@host:port/dbname for Render
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./avoflow.db")

# Render databases sometimes start with "postgres://" which SQLAlchemy 1.4+ doesn't support.
# We must replace it with "postgresql://" if it exists.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Conditional arguments for SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency to get the DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
