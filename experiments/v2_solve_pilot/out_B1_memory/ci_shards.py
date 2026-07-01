import heapq


def assign(jobs, m):
    n = len(jobs)
    result = [0] * n
    if n == 0 or m <= 0:
        return result

    # Longest-processing-time-first: place each job on the currently
    # least-loaded bin to keep the maximum load as small as possible.
    heap = [(0, b) for b in range(m)]
    heapq.heapify(heap)

    order = sorted(range(n), key=lambda i: jobs[i], reverse=True)
    for i in order:
        load, b = heapq.heappop(heap)
        result[i] = b
        heapq.heappush(heap, (load + jobs[i], b))
    return result
