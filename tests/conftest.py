import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import robostat
import robostat.db as model

@pytest.fixture(scope="session")
def tournament():
    ret = robostat.Tournament()
    with robostat.replace_default_tournament(ret):
        from . import init1
    return ret

@pytest.fixture
def db():
    engine = create_engine("sqlite://", echo="debug")
    model.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
