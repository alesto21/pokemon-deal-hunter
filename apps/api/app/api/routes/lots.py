from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.schemas import LotIn, LotItemIn
from app.core.config import get_settings
from app.db.models import Listing, Lot, LotItem
from app.db.session import get_db
from app.services.evaluation import evaluate_listing
from app.services.lots import lot_for_listing, value_lot

router = APIRouter(tags=["lots"])
ALLOWED_IMAGE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAGIC = {b"\xff\xd8\xff": ".jpg", b"\x89PNG": ".png", b"RIFF": ".webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _lot(db: Session, lot_id: int) -> Lot:
    lot = db.get(Lot, lot_id)
    if not lot:
        raise HTTPException(404, "Lot not found")
    return lot


def _out(db: Session, lot: Lot) -> dict:
    v = value_lot(db, lot)
    return {"id": lot.id, "listing_id": lot.listing_id, "notes": lot.notes, "images": lot.images,
            "valuation": v.__dict__}


@router.post("/lots", status_code=201)
def create_lot(body: LotIn, db: Session = Depends(get_db)) -> dict:
    listing = db.get(Listing, body.listing_id)
    if not listing:
        raise HTTPException(404, "Listing not found")
    lot = lot_for_listing(db, listing.id) or Lot(listing_id=listing.id, images=[])
    lot.notes = body.notes
    listing.listing_kind = "lot"
    db.add(lot)
    db.flush()
    return _out(db, lot)


@router.get("/lots/{lot_id}")
def get_lot(lot_id: int, db: Session = Depends(get_db)) -> dict:
    return _out(db, _lot(db, lot_id))


@router.post("/lots/{lot_id}/items", status_code=201)
def add_item(lot_id: int, body: LotItemIn, db: Session = Depends(get_db)) -> dict:
    lot = _lot(db, lot_id)
    if not (body.card_id or body.product_id or body.label):
        raise HTTPException(422, "Provide card_id, product_id or a label with manual_value_nok")
    lot.items.append(LotItem(**body.model_dump()))
    db.flush()
    evaluate_listing(db, db.get(Listing, lot.listing_id), send_alerts=False)  # type: ignore[arg-type]
    return _out(db, lot)


@router.delete("/lots/{lot_id}/items/{item_id}", status_code=204)
def delete_item(lot_id: int, item_id: int, db: Session = Depends(get_db)) -> None:
    item = db.get(LotItem, item_id)
    if item and item.lot_id == lot_id:
        db.delete(item)


@router.post("/lots/{lot_id}/images", status_code=201)
async def upload_image(lot_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)) -> dict:
    lot = _lot(db, lot_id)
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image too large (max 10 MB)")
    ext = next((e for magic, e in MAGIC.items() if data.startswith(magic)), None)
    if not ext or (file.content_type and file.content_type not in ALLOWED_IMAGE):
        raise HTTPException(415, "Only JPEG, PNG or WebP images are accepted")
    folder = get_settings().data_dir / "uploads" / "lots" / str(lot_id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    (folder / name).write_bytes(data)
    lot.images = [*lot.images, name]
    return _out(db, lot)


@router.get("/lots/{lot_id}/images/{name}")
def get_image(lot_id: int, name: str) -> FileResponse:
    if Path(name).name != name or not name[:-4].isalnum():
        raise HTTPException(400, "Invalid image name")
    path = get_settings().data_dir / "uploads" / "lots" / str(lot_id) / name
    if not path.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(path)
