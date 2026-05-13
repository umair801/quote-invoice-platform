# api/pricing_router.py
# Quote-to-Invoice Platform
# Pricing configurator endpoint: takes SKU selections + artwork dimensions,
# returns fully computed line items and totals.

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from builders.price_engine import calculate_price

router = APIRouter(prefix="/pricing", tags=["Pricing"])


# ─── Request / Response Schemas ───────────────────────────────────────────────

class CalculatePriceRequest(BaseModel):
    # Artwork dimensions (required)
    width_inches:  float = Field(..., gt=0, description="Artwork width in inches")
    height_inches: float = Field(..., gt=0, description="Artwork height in inches")

    # Material selections (all optional - only selected items are priced)
    moulding_sku:  Optional[str]       = Field(None, description="Moulding catalog SKU")
    glass_sku:     Optional[str]       = Field(None, description="Glass catalog SKU")
    mat_sku:       Optional[str]       = Field(None, description="Mat catalog SKU")
    mounting_sku:  Optional[str]       = Field(None, description="Mounting catalog SKU")
    labor_skus:    Optional[list[str]] = Field(default=[], description="One or more labor SKUs")

    # Pricing options
    tax_rate:      float  = Field(default=0.0, ge=0, le=1, description="Tax rate as decimal, e.g. 0.08875")
    notes:         str    = Field(default="", description="Free-text notes for this quote")


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/calculate")
def calculate(body: CalculatePriceRequest):
    """
    Calculate framing price from catalog SKU selections and artwork dimensions.

    Returns line items with computed quantities, unit prices, and totals.
    Moulding is priced per linear foot (perimeter + waste).
    Glass and mat are priced per square foot (area).
    Mounting and labor are priced per job or per square foot depending on catalog config.

    All SKUs are resolved live from the quote_catalog table.
    """
    if not any([
        body.moulding_sku,
        body.glass_sku,
        body.mat_sku,
        body.mounting_sku,
        body.labor_skus,
    ]):
        raise HTTPException(
            status_code=400,
            detail="At least one SKU must be provided (moulding, glass, mat, mounting, or labor).",
        )

    try:
        result = calculate_price(
            width_inches=body.width_inches,
            height_inches=body.height_inches,
            moulding_sku=body.moulding_sku,
            glass_sku=body.glass_sku,
            mat_sku=body.mat_sku,
            mounting_sku=body.mounting_sku,
            labor_skus=body.labor_skus,
            tax_rate=body.tax_rate,
            notes=body.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Price calculation failed: {exc}")

    return result.to_dict()


@router.get("/rules")
def get_pricing_rules():
    """
    Return the pricing rules documentation so the frontend can display
    how each category is calculated.
    """
    return {
        "rules": [
            {
                "category":        "moulding",
                "unit_of_measure": "per_foot",
                "formula":         "2 x (width + height) + 16 inches waste, converted to feet",
                "example":         "16x20 artwork = 3.83 ft perimeter + 1.33 ft waste = 5.17 ft",
            },
            {
                "category":        "glass",
                "unit_of_measure": "per_sqft",
                "formula":         "width x height / 144",
                "example":         "16x20 artwork = 320 sq in = 2.222 sqft",
            },
            {
                "category":        "mat",
                "unit_of_measure": "per_sqft",
                "formula":         "width x height / 144",
                "example":         "16x20 artwork = 320 sq in = 2.222 sqft",
            },
            {
                "category":        "mounting",
                "unit_of_measure": "each or per_sqft",
                "formula":         "Fixed per job (each) or area-based (per_sqft)",
                "example":         "Hinge mount = $25.00 each; Dry mount = $1.50/sqft",
            },
            {
                "category":        "labor",
                "unit_of_measure": "each or per_hour",
                "formula":         "Fixed per job (each) or hourly (per_hour)",
                "example":         "Frame assembly = $35.00 each",
            },
        ],
        "waste_factor_inches": 4.0,
        "waste_factor_note":   "4 inches added per side (16 inches total) for moulding joining waste",
        "tax_note":            "tax_rate is a decimal: 0.08875 = 8.875% NYC tax",
    }
