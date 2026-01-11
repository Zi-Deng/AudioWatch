"""Expression parser for watch rules.

Supports boolean expressions like:
- title contains "Moses"
- price < 3500
- title contains "HD800" AND price < 1000
- category = "headphones" OR category = "amplification"
- NOT title contains "broken"
- title matches "64\\s*[Aa]udio"  (regex)
- title fuzzy_contains "ThieAudio Monarch MK4"  (fuzzy ~80% match)

Supported operators:
- Comparison: =, !=, <, >, <=, >=
- String: contains, startswith, endswith
- Regex: matches (case-insensitive regex pattern)
- Fuzzy: fuzzy_contains (similarity matching, ~80% threshold)
- Boolean: AND, OR, NOT
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any

from pyparsing import (
    CaselessKeyword,
    Group,
    Literal,
    OpAssoc,
    ParserElement,
    QuotedString,
    Regex,
    Suppress,
    Word,
    alphanums,
    alphas,
    infix_notation,
    one_of,
    pyparsing_common,
)

# Enable packrat parsing for performance
ParserElement.enablePackrat()


class Operator(str, Enum):
    """Comparison operators."""

    EQ = "="
    NE = "!="
    LT = "<"
    GT = ">"
    LE = "<="
    GE = ">="
    CONTAINS = "contains"
    STARTSWITH = "startswith"
    ENDSWITH = "endswith"
    MATCHES = "matches"  # Regex matching
    FUZZY_CONTAINS = "fuzzy_contains"  # Fuzzy/similarity matching


class BoolOp(str, Enum):
    """Boolean operators."""

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


@dataclass
class Condition:
    """A single condition in an expression."""

    field: str
    operator: Operator
    value: Any

    def __repr__(self) -> str:
        return f"{self.field} {self.operator.value} {self.value!r}"


@dataclass
class BooleanExpr:
    """A boolean expression combining conditions."""

    operator: BoolOp
    operands: list[Condition | "BooleanExpr"]

    def __repr__(self) -> str:
        if self.operator == BoolOp.NOT:
            return f"NOT ({self.operands[0]})"
        op_str = f" {self.operator.value} "
        return f"({op_str.join(str(o) for o in self.operands)})"


# Type alias for parsed expressions
Expression = Condition | BooleanExpr


class RuleParser:
    """Parser for watch rule expressions."""

    def __init__(self):
        """Initialize the parser grammar."""
        self._parser = self._build_parser()

    def _build_parser(self) -> ParserElement:
        """Build the pyparsing grammar."""
        # Field names (alphanumeric with underscores)
        field = Word(alphas, alphanums + "_").setResultsName("field")

        # String values (quoted)
        string_value = QuotedString('"') | QuotedString("'")

        # Numeric values
        number = pyparsing_common.number()

        # Value (string or number)
        value = (string_value | number).setResultsName("value")

        # Comparison operators
        comp_op = one_of("= != < > <= >=").setResultsName("operator")

        # String operators (case insensitive)
        str_op = (
            CaselessKeyword("contains")
            | CaselessKeyword("startswith")
            | CaselessKeyword("endswith")
            | CaselessKeyword("matches")
            | CaselessKeyword("fuzzy_contains")
        ).setResultsName("operator")

        # Condition: field op value
        condition = Group(
            field + (comp_op | str_op) + value
        ).setParseAction(self._make_condition)

        # Boolean operators
        and_op = CaselessKeyword("AND")
        or_op = CaselessKeyword("OR")
        not_op = CaselessKeyword("NOT")

        # Boolean expression using infix notation
        expr = infix_notation(
            condition,
            [
                (not_op, 1, OpAssoc.RIGHT, self._make_not),
                (and_op, 2, OpAssoc.LEFT, self._make_and),
                (or_op, 2, OpAssoc.LEFT, self._make_or),
            ],
        )

        return expr

    def _make_condition(self, tokens) -> Condition:
        """Convert parsed tokens to a Condition."""
        t = tokens[0]
        field = t.field
        op_str = t.operator.lower() if isinstance(t.operator, str) else t.operator
        value = t.value

        # Map operator string to enum
        op_map = {
            "=": Operator.EQ,
            "!=": Operator.NE,
            "<": Operator.LT,
            ">": Operator.GT,
            "<=": Operator.LE,
            ">=": Operator.GE,
            "contains": Operator.CONTAINS,
            "startswith": Operator.STARTSWITH,
            "endswith": Operator.ENDSWITH,
            "matches": Operator.MATCHES,
            "fuzzy_contains": Operator.FUZZY_CONTAINS,
        }

        operator = op_map.get(op_str)
        if operator is None:
            raise ValueError(f"Unknown operator: {op_str}")

        return Condition(field=field, operator=operator, value=value)

    def _make_not(self, tokens) -> BooleanExpr:
        """Create a NOT expression."""
        t = tokens[0]
        return BooleanExpr(operator=BoolOp.NOT, operands=[t[1]])

    def _make_and(self, tokens) -> BooleanExpr:
        """Create an AND expression."""
        t = tokens[0]
        operands = [t[i] for i in range(0, len(t), 2)]
        return BooleanExpr(operator=BoolOp.AND, operands=operands)

    def _make_or(self, tokens) -> BooleanExpr:
        """Create an OR expression."""
        t = tokens[0]
        operands = [t[i] for i in range(0, len(t), 2)]
        return BooleanExpr(operator=BoolOp.OR, operands=operands)

    def parse(self, expression: str) -> Expression:
        """Parse an expression string.

        Args:
            expression: The expression to parse.

        Returns:
            Parsed Expression (Condition or BooleanExpr).

        Raises:
            ValueError: If the expression is invalid.
        """
        try:
            result = self._parser.parseString(expression, parseAll=True)
            return result[0]
        except Exception as e:
            raise ValueError(f"Failed to parse expression: {expression!r}: {e}") from e


# Global parser instance
_parser: RuleParser | None = None


def get_parser() -> RuleParser:
    """Get or create the global parser instance."""
    global _parser
    if _parser is None:
        _parser = RuleParser()
    return _parser


def parse_expression(expression: str) -> Expression:
    """Parse an expression string.

    Convenience function using the global parser.

    Args:
        expression: The expression to parse.

    Returns:
        Parsed Expression.
    """
    return get_parser().parse(expression)
