import itertools
import pytest
from robostat.ruleset import ValidationError
from robostat.rulesets import tanssi
from .helpers import combinations_range, check_catscores_equal, D

rs_interview, rs_perf = tanssi.get_dance_rulesets("2019")

@pytest.fixture(params=[rs_interview, rs_perf])
def ruleset(request):
    return request.param

# Antaa ison määrän kombinaatioita, sama idea kuin rescuessa
def get_valid_scores(ruleset):
    cats = list(ruleset.create_score().__cats__)
    c = itertools.count(start=1)

    for select_cats in combinations_range(cats):
        score = ruleset.create_score()

        for k,v in select_cats:
            val = 1 + next(c) % v.max
            setattr(score, k, val)

        yield score

# Sama kuin ylhäällä mutta laittaa virheellisiä arvoja
def get_invalid_scores(ruleset):
    cats = list(ruleset.create_score().__cats__)
    c = itertools.count(start=1)

    for select_cats in combinations_range(cats):
        score = ruleset.create_score()

        # laita eka kaikki ok arvoiks, nollatkin sallitaan tässä
        for k,v in cats:
            val = next(c) % (v.max+1)
            setattr(score, k, val)

        # muuta osa virheellisiks
        for k,v in select_cats:
            setattr(score, k, -1)
            yield score

        # sama liian isoilla arvoilla
        for k,v in select_cats:
            setattr(score, k, v.max+1)
            yield score

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

@pytest.mark.parametrize("score,expected", [
    (D(rs_interview, {}), 0),
    (D(rs_interview, {"suun_oma": 1}), 1),
    (D(rs_interview, {"suun_oma": 5, "suun_vaikeus": 0}), 5),
    (D(rs_interview, {"ohty_oma": 1, "ohty_selitys": 2, "ohty_vaikeus": 3}), 6),
    (D(rs_perf, {}), 0),
    (D(rs_perf, {"ktro_sommittelu": 1}), 1),
    (D(rs_perf, {"ktro_sommittelu": 3, "ktro_tehosteet": 0}), 3),
    (D(rs_perf, {"rkek_sopivuus": 1, "rkek_vaikeus": 2, "rkek_liikkuminen": 3}), 6)
])
def test_score_calculation(score, expected):
    assert int(score) == expected

def test_ranking():
    # TODO, sitten kun/jos tanssiranking joskus toteutetaan.
    pass
