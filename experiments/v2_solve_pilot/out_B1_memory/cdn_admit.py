def select(items, budget):
    n = len(items)
    if n == 0 or budget is None or budget < 0:
        return []

    costs = [it["cost"] for it in items]
    values = [it["value"] for it in items]

    # If everything fits, keep all positive-or-zero contributors (and the rest
    # cost nothing extra to leave out, but keeping all is feasible and optimal
    # only when no value is negative; otherwise fall through to DP).
    if all(v >= 0 for v in values) and sum(costs) <= budget:
        return list(range(n))

    def is_int(x):
        return isinstance(x, int) or (isinstance(x, float) and x.is_integer())

    # Optimal 0/1 knapsack via DP when costs/budget are integral and the table
    # stays a reasonable size.
    if is_int(budget) and all(is_int(c) for c in costs):
        B = int(budget)
        if B >= 0 and n * (B + 1) <= 60_000_000:
            dp = [0] * (B + 1)
            ninf = float("-inf")
            keep = []
            for i in range(n):
                c = int(costs[i])
                v = values[i]
                row = bytearray(B + 1)
                if 0 <= c <= B:
                    for b in range(B, c - 1, -1):
                        cand = dp[b - c] + v
                        if cand > dp[b]:
                            dp[b] = cand
                            row[b] = 1
                keep.append(row)
            chosen = []
            b = B
            for i in range(n - 1, -1, -1):
                if keep[i][b]:
                    chosen.append(i)
                    b -= int(costs[i])
            chosen.reverse()
            return chosen

    # Fallback: greedy by value-per-unit-cost for non-integral / huge inputs.
    def ratio(i):
        c = costs[i]
        if c <= 0:
            return float("inf") if values[i] >= 0 else float("-inf")
        return values[i] / c

    order = sorted(range(n), key=ratio, reverse=True)
    total = 0
    chosen = []
    for i in order:
        if values[i] <= 0 and costs[i] >= 0:
            continue
        if total + costs[i] <= budget:
            chosen.append(i)
            total += costs[i]
    chosen.sort()
    return chosen
