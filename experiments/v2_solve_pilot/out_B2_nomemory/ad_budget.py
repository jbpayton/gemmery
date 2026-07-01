import bisect


def _is_int(x):
    try:
        return float(x).is_integer()
    except (TypeError, ValueError, OverflowError):
        return False


def _knap_by_capacity(keep, cap):
    k = len(keep)
    icost = [int(round(c)) for (_, c, _) in keep]
    val = [v for (_, _, v) in keep]
    dp = [0.0] * (cap + 1)
    take = [bytearray(cap + 1) for _ in range(k)]
    for i in range(k):
        c = icost[i]
        v = val[i]
        ti = take[i]
        if c <= cap:
            for j in range(cap, c - 1, -1):
                cand = dp[j - c] + v
                if cand > dp[j]:
                    dp[j] = cand
                    ti[j] = 1
    chosen = []
    j = cap
    for i in range(k - 1, -1, -1):
        if take[i][j]:
            chosen.append(keep[i][0])
            j -= icost[i]
    chosen.sort()
    return chosen


def _knap_by_value(keep, budget, V):
    k = len(keep)
    ival = [int(round(v)) for (_, _, v) in keep]
    cost = [c for (_, c, _) in keep]
    INF = float('inf')
    mincost = [INF] * (V + 1)
    mincost[0] = 0.0
    take = [bytearray(V + 1) for _ in range(k)]
    for i in range(k):
        vv = ival[i]
        c = cost[i]
        ti = take[i]
        if vv <= 0:
            continue
        for v in range(V, vv - 1, -1):
            pc = mincost[v - vv]
            if pc + c < mincost[v]:
                mincost[v] = pc + c
                ti[v] = 1
    best_v = 0
    for v in range(V, -1, -1):
        if mincost[v] <= budget:
            best_v = v
            break
    chosen = []
    cur = best_v
    for i in range(k - 1, -1, -1):
        if cur > 0 and take[i][cur]:
            chosen.append(keep[i][0])
            cur -= ival[i]
    chosen.sort()
    return chosen


def _meet_in_middle(keep, budget):
    k = len(keep)
    half = k // 2
    A = keep[:half]
    B = keep[half:]

    def subsets(group):
        res = [(0.0, 0.0, 0)]
        for idx in range(len(group)):
            c = group[idx][1]
            v = group[idx][2]
            bit = 1 << idx
            add = []
            for (cc, vv, mask) in res:
                nc = cc + c
                if nc <= budget:
                    add.append((nc, vv + v, mask | bit))
            res.extend(add)
        return res

    SB = subsets(B)
    SB.sort()
    bc = []
    bestv = []
    bmask = []
    cur_best = -1.0
    cur_mask = 0
    for (cc, vv, mask) in SB:
        if vv > cur_best:
            cur_best = vv
            cur_mask = mask
        bc.append(cc)
        bestv.append(cur_best)
        bmask.append(cur_mask)

    SA = subsets(A)
    best_total = -1.0
    best_a_mask = 0
    best_b_mask = 0
    for (cc, vv, mask) in SA:
        rem = budget - cc
        if rem < 0:
            continue
        pos = bisect.bisect_right(bc, rem) - 1
        if pos >= 0:
            tot = vv + bestv[pos]
            if tot > best_total:
                best_total = tot
                best_a_mask = mask
                best_b_mask = bmask[pos]

    chosen = []
    for idx in range(len(A)):
        if best_a_mask & (1 << idx):
            chosen.append(A[idx][0])
    for idx in range(len(B)):
        if best_b_mask & (1 << idx):
            chosen.append(B[idx][0])
    chosen.sort()
    return chosen


def _greedy(keep, budget):
    order = sorted(
        keep,
        key=lambda t: (t[2] / t[1]) if t[1] > 0 else float('inf'),
        reverse=True,
    )
    chosen = []
    total = 0.0
    for (i, c, v) in order:
        if total + c <= budget:
            chosen.append(i)
            total += c
    chosen.sort()
    return chosen


def select(items, budget):
    n = len(items)
    if n == 0:
        return []
    try:
        if budget < 0:
            return []
    except TypeError:
        return []

    keep = []
    for i in range(n):
        it = items[i]
        c = it['cost']
        v = it['value']
        if v <= 0:
            continue
        if c < 0:
            c = 0
        if c > budget:
            continue
        keep.append((i, c, v))

    if not keep:
        return []

    values_int = all(_is_int(v) for (_, _, v) in keep)
    costs_int = all(_is_int(c) for (_, c, _) in keep) and _is_int(budget)

    LIMIT = 150000000

    val_dim = sum(int(round(v)) for (_, _, v) in keep) if values_int else None
    cap_dim = int(round(budget)) if costs_int else None

    val_cost = None
    if val_dim is not None and len(keep) * (val_dim + 1) <= LIMIT:
        val_cost = len(keep) * (val_dim + 1)
    cap_cost = None
    if cap_dim is not None and len(keep) * (cap_dim + 1) <= LIMIT:
        cap_cost = len(keep) * (cap_dim + 1)

    if val_cost is not None and (cap_cost is None or val_cost <= cap_cost):
        return _knap_by_value(keep, budget, val_dim)
    if cap_cost is not None:
        return _knap_by_capacity(keep, cap_dim)

    if len(keep) <= 30:
        return _meet_in_middle(keep, budget)
    return _greedy(keep, budget)
