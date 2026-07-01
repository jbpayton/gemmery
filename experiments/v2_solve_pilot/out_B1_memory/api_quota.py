from collections import deque


class Limiter:
    def __init__(self, n, w):
        self.n = n
        self.w = w
        self._admitted = deque()

    def allow(self, t):
        w = self.w
        q = self._admitted
        # Drop admits that fall outside the trailing window of length w,
        # i.e. keep only those with timestamp >= t - w (window [t-w, t]).
        threshold = t - w
        while q and q[0] < threshold:
            q.popleft()
        if len(q) < self.n:
            q.append(t)
            return True
        return False
