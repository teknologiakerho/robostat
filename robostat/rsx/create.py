import click
import robostat.db as model
from robostat.rsx import common

@click.command("create")
@common.verbose_option
@common.db_option
@common.init_option
def create_command(db, **kwargs):
    model.Base.metadata.create_all(db.engine)
