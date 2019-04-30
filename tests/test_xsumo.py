import itertools
import pytest
from robostat.ruleset import ValidationError
from robostat.rulesets import xsumo
from .helpers import product_range, XS, XS2, XM, XM2

MAX_TEST_ROUNDS = 3
MAX_TEST_PSEUDOROUNDS = 3

xs_ruleset = xsumo.XSRuleset()
xm_ruleset = xsumo.XMRuleset()

def reencode(ruleset, score):
    data = ruleset.encode(score)
    dec = ruleset.decode(data)

    assert dec.result == score.result
    assert len(dec.rounds) == len(score.rounds)

    return dec

# Kaikki tavat joilla xs kierros saa päättyä
valid_rounds_xs = [
    ((False, "L"), (False, "L")),
    *(((f, r1), (not f, r2))\
            for f in (True, False)\
            for r1,r2 in [("W", "L"), ("T", "T"), ("L", "W"), ("L", "L")])
]

# Kaikki tavat joilla xm (pseudo-)kierros saa päättyä
valid_pseudorounds_xm = [(3, 0), (0, 3), (1, 0), (0, 1), (2, 2)]
valid_rounds_xm = list(product_range(valid_pseudorounds_xm, max_len=MAX_TEST_PSEUDOROUNDS))

@pytest.fixture(scope="module")
def valid_scorepairs_xs():
    return list(map(XS2, product_range(valid_rounds_xs, max_len=MAX_TEST_ROUNDS)))

@pytest.fixture(scope="module")
def valid_scorepairs_xm():
    return list(map(XM2, product_range(valid_rounds_xm, max_len=MAX_TEST_ROUNDS)))

@pytest.fixture
def valid_scores_xs(valid_scorepairs_xs):
    # pistelista on symmetrinen joten riittää ottaa vaan ekat
    return (s1 for s1,s2 in valid_scorepairs_xs)

@pytest.fixture
def valid_scores_xm(valid_scorepairs_xm):
    return (s1 for s1,s2 in valid_scorepairs_xm)

@pytest.fixture
def invalid_scorepairs_xs():
    results = list(itertools.product((True, False), ("L", "T", "W")))
    outcomes = list(itertools.product(map(xsumo.XSumoResult, ("L", "T", "W")), repeat=2))

    def iterator():
        # Kaikki "mahdolliset" tavat jolla yksi kierros voi päättyä
        all_combinations = list(itertools.product(results, repeat=2))

        # min_len=1 koska tyhjä kierros on OK
        # Kaikki kierrosten jonot joissa jokainen kierros ei ole OK
        invalid_rounds = set(product_range(all_combinations, min_len=1, max_len=MAX_TEST_ROUNDS))\
                .difference(product_range(valid_rounds_xs, max_len=MAX_TEST_ROUNDS))

        yield from map(XS2, invalid_rounds)

        # OK kierrokset mutta väärät tulokset
        for s1, s2 in map(XS2, product_range(valid_rounds_xs, max_len=MAX_TEST_ROUNDS)):
            res = (s1.result, s2.result)
            for res1, res2 in filter(lambda x: x!=res, outcomes):
                s1.result = res1
                s2.result = res2
                yield s1, s2

        # Eripituiset kierrokset
        for len1, len2 in itertools.combinations(range(MAX_TEST_ROUNDS), 2):
            for rs1 in itertools.product(results, repeat=len1):
                for rs2 in itertools.product(results, repeat=len2):
                    yield XS("W", rs1), XS("L", rs2)
                    yield XS("L", rs1), XS("W", rs2)
                    yield XS("T", rs1), XS("T", rs2)

        # Puuttuvat tulokset
        NR = xsumo.XSumoScore(result=None)
        yield XS("W", []), NR
        yield NR, XS("W", [])
        yield NR, NR

    return iterator()

@pytest.fixture
def invalid_scorepairs_xm():
    # "Mahdolliset" tavat joilla pseudokierros voi päättyä
    results = list(itertools.product(range(4), repeat=2))

    def iterator():
        # "Mahdolliset" tavat joilla kierros voi päättyä
        all_combinations = list(product_range(results, max_len=MAX_TEST_PSEUDOROUNDS))

        # Sama idea kuin xs:ssä
        valid_rounds = set(product_range(valid_rounds_xm, max_len=MAX_TEST_ROUNDS))
        invalid_rounds = filter(
                lambda x: x not in valid_rounds,
                product_range(all_combinations, min_len=1, max_len=MAX_TEST_ROUNDS)
        )

        yield from map(XM2, invalid_rounds)

        # Eripituiset pseudokierrokset
        yield XM("W", [[3, 3]]), XM("L", [[]])
        yield XM("W", [[3, 3]]), XM("L", [[0]])
        yield XM("W", [[3, 3]]), XM("L", [[0, 0, 0]])

        # Virheellisiä arvoja
        yield XM("W", [[4]]), XM("L", [[0]])
        yield XM("W", [[3]]), XM("L", [[-1]])

        # Eripituiset kierrokset jne. tarkastetaan samalla logiikalla kaikissa
        # xsumo ruleseteissä joten niitä ei tarvii toistaa tässä

    return iterator()

def test_accept_valid_scorepairs_xs(valid_scorepairs_xs):
    for s1, s2 in valid_scorepairs_xs:
        xs_ruleset.validate(s1, s2)

def test_accept_valid_scorepairs_xm(valid_scorepairs_xm):
    for s1, s2 in valid_scorepairs_xm:
        xm_ruleset.validate(s1, s2)

def test_reject_invalid_scorepairs_xs(invalid_scorepairs_xs):
    for s1, s2 in invalid_scorepairs_xs:
        with pytest.raises(ValidationError):
            xs_ruleset.validate(s1, s2)

def test_reject_invalid_scorepairs_xm(invalid_scorepairs_xm):
    for s1, s2 in invalid_scorepairs_xm:
        with pytest.raises(ValidationError):
            xm_ruleset.validate(s1, s2)

def test_codec_xs(valid_scores_xs):
    for score in valid_scores_xs:
        dec = reencode(xs_ruleset, score)
        for rd,rs in zip(dec.rounds, score.rounds):
            assert rd.first == rs.first
            assert rd.result == rs.result

def test_codec_xm(valid_scores_xm):
    for score in valid_scores_xm:
        dec = reencode(xm_ruleset, score)
        for rd,rs in zip(dec.rounds, score.rounds):
            assert rd.results == rs.results

@pytest.mark.parametrize("scores,expected", [
    (XS2([]), (0, 0)),
    (XS2([((True, "W"), (False, "L"))]), (4, 0)),
    (XS2([((True, "T"), (False, "T"))]), (2, 1)),
    (XS2([((False, "W"), (True, "L")), ((True, "L"), (False, "W"))]), (4, 4)),
    (XM2([]), (0, 0)),
    (XM2([[(3, 0)]]), (3, 0)),
    (XM2([[(1, 0), (2, 2)]]), (3, 2)),
    (XM2([[(0, 3)], [(0, 1), (2, 2)]]), (2, 6))
])
def test_score_calculation(scores, expected):
    s1,s2 = scores
    e1,e2 = expected

    assert int(s1) == e1
    assert int(s2) == e2
    assert s1.result == s2.result.opposite

    if e1 > e2:
        assert str(s1.result) == "W"
        assert str(s2.result) == "L"
    elif e2 > e1:
        assert str(s1.result) == "L"
        assert str(s2.result) == "W"
    else:
        assert str(s1.result) == "T"
        assert str(s2.result) == "T"

def test_ranking():
    scores = {
        "A": (
            XS("W", [(True, "W"), (True, "W"), (True, "W")]),
            XS("L", [(False, "L")]),
            XS("L", [(False, "L")]),
            None
        ),
        "B": (
            XS("W", [(True, "W")]),
            XS("W", [(True, "W")]),
            XS("W", [(True, "W")]),
            None
        ),
        "C": (
            XS("L", [(False, "L")]),
            XS("L", [(False, "L"), (False, "L"), (False, "L")]),
            XS("L", [(False, "L")]),
            None
        ),
        "D": (
            XS("W", [(True, "W")]),
            XS("L", [(False, "L")]),
            XS("W", [(True, "W")]),
            None
        ),
        "E": (
            None,
            None,
            None,
            None
        )
    }

    score_ranks = dict((t, xsumo.XSumoScoreRank.from_scores(s)) for t,s in scores.items())
    win_ranks = dict((t, xsumo.XSumoWinsRank.from_scores(s)) for t,s in scores.items())

    assert score_ranks["C"] == score_ranks["E"]
    assert score_ranks["B"] > score_ranks["A"] > score_ranks["D"] > score_ranks["C"]

    assert win_ranks["C"] == win_ranks["E"]
    assert win_ranks["B"] > win_ranks["D"] > win_ranks["A"] > win_ranks["C"]
