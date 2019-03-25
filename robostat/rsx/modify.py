import click
from sqlalchemy.exc import IntegrityError
from robostat import db as model
from robostat.rsx.common import RsxError, verbose_option, db_option, ee, nameid, styleid

add_sym = click.style("[+]", fg="green", bold=True)
del_sym = click.style("[-]", fg="red", bold=True)

def query_named(db, cls, srch):
    if not srch:
        raise RsxError("Missing identifier")

    if srch[0] == "@":
        return db.query(cls).filter_by(name=srch[1:]).first()

    try:
        id = int(srch)
    except ValueError:
        raise RsxError("Not a valid id: '%s'" % srch)

    return db.query(cls).filter_by(id=id).first()

def del_block(db, srch):
    ndel = db.query(model.Event).filter_by(block_id=srch).delete()

    if ndel:
        click.echo("%s Deleted all events from block %s (%d total)" % (
            del_sym,
            styleid(srch),
            ndel
        ))
    else:
        ee("Block %s has no events; did nothing" % srch)

def del_team(db, srch):
    team = query_named(db, model.Team, srch)

    if team is None:
        raise RsxError("No such team: '%s'" % srch)

    db.delete(team)
    
    try:
        db.commit()
    except IntegrityError:
        # jos joukkueella on suorituksia niin ei anna poistaa
        db.rollback()
        raise RsxError("Cannot delete team with events")

    click.echo("%s %s" % (del_sym, nameid(team)))

deleters = {
    "block": del_block,
    "team": del_team
}

@click.command("del")
@verbose_option
@db_option
@click.argument("what", type=click.Choice(list(deleters)))
@click.argument("param")
def del_command(**kwargs):
    deleter = deleters[kwargs["what"]]
    deleter(kwargs["db"], kwargs["param"])
