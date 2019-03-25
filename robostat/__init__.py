from contextlib import contextmanager
from pkgutil import extend_path
from .tournament import Tournament

# ks. https://docs.python.org/3/library/pkgutil.html
# tämä siksi, että mm. robostat-web voi erottaa omaan pakettiin
__path__ = extend_path(__path__, __name__)

default_tournament = Tournament()

@contextmanager
def replace_default_tournament(tournament):
    global default_tournament
    old_default = default_tournament
    default_tournament = tournament
    try:
        yield
    finally:
        default_tournament = old_default

block = lambda *args, **kwargs: default_tournament.block(*args, **kwargs)
ranking = lambda *args, **kwargs: default_tournament.ranking(*args, **kwargs)
