class DuplicateKeyError(LookupError):
    pass

class udict(dict):

    def __setitem__(self, key, value):
        if key in self:
            raise DuplicateKeyError(key)
        super().__setitem__(key, value)

class lazy:

    def __init__(self, f):
        self.f = f

    def __get__(self, obj, cls):
        ret = self.f(obj)
        setattr(obj, self.f.__name__, ret)
        return ret

def enumerate_rank(it, start=1, key=lambda x: x):
    idx, cnt = start, start

    try:
        it = iter(it)
        x = next(it)
    except StopIteration:
        # python 3.7 muutos:
        # https://www.python.org/dev/peps/pep-0479/
        return

    k = key(x)
    yield idx, x

    for i in it:
        cnt += 1
        kk = key(i)
        if kk != k:
            k = kk
            idx = cnt
        yield idx, i

def noneflt(func):
    return lambda it, **kwargs: func(filter(lambda x: x is not None, it), **kwargs)
