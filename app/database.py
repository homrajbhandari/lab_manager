import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./lab_manager.db"
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)


# SQLite ignores foreign-key constraints by default. Toggle the pragma on
# every new connection so the bulk-delete pre-checks and FK references
# declared on Column(ForeignKey(...)) actually fire.
@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_connection, connection_record):  # noqa: ARG001
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        # Non-SQLite engines will raise here — that's fine, they don't need
        # the pragma.
        pass


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()