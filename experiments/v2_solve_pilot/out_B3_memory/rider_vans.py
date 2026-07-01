import heapq
import sys


def _map_back(assign_sorted, order, n):
    res = [0] * n
    for i in range(n):
        res[order[i]] = assign_sorted[i]
    return res


def assign(jobs, m):
    n = len(jobs)
    if n == 0:
        return []
    if m is None or m < 1:
        m = 1
    if m >= n:
        return list(range(n))

    order = sorted(range(n), key=lambda i: jobs[i], reverse=True)
    sjobs = [jobs[i] for i in order]
    total = 0
    for x in sjobs:
        total += x

    # Longest-processing-time first onto least-loaded bin (initial upper bound).
    heap = [(0, b) for b in range(m)]
    heapq.heapify(heap)
    lpt = [0] * n
    loads = [0] * m
    for i, load in enumerate(sjobs):
        cur, b = heapq.heappop(heap)
        lpt[i] = b
        nl = cur + load
        loads[b] = nl
        heapq.heappush(heap, (nl, b))
    lpt_makespan = max(loads)

    best = {'val': lpt_makespan, 'assign': list(lpt)}
    lower = max(sjobs[0], total / m)

    if lpt_makespan <= lower + 1e-12:
        return _map_back(best['assign'], order, n)

    # For larger inputs keep the LPT result; exact search only for modest n.
    if n > 26:
        return _map_back(best['assign'], order, n)

    bins = [0] * m
    cur_assign = [0] * n
    nodes = [0]
    stop = [False]
    LIMIT = 4_000_000

    try:
        sys.setrecursionlimit(max(1000, n + 100))
    except Exception:
        pass

    def dfs(i, cur_max):
        if stop[0]:
            return
        if cur_max >= best['val']:
            return
        if i == n:
            best['val'] = cur_max
            best['assign'] = list(cur_assign)
            return
        nodes[0] += 1
        if nodes[0] > LIMIT:
            stop[0] = True
            return
        job = sjobs[i]
        seen = set()
        for b in range(m):
            load = bins[b]
            if load in seen:
                continue
            seen.add(load)
            nl = load + job
            if nl >= best['val']:
                continue
            bins[b] = nl
            cur_assign[i] = b
            nm = cur_max if cur_max > nl else nl
            dfs(i + 1, nm)
            bins[b] = load
            if stop[0] or best['val'] <= lower + 1e-12:
                return

    dfs(0, 0)
    return _map_back(best['assign'], order, n)
