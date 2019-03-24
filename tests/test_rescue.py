import itertools
import pytest
from robostat.ruleset import ValidationError
from robostat.rulesets import rescue
from .helpers import combinations_range, check_catscores_equal, R

r1 = rescue.RescueRuleset.by_difficulty(1, max_time=600)
r2 = rescue.RescueRuleset.by_difficulty(2, max_time=600)
r3 = rescue.RescueRuleset.by_difficulty(3, max_time=600)

@pytest.fixture(params=[r1, r2, r3])
def ruleset(request):
    return request.param

# Antaa kaikki kombinaatiot nolla- ja nollasta eroavista kategorioista
def get_valid_scores(ruleset):
    cats = list(ruleset.create_score().score_categories)
    nz_values = itertools.cycle(range(1, 10))
    result_values = itertools.cycle(map(rescue.RescueResult, ("F", "1", "2")))
    time_values = itertools.cycle(range(600))

    for select_cats in combinations_range(cats):
        score = ruleset.create_score()

        for k,v in select_cats:
            if isinstance(v, rescue.RescueMultiObstacleCategory):
                setattr(score, k, rescue.RescueMultiObstacleScore(
                    fail=next(nz_values),
                    success1=next(nz_values),
                    success2=next(nz_values)
                ))
            else:
                setattr(score, k, next(result_values))

        # Nolla aika sallitaan
        yield score
        score.time = next(time_values)
        yield score

def get_invalid_scores(ruleset):
    # Rescuessa ei voi juuri laittaa vääriä arvoja, muuta kuin negatiivisia
    multi_cats = [k for k,v in ruleset.create_score().score_categories\
            if isinstance(v, rescue.RescueMultiObstacleCategory)]

    for k in multi_cats:
        yield R(ruleset, {k: (-1, 0, 0)})
        yield R(ruleset, {k: (0, -2, 0)})
        yield R(ruleset, {k: (-1, -2, -3)})

    # normipisteet mutta ajat on väärin, 
    # tässä tuskin tarvitsee testata kaikkia kombinaatioita
    yield R(ruleset, {"time": 601})
    yield R(ruleset, {"time": -1})

def test_accept_valid_scores(ruleset):
    for score in get_valid_scores(ruleset):
        ruleset.validate(score)

def test_reject_invalid_scores(ruleset):
    for score in get_invalid_scores(ruleset):
        with pytest.raises(ValidationError):
            ruleset.validate(score)

def test_codec(ruleset):
    for score in get_valid_scores(ruleset):
        data = ruleset.encode(score)
        dec = ruleset.decode(data)
        check_catscores_equal(dec, score)

@pytest.mark.parametrize("score,exp_score,exp_time", [
    ({}, 0, 0),
    ({"time": 100}, 0, 100),
    ({"viiva_punainen": "1"}, 20, 0),
    ({"viiva_punainen": "2"}, 10, 0),
    ({"viiva_punainen": "F"}, 0, 0),
    ({"viiva_palat": (1, 2, 3)}, 20+15, 0),
    ({
        "viiva_punainen": "1",
        "viiva_palat": (0, 1, 0),
        "viiva_kippi": (1, 0, 2),
        "uhri_alue": "1",
        "uhri_tunnistus": "2",
        "time": 123
    }, (20+10+10+10+5), 123)
])
def test_score_calculation(ruleset, score, exp_score, exp_time):
    s = R(ruleset, score)
    assert int(s) == exp_score
    assert s.time == exp_time

def test_ranking(ruleset):
    scores = {
        "A": (
            R(ruleset, {"viiva_punainen": "1", "viiva_palat": (1, 2, 3), "time": 100}),
            None
        ),
        "B": (
            R(ruleset, {"viiva_punainen": "1", "time": 200}),
            R(ruleset, {"viiva_punainen": "1", "viiva_palat": (1, 2, 3), "time": 300})
        ),
        "C": (
            R(ruleset, {"viiva_punainen": "1", "time": 100}),
            R(ruleset, {"time": 0})
        ),
        "D": (
            R(ruleset, {"time": 1}),
            R(ruleset, {"time": 100})
        ),
        "E": (
            None,
            None
        )
    }

    max_ranks = dict((t, rescue.RescueMaxRank.from_scores(s)) for t,s in scores.items())

    assert max_ranks["A"] > max_ranks["B"] > max_ranks["C"] > max_ranks["D"] > max_ranks["E"]
