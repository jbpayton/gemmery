def evaluate(s):
    tokens = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in '+-*/()':
            if c == '*' and i + 1 < n and s[i + 1] == '*':
                tokens.append('**')
                i += 2
            else:
                tokens.append(c)
                i += 1
            continue
        if c.isdigit() or c == '.':
            j = i
            while j < n and (s[j].isdigit() or s[j] == '.'):
                j += 1
            num = s[i:j]
            tokens.append(float(num) if '.' in num else int(num))
            i = j
            continue
        raise ValueError("invalid character: " + c)

    pos = 0

    def peek():
        return tokens[pos] if pos < len(tokens) else None

    def advance():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        return tok

    def parse_expr():
        value = parse_term()
        while peek() in ('+', '-'):
            op = advance()
            rhs = parse_term()
            value = value + rhs if op == '+' else value - rhs
        return value

    def parse_term():
        value = parse_factor()
        while peek() in ('*', '/'):
            op = advance()
            rhs = parse_factor()
            value = value * rhs if op == '*' else value / rhs
        return value

    def parse_factor():
        if peek() == '+':
            advance()
            return parse_factor()
        if peek() == '-':
            advance()
            return -parse_factor()
        return parse_power()

    def parse_power():
        value = parse_atom()
        if peek() == '**':
            advance()
            exponent = parse_factor()
            return value ** exponent
        return value

    def parse_atom():
        tok = peek()
        if tok == '(':
            advance()
            value = parse_expr()
            if peek() != ')':
                raise ValueError("missing closing parenthesis")
            advance()
            return value
        if isinstance(tok, (int, float)):
            return advance()
        raise ValueError("unexpected token: " + str(tok))

    result = parse_expr()
    if pos != len(tokens):
        raise ValueError("unexpected trailing tokens")
    return result
