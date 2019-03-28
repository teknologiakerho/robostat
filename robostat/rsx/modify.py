import click
from sqlalchemy.exc import IntegrityError
from robostat import db as model
from robostat.rsx.common import RsxError, verbose_option, db_option, ee, nameid, styleid
from robostat.rsx.crud import add_sym, del_sym, query_selectors

class Crud:

    def __init__(self, db):
        self.db = db

class BlockCrud(Crud):

    def del_(self, srch):
        ndel = self.db.query(model.Event).filter_by(block_id=srch).delete()

        if ndel:
            click.echo("%s Deleted all events from block %s (%d total)" % (
                del_sym,
                styleid(srch),
                ndel
            ))
        else:
            ee("Block %s has no events; did nothing" % srch)

class TeamCrud(Crud):

    def del_(self, srch):
        team = query_selectors(self.db, model.Team, [srch]).first()

        if team is None:
            raise RsxError("No such team: '%s'" % srch)

        self.db.delete(team)
        
        try:
            self.db.commit()
        except IntegrityError:
            # jos joukkueella on suorituksia niin ei anna poistaa
            self.db.rollback()
            raise RsxError("Cannot delete team with events")

        click.echo("%s %s" % (del_sym, nameid(team)))

cruds = {
    "block": BlockCrud,
    "team": TeamCrud
}

def get_cruds(attr):
    return [k for k,v in cruds.items() if hasattr(v, attr)]

@click.command("del")
@verbose_option
@db_option
@click.argument("what", type=click.Choice(get_cruds("del_")))
@click.argument("param")
def del_command(**kwargs):
    deleter = cruds[kwargs["what"]]
    crud = deleter(kwargs["db"])
    crud.del_(kwargs["param"])

@click.command("shadow")
@verbose_option
@db_option
@click.argument("selector")
def shadow_command(**kwargs):
    db = kwargs["db"]
    team = query_selectors(db, model.Team, [kwargs["selector"]]).first()

    if team is None:
        raise RsxError("Team not found: %s" % kwargs["selector"])

    old_nameid = nameid(team)
    team.is_shadow = not team.is_shadow

    click.echo("%s %s %s" % (
        old_nameid,
        click.style("=>", bold=True),
        nameid(team)
    ))

    db.commit()
