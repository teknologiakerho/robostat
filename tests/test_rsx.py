import os
import pytest
from click.testing import CliRunner
from robostat.rsx.main import main as rsx

path = os.path.dirname(os.path.realpath(__file__))
init_file = os.path.join(path, "init1.py")

class RsxRunner:

    def __init__(self, runner, db_file):
        self.runner = runner
        self.db_file = db_file

    def import_(self, bname, fname, *args):
        return self.runner.invoke(rsx, [
            "import",
            "-d", self.db_file,
            "-y",
            bname,
            os.path.join(path, fname),
            *args
        ])

    def export(self, bname, *args):
        return self.runner.invoke(rsx, [
            "export",
            "-d", self.db_file,
            bname,
            *args
        ])

    def show(self, what, *args):
        return self.runner.invoke(rsx, [
            "show",
            "-d", self.db_file,
            "-i", init_file,
            "--table-format", "plain",
            what,
            *args
        ])

    def del_(self, what, *args):
        return self.runner.invoke(rsx, [
            "del",
            "-d", self.db_file,
            what,
            *args
        ])

@pytest.fixture
def runner():
    cli_runner = CliRunner()
    with cli_runner.isolated_filesystem():
        # Tää on vähän hasardi viritelmä koska rsx on se mitä olis tarkotus testata
        # mutta tuskin tää räjähtää
        db_path = "sqlite:///db.sqlite3"
        res = cli_runner.invoke(rsx, ["create", "-d", db_path, "-i", init_file])
        assert res.exit_code == 0

        yield RsxRunner(cli_runner, db_path)

def test_import(runner):
    assert runner.import_("xsumo", "aikataulu-xsumo-15.tsv").exit_code == 0
    assert runner.import_("xsumo.2", "aikataulu-xsumo-16.tsv").exit_code == 0

    # Tässä pitäs tulla virhe kun importataan sama uusiks
    assert runner.import_("xsumo", "aikataulu-xsumo-15.tsv").exit_code == 1
    assert runner.import_("xsumo.3", "aikataulu-xsumo-15.tsv").exit_code == 1

def test_reimport_deleted(runner):
    assert runner.import_("xsumo", "aikataulu-xsumo-15.tsv").exit_code == 0
    assert runner.del_("block", "xsumo").exit_code == 0
    assert runner.import_("xsumo", "aikataulu-xsumo-15.tsv").exit_code == 0

def test_export(runner):
    runner.import_("rescue1.a", "aikataulu-rescue.tsv")
    res = runner.export("rescue1.a")

    assert res.exit_code == 0
    # Tää on vähän tyhmä tarkistus, sen vois tehä parse_timetablella mieluummin
    assert res.output == open(os.path.join(path, "aikataulu-rescue.tsv")).read()

def test_show(runner):
    num_lines = lambda s: len(s.strip().split("\n"))

    # Tyhjässä tietokannassa ei pitäs näkyä joukkueita
    res = runner.show("teams")
    assert res.exit_code == 0
    assert num_lines(res.output) == 1

    # Tyhjässä lohkosa ei pitäs olla mitään
    res = runner.show("block", "xsumo")
    assert res.exit_code == 0
    assert num_lines(res.output) == 1

    res = runner.show("blocks")
    assert res.exit_code == 0
    n_blocks = num_lines(res.output)

    runner.import_("xsumo", "aikataulu-xsumo-15.tsv")

    # Lohkoon pitäs olla ilmestynyt eventtejä
    res = runner.show("block", "xsumo")
    assert res.exit_code == 0
    assert num_lines(res.output) > 1

    # Mutta uutta lohkoa ei pitäs olla tullut koska xsumo on initissä
    res = runner.show("blocks")
    assert num_lines(res.output) == n_blocks
    assert "(Not in init)" not in res.output

    runner.import_("new-block.xxx", "aikataulu-rescue.tsv")

    # Nyt pitäs näkyä yks uus lohko
    res = runner.show("blocks")
    assert num_lines(res.output) == n_blocks+1
    assert "(Not in init)" in res.output

    # TODO tässä vois testata vielä rankingit
    # ja parse_timetablella että se antaa oikeet joukkueet jne.

def test_del(runner):
    # Ei pitäs pystyä poistaa jos ei oo olemassa
    res = runner.del_("team", "@Tropos")
    assert res.exit_code == 1
    assert "No such team" in res.output

    runner.import_("rescue1.a", "aikataulu-rescue.tsv")

    # Ei pitäs pystyä poistaa koska sillä on suorituksia
    res = runner.del_("team", "@Tropos")
    assert res.exit_code == 1
    assert "Cannot delete team with events" in res.output

    res = runner.del_("block", "rescue1.a")
    assert res.exit_code == 0

    # Nyt pitäs onnistua
    res = runner.del_("team", "@Tropos")
    assert res.exit_code == 0
    assert "[-] Tropos" in res.output
