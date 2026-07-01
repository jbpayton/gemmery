def evaluate(s):
    tokens = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in '()':
            tokens.append(c)
            i += 1
            continue
        if c.isalpha():
            j = i
            while j < n and s[j].isalpha():
                j += 1
            tokens.append(s[i:j])
            i = j
            continue
        raise ValueError("Unexpected character: " + c)

    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def advance():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def parse_or():
        value = parse_and()
        while peek() == 'or':
            advance()
            right = parse_and()
            value = value or right
        return value

    def parse_and():
        value = parse_not()
        while peek() == 'and':
            advance()
            right = parse_not()
            value = value and right
        return value

    def parse_not():
        if peek() == 'not':
            advance()
            return not parse_not()
        return parse_atom()

    def parse_atom():
        tok = peek()
        if tok == '(':
            advance()
            value = parse_or()
            if peek() != ')':
                raise ValueError("Expected ')'")
            advance()
            return value
        if tok == 'T':
            advance()
            return True
        if tok == 'F':
            advance()
            return False
        raise ValueError("Unexpected token: " + str(tok))

    result = parse_or()
    if pos != len(tokens):
        raise ValueError("Unexpected trailing tokens")
    return result
