import heapq
import math
import sys


def assign(jobs, m):
    n = len(jobs)
    if n == 0:
        return []
    if m <= 1:
        return [0] * n
    if m >= n:
        return list(range(n))

    order = sorted(range(n), key=lambda i: jobs[i], reverse=True)
    w = [jobs[i] for i in order]

    # Longest Processing Time greedy -> good initial solution / upper bound.
    heap = [(0, b) for b in range(m)]
    heapq.heapify(heap)
    lpt = [0] * n
    for k in range(n):
        load, b = heapq.heappop(heap)
        lpt[k] = b
        heapq.heappush(heap, (load + w[k], b))

    loads_tmp = [0] * m
    for k in range(n):
        loads_tmp[lpt[k]] += w[k]
    best_mk = max(loads_tmp)

    total = sum(w)
    lb = max(w[0], math.ceil(total / m)) if total > 0 else w[0]

    state = {"best": best_mk, "assign": lpt[:]}

    if best_mk > lb:
        loads = [0] * m
        cur = [0] * n
        nodes = [0]
        NODE_LIMIT = 400000
        sys.setrecursionlimit(max(1000, n + 100))

        def dfs(i):
            if nodes[0] >= NODE_LIMIT or state["best"] <= lb:
                return
            nodes[0] += 1
            if i == n:
                mk = max(loads)
                if mk < state["best"]:
                    state["best"] = mk
                    state["assign"] = cur[:]
                return
            wi = w[i]
            seen = set()
            for b in range(m):
                lv = loads[b]
                if lv in seen:
                    continue
                seen.add(lv)
                if lv + wi >= state["best"]:
                    continue
                loads[b] = lv + wi
                cur[i] = b
                dfs(i + 1)
                loads[b] = lv
                if nodes[0] >= NODE_LIMIT or state["best"] <= lb:
                    break

        dfs(0)

    result = [0] * n
    chosen = state["assign"]
    for k in range(n):
        result[order[k]] = chosen[k]
    return result
