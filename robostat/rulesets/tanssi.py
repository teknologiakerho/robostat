import functools
from robostat.ruleset import Ruleset, ValidationError, cat_score, CategoryRuleset

INTERVIEW_SCORING_2019 = {
        # suunnittelu ja rakenne, 12
        "suun_oma": 5,
        "suun_vaikeus": 2,
        "suun_tasapaino": 2,
        "suun_dokumentointi": 3,

        # ohjelmointi ja työskentely, 10
        "ohty_oma": 2,
        "ohty_vaikeus": 5,
        "ohty_selitys": 2,
        "ohty_tjako": 1,

        # sensoreiden ja tekniikan käyttö, 3
        "sntk_sensorit": 3,

        # esittelypiste, 5
        "esip_yleis": 2,
        "esip_esiintyminen": 3

        # => yht, 30
}

PERFORMANCE_SCORING_2019 = {
        # kokonaisuus: taiteellinen suunnittelu, rekvisiitta ja osallistuminen, 12
        "ktro_sommittelu": 3,
        "ktro_tehosteet": 3,
        "ktro_rekvisiitta": 3,
        "ktro_osallistuminen": 3,

        # robotin/robottien koreografia ja esiintymisalueen käyttö, 9
        "rkek_sopivuus": 3,
        "rkek_vaikeus": 3,
        "rkek_liikkuminen": 3,

        # r/rt sensorit ja teknologia, 5
        "rstk_alue": 3,
        "rstk_toimivuus": 2,

        # r/rt viihdyttävyys ja sujuvuus, 10
        "rvsj_vaihtelevuus": 4,
        "rvsj_hallinta": 3,
        "rvsj_ulkoasu_esitys": 3,

        # luotettavuus, 9
        "ltvs_toiminta": 2,
        "ltvs_aika": 2,
        "ltvs_aloitukset": 2,
        "ltvs_kosketukset": 3,

        # harkinnanvaraiset pisteet, 5
        "hvps_pisteet": 5

        # => yht, 50
}

class DanceCategory:

    default = 0

    def __init__(self, max):
        self.max = max

    def decode(self, src):
        return src.read(1)[0]

    def encode(self, dest, value):
        dest.append(value)

    def validate(self, value):
        if value < 0:
            raise ValidationError("Negative score: %d" % value)
        if value > self.max:
            raise ValidationError("Score exceeds max: %d > %d" % (value, self.max))

@functools.total_ordering
class DanceScore:

    def __int__(self):
        return sum(getattr(self, k) for k,_ in self.__cats__)

    def __str__(self):
        return "%dp" % int(self)

    def __eq__(self, other):
        return int(self) == int(other)

    def __lt__(self, other):
        return int(self) < int(other)

class DanceInterviewScore(DanceScore): pass
class DancePerformanceScore(DanceScore): pass

def _get_cats(src):
    return sorted((k, DanceCategory(v)) for k,v in src.items())

DanceInterviewScore2019 = cat_score("DanceInterviewScore2019",
        _get_cats(INTERVIEW_SCORING_2019),
        bases=[DanceInterviewScore]
)

DancePerformanceScore2019 = cat_score("DancePerformanceScore2019",
        _get_cats(PERFORMANCE_SCORING_2019),
        bases=[DancePerformanceScore]
)

class DanceRuleset(CategoryRuleset): pass
class DanceInterviewRuleset(DanceRuleset): pass
class DancePerformanceRuleset(DanceRuleset): pass

def get_dance_rulesets(rev):
    if int(rev) == 2019:
        iscore, pscore = DanceInterviewScore2019, DancePerformanceScore2019
    else:
        raise ValueError(rev)

    return DanceInterviewRuleset(iscore), DancePerformanceRuleset(pscore)
