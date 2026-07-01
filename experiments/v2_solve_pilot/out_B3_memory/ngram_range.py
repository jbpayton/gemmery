class RangeQuerier:
    def __init__(self, data):
        prefix = [0] * (len(data) + 1)
        s = 0
        for i, x in enumerate(data):
            s += x
            prefix[i + 1] = s
        self._prefix = prefix
        self._n = len(data)

    def query(self, lo, hi):
        n = self._n
        lo, hi, _ = slice(lo, hi).indices(n)
        if lo >= hi:
            return 0
        return self._prefix[hi] - self._prefix[lo]
