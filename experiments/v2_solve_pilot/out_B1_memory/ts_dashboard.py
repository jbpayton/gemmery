from itertools import accumulate


class RangeQuerier:
    def __init__(self, data):
        # prefix[k] = sum(data[:k]); one linear preprocessing pass.
        self._prefix = [0] + list(accumulate(data))

    def query(self, lo, hi):
        n = len(self._prefix) - 1
        if lo < 0:
            lo = 0
        if hi > n:
            hi = n
        if lo >= hi:
            return 0
        return self._prefix[hi] - self._prefix[lo]
