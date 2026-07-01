def select(items, budget):
    n = len(items)
    try:
        B = int(budget)
    except (TypeError, ValueError):
        return []
    if B < 0 or n == 0:
        return []
    dp = [0] * (B + 1)
    keep = [[False] * (B + 1) for _ in range(n)]
    for i in range(n):
        v = items[i]["value"]
        c = items[i]["cost"]
        if c < 0 or c > B:
            continue
        ci = int(c)
        for cap in range(B, ci - 1, -1):
            cand = dp[cap - ci] + v
            if cand > dp[cap]:
                dp[cap] = cand
                keep[i][cap] = True
    res = []
    cap = B
    for i in range(n - 1, -1, -1):
        if keep[i][cap]:
            res.append(i)
            cap -= int(items[i]["cost"])
    res.reverse()
    return res
