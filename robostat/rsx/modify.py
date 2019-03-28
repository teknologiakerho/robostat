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
        team = self._query_or_err(srch)
        self.db.delete(team)
        
        try:
            self.db.commit()
        except IntegrityError:
            # jos joukkueella on suorituksia niin ei anna poistaa
            self.db.rollback()
            raise RsxError("Cannot delete team with events")

        click.echo("%s %s" % (del_sym, nameid(team)))

    def rename(self, srch, name):
        team = self._query_or_err(srch)
        old_nameid = nameid(team)
        team.name = name

        try:
            self.db.commit()
        except IntegrityError as e:
            # todennäkösesti nimi on jo jollakin toisella joukkueella
            self.db.rollback()
            raise RsxError("Rename failed: %s" % str(e))

        click.echo("%s %s %s" %(
            old_nameid,
            click.style("=>", bold=True),
            nameid(team)
        ))

    def _query_or_err(self, srch):
        ret = query_selectors(self.db, model.Team, [srch]).first()

        if ret is None:
            raise RsxError("No such team: '%s'" % srch)

        return ret

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

@click.command("rename")
@verbose_option
@db_option
@click.argument("what", type=click.Choice(get_cruds("rename")))
@click.argument("from")
@click.argument("to")
def rename_command(**kwargs):
    cruds[kwargs["what"]](kwargs["db"]).rename(kwargs["from"], kwargs["to"])

@click.command("shadow")
@verbose_option
@db_option
@click.argument("selector")
@click.argument("state", default="toggle", type=click.Choice(["on", "off", "toggle"]))
def shadow_command(**kwargs):
    db = kwargs["db"]
    team = query_selectors(db, model.Team, [kwargs["selector"]]).first()

    if team is None:
        raise RsxError("Team not found: %s" % kwargs["selector"])

    old_nameid = nameid(team)

    v = {"on": True, "off": False, "toggle": not team.is_shadow}[kwargs["state"]]
    team.is_shadow = v

    click.echo("%s %s %s" % (
        old_nameid,
        click.style("=>", bold=True),
        nameid(team)
    ))

    db.commit()
