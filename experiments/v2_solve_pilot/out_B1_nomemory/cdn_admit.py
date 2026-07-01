def select(items, budget):
    n = len(items)
    budget = int(budget)
    if n == 0 or budget <= 0:
        return []
    costs = [int(it['cost']) for it in items]
    values = [it['value'] for it in items]
    dp = [0] * (budget + 1)
    keep = [bytearray(budget + 1) for _ in range(n)]
    for i in range(n):
        cost = costs[i]
        if cost < 0 or cost > budget:
            continue
        val = values[i]
        ki = keep[i]
        for c in range(budget, cost - 1, -1):
            cand = dp[c - cost] + val
            if cand > dp[c]:
                dp[c] = cand
                ki[c] = 1
    chosen = []
    c = budget
    for i in range(n - 1, -1, -1):
        if keep[i][c]:
            chosen.append(i)
            c -= costs[i]
    chosen.reverse()
    return chosen
