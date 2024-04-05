import re
from operator import eq, ne, gt, ge, lt, le
from lark import Lark, Transformer

# Define the grammar as a string
grammar = """
start: expr

?expr: ternary

?ternary: logic_expr "?" ternary ":" ternary
         | logic_expr

?logic_expr: logic_expr "&&" comp_expr -> and_expr
            | logic_expr "||" comp_expr -> or_expr
            | comp_expr

?comp_expr: sum_expr COMPARE_OP sum_expr -> comparison
           | sum_expr

?sum_expr: sum_expr "+" product -> add
          | sum_expr "-" product -> subtract
          | product

?product: product "*" atom -> multiply
         | product "/" atom -> divide
         | atom

?atom: INT -> int
      | "(" expr ")"

COMPARE_OP: "==" | "!=" | ">" | "<" | ">=" | "<="

%import common.INT
%import common.WS
%ignore WS
"""


# Define a transformer to process the parsed tree
class EvalTree(Transformer):
    def int(self, n):
        return int(n[0].value)

    def comparison(self, items):
        left, op, right = items
        return {
            "==": eq,
            "!=": ne,
            ">": gt,
            ">=": ge,
            "<": lt,
            "<=": le
        }[op](left, right)

    def and_expr(self, items):
        left, right = items
        return left and right

    def or_expr(self, items):
        left, right = items
        return left or right

    def ternary(self, items):
        condition, true_expr, false_expr = items
        return true_expr if condition else false_expr

    def add(self, items):
        left, right = items
        return left + right

    def subtract(self, items):
        left, right = items
        return left - right

    def multiply(self, items):
        left, right = items
        return left * right

    def divide(self, items):
        left, right = items
        return left / right


def contains_ternary_expression(expr):
    ternary_regex = r'(\(.*?\)|\d+)(\s*\?\s*(\(.*?\)|\d+)\s*:\s*(\(.*?\)|\d+))+'
    return bool(re.search(ternary_regex, str(expr)))


def eval_expression(expr: str | list) -> int | str | list[int | str]:
    if isinstance(expr, list):
        return [__try_eval_expression(e) for e in expr]
    return __try_eval_expression(expr)


def __try_eval_expression(expr: str):
    if not contains_ternary_expression(expr):
        return expr
    # Create the parser with the defined grammar
    parser = Lark(grammar, parser='lalr', transformer=EvalTree())
    try:
        result = parser.parse(expr)
        return result.children[-1]  # Return the last child, which is the final value
    except Exception as e:
        return expr