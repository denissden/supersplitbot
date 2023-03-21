from enum import Enum, unique
from sqlalchemy import Column, Integer, String, BigInteger, Float
from sqlalchemy.orm import relationship
from . import Base


class Total(Base):
    __tablename__ = "total"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Float, index=True)
    user = Column(String, index=True)
    value = Column(String, index=False)
