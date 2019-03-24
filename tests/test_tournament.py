import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, subqueryload
from sqlalchemy.exc import IntegrityError
import robostat
import robostat.tournament
import robostat.db as model
from robostat.rulesets.xsumo import XSRuleset
from .helpers import XS2, R

@pytest.fixture(scope="module")
def tournament():
    # TÄhän vois tehä jonku context managerin robostatiin
    old_default = robostat.default_tournament
    ret = robostat.tournament.Tournament()
    robostat.default_tournament = ret
    from . import init1
    robostat.default_tournament = old_default
    return ret

def insert_test_data(db):
    db.add_all([
        model.Team(id=1, name="Joukkue A"),
        model.Team(id=2, name="Joukkue B"),
        model.Team(id=3, name="Joukkue C"),

        model.Judge(id=1, name="Tuomari A"),
        model.Judge(id=2, name="Tuomari B")
    ])

    db.commit()

@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite://")
    model.Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)
    ret = session()
    insert_test_data(ret)
    return ret

def make_event(teams, judges, **kwargs):
    ret = model.Event(**kwargs)
    ret.team_ids.extend(teams)
    ret.judge_ids.extend(judges)
    return ret

def query_full_events(db, block):
    return block.events_query(db)\
            .order_by(model.Event.ts_sched)\
            .options(
                    subqueryload(model.Event.judgings)
                    .joinedload(model.EventJudging.judge, innerjoin=True),
                    subqueryload(model.Event.teams_part)
                    .joinedload(model.EventTeam.team, innerjoin=True),
                    subqueryload(model.Event.scores)
            ).all()

def test_tournament_single_xsumo(db, tournament):
    db.add_all([
        make_event(teams=[1, 2], judges=[1], block_id="xsumo", ts_sched=0, arena="xsumo.1"),
        make_event(teams=[2, 3], judges=[1], block_id="xsumo", ts_sched=1, arena="xsumo.1"),
        make_event(teams=[3, 1], judges=[1], block_id="xsumo", ts_sched=2, arena="xsumo.1"),
    ])

    db.commit()

    events = query_full_events(db, tournament.blocks["xsumo"])

    assert len(events) == 3
    assert all(len(e.judges) == 1 for e in events)
    assert all(len(e.teams) == 2 for e in events)
    assert all(len(e.scores) == 2 for e in events)
    assert all(e.judgings[0].is_future for e in events)

    assert tournament.blocks["xsumo"].scores_query(db).count() == 6
    assert tournament.blocks["xsumo"].scores_query(db)\
            .filter(model.Score.has_score)\
            .count() == 0

    assert tournament.blocks["xsumo.karsinnat"].events_query(db).count() == 0

    s1, s2 = XS2([((False, "W"), (True, "L"))])
    es1, es2 = events[0].scores
    if es1.team_id != 1:
        es1, es2 = es2, es1

    es1.data = tournament.blocks["xsumo"].ruleset.encode(s1)
    es2.data = tournament.blocks["xsumo"].ruleset.encode(s2)
    events[0].judgings[0].ts = 100

    db.commit()

    assert not events[0].judgings[0].is_future
    assert all(e.judgings[0].is_future for e in events[1:])
    assert tournament.blocks["xsumo"].scores_query(db)\
            .filter(model.Score.has_score)\
            .count() == 2

    rank_score = tournament.rankings["xsumo.score"](db)
    assert [t.id for t,r in rank_score] == [1, 2, 3]

    rank_wins = tournament.rankings["xsumo.wins"](db)
    assert [t.id for t,r in rank_wins] == [1, 2, 3]

def test_tournament_double_rescue(db, tournament):
    db.add_all([
        make_event(teams=[1], judges=[1], block_id="rescue1.a", ts_sched=10, arena="rescue.1"),
        make_event(teams=[2], judges=[2], block_id="rescue1.a", ts_sched=10, arena="rescue.2"),
        make_event(teams=[1], judges=[1], block_id="rescue1.b", ts_sched=11, arena="rescue.1"),
        make_event(teams=[2], judges=[2], block_id="rescue1.b", ts_sched=11, arena="rescue.2")
    ])

    db.commit()

    events_a = query_full_events(db, tournament.blocks["rescue1.a"])
    events_b = query_full_events(db, tournament.blocks["rescue1.b"])

    for evs in (events_a, events_b):
        assert len(evs) == 2
        assert all(len(e.judges) == 1 for e in evs)
        assert all(len(e.teams) == 1 for e in evs)
        assert all(len(e.scores) == 1 for e in evs)

    ruleset = tournament.blocks["rescue1.a"].ruleset
    s1 = R(ruleset, {"viiva_punainen": "1", "time": 200})
    events_a[0].scores[0].data = ruleset.encode(s1)

    db.commit()

    ranks = tournament.rankings["rescue1"](db)
    assert ranks[0][1].best.time == 200
    assert ranks[1][1].best is None

    s2 = R(ruleset, {"viiva_punainen": "1", "time": 100})
    events_b[0].scores[0].data = ruleset.encode(s2)

    db.commit()

    ranks = tournament.rankings["rescue1"](db)
    assert ranks[0][1].best.time == 100
    assert ranks[1][1].best is None

def test_remove_events(db, tournament):
    db.add_all([
        make_event(teams=[1,2], judges=[1], block_id="xsumo.karsinnat", ts_sched=100,
            arena="xsumo.1")
    ])

    db.commit()

    assert tournament.blocks["xsumo.karsinnat"].events_query(db).count() == 1
    assert tournament.blocks["xsumo.karsinnat"].scores_query(db).count() == 2

    tournament.blocks["xsumo.karsinnat"].events_query(db).delete()

    db.commit()

    assert tournament.blocks["xsumo.karsinnat"].events_query(db).count() == 0
    assert tournament.blocks["xsumo.karsinnat"].scores_query(db).count() == 0

def test_remove_scores(db, tournament):
    event = make_event(teams=[1], judges=[1], block_id="remove-scores.xxx", ts_sched=1,
            arena="remove-scores.xxx")

    db.add(event)
    db.commit()

    db.delete(event.scores[0])

    with pytest.raises(IntegrityError):
        # jostakin syystä se triggeri aktivoituu vasta tässä mutta foreign key
        # cascadet aktivoituu jo ennen committia
        db.commit()

    db.rollback()

def test_remove_people(db):
    db.add_all([
        model.Team(id=100, name="asdt 1"),
        model.Judge(id=100, name="asdj 1"),
        make_event(teams=[100], judges=[100], block_id="remove.xxx", ts_sched=1,
            arena="remove.xxx"),
        make_event(teams=[1,100], judges=[100], block_id="remove.xxx", ts_sched=2,
            arena="remove.xxx")
    ])

    db.commit()

    with pytest.raises(IntegrityError):
        db.query(model.Team).filter_by(id=100).delete()

    with pytest.raises(IntegrityError):
        db.query(model.Judge).filter_by(id=100).delete()

    db.query(model.Event).filter_by(block_id="remove.xxx").delete()
    db.query(model.Team).filter_by(id=100).delete()
    db.query(model.Judge).filter_by(id=100).delete()

    db.commit()

def test_block_conflict(db):
    db.add_all([
        make_event(teams=[1], judges=[1], block_id="rescue1.a", ts_sched=200, arena="rescue.1"),
        make_event(teams=[2], judges=[2], block_id="rescue1.b", ts_sched=200, arena="rescue.1")
    ])

    with pytest.raises(IntegrityError):
        db.commit()
