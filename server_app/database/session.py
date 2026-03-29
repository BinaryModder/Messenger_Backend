from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import create_engine

from core.config import settings

engine = create_engine(url=settings.DATABASE_URL, echo=True)

LocalSession = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
Base = declarative_base()
