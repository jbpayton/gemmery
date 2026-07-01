def first_repeat_index(data):
    seen = set()
    unhashable_seen = []
    for index, value in enumerate(data):
        try:
            if value in seen:
                return index
            seen.add(value)
        except TypeError:
            if value in unhashable_seen:
                return index
            unhashable_seen.append(value)
    return -1
