import io

class Ruleset:

    # voi palauttaa mitä tahansa, mikä kuvaa suorituksen pisteitä (luku, dict, olio, ...)
    # robostat ei tee mitään oletuksia sen suhteen millainen score on
    def create_score(self):
        raise NotImplementedError

    # muutaa bytes objektin scoreksi
    def decode(self, data):
        raise NotImplementedError

    # muuttaa scoren bytes objectkiksi
    def encode(self, score):
        raise NotImplementedError

    # tarkistaa _kaikki_ 
    def validate(self, *scores):
        pass

class ValidationError(Exception): pass
class CodecError(Exception): pass

class _CategoryScore:

    # laita __slots__ ja __cats__

    def __init__(self, stream=None):
        if stream is None:
            for k,v in self.__cats__:
                setattr(self, k, v.default)
        else:
            self.decode(stream)

    def decode(self, src):
        for k,v in self.__cats__:
            setattr(self, k, v.decode(src))

    def encode(self, dest):
        for k,v in self.__cats__:
            v.encode(dest, getattr(self, k))

    def validate(self):
        for k,v in self.__cats__:
            v.validate(getattr(self, k))

# cats_sorted: list(nimi, cat)
def cat_score(name, cats_sorted, bases=[]):
    class Ret(_CategoryScore, *bases):
        __slots__ = [k for k,v in cats_sorted]
        __cats__ = cats_sorted

    Ret.__name__ = name
    return Ret

class CategoryRuleset(Ruleset):

    def __init__(self, score_type):
        self.score_type = score_type

    def create_score(self):
        return self.score_type()

    def decode(self, data):
        stream = io.BytesIO(data)
        ret = self.score_type(stream)

        tail = stream.read()
        if tail != b"":
            raise CodecError("stream not fully read, trailing bytes (%d): %s"\
                    % (len(tail),tail.hex()))

        return ret

    def encode(self, score):
        ret = bytearray()
        score.encode(ret)
        return ret

    def validate(self, score):
        score.validate()

class IntCategory:

    def __init__(self, default=0, length=2, signed=False):
        self.default = default
        self._length = length
        self._signed = signed

    def decode(self, src):
        return int.from_bytes(src.read(self._length), byteorder="big", signed=self._signed)

    def encode(self, dest, value):
        dest.extend(value.to_bytes(self._length, byteorder="big", signed=self._signed))

    def validate(self, value):
        if value<0 and not self._signed:
            raise ValidationError("Expected unsigned integer")
        if value.bit_length() > 8*self._length:
            raise ValidationError("Value %d overflows %d bytes" % (value, self._length))

class ListCategory:

    def __init__(self, cat):
        self._cat = cat

    @property
    def default(self):
        return []

    def decode(self, src):
        ret = self.default
        num = src.read(1)[0]

        for _ in range(num):
            ret.append(self._cat.decode(src))

        return ret

    def encode(self, dest, value):
        dest.append(len(value))
        for v in value:
            self._cat.encode(dest, v)

    def validate(self, value):
        if len(value) > 0xff:
            raise ValidationError("List length overflow: %d" % len(value))
        for v in value:
            self._cat.validate(v)

# (db.Score) -> (team, ruleset_score)
def decode_scores(ruleset, scores):
    return ((s.team, (ruleset.decode(s.data) if s.has_score else None)) for s in scores)
