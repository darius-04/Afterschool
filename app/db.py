"""Conexiunea la baza de date.

Implicit: PostgreSQL din docker-compose.
Fallback fara PostgreSQL: DATABASE_URL=sqlite:///afterschool.db (acelasi cod).
"""
import os

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://afterschool:afterschool@localhost:5432/afterschool"
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def create_tables() -> None:
    from app import models  # noqa: F401  (inregistreaza tabelele)

    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
