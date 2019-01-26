import click
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from robostat.util import lazy

class SQLAParam:

    def __init__(self, engine, autocommit=True, session_args={}):
        self.engine = engine
        self.autocommit = autocommit
        self.session_args = session_args

    @lazy
    def session(self):
        return sessionmaker(bind=self.engine, **self.session_args)()

    def query(self, *args, **kwargs):
        return self.session.query(*args, **kwargs)

    def close(self):
        if "session" in self.__dict__:
            if self.autocommit:
                try:
                    self.session.commit()
                except SQLAlchemyError as e:
                    click.secho(str(e), fg="red", bold=True)
            self.session.close()
            del self.session

    def conf_verbosity(self, verbosity):
        if verbosity >= 2:
            self.engine.echo = "debug"
        elif verbosity >= 1:
            self.engine.echo = True

class SQLAParamType(click.ParamType):
    name = "sqlalchemy"

    def __init__(self, autocommit=True, autoclose=True, autoverbose="verbose",
            engine_args={}, session_args={}):
        self.autocommit = autocommit
        self.autoclose = autoclose
        self.autoverbose = autoverbose
        self.engine_args = engine_args
        self.session_args = session_args

    def convert(self, value, param, ctx):
        if isinstance(value, SQLAParam):
            return value

        engine = create_engine(value, **self.engine_args)
        value = SQLAParam(engine, autocommit=self.autocommit, session_args=self.session_args)

        if ctx is not None:
            if self.autoverbose in ctx.params:
                value.conf_verbosity(ctx.params[self.autoverbose])
            if self.autoclose:
                ctx.call_on_close(value.close)

        return value
