from decimal import Decimal

import pytest

from app.pricing import PricingError, quote


def test_standard_two_days_costs_120():
    assert quote("standard", 2) == Decimal("125.00")


def test_long_rental_gets_discount():
    assert quote("economy", 7) == Decimal("283.50")


def test_unknown_category_is_rejected():
    with pytest.raises(PricingError):
        quote("spaceship", 2)


def test_zero_days_is_rejected():
    with pytest.raises(PricingError):
        quote("standard", 0)
