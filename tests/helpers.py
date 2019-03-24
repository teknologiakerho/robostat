import itertools
import pytest
from robostat.rulesets.xsumo import XSumoScore, XSRoundScore, XMRoundScore, XSumoResult,\
        calc_results
from robostat.rulesets.rescue import RescueResult, RescueMultiObstacleScore

def product_range(src, min_len=0, max_len=1):
    for r in range(min_len, max_len):
        yield from itertools.product(src, repeat=r)

def combinations_range(src, min_len=0, max_len=None):
    if max_len is None:
        max_len = len(src) + 1

    for r in range(min_len, max_len):
        yield from itertools.combinations(src, r=r)

def check_catscores_equal(score1, score2):
    __tracebackhide__ = True

    cats1 = set(score1.__cats__)
    cats2 = set(score2.__cats__)

    if cats1 != cats2:
        pytest.fail("Category sets disagree: %s | %s" % (cats1, cats2))

    for k,v in cats1:
        if getattr(score1, k) != getattr(score2, k):
            pytest.fail("Category values disagree [%s]: %s != %s"\
                    % (k, getattr(score1, k), getattr(score2, k)))

def _make_xsumo_scores(rounds1, rounds2):
    s1 = XSumoScore(rounds=rounds1)
    s2 = XSumoScore(rounds=rounds2)
    calc_results(s1, s2)
    return s1, s2

def XS(res, rounds):
    return XSumoScore(
        result=XSumoResult(res),
        rounds=[XSRoundScore(f, XSumoResult(r)) for f,r in rounds]
    )

def XS2(rounds):
    rs = [[XSRoundScore(f, XSumoResult(r)) for f,r in res] for res in rounds]
    return _make_xsumo_scores([r[0] for r in rs], [r[1] for r in rs])

def XM(res, rounds):
    return XSumoScore(
        result=XSumoResult(res),
        rounds=list(map(XMRoundScore, rounds))
    )

def XM2(rounds):
    rs1 = [XMRoundScore([r[0] for r in res]) for res in rounds]
    rs2 = [XMRoundScore([r[1] for r in res]) for res in rounds]
    return _make_xsumo_scores(rs1, rs2)

def R(ruleset, values):
    ret = ruleset.create_score()

    for k,v in values.items():
        if isinstance(v, tuple):
            setattr(ret, k, RescueMultiObstacleScore(*v))
        elif isinstance(v, str):
            setattr(ret, k, RescueResult(v))
        else:
            setattr(ret, k, v)

    return ret

def D(ruleset, values):
    ret = ruleset.create_score()

    for k,v in values.items():
        setattr(ret, k, v)

    return ret
