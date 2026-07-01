import heapq


def assign(jobs, m):
    n = len(jobs)
    result = [0] * n
    if n == 0:
        return result
    if m <= 0:
        return result
    order = sorted(range(n), key=lambda i: jobs[i], reverse=True)
    heap = [(0, b) for b in range(m)]
    heapq.heapify(heap)
    for i in order:
        load, b = heapq.heappop(heap)
        result[i] = b
        heapq.heappush(heap, (load + jobs[i], b))
    return result
