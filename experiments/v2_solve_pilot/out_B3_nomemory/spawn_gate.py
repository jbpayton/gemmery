from collections import deque


class Limiter:
    def __init__(self, n, w):
        self.n = n
        self.w = w
        self.q = deque()

    def allow(self, t):
        q = self.q
        cutoff = t - self.w
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) < self.n:
            q.append(t)
            return True
        return False
