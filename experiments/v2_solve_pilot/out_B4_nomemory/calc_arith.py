def evaluate(s):
    tokens = _tokenize(s)
    parser = _Parser(tokens)
    value = parser.parse_expr()
    parser.expect_end()
    return value


def _tokenize(s):
    tokens = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or c == '.':
            j = i
            while j < n and (s[j].isdigit() or s[j] == '.'):
                j += 1
            num_str = s[i:j]
            if num_str.count('.') > 1:
                raise ValueError("invalid number: " + num_str)
            if '.' in num_str:
                tokens.append(('num', float(num_str)))
            else:
                tokens.append(('num', int(num_str)))
            i = j
            continue
        if c == '*' and i + 1 < n and s[i + 1] == '*':
            tokens.append(('op', '**'))
            i += 2
            continue
        if c in '+-*/()':
            tokens.append(('op', c))
            i += 1
            continue
        raise ValueError("unexpected character: " + c)
    return tokens


class _Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return (None, None)

    def _advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect_end(self):
        if self.pos != len(self.tokens):
            raise ValueError("unexpected trailing input")

    def parse_expr(self):
        value = self.parse_term()
        while True:
            kind, val = self._peek()
            if kind == 'op' and val in ('+', '-'):
                self._advance()
                rhs = self.parse_term()
                if val == '+':
                    value = value + rhs
                else:
                    value = value - rhs
            else:
                break
        return value

    def parse_term(self):
        value = self.parse_factor()
        while True:
            kind, val = self._peek()
            if kind == 'op' and val in ('*', '/'):
                self._advance()
                rhs = self.parse_factor()
                if val == '*':
                    value = value * rhs
                else:
                    value = value / rhs
            else:
                break
        return value

    def parse_factor(self):
        kind, val = self._peek()
        if kind == 'op' and val in ('+', '-'):
            self._advance()
            operand = self.parse_factor()
            return operand if val == '+' else -operand
        return self.parse_power()

    def parse_power(self):
        base = self.parse_atom()
        kind, val = self._peek()
        if kind == 'op' and val == '**':
            self._advance()
            exponent = self.parse_factor()
            return base ** exponent
        return base

    def parse_atom(self):
        kind, val = self._peek()
        if kind == 'num':
            self._advance()
            return val
        if kind == 'op' and val == '(':
            self._advance()
            value = self.parse_expr()
            close_kind, close_val = self._peek()
            if close_kind != 'op' or close_val != ')':
                raise ValueError("missing closing parenthesis")
            self._advance()
            return value
        raise ValueError("unexpected token")
