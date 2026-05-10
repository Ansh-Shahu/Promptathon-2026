# backend/database.py

"""
database.py
─────────────────────────────────────────────────────────────────────────────
SQLAlchemy 2.0 database configuration, session factory, and FastAPI dependency
injection for the HVAC Chiller Predictive Maintenance persistence layer.

Architecture
────────────
  Engine       — Single shared connection pool bound to the SQLite file.
  SessionLocal — Factory producing per-request database sessions. Each
                 session is the unit of work for one HTTP request lifecycle.
  Base         — Declarative base class inherited by all ORM model definitions.
  get_db()     — FastAPI dependency that yields a scoped session and
                 guarantees teardown via a finally block.

SQLite vs. Production Databases
────────────────────────────────
  SQLite is used here for zero-configuration local development and hackathon
  portability. To migrate to PostgreSQL or MySQL for production, replace
  SQLALCHEMY_DATABASE_URL with the appropriate connection string and remove
  the `connect_args` override — it is SQLite-specific.

  Example PostgreSQL swap:
    SQLALCHEMY_DATABASE_URL = (
        "postgresql+psycopg2://user:password@host:5432/hvac_telemetry"
    )
    engine = create_engine(SQLALCHEMY_DATABASE_URL)  # no connect_args needed
"""

import os
from typing import Generator
from config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ══════════════════════════════════════════════════════════════════════════════
#  CONNECTION STRING
# ══════════════════════════════════════════════════════════════════════════════

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///./"):
    db_name = SQLALCHEMY_DATABASE_URL.replace("sqlite:///./", "")
    db_path = os.path.join(os.path.dirname(__file__), db_name)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"
"""
SQLite connection string.

The `./` prefix resolves the database file relative to the working directory
from which uvicorn is launched (typically the project root). The file is
created automatically on first connection if it does not exist.

For an in-memory database (useful in test fixtures), replace with:
    "sqlite:///:memory:"
"""

# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE
# ══════════════════════════════════════════════════════════════════════════════

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
"""
SQLAlchemy engine: manages the underlying connection pool and dialect.

`connect_args={"check_same_thread": False}` — SQLite Thread-Safety Override
─────────────────────────────────────────────────────────────────────────────
SQLite's default Python driver (sqlite3) enforces a strict rule: a database
connection created in one thread must not be used in another. This guard was
designed for synchronous, single-threaded applications where sharing a
connection across threads without external locking would cause data corruption.

FastAPI violates this assumption in two ways:

  1. ASYNC WORKERS: FastAPI runs on an ASGI event loop (uvicorn/asyncio).
     Even synchronous route handlers are dispatched to a thread pool executor,
     meaning the thread that creates the SQLAlchemy session during dependency
     injection may differ from the thread that executes the route handler's
     database operations.

  2. CONCURRENT REQUESTS: Multiple simultaneous requests share the same
     SQLAlchemy connection pool. Without this override, the second concurrent
     request to touch the database raises:
       ProgrammingError: SQLite objects created in a thread can only be used
       in that same thread.

Setting `check_same_thread=False` disables this driver-level guard and
delegates thread safety to SQLAlchemy's connection pool and the per-request
session scoping enforced by `get_db()`. Because each request receives its
own `SessionLocal` instance (yielded fresh and closed in the finally block),
sessions are never shared across requests — making this override safe in the
FastAPI concurrency model.

DO NOT disable this check in a raw sqlite3 connection that is shared across
threads without SQLAlchemy's session management layer.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION FACTORY
# ══════════════════════════════════════════════════════════════════════════════

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
"""
Per-request SQLAlchemy session factory.

autocommit=False
    Transactions must be explicitly committed via `db.commit()`. This is the
    correct default for a web API: it ensures that a partially executed
    multi-statement operation (e.g., write telemetry row + update aggregate
    table) is never partially committed if the request handler raises an
    exception mid-way. The finally block in `get_db()` closes (and
    implicitly rolls back any uncommitted transaction on) the session.

autoflush=False
    Prevents SQLAlchemy from automatically flushing pending ORM changes to
    the database before every query. Explicit control over flush timing is
    preferable in a predictive maintenance context where a sensor reading
    write and a prediction write must be treated as a single atomic unit.

bind=engine
    Associates every session produced by this factory with the shared engine
    and its connection pool, rather than opening a new raw connection per
    session.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  DECLARATIVE BASE
# ══════════════════════════════════════════════════════════════════════════════

Base = declarative_base()
"""
Declarative base class for all SQLAlchemy ORM models in this application.

All model files (e.g., models.py) must inherit from this Base:

    from database import Base

    class SensorReading(Base):
        __tablename__ = "sensor_readings"
        ...

`Base.metadata.create_all(bind=engine)` is called in the application entry
point (main.py lifespan hook) to materialise all declared tables into the
SQLite file on first startup without requiring a migration tool for the
hackathon phase. For production, replace with Alembic migrations.
"""

# ══════════════════════════════════════════════════════════════════════════════
#  FASTAPI DEPENDENCY — PER-REQUEST SESSION
# ══════════════════════════════════════════════════════════════════════════════

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a scoped SQLAlchemy database session for
    the duration of a single HTTP request and guarantees teardown.

    Usage in a route handler
    ────────────────────────
    Declare `db: Session = Depends(get_db)` as a parameter in any route
    function that requires database access:

        from fastapi import Depends
        from sqlalchemy.orm import Session
        from database import get_db

        @app.post("/api/v1/readings")
        async def create_reading(
            payload: SensorPayload,
            db: Session = Depends(get_db),
        ) -> dict:
            reading = SensorReading(**payload.model_dump())
            db.add(reading)
            db.commit()
            db.refresh(reading)
            return {"id": reading.id}

    Lifecycle
    ─────────
    1. FastAPI calls this generator before the route handler executes.
    2. A fresh `SessionLocal()` instance is created and yielded to the handler.
    3. The route handler performs all database operations using this session.
    4. After the handler returns (or raises), FastAPI resumes the generator.
    5. The `finally` block closes the session unconditionally — committing
       nothing automatically, rolling back any open transaction, and returning
       the underlying connection to the pool.

    Connection Pool Leak Prevention
    ─────────────────────────────────
    The `finally` block is non-negotiable. Without it:
      • An unhandled exception in the route handler would exit the generator
        without closing the session, holding the connection open indefinitely.
      • Under sustained load, the connection pool (default size: 5 for SQLite)
        would exhaust within seconds, causing all subsequent requests to block
        waiting for a free connection — a complete service outage.

    Yields
    ------
    Session
        A SQLAlchemy ORM session bound to the shared engine, scoped to the
        lifetime of the current HTTP request.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()