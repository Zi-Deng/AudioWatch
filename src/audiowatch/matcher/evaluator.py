"""Expression evaluator for matching listings against watch rules."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from audiowatch.database.models import Listing
from audiowatch.logging import get_logger
from audiowatch.matcher.parser import (
    BooleanExpr,
    BoolOp,
    Condition,
    Expression,
    Operator,
    parse_expression,
)

logger = get_logger(__name__)


class RuleEvaluator:
    """Evaluator for watch rule expressions against listings."""

    # Map listing attribute names to their database column names
    FIELD_MAPPING = {
        "title": "title",
        "price": "price",
        "currency": "currency",
        "category": "category",
        "condition": "condition",
        "seller": "seller_username",
        "seller_username": "seller_username",
        "seller_reputation": "seller_reputation",
        "listing_type": "listing_type",
        "type": "listing_type",
        "shipping": "shipping_regions",
        "ships_to": "shipping_regions",
    }

    def __init__(self, expression: Expression):
        """Initialize with a parsed expression.

        Args:
            expression: Parsed expression from RuleParser.
        """
        self.expression = expression

    @classmethod
    def from_string(cls, expression_str: str) -> "RuleEvaluator":
        """Create an evaluator from an expression string.

        Args:
            expression_str: Expression string to parse.

        Returns:
            RuleEvaluator instance.
        """
        expr = parse_expression(expression_str)
        return cls(expr)

    def matches(self, listing: Listing) -> bool:
        """Check if a listing matches the expression.

        Args:
            listing: The listing to check.

        Returns:
            True if the listing matches, False otherwise.
        """
        try:
            return self._evaluate(self.expression, listing)
        except Exception as e:
            logger.warning(
                "Error evaluating expression",
                listing_id=listing.id,
                error=str(e),
            )
            return False

    def _evaluate(self, expr: Expression, listing: Listing) -> bool:
        """Evaluate an expression against a listing.

        Args:
            expr: The expression to evaluate.
            listing: The listing to check.

        Returns:
            True if the expression matches.
        """
        if isinstance(expr, Condition):
            return self._evaluate_condition(expr, listing)
        elif isinstance(expr, BooleanExpr):
            return self._evaluate_boolean(expr, listing)
        else:
            raise ValueError(f"Unknown expression type: {type(expr)}")

    def _evaluate_condition(self, cond: Condition, listing: Listing) -> bool:
        """Evaluate a single condition against a listing.

        Args:
            cond: The condition to evaluate.
            listing: The listing to check.

        Returns:
            True if the condition matches.
        """
        # Get the field value from the listing
        field_name = self.FIELD_MAPPING.get(cond.field.lower(), cond.field)
        field_value = getattr(listing, field_name, None)

        if field_value is None:
            # Field is None - comparison depends on operator
            if cond.operator in (Operator.NE,):
                return True  # None != anything
            return False

        # Normalize values for comparison
        compare_value = cond.value

        # Handle numeric comparisons
        if cond.operator in (Operator.LT, Operator.GT, Operator.LE, Operator.GE):
            try:
                if isinstance(field_value, Decimal):
                    compare_value = Decimal(str(compare_value))
                elif isinstance(field_value, (int, float)):
                    compare_value = type(field_value)(compare_value)
            except (ValueError, TypeError):
                return False

        # Evaluate based on operator
        match cond.operator:
            case Operator.EQ:
                return self._equals(field_value, compare_value)
            case Operator.NE:
                return not self._equals(field_value, compare_value)
            case Operator.LT:
                return field_value < compare_value
            case Operator.GT:
                return field_value > compare_value
            case Operator.LE:
                return field_value <= compare_value
            case Operator.GE:
                return field_value >= compare_value
            case Operator.CONTAINS:
                return self._contains(field_value, compare_value)
            case Operator.STARTSWITH:
                return self._startswith(field_value, compare_value)
            case Operator.ENDSWITH:
                return self._endswith(field_value, compare_value)
            case _:
                raise ValueError(f"Unknown operator: {cond.operator}")

    def _evaluate_boolean(self, expr: BooleanExpr, listing: Listing) -> bool:
        """Evaluate a boolean expression.

        Args:
            expr: The boolean expression.
            listing: The listing to check.

        Returns:
            True if the expression matches.
        """
        match expr.operator:
            case BoolOp.AND:
                return all(self._evaluate(op, listing) for op in expr.operands)
            case BoolOp.OR:
                return any(self._evaluate(op, listing) for op in expr.operands)
            case BoolOp.NOT:
                return not self._evaluate(expr.operands[0], listing)
            case _:
                raise ValueError(f"Unknown boolean operator: {expr.operator}")

    def _equals(self, field_value: Any, compare_value: Any) -> bool:
        """Check equality with case-insensitive string comparison."""
        if isinstance(field_value, str) and isinstance(compare_value, str):
            return field_value.lower() == compare_value.lower()
        return field_value == compare_value

    def _contains(self, field_value: Any, compare_value: Any) -> bool:
        """Check if field contains value (case-insensitive for strings)."""
        if isinstance(field_value, str) and isinstance(compare_value, str):
            return compare_value.lower() in field_value.lower()
        return compare_value in field_value

    def _startswith(self, field_value: Any, compare_value: Any) -> bool:
        """Check if field starts with value (case-insensitive for strings)."""
        if isinstance(field_value, str) and isinstance(compare_value, str):
            return field_value.lower().startswith(compare_value.lower())
        return str(field_value).startswith(str(compare_value))

    def _endswith(self, field_value: Any, compare_value: Any) -> bool:
        """Check if field ends with value (case-insensitive for strings)."""
        if isinstance(field_value, str) and isinstance(compare_value, str):
            return field_value.lower().endswith(compare_value.lower())
        return str(field_value).endswith(str(compare_value))


def evaluate_listing(listing: Listing, expression: str) -> bool:
    """Evaluate whether a listing matches an expression.

    Convenience function for one-off evaluations.

    Args:
        listing: The listing to check.
        expression: The expression string.

    Returns:
        True if the listing matches.
    """
    evaluator = RuleEvaluator.from_string(expression)
    return evaluator.matches(listing)
