import sys
import functools
import click
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
import robostat as rs
import robostat.db as model
from robostat.util import lazy, enumerate_rank

class RsxError(click.ClickException):
    def show(self, file=None):
        if file is None:
            file=sys.stderr
        click.secho("Error: %s" % self.message, fg="red", file=file)

def ee(mes):
    click.secho(mes, err=True, fg="red")

def ww(mes):
    click.secho(mes, err=True, fg="yellow")

def echo_insert(dest, what, num=None):
    if num is None:
        num = len(what)

    if num == 1:
        num = ""
    else:
        num = " (%d) " % num

    click.echo("%s %s%s: %s" % (
        click.style("[+]", fg="green", bold=True),
        dest,
        num,
        str(what)
    ))

# XXX
def print_ranking(ranking):
    for rank, (team, score) in enumerate_rank(ranking, key=lambda x: x[1]):
        click.echo("%2d. %-20s %s" % (rank, team.name, str(score)))

# XXX
def print_events(block, events):
    for e in events:
        click.echo("%-4d" % e.id, nl=False)

        for t in e.teams:
            click.echo(" %-20s" % t.name, nl=False)

        for j in e.judgings:
            click.echo(" %s: " % j.judge.name, nl=False)

            scores = {s.team_id:s for s in j.scores}
            ss = [str(block.ruleset.decode(scores[tid].data)) if scores[tid].data is not None\
                    else "(null)" for tid in e.team_ids]
            click.echo(" - ".join(ss), nl=False)

        click.echo()

def get_teams(db, names, **kwargs):
    return _get_or_insert(db, model.Team, names, **kwargs)

def get_judges(db, names, **kwargs):
    return _get_or_insert(db, model.Judge, names, **kwargs)

def _get_or_insert(db, M, names, allow_insert=False, confirm=True):
    ret = db.query(M).filter(M.name.in_(names)).all()

    if len(ret) < len(names):
        missing = set(names).difference(x.name for x in ret)

        if not allow_insert:
            raise RsxError("Missing names: %s" % missing)

        echo_insert(M.__tablename__, ", ".join(missing), num=len(missing))

        if confirm:
            click.confirm("Proceed with insert?", abort=True)

        ret.extend(M(name=name) for name in missing)

    return ret

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

class InitParam:

    def __init__(self, fname, ctx):
        self.fname = fname
        self.ctx = ctx

    @property
    def tournament(self):
        # TODO: tähän että voi ottaa init tiedostosta
        # jonkun muuttujan jossa on tournament
        return rs.default_tournament

# HUOM: tää ajaa koodia, vaarallinen
class InitParamType(click.ParamType):
    name = "init"

    def convert(self, value, param, ctx):
        if isinstance(value, InitParamType):
            return value

        ctx = {}
        exec(open(value).read(), ctx)

        return InitParam(value, ctx)
