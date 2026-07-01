import bisect


def _is_int(x):
    if isinstance(x, bool):
        return True
    if isinstance(x, int):
        return True
    if isinstance(x, float):
        return x.is_integer()
    return False


def _knapsack_capacity(values, costs, B):
    n = len(values)
    dp = [0.0] * (B + 1)
    take = [bytearray(B + 1) for _ in range(n)]
    for i in range(n):
        ci = costs[i]
        vi = values[i]
        if ci < 0 or ci > B or vi <= 0:
            continue
        ti = take[i]
        for c in range(B, ci - 1, -1):
            cand = dp[c - ci] + vi
            if cand > dp[c]:
                dp[c] = cand
                ti[c] = 1
    chosen = []
    c = B
    for i in range(n - 1, -1, -1):
        if take[i][c]:
            chosen.append(i)
            c -= costs[i]
    chosen.sort()
    return chosen


def _knapsack_value(values, costs, budget):
    n = len(values)
    pos = [i for i in range(n) if values[i] > 0 and costs[i] <= budget and costs[i] >= 0]
    Vtot = 0
    for i in pos:
        Vtot += int(round(values[i]))
    if Vtot <= 0:
        return []
    if Vtot > 3_000_000 or len(pos) * (Vtot + 1) > 60_000_000:
        return None
    INF = float('inf')
    dp = [INF] * (Vtot + 1)
    dp[0] = 0.0
    take = [bytearray(Vtot + 1) for _ in range(len(pos))]
    for k, i in enumerate(pos):
        vi = int(round(values[i]))
        cst = costs[i]
        tk = take[k]
        for v in range(Vtot, vi - 1, -1):
            nc = dp[v - vi] + cst
            if nc < dp[v]:
                dp[v] = nc
                tk[v] = 1
    bestv = 0
    for v in range(Vtot, -1, -1):
        if dp[v] <= budget + 1e-9:
            bestv = v
            break
    chosen = []
    v = bestv
    for k in range(len(pos) - 1, -1, -1):
        if take[k][v]:
            i = pos[k]
            chosen.append(i)
            v -= int(round(values[i]))
    chosen.sort()
    return chosen


def _knapsack_mim(values, costs, budget):
    n = len(values)
    half = n // 2
    left = list(range(half))
    right = list(range(half, n))

    def enumerate_subsets(idxs):
        out = []
        L = len(idxs)
        for mask in range(1 << L):
            c = 0.0
            v = 0.0
            chosen = []
            for j in range(L):
                if mask >> j & 1:
                    i = idxs[j]
                    c += costs[i]
                    v += values[i]
                    chosen.append(i)
            out.append((c, v, chosen))
        return out

    sa = enumerate_subsets(left)
    sb = enumerate_subsets(right)
    sb.sort(key=lambda x: x[0])

    pre_cost = []
    pre_val = []
    pre_chosen = []
    bv = float('-inf')
    bchosen = []
    for c, v, ch in sb:
        if v > bv:
            bv = v
            bchosen = ch
        pre_cost.append(c)
        pre_val.append(bv)
        pre_chosen.append(bchosen)

    best_total = float('-inf')
    best_set = []
    for c, v, ch in sa:
        if c > budget + 1e-9:
            continue
        rem = budget - c
        j = bisect.bisect_right(pre_cost, rem + 1e-9) - 1
        if j >= 0:
            total = v + pre_val[j]
            if total > best_total:
                best_total = total
                best_set = ch + pre_chosen[j]
    best_set = sorted(best_set)
    return best_set


def _knapsack_greedy(values, costs, budget):
    def ratio(i):
        c = costs[i]
        if c <= 0:
            return float('inf')
        return values[i] / c

    order = sorted(range(len(values)), key=ratio, reverse=True)
    chosen = []
    total = 0.0
    for i in order:
        if values[i] <= 0:
            continue
        if total + costs[i] <= budget:
            chosen.append(i)
            total += costs[i]
    chosen.sort()
    return chosen


def select(items, budget):
    n = len(items)
    if n == 0 or budget is None or budget < 0:
        return []
    values = [it['value'] for it in items]
    costs = [it['cost'] for it in items]

    int_costs = _is_int(budget) and all(_is_int(c) and c >= 0 for c in costs)
    if int_costs:
        B = int(round(budget))
        ci = [int(round(c)) for c in costs]
        if n * (B + 1) <= 30_000_000:
            return _knapsack_capacity(values, ci, B)

    if all(_is_int(v) for v in values):
        res = _knapsack_value(values, costs, budget)
        if res is not None:
            return res

    if n <= 30:
        return _knapsack_mim(values, costs, budget)

    return _knapsack_greedy(values, costs, budget)
