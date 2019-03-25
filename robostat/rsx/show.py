import collections
import functools
import operator
from base64 import b64encode
from datetime import datetime
import click
import sqlalchemy as sa
from sqlalchemy.orm import subqueryload, contains_eager
from tabulate import tabulate
from robostat import db as model
from robostat.util import enumerate_rank
from robostat.rsx.common import RsxError, InitParamType, db_option, verbose_option, nameid, styleid

def localts(ts, fmt="%d.%m.%Y %H:%M"):
    return datetime.fromtimestamp(ts).strftime(fmt)

def table_generator(headers):
    def ret(f):
        @functools.wraps(f)
        def wrapper(self, *args, **kwargs):
            data = list(f(self, *args, **kwargs))
            click.echo(tabulate(data,
                headers=headers,
                tablefmt=self.tablefmt
            ))
        return wrapper
    return ret

class PrettyFormatter:

    def __init__(self, tablefmt):
        self.tablefmt = tablefmt

    @table_generator(["Id", "Time", "Teams", "Judges"])
    def print_block(self, events):
        for e in events:
            yield (
                styleid(e.id),
                localts(e.ts_sched),
                "\n".join(map(nameid, e.teams)),
                "\n".join(("%s %s" % (
                    nameid(j.judge),
                    ("%s (%s)" % (
                        click.style("OK", fg="green"),
                        localts(e.ts_sched, "%d.%m %H:%M")
                    )) if not j.is_future else ""
                )) for j in e.judgings)
            )

    @table_generator(["Event", "Team", "Judge", "Score", "Data"])
    def print_scores(self, scores):
        for s in scores:
            if hasattr(s, "decoded_score"):
                score = str(s.decoded_score)
            else:
                score = ""

            if s.has_score:
                data = b64encode(s.data).decode("utf8")
            else:
                data = ""

            yield (
                styleid(s.event_id),
                nameid(s.team),
                nameid(s.judge),
                score,
                data
            )

    @table_generator(["Id", "Name", "Time", "Judging"])
    def print_blocks(self, block_info):
        for id, info in block_info:
            if info.block is None:
                name = click.style("(Not in init)", fg="red")
            else:
                name = info.block.name

            if info.start_ts is None:
                time = ""
            else:
                time = "%s - %s" % (localts(info.start_ts), localts(info.end_ts, "%d.%m %H:%M"))

            if info.judging_count > 0:
                if info.judging_done == info.judging_count:
                    judging_color = "green"
                elif info.judging_done > 0:
                    judging_color = "white"
                else:
                    judging_color = "red"
            else:
                judging_color = "bright_black"

            yield (
                click.style(id, fg="cyan"),
                name,
                time,
                click.style("%d/%d" % (info.judging_done, info.judging_count), fg=judging_color)
            )

    @table_generator(["Rank", "Team", "Score"])
    def print_ranking(self, ranking):
        for rank, (team, score) in enumerate_rank(ranking, key=operator.itemgetter(1)):
            yield (
                "#%d" % rank,
                nameid(team),
                score
            )

    @table_generator(["Id", "Name", "Blocks"])
    def print_teams(self, team_info):
        for team, blocks in team_info:
            bs = ", ".join(
                styleid(b) if isinstance(b, str) else nameid(b) for b in blocks
            )

            yield (
                styleid(team.id),
                team.name,
                bs
            )

class BlockInfo:

    def __init__(self):
        self.event_count = 0
        self.judging_count = 0
        self.judging_done = 0
        self.start_ts = None
        self.end_ts = None
        self.block = None

class ShowOpt:

    def __init__(self, db, init, fmt, param):
        self.db = db
        self.init = init
        self.fmt = fmt
        self.param = param

def require_init(f):
    @functools.wraps(f)
    def ret(opt):
        if opt.init is None:
            raise RsxError("No init given")
        return f(opt)
    return ret

def require_param(name):
    def ret(f):
        @functools.wraps(f)
        def wrapper(opt):
            if opt.param is None:
                raise RsxError("Missing parameter: %s" % name)
            return f(**{name:opt.param, "opt":opt})
        return wrapper
    return ret

@require_param("block")
def show_block(block, opt):
    events = opt.db.query(model.Event)\
            .filter_by(block_id=block)\
            .options(
                    subqueryload(model.Event.teams_part)
                    .joinedload(model.EventTeam.team, innerjoin=True),
                    subqueryload(model.Event.judgings)
                    .joinedload(model.EventJudging.judge, innerjoin=True),
                    subqueryload(model.Event.judgings)
                    .joinedload(model.EventJudging.scores, innerjoin=True)
            )\
            .all()

    opt.fmt.print_block(events)

@require_param("block")
def show_scores(block, opt):
    scores = opt.db.query(model.Score)\
            .join(model.Score.event)\
            .filter(model.Event.block_id == block)\
            .order_by(
                    model.Score.event_id,
                    model.Score.team_id,
                    model.Score.judge_id
            )\
            .options(
                    contains_eager(model.Score.event),
                    subqueryload(model.Score.team),
                    subqueryload(model.Score.judge)
            )\
            .all()

    if opt.init is not None and block in opt.init.tournament.blocks:
        ruleset = opt.init.tournament.blocks[block].ruleset
        for s in scores:
            if s.has_score:
                s.decoded_score = ruleset.decode(s.data)

    opt.fmt.print_scores(scores)

@require_init
def show_blocks(opt):
    block_info = collections.defaultdict(BlockInfo)

    block_summary = opt.db.query(
            model.Event.block_id,
            sa.func.count(),
            sa.func.min(model.Event.ts_sched),
            sa.func.max(model.Event.ts_sched)
        )\
        .select_from(model.Event)\
        .group_by(model.Event.block_id)\
        .all()

    for id, event_count, start_ts, end_ts in block_summary:
        block_info[id].event_count = event_count
        block_info[id].start_ts = start_ts
        block_info[id].end_ts = end_ts

    judging_counts = opt.db.query(
            model.Event.block_id,
            sa.func.count(),
            sa.func.count(model.EventJudging.ts)
        )\
        .select_from(model.Event)\
        .join(model.Event.judgings)\
        .group_by(model.Event.block_id)\
        .all()

    for id, judging_count, judging_done in judging_counts:
        block_info[id].judging_count = judging_count
        block_info[id].judging_done = judging_done

    for id, block in opt.init.tournament.blocks.items():
        block_info[id].block = block

    opt.fmt.print_blocks(sorted(block_info.items(), key=operator.itemgetter(0)))

@require_init
@require_param("ranking")
def show_ranking(ranking, opt):
    try:
        r = opt.init.tournament.rankings[ranking]
    except KeyError:
        raise RsxError("No such ranking: '%s'" % ranking)

    opt.fmt.print_ranking(r(opt.db))

def show_teams(opt):
    teams = opt.db.query(model.Team)\
            .order_by(model.Team.id)\
            .all()

    team_blocks = opt.db.query(
            model.EventTeam.team_id,
            model.Event.block_id
        )\
        .select_from(model.Event)\
        .join(model.Event.teams_part)\
        .distinct()\
        .order_by(model.Event.block_id)\
        .all()

    block_info = collections.defaultdict(list)

    for tid, bid in team_blocks:
        block_info[tid].append(bid)

    if opt.init is not None:
        blocks = opt.init.tournament.blocks
        for tid, bids in block_info.items():
            for i in range(len(bids)):
                if bids[i] in blocks:
                    bids[i] = blocks[bids[i]]

    opt.fmt.print_teams([(t, block_info[t.id]) for t in teams])

choices = {
    "block": show_block,
    "blocks": show_blocks,
    "scores": show_scores,
    "ranking": show_ranking,
    "teams": show_teams
}

@click.command("show")
@verbose_option
@db_option
@click.option("-i", "--init", type=InitParamType(), envvar="ROBOSTAT_INIT")
@click.option("-f", "--format", default="pretty", type=click.Choice(["pretty", "csv"]))
@click.option("--csv-delimiter", default=",")
@click.option("--table-format", default="simple")
@click.argument("what", type=click.Choice(list(choices)))
@click.argument("param", required=False)
def show_command(**kwargs):
    if kwargs["format"] == "pretty":
        fmt = PrettyFormatter(kwargs["table_format"])
    else:
        fmt = CsvFormatter(kwargs["csv_delimiter"])

    opt = ShowOpt(
            db=kwargs["db"],
            init=kwargs["init"],
            fmt=fmt,
            param=kwargs["param"]
    )

    show = choices[kwargs["what"]]
    show(opt)
