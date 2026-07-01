class RangeQuerier:
    def __init__(self, data):
        prefix = [0] * (len(data) + 1)
        acc = 0
        for i, x in enumerate(data):
            acc += x
            prefix[i + 1] = acc
        self.prefix = prefix
        self.n = len(data)

    def query(self, lo, hi):
        n = self.n
        if lo < 0:
            lo = 0
        if hi > n:
            hi = n
        if hi <= lo:
            return 0
        return self.prefix[hi] - self.prefix[lo]
