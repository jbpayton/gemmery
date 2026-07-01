def select(items, budget):
    n = len(items)
    if n == 0:
        return []
    costs = [it['cost'] for it in items]
    values = [it['value'] for it in items]

    def integral(x):
        if isinstance(x, bool):
            return True
        if isinstance(x, int):
            return True
        if isinstance(x, float):
            return x.is_integer()
        return False

    # Primary: exact 0/1 knapsack, DP indexed by cost (needs integral costs/budget).
    # Greedy value-per-cost is only approximate; this returns the optimal subset.
    if integral(budget) and all(integral(c) for c in costs) and budget >= 0:
        B = int(budget)
        icosts = [int(c) for c in costs]
        dp = [0] * (B + 1)
        keep = []
        for i in range(n):
            c = icosts[i]
            v = values[i]
            k = bytearray(B + 1)
            if 0 <= c <= B:
                for cap in range(B, c - 1, -1):
                    cand = dp[cap - c] + v
                    if cand > dp[cap]:
                        dp[cap] = cand
                        k[cap] = 1
            keep.append(k)
        res = []
        cap = B
        for i in range(n - 1, -1, -1):
            if keep[i][cap]:
                res.append(i)
                cap -= icosts[i]
        res.reverse()
        return res

    # Fallback: exact DP indexed by total value (handles non-integral costs;
    # requires integral, non-negative values, e.g. sign-up counts).
    if all(integral(v) and v >= 0 for v in values):
        ivalues = [int(v) for v in values]
        V = sum(ivalues)
        INF = float('inf')
        dp = [INF] * (V + 1)
        dp[0] = 0.0
        keep = []
        for i in range(n):
            c = costs[i]
            v = ivalues[i]
            k = bytearray(V + 1)
            for val in range(V, v - 1, -1):
                cand = dp[val - v] + c
                if cand < dp[val]:
                    dp[val] = cand
                    k[val] = 1
            keep.append(k)
        bestv = 0
        for val in range(V + 1):
            if dp[val] <= budget:
                bestv = val
        res = []
        val = bestv
        for i in range(n - 1, -1, -1):
            if keep[i][val]:
                res.append(i)
                val -= ivalues[i]
        res.reverse()
        return res

    # Last resort: greedy by value-per-cost.
    order = sorted(
        range(n),
        key=lambda i: (values[i] / costs[i]) if costs[i] else float('inf'),
        reverse=True,
    )
    res = []
    spent = 0
    for i in order:
        if costs[i] <= 0 and values[i] > 0:
            res.append(i)
            spent += costs[i]
        elif spent + costs[i] <= budget:
            res.append(i)
            spent += costs[i]
    res.sort()
    return res
