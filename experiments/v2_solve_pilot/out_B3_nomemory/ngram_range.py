class RangeQuerier:
    def __init__(self, data):
        n = len(data)
        prefix = [0] * (n + 1)
        s = 0
        for i in range(n):
            s += data[i]
            prefix[i + 1] = s
        self.prefix = prefix
        self.n = n

    def query(self, lo, hi):
        n = self.n
        if lo < 0:
            lo += n
            if lo < 0:
                lo = 0
        elif lo > n:
            lo = n
        if hi < 0:
            hi += n
            if hi < 0:
                hi = 0
        elif hi > n:
            hi = n
        if lo >= hi:
            return 0
        return self.prefix[hi] - self.prefix[lo]
