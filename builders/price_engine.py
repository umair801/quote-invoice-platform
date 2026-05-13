# builders/price_engine.py
# Quote-to-Invoice Platform
# Pricing rules engine for custom framing.
# Computes line item prices from catalog SKUs + artwork dimensions.

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from core.database import get_catalog_item_by_sku

# ─── Constants ────────────────────────────────────────────────────────────────

# Extra moulding added to each side to account for joining waste (inches)
MOULDING_WASTE_INCHES: Decimal = Decimal("4.0")

# Minimum moulding order in feet (most suppliers require at least 1 foot per side)
MOULDING_MIN_FEET: Decimal = Decimal("1.0")

# Rounding precision for all monetary values
MONEY = Decimal("0.01")

# Rounding precision for measurements
MEASURE = Decimal("0.001")


# ─── Pricing result models ────────────────────────────────────────────────────

class PricedLineItem:
    """A single computed line item ready for quote assembly."""

    def __init__(
        self,
        line_number: int,
        sku: str,
        category: str,
        description: str,
        quantity: Decimal,
        unit_price: Decimal,
        unit_of_measure: str,
        notes: str = "",
    ):
        self.line_number = line_number
        self.sku = sku
        self.category = category
        self.description = description
        self.quantity = quantity.quantize(MEASURE, rounding=ROUND_HALF_UP)
        self.unit_price = unit_price.quantize(MONEY, rounding=ROUND_HALF_UP)
        self.unit_of_measure = unit_of_measure
        self.total = (self.quantity * self.unit_price).quantize(MONEY, rounding=ROUND_HALF_UP)
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "line_number":     self.line_number,
            "sku":             self.sku,
            "category":        self.category,
            "description":     self.description,
            "quantity":        float(self.quantity),
            "unit_price":      float(self.unit_price),
            "unit_of_measure": self.unit_of_measure,
            "total":           float(self.total),
            "notes":           self.notes,
        }


class PriceCalculationResult:
    """Full result of a calculate_price() call."""

    def __init__(
        self,
        line_items: list[PricedLineItem],
        tax_rate: Decimal = Decimal("0"),
        notes: str = "",
    ):
        self.line_items = line_items
        self.subtotal = sum(
            (item.total for item in line_items), Decimal("0")
        ).quantize(MONEY, rounding=ROUND_HALF_UP)
        self.tax_rate = tax_rate
        self.tax = (self.subtotal * tax_rate).quantize(MONEY, rounding=ROUND_HALF_UP)
        self.total = (self.subtotal + self.tax).quantize(MONEY, rounding=ROUND_HALF_UP)
        self.notes = notes
        self.errors: list[str] = []

    def to_dict(self) -> dict:
        return {
            "line_items": [item.to_dict() for item in self.line_items],
            "subtotal":   float(self.subtotal),
            "tax_rate":   float(self.tax_rate),
            "tax":        float(self.tax),
            "total":      float(self.total),
            "notes":      self.notes,
            "errors":     self.errors,
        }


# ─── Measurement helpers ──────────────────────────────────────────────────────

def _area_sqft(width_inches: Decimal, height_inches: Decimal) -> Decimal:
    """Convert artwork dimensions to area in square feet."""
    area_sq_inches = width_inches * height_inches
    return (area_sq_inches / Decimal("144")).quantize(MEASURE, rounding=ROUND_HALF_UP)


def _perimeter_feet(width_inches: Decimal, height_inches: Decimal) -> Decimal:
    """
    Compute moulding length needed in feet.
    Formula: 2 x (W + H) + waste per side (4 inches x 4 sides = 16 inches total).
    Result is in feet.
    """
    perimeter_inches = (
        Decimal("2") * (width_inches + height_inches) + MOULDING_WASTE_INCHES * Decimal("4")
    )
    feet = (perimeter_inches / Decimal("12")).quantize(MEASURE, rounding=ROUND_HALF_UP)
    return max(feet, MOULDING_MIN_FEET)


# ─── Per-category pricing functions ───────────────────────────────────────────

def _price_moulding(
    item: dict,
    width_inches: Decimal,
    height_inches: Decimal,
    line_number: int,
) -> PricedLineItem:
    """
    Moulding is priced per linear foot.
    Quantity = perimeter feet including waste.
    """
    feet = _perimeter_feet(width_inches, height_inches)
    return PricedLineItem(
        line_number=line_number,
        sku=item["sku"],
        category="moulding",
        description=item["name"],
        quantity=feet,
        unit_price=Decimal(str(item["unit_price"])),
        unit_of_measure="per_foot",
        notes=f"Frame perimeter: {float(feet):.2f} ft (includes joining waste)",
    )


def _price_glass(
    item: dict,
    width_inches: Decimal,
    height_inches: Decimal,
    line_number: int,
) -> PricedLineItem:
    """
    Glass is priced per square foot.
    Quantity = artwork area in sqft.
    """
    sqft = _area_sqft(width_inches, height_inches)
    uom = item.get("unit_of_measure", "per_sqft")

    if uom == "each":
        quantity = Decimal("1")
        notes = "Fixed price per piece"
    else:
        quantity = sqft
        notes = f"Area: {float(sqft):.3f} sqft"

    return PricedLineItem(
        line_number=line_number,
        sku=item["sku"],
        category="glass",
        description=item["name"],
        quantity=quantity,
        unit_price=Decimal(str(item["unit_price"])),
        unit_of_measure=uom,
        notes=notes,
    )


def _price_mat(
    item: dict,
    width_inches: Decimal,
    height_inches: Decimal,
    line_number: int,
) -> PricedLineItem:
    """
    Mat board is priced per square foot.
    Quantity = artwork area in sqft (mat cut to fit).
    """
    sqft = _area_sqft(width_inches, height_inches)
    uom = item.get("unit_of_measure", "per_sqft")

    if uom == "each":
        quantity = Decimal("1")
        notes = "Fixed price per mat"
    else:
        quantity = sqft
        notes = f"Area: {float(sqft):.3f} sqft"

    return PricedLineItem(
        line_number=line_number,
        sku=item["sku"],
        category="mat",
        description=item["name"],
        quantity=quantity,
        unit_price=Decimal(str(item["unit_price"])),
        unit_of_measure=uom,
        notes=notes,
    )


def _price_mounting(
    item: dict,
    width_inches: Decimal,
    height_inches: Decimal,
    line_number: int,
) -> PricedLineItem:
    """
    Mounting is either per_sqft (e.g. dry mount tissue) or each (e.g. hinge mount).
    """
    uom = item.get("unit_of_measure", "each")

    if uom == "per_sqft":
        quantity = _area_sqft(width_inches, height_inches)
        notes = f"Area: {float(quantity):.3f} sqft"
    else:
        quantity = Decimal("1")
        notes = "Fixed price per job"

    return PricedLineItem(
        line_number=line_number,
        sku=item["sku"],
        category="mounting",
        description=item["name"],
        quantity=quantity,
        unit_price=Decimal(str(item["unit_price"])),
        unit_of_measure=uom,
        notes=notes,
    )


def _price_labor(
    item: dict,
    line_number: int,
    quantity: Decimal = Decimal("1"),
) -> PricedLineItem:
    """
    Labor is either a fixed each price or per_hour.
    Default quantity is 1 (one job / one assembly).
    """
    uom = item.get("unit_of_measure", "each")
    return PricedLineItem(
        line_number=line_number,
        sku=item["sku"],
        category="labor",
        description=item["name"],
        quantity=quantity,
        unit_price=Decimal(str(item["unit_price"])),
        unit_of_measure=uom,
        notes="",
    )


# ─── Main public function ─────────────────────────────────────────────────────

def calculate_price(
    width_inches: float,
    height_inches: float,
    moulding_sku: Optional[str] = None,
    glass_sku: Optional[str] = None,
    mat_sku: Optional[str] = None,
    mounting_sku: Optional[str] = None,
    labor_skus: Optional[list[str]] = None,
    tax_rate: float = 0.0,
    notes: str = "",
) -> PriceCalculationResult:
    """
    Calculate a full framing price from catalog SKUs and artwork dimensions.

    Args:
        width_inches:   Artwork width in inches.
        height_inches:  Artwork height in inches.
        moulding_sku:   SKU of selected moulding (optional).
        glass_sku:      SKU of selected glass (optional).
        mat_sku:        SKU of selected mat (optional).
        mounting_sku:   SKU of selected mounting method (optional).
        labor_skus:     List of labor SKUs to include (optional, e.g. assembly + mat cutting).
        tax_rate:       Tax rate as a decimal (e.g. 0.08875 for 8.875%).
        notes:          Free-text notes to attach to the result.

    Returns:
        PriceCalculationResult with line_items, subtotal, tax, and total.
    """
    W = Decimal(str(width_inches))
    H = Decimal(str(height_inches))
    tax = Decimal(str(tax_rate))

    line_items: list[PricedLineItem] = []
    errors: list[str] = []
    line_num = 1

    # Validate dimensions
    if W <= 0 or H <= 0:
        result = PriceCalculationResult([], tax)
        result.errors.append("width_inches and height_inches must be greater than 0.")
        return result

    # --- Moulding ---
    if moulding_sku:
        item = get_catalog_item_by_sku(moulding_sku)
        if not item:
            errors.append(f"Moulding SKU '{moulding_sku}' not found in catalog.")
        elif not item.get("is_active"):
            errors.append(f"Moulding SKU '{moulding_sku}' is inactive.")
        else:
            line_items.append(_price_moulding(item, W, H, line_num))
            line_num += 1

    # --- Glass ---
    if glass_sku:
        item = get_catalog_item_by_sku(glass_sku)
        if not item:
            errors.append(f"Glass SKU '{glass_sku}' not found in catalog.")
        elif not item.get("is_active"):
            errors.append(f"Glass SKU '{glass_sku}' is inactive.")
        else:
            line_items.append(_price_glass(item, W, H, line_num))
            line_num += 1

    # --- Mat ---
    if mat_sku:
        item = get_catalog_item_by_sku(mat_sku)
        if not item:
            errors.append(f"Mat SKU '{mat_sku}' not found in catalog.")
        elif not item.get("is_active"):
            errors.append(f"Mat SKU '{mat_sku}' is inactive.")
        else:
            line_items.append(_price_mat(item, W, H, line_num))
            line_num += 1

    # --- Mounting ---
    if mounting_sku:
        item = get_catalog_item_by_sku(mounting_sku)
        if not item:
            errors.append(f"Mounting SKU '{mounting_sku}' not found in catalog.")
        elif not item.get("is_active"):
            errors.append(f"Mounting SKU '{mounting_sku}' is inactive.")
        else:
            line_items.append(_price_mounting(item, W, H, line_num))
            line_num += 1

    # --- Labor (one line item per SKU) ---
    for sku in (labor_skus or []):
        item = get_catalog_item_by_sku(sku)
        if not item:
            errors.append(f"Labor SKU '{sku}' not found in catalog.")
        elif not item.get("is_active"):
            errors.append(f"Labor SKU '{sku}' is inactive.")
        else:
            line_items.append(_price_labor(item, line_num))
            line_num += 1

    result = PriceCalculationResult(line_items, tax, notes)
    result.errors = errors
    return result
