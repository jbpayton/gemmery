from collections import deque


class Limiter:
    def __init__(self, n, w):
        self.n = n
        self.w = w
        self._admitted = deque()

    def allow(self, t):
        w = self.w
        q = self._admitted
        cutoff = t - w
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) < self.n:
            q.append(t)
            return True
        return False
