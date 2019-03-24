import itertools
import functools
import collections
from enum import Enum
from robostat.util import noneflt
from robostat.ruleset import Ruleset, ValidationError, cat_score, IntCategory, CategoryRuleset

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

class RescueResult(Enum):
    FAIL = "F"
    SUCCESS_2 = "2"
    SUCCESS_1 = "1"

    def __init__(self, char):
        self.char = char

    def __str__(self):
        return self.char

    @property
    def opcode(self):
        return ord(self.char)

    @staticmethod
    def by_opcode(opcode):
        return RescueResult(chr(opcode))

SCORING_MULTIPLIERS = {
    "F": 0,
    "2": 0.5,
    "1": 1
}

class RescueCategory:
    pass

# näistä saa
# * täydet pisteet jos onnistuu ekalla
# * puolet pisteet jos toisella
# * 0 pistettä muuten
class RescueObstacleCategory(RescueCategory):

    default = RescueResult("F")

    def __init__(self, max, retryable=True):
        self.max = max
        self.retryable = retryable

    def score(self, val):
        return int(self.max * SCORING_MULTIPLIERS[str(val)])

    def decode(self, src):
        return RescueResult.by_opcode(src.read(1)[0])

    def encode(self, dest, value):
        dest.append(value.opcode)

    def validate(self, value):
        if value not in (RescueResult.FAIL, RescueResult.SUCCESS_1, RescueResult.SUCCESS_2):
            raise TypeError("Not a result: %s" % value)

        if value == RescueResult.SUCCESS_2 and not self.retryable:
            raise ValidationError("Unexpected SUCCESS_2 in non-retryable category")

class RescueMultiObstacleScore:

    __slots__ = "fail", "success1", "success2"

    def __init__(self, fail=0, success1=0, success2=0):
        self.fail = fail
        self.success1 = success1
        self.success2 = success2

    def __str__(self):
        return "%d/%d/%d" % (self.success1, self.success2, self.fail)

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        return self.fail == other.fail\
                and self.success1 == other.success1\
                and self.success2 == other.success2

    @property
    def multiplier(self):
        return self.success1*SCORING_MULTIPLIERS["1"] + self.success2*SCORING_MULTIPLIERS["2"]

class RescueMultiObstacleCategory(RescueCategory):

    def __init__(self, max):
        self.max = max

    @property
    def default(self):
        return RescueMultiObstacleScore()

    def score(self, val):
        return int(self.max * val.multiplier)

    def decode(self, src):
        return RescueMultiObstacleScore(*src.read(3))

    def encode(self, dest, value):
        dest.extend((value.fail, value.success1, value.success2))

    def validate(self, value):
        if not all(type(x) == int for x in (value.fail, value.success1, value.success2)):
            raise TypeError("Not a multi result: %s" % value)

        if min(value.fail, value.success1, value.success2) < 0:
            raise ValidationError("Negative count")

@functools.total_ordering
class RescueScore:

    @property
    def time_min(self):
        return self.time // 60

    @property
    def time_sec(self):
        return self.time % 60

    @property
    def score_categories(self):
        return filter(lambda x: isinstance(x[1], RescueCategory), self.__cats__)

    def __int__(self):
        return sum(v.score(getattr(self, k)) for k,v in self.score_categories)

    def __str__(self):
        return "%dp, %02d:%02d" % (int(self), self.time_min, self.time_sec)

    def __eq__(self, other):
        return int(self) == int(other) and self.time == other.time

    def __lt__(self, other):
        own_score = int(self)
        other_score = int(other)

        if own_score != other_score:
            return own_score < other_score

        # isompi aika on huonompi
        return self.time > other.time

# TODO: nää agregaattijutut vois kerätä johonki erilliseen yläluokkaan (AggregateRank)
# koska ne pätee esim tanssiin jne melkein kaikkeen muuhun paitsi sumoon
# TODO: tää nimeäminen ei ehkä oo paras jos tekee esim RescueSumRank
@functools.total_ordering
class RescueRank:

    def __init__(self, best, all):
        self.best = best
        self.all = all

    def __str__(self):
        return "%s [%s]" % (
            str(self.best),
            ", ".join(map(str, self.other_scores))
        )

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if self.best is None:
            return other.best is None
        if other.best is None:
            return self.best is None

        return self.best == other.best

    def __lt__(self, other):
        if self.best is None:
            return other.best is not None
        if other.best is None:
            return False

        return self.best < other.best

    @property
    def other_scores(self):
        return [s for s in self.all if s is not self.best]

    @property
    def played_scores(self):
        return [s for s in self.all if s is not None]

    @classmethod
    def from_scores(cls, scores):
        best = cls.aggregate(scores)
        return cls(best, scores)

class RescueMaxRank(RescueRank):
    aggregate = noneflt(functools.partial(max, default=None))

def make_cat(c, w):
    if c in REPEAT:
        return RescueMultiObstacleCategory(w)
    else:
        return RescueObstacleCategory(w)

TIME_CAT = IntCategory(signed=False)
CATS = dict((c, make_cat(c, w)) for c,w in WEIGHTS.items())

def _get_cats(l):
    return [("time", TIME_CAT), *((c, CATS[c]) for c in l)]

Rescue1Score = cat_score("Rescue1Score", _get_cats(R1_VIIVA + R1_UHRI), bases=[RescueScore])
Rescue2Score = cat_score("Rescue2Score", _get_cats(R2_VIIVA + R2_UHRI), bases=[RescueScore])
Rescue3Score = cat_score("Rescue3Score", _get_cats(R3_VIIVA + R3_UHRI), bases=[RescueScore])

class RescueRuleset(CategoryRuleset):

    def __init__(self, score_type, difficulty, max_time=None):
        super().__init__(score_type)
        self.difficulty = difficulty
        self.max_time = max_time

    def validate(self, score):
        super().validate(score)
        if score.time > self.max_time:
            raise ValidationError("Time exceeds max time (%d > %d)" % (score.time, self.max_time))

    @classmethod
    def by_difficulty(cls, difficulty, max_time=None):
        score = [Rescue1Score, Rescue2Score, Rescue3Score][difficulty-1]
        return cls(score_type=score, difficulty=difficulty, max_time=max_time)
