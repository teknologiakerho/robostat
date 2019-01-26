import functools
import robostat.db
from robostat.util import udict

class Tournament:

    def __init__(self):
        self.blocks = udict()
        self.rankings = udict()

    def block(self, *args, **kwargs):
        ret = Block(self, *args, **kwargs)
        self.blocks[ret.id] = ret
        return ret

    def ranking(self, *args, **kwargs):
        def ret(f):
            self.add_ranking(Ranking(self, *args, **kwargs, f=f))
            return f
        return ret

    def add_ranking(self, ranking):
        self.rankings[ranking.id] = ranking

class Block:

    def __init__(self, tournament, id, ruleset, *, name=None):
        self.tournament = tournament
        self.id = id
        self.ruleset = ruleset
        self.name = name or id

    def events_query(self, db):
        return db.query(robostat.db.Event).filter(robostat.db.Event.block_id == self.id)

    def scores_query(self, db):
        return db.query(robostat.db.Score)\
                .join(robostat.db.Score.event)\
                .filter(robostat.db.Event.block_id == self.id)

class Ranking:

    def __init__(self, tournament, id, f, *, name=None):
        self.tournament = tournament
        self.id = id
        self.f = f
        self.name = name or id

    def __call__(self, db):
        return self.f(db)

    def __getattr__(self, name):
        return getattr(self.f, name)
