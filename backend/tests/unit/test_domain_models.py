from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cost_optimization.domain.models import Money


def test_money_preserves_decimal_precision_and_normalizes_currency() -> None:
    money = Money(amount=Decimal("12.345"), currency="usd")

    assert money.amount == Decimal("12.345")
    assert money.currency == "USD"


def test_money_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        Money(amount=Decimal("-0.01"), currency="USD")
