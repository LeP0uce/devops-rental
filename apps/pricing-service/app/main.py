"""API HTTP du service de tarification."""
from fastapi import FastAPI, HTTPException, Query
from app.pricing import DAILY_RATES, PricingError, quote

app = FastAPI(title="pricing-service")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "UP"}


@app.get("/cars")
def categories() -> list[dict[str, object]]:
    """Grille tarifaire par catégorie de véhicule."""
    return [{"category": name, "daily_rate": float(rate), "currency": "EUR"} for name, rate in DAILY_RATES.items()]


@app.get("/quote")
def get_quote(category: str = Query(...), days: int = Query(..., ge=1)) -> dict[str, object]:
    try:
        total = quote(category, days)
    except PricingError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"category": category, "days": days, "total": float(total), "currency": "EUR"}
