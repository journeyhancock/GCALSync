import datetime

from sqlalchemy import Column, Integer, String, TIMESTAMP, UniqueConstraint, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, scoped_session

Base = declarative_base()

class JourneyEventMap(Base):
    __tablename__ = "journey_event_map"
    id = Column(Integer, primary_key=True)
    original_event_id = Column(String, nullable=False)
    new_event_id = Column(String, nullable=False)
    last_synced = Column(TIMESTAMP, default=datetime.datetime.now(tz=datetime.timezone.utc))
    __table_args__ = (UniqueConstraint("original_event_id", "new_event_id"),)

class MolleeEventMap(Base):
    __tablename__ = "mollee_event_map"
    id = Column(Integer, primary_key=True)
    original_event_id = Column(String, nullable=False)
    new_event_id = Column(String, nullable=False)
    last_synced = Column(TIMESTAMP, default=datetime.datetime.now(tz=datetime.timezone.utc))
    __table_args__ = (UniqueConstraint("original_event_id", "new_event_id"),)

class TasksDayEventMap(Base):
    __tablename__ = "tasks_day_event_map"
    id = Column(Integer, primary_key=True)
    day = Column(String, nullable=False)
    event_id = Column(String, nullable=False)
    last_synced = Column(TIMESTAMP, default=datetime.datetime.now(tz=datetime.timezone.utc))
    __table_args__ = (UniqueConstraint("day", "event_id"),)

engine = create_engine("postgresql://gcalsync_user:user@localhost:5432/gcalsync")
LocalSession = scoped_session(sessionmaker(bind=engine))

def init_db():
    Base.metadata.create_all(bind=engine)

def get_session():
    return LocalSession()