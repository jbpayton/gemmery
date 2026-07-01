import heapq


def assign(jobs, m):
    n = len(jobs)
    if n == 0:
        return []
    if m <= 1:
        return [0] * n

    # LPT heuristic: largest first into the currently least-loaded bin.
    order = sorted(range(n), key=lambda i: jobs[i], reverse=True)
    heap = [(0, b) for b in range(m)]
    heapq.heapify(heap)
    assignment = [0] * n
    loads = [0] * m
    for i in order:
        load, b = heapq.heappop(heap)
        assignment[i] = b
        loads[b] = load + jobs[i]
        heapq.heappush(heap, (loads[b], b))
    lpt_max = max(loads)

    s = [jobs[i] for i in order]
    total = sum(s)
    if all(isinstance(x, int) and not isinstance(x, bool) for x in s):
        lb_div = -(-total // m)
    else:
        lb_div = total / m
    lb = max(max(s), lb_div)

    # LPT already optimal, or problem too large for exact search -> return heuristic.
    if lpt_max <= lb or n > 20:
        return assignment

    # Exact branch-and-bound to minimise the maximum bin load, seeded by LPT.
    best_max = [lpt_max]
    best_assign = [None]
    counter = [0]
    LIMIT = 2000000
    loadsbb = [0] * m
    binof = [0] * n

    def dfs(k, curmax):
        if counter[0] > LIMIT or best_max[0] <= lb:
            return
        counter[0] += 1
        if k == n:
            if curmax < best_max[0]:
                best_max[0] = curmax
                best_assign[0] = binof[:]
            return
        item = s[k]
        seen = set()
        placed_empty = False
        for j in range(m):
            lj = loadsbb[j]
            if lj == 0:
                if placed_empty:
                    continue
                placed_empty = True
            else:
                if lj in seen:
                    continue
                seen.add(lj)
            newload = lj + item
            if newload >= best_max[0]:
                continue
            loadsbb[j] = newload
            binof[k] = j
            nm = curmax if curmax > newload else newload
            dfs(k + 1, nm)
            loadsbb[j] = lj

    dfs(0, 0)

    if best_assign[0] is not None and best_max[0] < lpt_max:
        res = [0] * n
        for k in range(n):
            res[order[k]] = best_assign[0][k]
        return res
    return assignment
