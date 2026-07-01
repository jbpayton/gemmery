class RangeQuerier:
    def __init__(self, data):
        n = len(data)
        prefix = [0] * (n + 1)
        acc = 0
        for i in range(n):
            acc += data[i]
            prefix[i + 1] = acc
        self.prefix = prefix
        self.n = n

    def query(self, lo, hi):
        start, stop, _ = slice(lo, hi).indices(self.n)
        if stop < start:
            stop = start
        return self.prefix[stop] - self.prefix[start]
