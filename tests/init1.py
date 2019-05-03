import robostat
from robostat.tournament import WeightedRank, aggregate_scores, sort_ranking, decode_block_scores,\
        tiebreak_ranking, combine_ranks
from robostat.rulesets.xsumo import XSRuleset, XSumoScoreRank, XSumoWinsRank
from robostat.rulesets.rescue import RescueRuleset, RescueMaxRank

xsumo_ruleset = XSRuleset()
rescue1_ruleset = RescueRuleset.by_difficulty(1, max_time=600)

xsumo = robostat.block(
        id="xsumo",
        ruleset=xsumo_ruleset,
        name="XSumo"
)

xsumo_karsinnat = robostat.block(
        id="xsumo.karsinnat",
        ruleset=xsumo_ruleset,
        name="XSumo (karsinnat)"
)

rescue1_a = robostat.block(
        id="rescue1.a",
        ruleset=rescue1_ruleset,
        name="Rescue 1 (A)"
)

rescue1_b = robostat.block(
        id="rescue1.b",
        ruleset=rescue1_ruleset,
        name="Rescue 1 (B)"
)

@robostat.ranking("xsumo.score", name="XSumo A (Pisteet)")
def rank_xsumo_score(db):
    scores = xsumo.decode_scores(db)
    ranks = aggregate_scores(scores, XSumoScoreRank.from_scores)
    return sort_ranking(ranks.items())

@robostat.ranking("xsumo.wins", name="XSumo A (Voitot)")
def rank_xsumo_wins(db):
    scores = xsumo.decode_scores(db)
    ranks = aggregate_scores(scores, XSumoWinsRank.from_scores)
    return sort_ranking(ranks.items())

@robostat.ranking("xsumo.tb", name="XSumo A (Pisteet+tiebreak)")
def rank_xsumo_tb(db):
    scores = xsumo.decode_scores(db)
    ranks = aggregate_scores(scores, XSumoScoreRank.from_scores)
    tiebreaks = tiebreak_ranking(db, "xsumo.tb")
    combined = combine_ranks(ranks, tiebreaks)
    return sort_ranking(combined.items())

@robostat.ranking("rescue1", name="Rescue 1")
def rank_rescue1(db):
    scores = decode_block_scores(db, rescue1_a, rescue1_b)
    ranks = aggregate_scores(scores, RescueMaxRank.from_scores)
    return sort_ranking(ranks.items())

@robostat.ranking("rescue1.weighted", name="Rescue 1 (Painotettu)")
def rank_rescue1_weighted(db):
    scores_a = rescue1_a.decode_scores(db)
    scores_b = rescue1_b.decode_scores(db)
    ranks = aggregate_scores(scores_a, WeightedRank.wrap_aggregate(2, RescueMaxRank.from_scores))
    ranks.update(aggregate_scores(scores_b, WeightedRank.wrap_aggregate(1, RescueMaxRank.from_scores)))
    return sort_ranking(ranks.items())
