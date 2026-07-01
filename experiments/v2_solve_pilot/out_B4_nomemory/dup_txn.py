def first_repeat_index(data):
    seen = set()
    try:
        for i, value in enumerate(data):
            if value in seen:
                return i
            seen.add(value)
        return -1
    except TypeError:
        seen_list = []
        for i, value in enumerate(data):
            if value in seen_list:
                return i
            seen_list.append(value)
        return -1
