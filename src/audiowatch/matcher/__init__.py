"""Matcher module for AudioWatch.

Provides watch rule parsing and listing matching functionality.
"""

from audiowatch.matcher.parser import RuleParser, parse_expression
from audiowatch.matcher.evaluator import RuleEvaluator, evaluate_listing

__all__ = [
    "RuleParser",
    "RuleEvaluator",
    "parse_expression",
    "evaluate_listing",
]
