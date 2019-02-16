import itertools
import functools
from robostat.ruleset import Ruleset, ValidationError, cat_score, ListCategory, IntCategory,\
        CategoryRuleset

WEIGHTS = {
        "viiva_punainen": 20,
        "viiva_palat": 10,
        "viiva_kippi": 10,
        "viiva_maki": 10,
        "viiva_kulma": 10,
        "viiva_hidasteet": 10,
        "viiva_risteys": 10,
        "viiva_katkos": 10,
        "viiva_este": 10,

        "uhri_alue": 10,
        "uhri_tunnistus": 10,
        "uhri_nosto": 10,
        "uhri_koroke": 10,
        "uhri_tarttuminen": 10,
        "uhri_ulos": 10,
        "uhri_pelastus": 20,
        "uhri_peruutus": 10
}

REPEAT = set([
        "viiva_palat",
        "viiva_kippi",
        "viiva_maki",
        "viiva_kulma",
        "viiva_hidasteet",
        "viiva_risteys",
        "viiva_katkos",
        "viiva_este"
])

R1_VIIVA = [
        "viiva_punainen",
        "viiva_palat",
        "viiva_kippi"
]

R1_UHRI = [
        "uhri_alue",
        "uhri_tunnistus",
        "uhri_ulos",
        "uhri_peruutus"
]

R2_VIIVA = [
        *R1_VIIVA,
        "viiva_maki",
        "viiva_kulma",
        "viiva_hidasteet",
        "viiva_risteys"
]

R2_UHRI = [
        *R1_UHRI,
        "uhri_tarttuminen"
]

R3_VIIVA = [
        *R2_VIIVA,
        "viiva_katkos",
        "viiva_este"
]

R3_UHRI = [
        "uhri_alue",
        "uhri_tunnistus",
        "uhri_nosto",
        "uhri_koroke",
        "uhri_pelastus",
        "uhri_peruutus"
]

FAIL = 0
SUCCESS_2 = 1
SUCCESS_1 = 2

class RescueCategory:
    pass

# näistä saa
# * täydet pisteet jos onnistuu ekalla
# * puolet pisteet jos toisella
# * 0 pistettä muuten
class RescueObstacleCategory(RescueCategory):

    default = FAIL

    def __init__(self, max, retryable=True):
        self.max = max
        self.retryable = retryable

    def score(self, val):
        return (val * self.max) // 2

    def decode(self, data):
        return int(data[0]), 1

    def encode(self, dest, value):
        dest.append(value)

    def validate(self, value):
        if value == SUCCESS_2 and not self.retryable:
            raise ValidationError("Unexpected SUCCESS_2 in non-retryable category")
        if value not in (FAIL, SUCCESS_1):
            raise ValidationError("Unexpected retry value: %d" % value)

class RescueListCategory(RescueCategory, ListCategory):

    def score(self, val):
        return sum(self._cat.score(v) for v in val)

@functools.total_ordering
class _RescueScore:

    @property
    def time_min(self):
        return self.time // 60

    @property
    def time_sec(self):
        return self.time % 60

    def __int__(self):
        return sum(v.score(getattr(self, k)) for k,v in self.__cats__\
                if isinstance(v, RescueCategory))

    def __str__(self):
        return "%dp, %02d:%02d" % (int(self), self.time_min, self.time_sec)

    def __eq__(self, other):
        return int(self) == int(other) and self.time == other.time

    def __lt__(self, other):
        own_score = int(self)
        other_score = int(other)
        if own_score != other_score:
            return own_score < other_score
        return self.time < other.time

# väliluokka että tähän voi tunkee field_injectorilla jotakin
class RescueRuleset(CategoryRuleset):
    pass

# TODO tähän vois tehä myös jonkun RescueRank luokan (vähän niiku xsumorank)
# jossa on lista suorituksista tjsp
# tai samantien max rank luokan koska sama idea pätee myös tanssiin

def make_cat(c, w):
    ret = RescueObstacleCategory(w)
    if c in REPEAT:
        ret = RescueListCategory(ret)
    return ret

TIME_CAT = IntCategory(signed=False)
CATS = dict((c, make_cat(c, w)) for c,w in WEIGHTS.items())

def _get_cats(l):
    return [("time", TIME_CAT), *((c, CATS[c]) for c in l)]

Rescue1Score = cat_score("Rescue1Score", _get_cats(R1_VIIVA + R1_UHRI), bases=[_RescueScore])
Rescue2Score = cat_score("Rescue2Score", _get_cats(R2_VIIVA + R2_UHRI), bases=[_RescueScore])
Rescue3Score = cat_score("Rescue3Score", _get_cats(R3_VIIVA + R3_UHRI), bases=[_RescueScore])

rescue1_ruleset = RescueRuleset(Rescue1Score)
rescue2_ruleset = RescueRuleset(Rescue2Score)
rescue3_ruleset = RescueRuleset(Rescue3Score)
