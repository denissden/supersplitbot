import asyncio

import sqlalchemy.orm
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


engine = None
SessionLocal: sqlalchemy.orm.sessionmaker = None
Base = declarative_base()


def get_session():
    return SessionLocal()


async def create_db(url: str):
    global engine, SessionLocal
    engine = create_async_engine(url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def create_db_sync(url: str):
    asyncio.get_event_loop().create_task(create_db(url))