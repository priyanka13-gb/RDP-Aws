"""Initialize the task table without modifying existing tables or records."""

from sqlalchemy.exc import SQLAlchemyError

from app.main import Settings, create_database_engine
from app.tasks import Base


def main():
    settings = Settings.from_environment()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL must be configured")
    engine = create_database_engine(settings)
    try:
        try:
            Base.metadata.create_all(engine)
        except SQLAlchemyError:
            raise SystemExit("Task schema initialization failed; check database") from None
    finally:
        engine.dispose()
    print("Task schema initialized")


if __name__ == "__main__":
    main()
