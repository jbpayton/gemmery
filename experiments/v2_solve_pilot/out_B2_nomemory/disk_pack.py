import heapq


def _lpt(jobs, m):
    n = len(jobs)
    order = sorted(range(n), key=lambda i: jobs[i], reverse=True)
    heap = [(0.0, b) for b in range(m)]
    heapq.heapify(heap)
    res = [0] * n
    for i in order:
        load, b = heapq.heappop(heap)
        res[i] = b
        heapq.heappush(heap, (load + jobs[i], b))
    return res


def _loads(jobs, m, res):
    L = [0.0] * m
    for i, b in enumerate(res):
        L[b] += jobs[i]
    return L


def _makespan(jobs, m, res):
    return max(_loads(jobs, m, res))


def _local_search(jobs, m, res):
    res = list(res)
    for _ in range(100000):
        L = _loads(jobs, m, res)
        make = max(L)
        members = [[] for _ in range(m)]
        for i, b in enumerate(res):
            members[b].append(i)
        applied = False
        for mb in range(m):
            if make - L[mb] > 1e-12:
                continue
            for j in members[mb]:
                for b in range(m):
                    if b == mb:
                        continue
                    if L[b] + jobs[j] < make - 1e-12:
                        old = res[j]
                        res[j] = b
                        if _makespan(jobs, m, res) < make - 1e-12:
                            applied = True
                            break
                        res[j] = old
                if applied:
                    break
            if applied:
                break
            for j in members[mb]:
                for b in range(m):
                    if b == mb:
                        continue
                    for k in members[b]:
                        if jobs[j] <= jobs[k]:
                            continue
                        res[j], res[k] = b, mb
                        if _makespan(jobs, m, res) < make - 1e-12:
                            applied = True
                            break
                        res[j], res[k] = mb, b
                    if applied:
                        break
                if applied:
                    break
            if applied:
                break
        if not applied:
            break
    return res


def _exact(jobs, m, init_assign, init_make):
    n = len(jobs)
    order = sorted(range(n), key=lambda i: jobs[i], reverse=True)
    sj = [jobs[i] for i in order]
    best = [init_make]
    best_assign = [list(init_assign)]
    cur = [0.0] * m
    place = [0] * n
    nodes = [0]
    LIMIT = 3000000

    def dfs(idx):
        if nodes[0] > LIMIT:
            return
        nodes[0] += 1
        if idx == n:
            mk = max(cur)
            if mk < best[0] - 1e-12:
                best[0] = mk
                ba = [0] * n
                for p in range(n):
                    ba[order[p]] = place[p]
                best_assign[0] = ba
            return
        seen = set()
        s = sj[idx]
        for b in range(m):
            load = cur[b]
            key = round(load, 9)
            if key in seen:
                continue
            seen.add(key)
            if load + s >= best[0] - 1e-12:
                continue
            cur[b] += s
            place[idx] = b
            dfs(idx + 1)
            cur[b] -= s

    dfs(0)
    return best_assign[0], best[0]


def assign(jobs, m):
    n = len(jobs)
    if n == 0:
        return []
    if m is None or m <= 0:
        m = 1
    if m == 1:
        return [0] * n

    res = _lpt(jobs, m)
    res = _local_search(jobs, m, res)

    total = 0.0
    mx = None
    for x in jobs:
        total += x
        if mx is None or x > mx:
            mx = x
    lb = total / m
    if mx > lb:
        lb = mx
    make = _makespan(jobs, m, res)

    if n <= 18 and make > lb + 1e-9:
        res2, mk2 = _exact(jobs, m, res, make)
        if mk2 + 1e-12 < make:
            res = res2
    return res
