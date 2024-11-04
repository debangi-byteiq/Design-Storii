from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from config.database_bucket import DATABASE_URL, POOL_RECYCLE


# This module is used to create database engine and the session.
engine = create_engine(DATABASE_URL, pool_recycle = POOL_RECYCLE)
Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


