import itertools
import functools
import collections
from robostat.ruleset import Ruleset, ValidationError

LOSE = 0
TIE = 1
WIN = 3
RESULT_CHAR = "LT-W?"

def result(s1, s2):
    if s1 == s2:
        return TIE
    return WIN if s1 > s2 else LOSE

def other(res):
    if res == TIE:
        return TIE
    return 3 - res

class XSumoScore:

    __slots__ = "result", "rounds"

    def __init__(self):
        self.result = None
        self.rounds = []

    def __int__(self):
        return sum(map(int, self.rounds))

    def __str__(self):
        return "|".join(itertools.chain(
            RESULT_CHAR[self.result],
            map(str, self.rounds)
        ))

def calc_results(s1, s2):
    s1.result = result(int(s1), int(s2))
    s2.result = other(s1.result)

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
                if s.result == WIN:
                    ret.wins += 1
                elif s.result == TIE:
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
        ret = XSumoScore()
        ret.result = int(data[0])
        num_rounds = int(data[1])
        self._decode_rounds(data[2:], ret, num_rounds)
        return ret

    def encode(self, score):
        ret = bytearray(2+self._data_length(score))
        ret[0] = int(score.result)
        ret[1] = len(score.rounds)
        self._encode_rounds(ret, score, 2)
        return ret

    def validate(self, s1, s2):
        if s1.result is None or s2.result is None:
            raise ValidationError("result is not set, call calc_results() first")

        win_res = max(s1.result, s2.result)
        lose_res = min(s1.result, s2.result)

        if not ((win_res == 3 and lose_res == 0) or (win_res == 1 and lose_res == 1)):
            raise ValidationError("Invalid score result (%d, %d)" % (s1.result, s2.result))

        if len(s1.rounds) != len(s2.rounds):
            raise ValidationError("Inconsistent number of rounds (%d, %d)" \
                    % (len(s1.rounds), len(s2.rounds)))

    def _decode_rounds(self, data, score, num_rounds):
        raise NotImplementedError

    def _encode_rounds(self, data, score, offset):
        raise NotImplementedError

    def _data_length(self, score):
        raise NotImplementedError

# Perinteinen xsumo

class XSRoundScore:

    __slots__ = "first", "result"

    def __init__(self, first, result):
        self.first = first
        self.result = result

    def __int__(self):
        return int(self.first) + self.result

    def __str__(self):
        return "%d+%d" % (int(self.first), self.result)

class XSRuleset(XSumoRuleset):

    def _decode_rounds(self, data, score, num_rounds):
        for i in range(num_rounds):
            r = int(data[i])
            score.rounds.append(XSRoundScore(bool(r&1), r>>1))

    def _encode_rounds(self, data, score, offset):
        for i in range(len(score.rounds)):
            data[i+offset] = int(score.rounds[i].first)|(score.rounds[i].result<<1)

    def _data_length(self, score):
        return len(score.rounds)

    def _validate_rounds(self, r1, r2):
        # Molemmat ei voi olla ensimmäisiä
        if r1.first and r2.first:
            raise ValidationError("Both scores marked first")

        # Jos kumpikaan ei ole ensimmäinen, kumpikaan ei ehtinyt laudalle,
        # joten molemmat häviävät välttämättä
        if (not (r1.first or r2.first)) and (r1.result != 0 or r2.result != 0):
            raise ValidationError("Nonzero result in lose-lose round")

        # Muuten peli voi päättyä joko
        # * Toinen voittaa ja toinen häviää
        # * Tasapeli
        # * Molemmat häviävät
        win_res = max(r1.result, r2.result)
        lose_res = min(r1.result, r2.result)
        if win_res == 3 and lose_res == 0:
            return
        if win_res == 1 and lose_res == 1:
            return
        if win_res == 0 and lose_res == 0:
            return

        raise ValidationError("Invalid round result (%d, %d)" % (r1.result, r2.result))

    def validate(self, s1, s2):
        super().validate(s1, s2)

        for r1, r2 in zip(s1.rounds, s2.rounds):
            self._validate_rounds(r1, r2)

# Robomestarit XSumo

class XMRoundScore:

    __slots__ = "pseudorounds"

    def __init__(self, pseudorounds):
        self.pseudorounds = pseudorounds

    def __int__(self):
        return sum(self.pseudorounds)

    def __str__(self):
        return str(int(self))

class XMRuleset(XSumoRuleset):

    def _decode_rounds(self, data, score, num_rounds):
        lengths, data = data[:num_rounds], data[num_rounds:]
        for l in lengths:
            score.rounds.append(XMRoundScore(map(int, data[:l])))
            data = data[l:]

    def _encode_rounds(self, data, score, offset):
        data[offset:] = itertools.chain(
                (len(r.pseudorounds) for r in score.rounds),
                *(r.pseudorounds for r in score.rounds)
        )

    def _data_length(self, score):
        return sum(len(r.pseudorounds) for r in score.rounds) + len(score.rounds)

# Innokas-Robomestarit XSumo (Robomestarit + viivanseuraus)

class XIRoundScore:

    __slots__ = "first", "pseudorounds"

    def __init__(self, first, pseudorounds):
        self.first = first
        self.pseudorounds = pseudorounds

    def __int__(self):
        return int(self.first) + sum(self.pseudorounds)

    def __str__(self):
        return "%d+%d" % (int(self.first), sum(self.pseudorounds))

class XIRuleset(XSumoRuleset):

    def _decode_rounds(self, data, score, num_rounds):
        lengths, data = data[:num_rounds], data[num_rounds:]
        for l in lengths:
            score.rounds.append(XIRoundScore(bool(data[0]), map(int, data[1:l+1])))
            data = data[l+1:]

    def _encode_rounds(self, data, score, offset):
        data[offset:] = itertools.chain(
                (len(r.pseudorounds) for r in score.rounds),
                *([1, *r.pseudorounds] for r in score.rounds)
        )

    def _data_length(self, score):
        return sum(len(r.pseudorounds) for r in score.rounds) + 2*len(score.rounds)

    def validate(self, s1, s2):
        super().validate(s1, s2)

        # TODO
        # Mahdolliset tilanteet:
        # - Pelataan yksi kierros, jossa toinen robotti on ensimmäinen ja siinä on
        #   yksi pseudokierros jossa voittaja saa 5 pistettä ja häviäjä 0.
        #   (voittaja saa siis yhteensä 6=1+5 pistettä)
        # - Pelataan n >= 0 kierrosta, joissa toinen tai ei kumpikaan joukkue on
        #   ensimmäinen kentällä ja jokaisella pseudokierroksella toinen saa
        #   [1,2,3] pistettä ja toinen 0. (jos kumpikaan ei ehdi kentälle, niin
        #   0 pseudokierrosta).

        #### nvm ne pisteet voi antaa vaan 3+2 pseudokierroksina.

        for r1, r2, in zip(s1.rounds, s2.rounds):
            if r1.first and r2.first:
                raise ValidationError("Both scores marked first")

            if (not (r1.first or r2.first)) and (int(r1) != 0 or int(r2) != 0):
                raise ValidationError("Neither marked first in non zero-zero round")
