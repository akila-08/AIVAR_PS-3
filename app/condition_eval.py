"""
Safe evaluator for policy rule conditions, e.g. "record_count > 100" or
"'confidential' in path". Built on Python's `ast` module with a strict
whitelist of node types — NEVER use eval()/exec() on rule text, since
policy rules may originate from a config file or admin API and must not
become a code-execution vector.
"""
import ast
import operator
from typing import Any


class ConditionError(Exception):
    """Raised when a rule condition is malformed or uses a disallowed construct."""


_COMPARE_OPS = {
    ast.Gt: operator.gt,
    ast.Lt: operator.lt,
    ast.GtE: operator.ge,
    ast.LtE: operator.le,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


def safe_eval_condition(expr: str, context: dict[str, Any]) -> bool:
    """Evaluate a boolean condition string against a context dict of action params.

    Supported grammar: comparisons (>, <, >=, <=, ==, !=, in, not in),
    boolean combinators (and, or, not), names resolved from `context`,
    and literal constants (numbers, strings). Nothing else is permitted —
    no function calls, no attribute access, no subscripting.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise ConditionError(f"Invalid condition syntax: {expr!r}") from exc
    return bool(_eval_node(tree.body, context))


def _eval_node(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, context) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ConditionError("Unsupported boolean operator")

    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, context)

    if isinstance(node, ast.Compare):
        left = _eval_operand(node.left, context)
        result = True
        for op, comparator in zip(node.ops, node.comparators):
            fn = _COMPARE_OPS.get(type(op))
            if fn is None:
                raise ConditionError(f"Unsupported operator: {type(op).__name__}")
            right = _eval_operand(comparator, context)
            result = result and fn(left, right)
            left = right
        return result

    raise ConditionError(f"Unsupported expression node: {type(node).__name__}")


def _eval_operand(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.Name):
        if node.id not in context:
            raise ConditionError(f"Unknown field referenced in condition: {node.id!r}")
        return context[node.id]
    if isinstance(node, ast.Constant):
        return node.value
    raise ConditionError(f"Unsupported operand node: {type(node).__name__}")
