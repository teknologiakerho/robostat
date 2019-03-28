import functools
import collections
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.query import Query
import robostat.db as model
from robostat.util import udict
from robostat.ruleset import decode_scores

_shadow_subquery = ~Query(model.EventTeam)\
        .join(model.EventTeam.team)\
        .filter(model.EventTeam.event_id==model.Event.id)\
        .filter(model.Team.is_shadow)\
        .exists()

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

    def events_query(self, db, hide_shadows=False):
        query = db.query(model.Event).filter_by(block_id=self.id)

        if hide_shadows:
            query = hide_query_shadows(query)

        return query

    def scores_query(self, db, hide_shadows=False):
        query = db.query(model.Score)\
                .join(model.Score.event)\
                .filter(model.Event.block_id == self.id)

        if hide_shadows:
            # Tässä pitää filtteröidä myös pois ne scoret jotka on "pelattu" shadoweja
            # vastaan joten pitää tehä koko subquery.
            # Jos jokasessa eventissä olis vaan yks joukkue niin riittäs
            # joinata teameihin kun team.is_shadow=0.
            query = hide_query_shadows(query)

        return query

    def decode_scores(self, db, hide_shadows=False):
        scores = self.scores_query(db, hide_shadows=hide_shadows)\
                .options(joinedload(model.Score.team, innerjoin=True))\
                .all()

        return list(decode_scores(self.ruleset, scores))

def hide_query_shadows(query):
    return query.filter(_shadow_subquery)

def scores_query(db, *blocks, hide_shadows=False):
    query = db.query(model.Score)\
            .join(model.Score.event)\
            .filter(model.Event.block_id.in_([
                (b.id if isinstance(b, Block) else b) for b in blocks
            ]))

    if hide_shadows:
        query = hide_query_shadows(query)

    return query

def decode_block_scores(db, *blocks, hide_shadows=False):
    bs = dict((b.id, b) for b in blocks)

    # Tää vois olla myös selectinload tjsp
    scores = scores_query(db, *blocks, hide_shadows=hide_shadows)\
            .options(joinedload(model.Score.team, innerjoin=True))\
            .all()

    return [((s.team, bs[s.event.block_id].ruleset.decode(s.data) if s.has_score else None))\
            for s in scores]

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

def aggregate_scores(scores, aggregate):
    grouped = collections.defaultdict(list)

    for team, score in scores:
        grouped[team].append(score)

    ret = {}

    for team, ss in grouped.items():
        ret[team] = aggregate(ss)

    return ret

def sort_ranking(groups):
    return sorted(groups, key=lambda x: x[1], reverse=True)
