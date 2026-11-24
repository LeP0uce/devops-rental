"""Règles de tarification du service Rental."""

from decimal import ROUND_HALF_UP, Decimal

DAILY_RATES = {
    "economy": Decimal("45"),
    "standard": Decimal("60"),
    "premium": Decimal("95"),
}

LONG_RENTAL_DAYS = 7
LONG_RENTAL_DISCOUNT = Decimal("0.10")


class PricingError(ValueError):
    """Demande de cotation invalide."""


def quote(category: str, days: int) -> Decimal:
    """Retourne le prix total en euros pour une catégorie et une durée."""
    if category not in DAILY_RATES:
        raise PricingError(f"unknown category: {category}")
    if days < 1:
        raise PricingError("days must be >= 1")
    total = DAILY_RATES[category] * days
    if days >= LONG_RENTAL_DAYS:
        total = total * (1 - LONG_RENTAL_DISCOUNT)
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
