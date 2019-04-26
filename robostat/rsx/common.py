import sys
import click
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import robostat
import robostat.db as model
from robostat.util import lazy

def ee(mes):
    click.secho(mes, err=True, fg="red")

def ww(mes):
    click.secho(mes, err=True, fg="yellow")

def styleid(id):
    return click.style("[%s]" % id, fg="cyan")

def nameid(obj):
    name = obj.name

    if getattr(obj, "is_shadow", False):
        name = click.style(name, fg="bright_black")

    return "%s %s" % (
        name,
        styleid(obj.id)
    )

class RsxError(click.ClickException):
    def show(self, file=None):
        if file is None:
            file=sys.stderr
        click.secho("Error: %s" % self.message, fg="red", file=file)

class SQLAParam:

    def __init__(self, engine, autocommit=True, session_args={}):
        self.engine = engine
        self.autocommit = autocommit
        self.session_args = session_args

    @lazy
    def session(self):
        return sessionmaker(bind=self.engine, **self.session_args)()

    def __getattr__(self, name):
        return getattr(self.session, name)

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
            engine_args={}, session_args={}, prefix="sqlite:///"):
        self.autocommit = autocommit
        self.autoclose = autoclose
        self.autoverbose = autoverbose
        self.engine_args = engine_args
        self.session_args = session_args
        self.prefix = prefix

    def convert(self, value, param, ctx):
        if isinstance(value, SQLAParam):
            return value

        engine = create_engine("%s%s" % (self.prefix, value), **self.engine_args)
        value = SQLAParam(engine, autocommit=self.autocommit, session_args=self.session_args)

        if ctx is not None:
            if self.autoverbose in ctx.params:
                value.conf_verbosity(ctx.params[self.autoverbose])
            if self.autoclose:
                ctx.call_on_close(value.close)

        return value

class InitParam:

    def __init__(self, fname, ctx, tournament):
        self.fname = fname
        self.ctx = ctx
        self.tournament = tournament

# HUOM: tää ajaa koodia, vaarallinen
class InitParamType(click.ParamType):
    name = "init"

    def convert(self, value, param, ctx):
        if isinstance(value, InitParamType):
            return value

        # TODO joku tapa jolla tässä voi käyttää muutaki kun defaulttia
        ctx = {}
        tournament = robostat.Tournament()
        with robostat.replace_default_tournament(tournament):
            exec(open(value).read(), ctx)

        return InitParam(value, ctx, tournament)

verbose_option = click.option(
    "-v", "--verbose",
    count=True
)

db_option = click.option(
    "-d", "--db",
    type=SQLAParamType(session_args={"expire_on_commit": False}),
    envvar="ROBOSTAT_DB",
    required=True
)

init_option = click.option(
    "-i", "--init",
    type=InitParamType(),
    envvar="ROBOSTAT_INIT",
    required=True
)

