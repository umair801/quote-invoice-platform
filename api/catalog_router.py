# api/catalog_router.py
# Quote-to-Invoice Platform
# Moulding and materials catalog: CRUD + image upload to Supabase Storage.

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field

from core.database import (
    get_supabase,
    insert_catalog_item,
    get_catalog_item_by_sku,
    get_catalog_item_by_id,
    update_catalog_item,
    delete_catalog_item,
    list_catalog_items,
)
from core.config import get_settings

router = APIRouter(prefix="/catalog", tags=["Catalog"])
settings = get_settings()

# Valid categories enforced at API level
VALID_CATEGORIES = {"moulding", "glass", "mat", "mounting", "labor"}
VALID_UNITS = {"each", "per_foot", "per_sqft", "per_hour"}
STORAGE_BUCKET = "catalog-images"


# ─── Request / Response Schemas ───────────────────────────────────────────────

class CreateCatalogItemRequest(BaseModel):
    sku:             str
    name:            str
    category:        str   # moulding | glass | mat | mounting | labor
    subcategory:     Optional[str]   = None
    unit_price:      float
    unit_of_measure: str             = "each"
    description:     Optional[str]  = None
    color:           Optional[str]  = None
    material:        Optional[str]  = None
    width_inches:    Optional[float] = None
    height_inches:   Optional[float] = None
    supplier:        Optional[str]  = None
    supplier_sku:    Optional[str]  = None
    notes:           Optional[str]  = None
    sort_order:      int            = 0
    is_active:       bool           = True


class UpdateCatalogItemRequest(BaseModel):
    name:            Optional[str]   = None
    subcategory:     Optional[str]   = None
    unit_price:      Optional[float] = None
    unit_of_measure: Optional[str]   = None
    description:     Optional[str]   = None
    color:           Optional[str]   = None
    material:        Optional[str]   = None
    width_inches:    Optional[float] = None
    height_inches:   Optional[float] = None
    supplier:        Optional[str]   = None
    supplier_sku:    Optional[str]   = None
    notes:           Optional[str]   = None
    sort_order:      Optional[int]   = None
    is_active:       Optional[bool]  = None


# ─── Validation helpers ───────────────────────────────────────────────────────

def _validate_category(category: str) -> None:
    if category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {sorted(VALID_CATEGORIES)}",
        )


def _validate_unit(unit: str) -> None:
    if unit not in VALID_UNITS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid unit_of_measure '{unit}'. Must be one of: {sorted(VALID_UNITS)}",
        )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_catalog_item(body: CreateCatalogItemRequest):
    """
    Create a new catalog item (moulding, glass, mat, mounting, or labor).
    SKU must be unique across the catalog.
    """
    _validate_category(body.category)
    _validate_unit(body.unit_of_measure)

    # Check SKU uniqueness
    existing = get_catalog_item_by_sku(body.sku)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A catalog item with SKU '{body.sku}' already exists.",
        )

    data = {
        "id":              str(uuid.uuid4()),
        "sku":             body.sku,
        "name":            body.name,
        "category":        body.category,
        "subcategory":     body.subcategory,
        "unit_price":      body.unit_price,
        "unit_of_measure": body.unit_of_measure,
        "description":     body.description,
        "color":           body.color,
        "material":        body.material,
        "width_inches":    body.width_inches,
        "height_inches":   body.height_inches,
        "supplier":        body.supplier,
        "supplier_sku":    body.supplier_sku,
        "notes":           body.notes,
        "sort_order":      body.sort_order,
        "is_active":       body.is_active,
        "image_url":       None,
    }

    try:
        row = insert_catalog_item(data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {exc}")

    return {"id": row.get("id"), "sku": row.get("sku"), "name": row.get("name")}


@router.get("/")
def list_catalog(
    category:    Optional[str] = Query(default=None, description="Filter by category"),
    active_only: bool          = Query(default=True, description="Only return active items"),
    limit:       int           = Query(default=200, le=500),
):
    """
    List all catalog items. Optionally filter by category (moulding, glass, mat, mounting, labor).
    Returns items sorted by sort_order then name.
    """
    if category and category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category '{category}'. Must be one of: {sorted(VALID_CATEGORIES)}",
        )
    rows = list_catalog_items(category=category, active_only=active_only, limit=limit)
    return {"count": len(rows), "items": rows}


@router.get("/categories")
def get_categories():
    """Return the valid product categories and units of measure."""
    return {
        "categories":        sorted(VALID_CATEGORIES),
        "units_of_measure":  sorted(VALID_UNITS),
    }


@router.get("/sku/{sku}")
def get_by_sku(sku: str):
    """Fetch a catalog item by its SKU."""
    row = get_catalog_item_by_sku(sku)
    if not row:
        raise HTTPException(status_code=404, detail=f"No catalog item with SKU '{sku}'.")
    return row


@router.get("/{item_id}")
def get_by_id(item_id: str):
    """Fetch a catalog item by its UUID."""
    row = get_catalog_item_by_id(item_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"No catalog item with id '{item_id}'.")
    return row


@router.patch("/{item_id}")
def update_item(item_id: str, body: UpdateCatalogItemRequest):
    """
    Partially update a catalog item.
    Only fields included in the request body are changed.
    """
    existing = get_catalog_item_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"No catalog item with id '{item_id}'.")

    payload = body.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields provided to update.")

    if "unit_of_measure" in payload:
        _validate_unit(payload["unit_of_measure"])

    try:
        row = update_catalog_item(item_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DB update failed: {exc}")

    return {"id": item_id, "updated_fields": list(payload.keys()), "item": row}


@router.delete("/{item_id}")
def deactivate_item(item_id: str):
    """
    Soft-delete a catalog item by setting is_active=False.
    The item remains in the DB for historical quote integrity.
    """
    existing = get_catalog_item_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"No catalog item with id '{item_id}'.")

    success = delete_catalog_item(item_id)
    if not success:
        raise HTTPException(status_code=500, detail="Deactivation failed.")

    return {"id": item_id, "is_active": False, "message": "Item deactivated (soft delete)."}


@router.post("/{item_id}/upload-image")
async def upload_image(item_id: str, file: UploadFile = File(...)):
    """
    Upload a product image for a catalog item to Supabase Storage.
    Accepted formats: JPEG, PNG, WebP.
    Returns the public URL stored on the catalog item row.
    """
    existing = get_catalog_item_by_id(item_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"No catalog item with id '{item_id}'.")

    # Validate content type
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. Accepted: jpeg, png, webp.",
        )

    # Build a stable storage path: catalog-images/<item_id>/<original_filename>
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    storage_path = f"{item_id}/image.{ext}"

    file_bytes = await file.read()

    try:
        sb = get_supabase()
        # Upsert so re-uploads overwrite the existing file
        sb.storage.from_(STORAGE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={
                "content-type": file.content_type,
                "upsert": "true",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase Storage upload failed: {exc}",
        )

    # Build the public URL from the Supabase project URL
    supabase_url = settings.SUPABASE_URL.rstrip("/")
    public_url = f"{supabase_url}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"

    # Persist the URL on the catalog row
    try:
        update_catalog_item(item_id, {"image_url": public_url})
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"DB update for image_url failed: {exc}",
        )

    return {
        "item_id":    item_id,
        "image_url":  public_url,
        "message":    "Image uploaded and catalog item updated.",
    }


@router.post("/seed-samples")
def seed_sample_items():
    """
    Seed the catalog with representative sample items for all five categories.
    Safe to call multiple times - skips SKUs that already exist.
    Useful for development and demo purposes.
    """
    samples = [
        # Moulding samples
        {"sku": "MLD-001", "name": "Classic Gold Leaf", "category": "moulding",
         "subcategory": "wood", "unit_price": 18.50, "unit_of_measure": "per_foot",
         "color": "Gold", "material": "Wood", "width_inches": 2.5, "height_inches": 1.25,
         "description": "Traditional gold leaf finish, hardwood core"},
        {"sku": "MLD-002", "name": "Ebony Slim", "category": "moulding",
         "subcategory": "wood", "unit_price": 12.00, "unit_of_measure": "per_foot",
         "color": "Ebony", "material": "Wood", "width_inches": 1.5, "height_inches": 0.75,
         "description": "Narrow ebony-stained profile, modern aesthetic"},
        {"sku": "MLD-003", "name": "Brushed Silver Metal", "category": "moulding",
         "subcategory": "metal", "unit_price": 22.00, "unit_of_measure": "per_foot",
         "color": "Silver", "material": "Aluminum", "width_inches": 1.0, "height_inches": 0.5,
         "description": "Brushed aluminum, museum-style float frame"},

        # Glass samples
        {"sku": "GLS-001", "name": "Conservation Clear", "category": "glass",
         "subcategory": "conservation", "unit_price": 4.50, "unit_of_measure": "per_sqft",
         "description": "UV-filtering conservation glass, 99% UV protection"},
        {"sku": "GLS-002", "name": "Museum Glass", "category": "glass",
         "subcategory": "museum", "unit_price": 9.00, "unit_of_measure": "per_sqft",
         "description": "Anti-reflective museum glass, near-invisible"},
        {"sku": "GLS-003", "name": "Acrylic Standard", "category": "glass",
         "subcategory": "acrylic", "unit_price": 3.00, "unit_of_measure": "per_sqft",
         "description": "Lightweight acrylic glazing, shatter-resistant"},

        # Mat samples
        {"sku": "MAT-001", "name": "White Rag Mat", "category": "mat",
         "subcategory": "rag", "unit_price": 2.25, "unit_of_measure": "per_sqft",
         "color": "White", "material": "Cotton Rag",
         "description": "Acid-free cotton rag mat board, archival quality"},
        {"sku": "MAT-002", "name": "Black Core Mat", "category": "mat",
         "subcategory": "standard", "unit_price": 1.75, "unit_of_measure": "per_sqft",
         "color": "Cream/Black", "material": "Alpha-cellulose",
         "description": "Cream surface with black core bevel reveal"},

        # Mounting samples
        {"sku": "MNT-001", "name": "Dry Mount", "category": "mounting",
         "unit_price": 1.50, "unit_of_measure": "per_sqft",
         "description": "Heat-activated dry mounting tissue, permanent"},
        {"sku": "MNT-002", "name": "Hinge Mount (Archival)", "category": "mounting",
         "unit_price": 25.00, "unit_of_measure": "each",
         "description": "Japanese tissue hinges, fully reversible archival mounting"},

        # Labor samples
        {"sku": "LAB-001", "name": "Frame Assembly", "category": "labor",
         "unit_price": 35.00, "unit_of_measure": "each",
         "description": "Standard frame joining, fitting, and backing"},
        {"sku": "LAB-002", "name": "Mat Cutting", "category": "labor",
         "unit_price": 15.00, "unit_of_measure": "each",
         "description": "Single mat cut, standard opening"},
        {"sku": "LAB-003", "name": "Double Mat Cutting", "category": "labor",
         "unit_price": 22.00, "unit_of_measure": "each",
         "description": "Double mat cut with reveal bevel"},
    ]

    inserted = []
    skipped = []

    for item in samples:
        existing = get_catalog_item_by_sku(item["sku"])
        if existing:
            skipped.append(item["sku"])
            continue
        data = {
            "id":              str(uuid.uuid4()),
            "is_active":       True,
            "sort_order":      0,
            "image_url":       None,
            **item,
        }
        # Fill optional fields with None if absent
        for field in ["subcategory", "color", "material", "width_inches",
                       "height_inches", "supplier", "supplier_sku", "notes"]:
            data.setdefault(field, None)

        try:
            insert_catalog_item(data)
            inserted.append(item["sku"])
        except Exception as exc:
            skipped.append(f"{item['sku']} (error: {exc})")

    return {
        "inserted": inserted,
        "skipped":  skipped,
        "message":  f"{len(inserted)} items seeded, {len(skipped)} skipped.",
    }
