"""Intermediate Representation (IR) for AST canonicalization.

This module defines lightweight IR node classes that represent semantic code patterns.
These IR trees can be serialized to canonical strings for hashing,
or used directly for tree comparison.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class IRNode:
    """Base class for IR nodes."""

    node_type: str
    children: tuple[IRNode, ...] = field(default_factory=tuple)
    value: str | None = None

    def serialize(self) -> str:
        """Serialize IR node to canonical string."""
        if not self.children:
            if self.value is not None:
                return f"[{self.node_type}:{self.value}]"
            return f"[{self.node_type}]"
        
        child_strs = [c.serialize() for c in self.children]
        return f"{self.node_type}({', '.join(child_strs)})"


class AssignIR(IRNode):
    """Assignment: x = expr or x += expr"""

    __slots__ = ()

    def __init__(self, target: IRNode, op: str, value: IRNode):
        self.node_type = "ASSIGN"
        self.children = (target, value)
        self.value = op


class LoopIR(IRNode):
    """Loop: for/while/do statements"""

    __slots__ = ()

    def __init__(self, iterator: IRNode | None, body: IRNode, iter_var: IRNode | None = None):
        self.node_type = "LOOP"
        if iter_var and iterator:
            self.children = (iter_var, iterator, body)
        elif iterator:
            self.children = (iterator, body)
        elif body:
            self.children = (body,)
        else:
            self.children = ()


class MapReduceIR(IRNode):
    """Map/Reduce: list comprehensions, map(), filter(), reduce(), etc.
    
    This handles:
    - [x for x in y]
    - for x in y: append(z)
    - list(map(lambda...))
    - list(filter(...))
    - reduce(...)
    """

    __slots__ = ()

    def __init__(self, elem_expr: IRNode, iter_expr: IRNode, cond_expr: IRNode | None = None):
        self.node_type = "MAP_REDUCE"
        if cond_expr:
            self.children = (elem_expr, iter_expr, cond_expr)
        else:
            self.children = (elem_expr, iter_expr)


class ConditionIR(IRNode):
    """Conditional: if/else, ternary expressions"""

    __slots__ = ()

    def __init__(self, condition: IRNode, then_expr: IRNode, else_expr: IRNode | None = None):
        self.node_type = "CONDITION"
        if else_expr:
            self.children = (condition, then_expr, else_expr)
        else:
            self.children = (condition, then_expr)


class BinaryOpIR(IRNode):
    """Binary operation: arithmetic, comparison, logical"""

    __slots__ = ()

    def __init__(self, left: IRNode, op: str, right: IRNode):
        self.node_type = "BINARY_OP"
        self.children = (left, right)
        self.value = op


class CallIR(IRNode):
    """Function call"""

    __slots__ = ()

    def __init__(self, func_name: str, args: tuple[IRNode, ...]):
        self.node_type = "CALL"
        self.children = args
        self.value = func_name


class IdentifierIR(IRNode):
    """Variable/function identifier"""

    __slots__ = ()

    def __init__(self, name: str | None = None, is_builtin: bool = False):
        self.node_type = "IDENTIFIER"
        self.children = ()
        self.value = name if not is_builtin else f"[builtin:{name}]"


class LiteralIR(IRNode):
    """Literal value: int, float, bool, string"""

    __slots__ = ()

    def __init__(self, literal_type: str, value: str):
        self.node_type = literal_type.upper()
        self.children = ()
        self.value = value


def ir_node(node_type: str, children: tuple[IRNode, ...] = (), value: str | None = None) -> IRNode:
    """Factory function to create generic IR nodes."""
    return IRNode(node_type=node_type, children=children, value=value)