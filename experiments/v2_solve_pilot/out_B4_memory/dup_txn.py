def first_repeat_index(data):
    seen = set()
    for i, value in enumerate(data):
        if value in seen:
            return i
        seen.add(value)
    return -1
