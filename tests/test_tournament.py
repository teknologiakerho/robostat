import pytest
from sqlalchemy.orm import subqueryload
from sqlalchemy.exc import IntegrityError
import robostat
import robostat.db as model
from robostat.util import enumerate_rank
from robostat.rulesets.xsumo import XSRuleset
from .helpers import XS2, R, data, make_event

tj_data = data(lambda: [
    model.Team(id=1, name="Joukkue A"),
    model.Team(id=2, name="Joukkue B"),
    model.Team(id=3, name="Joukkue C"),
    model.Team(id=4, name="Joukkue D", is_shadow=1),

    model.Judge(id=1, name="Tuomari A"),
    model.Judge(id=2, name="Tuomari B")
])

xsumo_events = data(lambda: [
    make_event(teams=[1, 2], judges=[1], block_id="xsumo", ts_sched=0, arena="xsumo.1"),
    make_event(teams=[2, 3], judges=[1], block_id="xsumo", ts_sched=1, arena="xsumo.1"),
    make_event(teams=[3, 1], judges=[1], block_id="xsumo", ts_sched=2, arena="xsumo.1"),
])

rescue_events = data(lambda: [
    make_event(teams=[1], judges=[1], block_id="rescue1.a", ts_sched=0, arena="rescue.1"),
    make_event(teams=[2], judges=[2], block_id="rescue1.a", ts_sched=0, arena="rescue.2"),
    make_event(teams=[1], judges=[1], block_id="rescue1.b", ts_sched=1, arena="rescue.1"),
    make_event(teams=[2], judges=[2], block_id="rescue1.b", ts_sched=1, arena="rescue.2")
])

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

@tj_data
@xsumo_events
def test_single_block_query_events(db, tournament):
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

@tj_data
@xsumo_events
def test_single_judging(db, tournament):
    events = query_full_events(db, tournament.blocks["xsumo"])

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

@tj_data
@rescue_events
def test_query_double_block_events(db, tournament):
    events_a = query_full_events(db, tournament.blocks["rescue1.a"])
    events_b = query_full_events(db, tournament.blocks["rescue1.b"])

    for evs in (events_a, events_b):
        assert len(evs) == 2
        assert all(len(e.judges) == 1 for e in evs)
        assert all(len(e.teams) == 1 for e in evs)
        assert all(len(e.scores) == 1 for e in evs)

@tj_data
@rescue_events
def test_ranking_double_block(db, tournament):
    event_a = query_full_events(db, tournament.blocks["rescue1.a"])[0]
    event_b = query_full_events(db, tournament.blocks["rescue1.b"])[0]
    ruleset = tournament.blocks["rescue1.a"].ruleset

    s1 = R(ruleset, {"viiva_punainen": "S", "time": 200})
    event_a.scores[0].data = ruleset.encode(s1)

    db.commit()

    ranks = tournament.rankings["rescue1"](db)
    assert ranks[0][1].best.time == 200
    assert ranks[1][1].best is None

    s2 = R(ruleset, {"viiva_punainen": "S", "time": 100})
    event_b.scores[0].data = ruleset.encode(s2)

    db.commit()

    ranks = tournament.rankings["rescue1"](db)
    assert ranks[0][1].best.time == 100
    assert ranks[1][1].best is None

@tj_data
@data(lambda: [
    make_event(teams=[1,2], judges=[1], block_id="xsumo.karsinnat", ts_sched=100,
        arena="xsumo.1")
])
def test_remove_events(db, tournament):
    assert tournament.blocks["xsumo.karsinnat"].events_query(db).count() == 1
    assert tournament.blocks["xsumo.karsinnat"].scores_query(db).count() == 2

    tournament.blocks["xsumo.karsinnat"].events_query(db).delete()

    db.commit()

    assert tournament.blocks["xsumo.karsinnat"].events_query(db).count() == 0
    assert tournament.blocks["xsumo.karsinnat"].scores_query(db).count() == 0

@tj_data
def test_remove_scores(db):
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

@tj_data
@data(lambda: [
    model.Team(id=100, name="asdt 1"),
    model.Judge(id=100, name="asdj 1"),
    make_event(teams=[100], judges=[100], block_id="remove.xxx", ts_sched=1,
        arena="remove.xxx"),
    make_event(teams=[1,100], judges=[100], block_id="remove.xxx", ts_sched=2,
        arena="remove.xxx")
])
def test_remove_people(db):
    with pytest.raises(IntegrityError):
        db.query(model.Team).filter_by(id=100).delete()

    with pytest.raises(IntegrityError):
        db.query(model.Judge).filter_by(id=100).delete()

    db.query(model.Event).filter_by(block_id="remove.xxx").delete()
    db.query(model.Team).filter_by(id=100).delete()
    db.query(model.Judge).filter_by(id=100).delete()

    db.commit()

@tj_data
def test_block_conflict(db):
    db.add_all([
        make_event(teams=[1], judges=[1], block_id="rescue1.a", ts_sched=200, arena="rescue.1"),
        make_event(teams=[2], judges=[2], block_id="rescue1.b", ts_sched=200, arena="rescue.1")
    ])

    with pytest.raises(IntegrityError):
        db.commit()

@tj_data
@data(lambda: [
    make_event(teams=[2], judges=[1], block_id="rescue1.a", ts_sched=300, arena="rescue.1"),
    make_event(teams=[3], judges=[1], block_id="rescue1.a", ts_sched=301, arena="rescue.1"),
    make_event(teams=[4], judges=[1], block_id="rescue1.a", ts_sched=302, arena="rescue.1")
])
def test_hide_shadows(db, tournament):
    assert tournament.blocks["rescue1.a"].events_query(db, hide_shadows=True).count() == 2
    assert tournament.blocks["rescue1.a"].events_query(db, hide_shadows=False).count() == 3

@tj_data
def test_weighted_ranking(db, tournament):
    event_a = make_event(teams=[1], judges=[1], block_id="rescue1.a", ts_sched=0, arena="rescue.1")
    event_b = make_event(teams=[2], judges=[1], block_id="rescue1.b", ts_sched=1, arena="rescue.2")
    db.add_all([event_a, event_b])
    db.commit()

    ruleset = tournament.blocks["rescue1.a"].ruleset
    event_a.scores[0].data = ruleset.encode(R(ruleset, {"time": 0}))
    event_b.scores[0].data = ruleset.encode(R(ruleset, {"viiva_punainen": "S", "time": 200}))
    db.commit()

    ranks = tournament.rankings["rescue1.weighted"](db)
    assert [t.id for t,_ in ranks] == [1, 2]
    assert [i for i,_ in enumerate_rank(ranks, key=lambda x:x[1])] == [1, 2]

@tj_data
@xsumo_events
@data(lambda: [
    model.Tiebreak(ranking_id="xsumo.tb", team_id=1, weight=3),
    model.Tiebreak(ranking_id="xsumo.tb", team_id=2, weight=2),
    model.Tiebreak(ranking_id="xsumo.tb", team_id=3, weight=1)
])
def test_tiebreak_no_scores(db, tournament):
    ranks = tournament.rankings["xsumo.tb"](db)

    assert [t.id for t,_ in ranks] == [1, 2, 3]
    assert [i for i,_ in enumerate_rank(ranks, key=lambda x:x[1])] == [1, 2, 3]

@tj_data
@xsumo_events
@data(lambda: [
    model.Tiebreak(ranking_id="xsumo.tb", team_id=1, weight=3),
    model.Tiebreak(ranking_id="xsumo.tb", team_id=2, weight=2),
    model.Tiebreak(ranking_id="xsumo.tb", team_id=3, weight=100)
])
def test_tiebreak_with_scores(db, tournament):
    ranking = tournament.rankings["xsumo.tb"]

    scores = db.query(model.Score)\
            .filter_by(event_id=1)\
            .order_by(model.Score.team_id)\
            .all()

    s1, s2, = XS2([((True, "W"), (False, "L")), ((False, "L"), (True, "W"))])
    scores[0].data = tournament.blocks["xsumo"].ruleset.encode(s1)
    scores[1].data = tournament.blocks["xsumo"].ruleset.encode(s2)
    db.commit()

    ranks = ranking(db)
    assert [t.id for t,_ in ranks] == [1, 2, 3]
    assert [i for i,_ in enumerate_rank(ranks, key=lambda x:x[1])] == [1, 2, 3]
