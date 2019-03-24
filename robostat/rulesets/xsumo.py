import io
import itertools
import functools
import collections
from enum import Enum
from robostat.ruleset import Ruleset, ValidationError

class XSumoResult(Enum):
    LOSE = "L"
    TIE = "T"
    WIN = "W"

    def __init__(self, char):
        self.char = char

    def __str__(self):
        return self.char

    @property
    def opposite(self):
        return OPPOSITE_RESULT[self.char]

    @property
    def opcode(self):
        return ord(self.char)

    @staticmethod
    def by_opcode(opcode):
        return XSumoResult(chr(opcode))

OPPOSITE_RESULT = {
    "L": XSumoResult("W"),
    "T": XSumoResult("T"),
    "W": XSumoResult("L")
}

class XSumoScore:

    __slots__ = "result", "rounds"

    def __init__(self, result=None, rounds=None):
        self.result = result
        self.rounds = rounds if rounds is not None else []

    def __int__(self):
        return sum(map(int, self.rounds))

    def __str__(self):
        return "|".join(itertools.chain(
            str(self.result),
            map(str, self.rounds)
        ))

    def __repr__(self):
        return "%s:%s" % (self.result, self.rounds)

def result(ns1, ns2):
    if ns1 > ns2:
        return XSumoResult("W")
    if ns1 < ns2:
        return XSumoResult("L")
    return XSumoResult("T")

def calc_results(s1, s2):
    s1.result = result(int(s1), int(s2))
    s2.result = s1.result.opposite

class XSumoRank:

    __slots__ = "score", "wins", "ties", "losses", "unplayed"

    def __init__(self):
        self.score = 0
        self.wins = 0
        self.ties = 0
        self.losses = 0
        self.unplayed = 0

    def __str__(self):
        return "%d (%d/%d/%d/%d)" % (
                self.score,
                self.wins,
                self.ties,
                self.losses,
                self.unplayed
        )

    def __repr__(self):
        return str(self)

    @property
    def played(self):
        return self.wins + self.ties + self.losses

    @classmethod
    def from_scores(cls, scores):
        ret = cls()

        for s in scores:
            if s is None:
                ret.unplayed += 1
            else:
                ret.score += int(s)
                if str(s.result) == "W":
                    ret.wins += 1
                elif str(s.result) == "T":
                    ret.ties += 1
                else:
                    ret.losses += 1

        return ret

@functools.total_ordering
class XSumoScoreRank(XSumoRank):

    def __eq__(self, other):
        return self.score == other.score

    def __lt__(self, other):
        return self.score < other.score

@functools.total_ordering
class XSumoWinsRank(XSumoRank):

    def __eq__(self, other):
        return self.wins == other.wins and self.ties == other.ties

    def __lt__(self, other):
        if self.wins != other.wins:
            return self.wins < other.wins
        return self.ties < other.ties

class XSumoRuleset(Ruleset):

    def create_score(self):
        return XSumoScore()

    def decode(self, data):
        stream = io.BytesIO(data)
        ret = self.create_score()
        ret.result = XSumoResult.by_opcode(stream.read(1)[0])
        num_rounds = stream.read(1)[0]
        for _ in range(num_rounds):
            ret.rounds.append(self._decode_round(stream))
        return ret

    def encode(self, score):
        ret = bytearray()
        ret.append(score.result.opcode)
        ret.append(len(score.rounds))
        for r in score.rounds:
            self._encode_round(ret, r)
        return ret

    def validate(self, s1, s2):
        if s1.result is None or s2.result is None:
            raise ValidationError("Result is not set, call calc_results() first")

        if s1.result != s2.result.opposite:
            raise ValidationError("Conflicting results: (%s, %s)" % (s1.result, s2.result))

        if s1.result != result(int(s1), int(s2)):
            raise ValidationError("Conflicting scores: (%s, %s), (%d, %d)"\
                    % (s1.result, s2.result, int(s1), int(s2)))

        if len(s1.rounds) != len(s2.rounds):
            raise ValidationError("Inconsistent number of rounds (%d, %d)" \
                    % (len(s1.rounds), len(s2.rounds)))

        for r1, r2 in zip(s1.rounds, s2.rounds):
            self._validate_rounds(r1, r2)

    def _decode_round(self, stream):
        raise NotImplementedError

    def _encode_round(self, dest, rnd):
        raise NotImplementedError

    def _validate_rounds(self, r1, r2):
        pass

#####
# Perinteinen xsumo (xs): Viivanseuraus + sumo-ottelu
# * Ensimmäisenä ehtinyt +1p
# * Jos molemmat pääsevät areenalle, pisteet jaetaan seuraavasti:
#   - Häviö: 0p
#   - Tasapeli: 1p
#   - Voitto: 3p
# * Jos kumpikaan ei pääse areenalle, tilanne tulkitaan molempien häviöksi

# XSumo-kierros (ilman viivanseurausta) voi päättyä seuraavasti:
# * Toinen voittaa ja toinen häviää
# * Tasapeli
# * Molemmat häviävät:
#   - Viivallisissa lajeissa (xs,xi) kumpikaan ei ehdi areenalle
#   - Viivallisissa lajeissa toinen ehtii areenalla mutta ajaa ulos ja toinen ei ehdi
#   - Säännöt eivät yksikäsitteisesti määrittele mitä tapahtuu jos molemmat kaatuvat

def round_result_valid(res1, res2):
    if str(res1) == "L" and str(res2) == "L":
        return True
    return res1 == res2.opposite

class XSRoundScore:

    __slots__ = "first", "result"
    SCORING = {"L": 0, "T": 1, "W": 3}

    def __init__(self, first, result):
        self.first = first
        self.result = result

    def __int__(self):
        return int(self.first) + self.SCORING[str(self.result)]

    def __str__(self):
        return "%d+%d" % (int(self.first), self.SCORING[str(self.result)])

    def __repr__(self):
        return "%d:%s" % (int(self.first), self.result)

class XSRuleset(XSumoRuleset):

    def _decode_round(self, stream):
        first, res = stream.read(2)
        return XSRoundScore(bool(first), XSumoResult.by_opcode(res))

    def _encode_round(self, dest, rnd):
        dest.append(int(rnd.first))
        dest.append(rnd.result.opcode)

    def _validate_rounds(self, r1, r2):
        # Molemmat ei voi olla ensimmäisiä
        if r1.first and r2.first:
            raise ValidationError("Both marked first")

        if r1.first or r2.first:
            # Toinen ehti ensin joten pisteytys normaalin sumo-ottelun mukaan (L-L mukaanlukien)
            if not round_result_valid(r1.result, r2.result):
                raise ValidationError("Invalid result: (%s, %s)" % (r1.result, r2.result))
        else:
            # Kumpikaan ei ole ensimmäinen joten L-L on ainoa hyväksyttävä tilanne 
            if str(r1.result) != "L" or str(r2.result) != "L":
                raise ValidationError("Invalid result: Expected L-L got (%s, %s)"\
                        % (r1.result, r2.result))

# Robomestarit- ja Innokas-xsumoissa kierros koostuu pienistä eristä, jotka voivat päättyä
# seuraavasti:
# * Toinen robotti voittaa ja saa 3 pistettä, toinen häviää ja saa 0 pistettä
# * Toinen robotti voittaa ja saa 1 pisteen, toinen häviää ja saa 0 pistettä
# * Tasapeli ja molemmat saavat 2 pistettä
# * Erityisesti 0-0 tilanne ei ole mahdollinen
#
# Säännöissä ei määritellä miten lopulliset pisteet määräytyvät eräpisteistä.
# Robostat laskee lopulliset pisteet summana pseudokierrosten yli.
#
# Tällä hetkellä vain robomestarit-versio on toteutettu robostatissa:
# innokas-version määrittely ei ole riittävän yksikäsitteinen,
# mutta se on helppo toteuttaa alla olevien apuluokkien avulla

def pseudoround_result_valid(res1, res2):
    res_max, res_min = max(res1, res2), min(res1, res2)

    if res_max == 3 and res_min == 0:
        return True
    if res_max == 1 and res_min == 0:
        return True
    if res_max == 2 and res_min == 2:
        return True

    return False

class _XSumoPseudoroundScore:

    def __init__(self, results):
        self.results = results

    @property
    def res_value(self):
        return sum(self.results)

class _XSumoPseudoroundRuleset:

    def _decode_results(self, stream):
        num_rounds = stream.read(1)[0]
        return list(stream.read(num_rounds))

    def _decode_round(self, stream):
        return _XSumoPseudoroundScore(self._decode_results(stream))

    def _encode_round(self, dest, rnd):
        dest.append(len(rnd.results))
        dest.extend(rnd.results)

    def _validate_rounds(self, r1, r2):
        if len(r1.results) != len(r2.results):
            raise ValidationError("Result length mismatch: %d != %d"\
                    % (len(r1.results), len(r2.results)))

        for res1, res2 in zip(r1.results, r2.results):
            if not pseudoround_result_valid(res1, res2):
                raise ValidationError("Invalid result: (%d, %d)" % (res1, res2))

#####
# Robomestarit xsumo (xm): jokainen kierros jaetaan pienempiin kierroksiin
# * Ei viivanseurausta
# * Yleensä kierroksessa rajallinen aika ja pelataan niin monta pientä kierrosta kuin ehditään
# * Ottelun pisteet summa pienten kierroksien yli

class XMRoundScore(_XSumoPseudoroundScore):

    __slots__ = "results"

    def __init__(self, results):
        super().__init__(results)

    def __int__(self):
        return self.res_value

    def __str__(self):
        return str(int(self))

    def __repr__(self):
        return str(self.results)

class XMRuleset(_XSumoPseudoroundRuleset, XSumoRuleset):

    def _decode_round(self, stream):
        return XMRoundScore(self._decode_results(stream))
