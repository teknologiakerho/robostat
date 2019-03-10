from pkgutil import extend_path
from .tournament import Tournament

# ks. https://docs.python.org/3/library/pkgutil.html
# tämä siksi, että mm. robostat-web voi erottaa omaan pakettiin
__path__ = extend_path(__path__, __name__)

default_tournament = Tournament()

block = lambda *args, **kwargs: default_tournament.block(*args, **kwargs)
ranking = lambda *args, **kwargs: default_tournament.ranking(*args, **kwargs)
