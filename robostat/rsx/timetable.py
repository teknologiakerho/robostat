from datetime import datetime
import click
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import subqueryload
from pttt.timetable import parse_timetable, create_timetable, AbsoluteTime
from robostat import db as model
from robostat.rsx.common import RsxError, verbose_option, db_option, nameid

def get_or_insert(db, cls, names, strict=False, confirm=True):
    ret = db.query(cls).filter(cls.name.in_(names)).all()

    if len(ret) < len(names):
        missing = set(names).difference(x.name for x in ret)

        if strict:
            raise RsxError("Missing names: %s" % missing)

        if confirm:
            click.echo("Not in db (%d): %s" % (len(missing), ", ".join(missing)))
            click.confirm("OK to add?", abort=True)

        added = [cls(name=name) for name in missing]
        db.add_all(added)
        db.commit()

        for x in added:
            click.echo("%s %s" % (
                click.style("[+]", fg="green", bold=True),
                nameid(x)
            ))

        ret.extend(added)

    return ret

@click.command("import")
@verbose_option
@db_option
@click.option("-j", "--num-judges", "j", default=1)
@click.option("-s", "--strict", is_flag=True)
@click.option("-y", "--no-confirm", "y", is_flag=True)
@click.option("--datefmt", default="%d.%m.%Y %H:%M")
@click.argument("block")
@click.argument("file", type=click.File("r"), default="-")
def import_command(db, strict, y, **kwargs):
    timetable = parse_timetable(kwargs["file"].read(), datefmt=kwargs["datefmt"])

    if not timetable:
        return

    k = len(timetable[0]) - kwargs["j"] - 1
    teams = set(timetable[:,1:1+k].labels)
    judges = set(timetable[:,1+k:].labels)

    teams = get_or_insert(db, model.Team, teams, strict=strict, confirm=not y)
    judges = get_or_insert(db, model.Judge, judges, strict=strict, confirm=not y)

    teams = dict((t.name, t) for t in teams)
    judges = dict((j.name, j) for j in judges)

    events = []
    for e in timetable:
        event = model.Event(
            block_id=kwargs["block"],
            ts_sched=int(e.time),
            arena=e[0].name,
            teams_part=[model.EventTeam(team_id=teams[l.name].id) for l in e[1:1+k]],
            judgings=[model.EventJudging(judge_id=judges[l.name].id) for l in e[1+k:]]
        )

        #print([teams[l.name].id for l in e[1:1+k]])

        #event.team_ids.extend(teams[l.name].id for l in e[1:1+k])
        #event.judge_ids.extend(judges[l.name].id for l in e[1+k:])
        events.append(event)

    db.add_all(events)

    try:
        db.commit()
    except IntegrityError:
        # TODO tähän joku hyödyllisempi virhe, etsi vaikka mitkä eventit aiheuttaa ongelmia
        db.rollback()
        raise RsxError("Block conflict")

    click.echo("%s Added %d events to block %s" % (
        click.style("[+]", fg="green", bold=True),
        len(events),
        kwargs["block"]
    ))

@click.command("export")
@verbose_option
@db_option
@click.option("--ids", is_flag=True)
@click.argument("block")
def export_command(db, block, ids, **kwargs):
    events = db.query(model.Event)\
            .options(
                subqueryload(model.Event.teams_part)
                .joinedload(model.EventTeam.team, innerjoin=True),
                subqueryload(model.Event.judgings)
                .joinedload(model.EventJudging.judge, innerjoin=True)
            )\
            .filter(model.Event.block_id == block)\
            .order_by(model.Event.ts_sched)\
            .all()

    if ids:
        t_name = lambda team: "T%d" % team.id
        j_name = lambda judge: "J%d" % judge.id
    else:
        t_name = lambda team: team.name
        j_name = lambda judge: judge.name

    timetable = create_timetable(
        (
            AbsoluteTime(datetime.fromtimestamp(e.ts_sched)),
            [e.arena, *map(t_name, e.teams), *map(j_name, e.judges)]
        ) for e in events
    )

    print(timetable)
