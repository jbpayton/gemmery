from collections import deque


class Limiter:
    def __init__(self, n, w):
        self.n = n
        self.w = w
        self.q = deque()

    def allow(self, t):
        w = self.w
        q = self.q
        while q and q[0] <= t - w:
            q.popleft()
        if len(q) < self.n:
            q.append(t)
            return True
        return False
