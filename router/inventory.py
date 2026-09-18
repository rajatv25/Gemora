from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from model import InventoryItem, InventoryTransaction, User
from schemas import INVENTORY_MOVEMENTS, INVENTORY_STATUSES, InventoryItemCreate, InventoryItemUpdate, InventoryStockMovement
from security import get_current_user

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def validate_item(item: InventoryItemCreate) -> None:
    if item.status not in INVENTORY_STATUSES:
        raise HTTPException(status_code=422, detail=f"Status must be one of: {', '.join(INVENTORY_STATUSES)}")
    if item.metal_type.title() not in ("Gold", "Silver", "Platinum"):
        raise HTTPException(status_code=422, detail="Metal type must be Gold, Silver, or Platinum")
    if item.gross_weight <= 0:
        raise HTTPException(status_code=422, detail="Gross weight must be greater than zero")
    if item.stone_weight < 0 or item.stone_weight > item.gross_weight:
        raise HTTPException(status_code=422, detail="Stone weight must be between zero and gross weight")
    if item.net_metal_weight is not None and not 0 <= item.net_metal_weight <= item.gross_weight:
        raise HTTPException(status_code=422, detail="Net metal weight must be between zero and gross weight")
    for field_name in ("making_charges", "wastage_percentage", "stone_charges", "diamond_charges", "purchase_price", "selling_price"):
        if getattr(item, field_name) < 0:
            raise HTTPException(status_code=422, detail=f"{field_name.replace('_', ' ').title()} cannot be negative")
    if item.wastage_percentage > 100:
        raise HTTPException(status_code=422, detail="Wastage percentage cannot exceed 100")


def to_model(item: InventoryItemCreate, user_id: int) -> InventoryItem:
    values = item.model_dump()
    values["metal_type"] = item.metal_type.title()
    values["net_metal_weight"] = item.net_metal_weight if item.net_metal_weight is not None else item.gross_weight - item.stone_weight
    return InventoryItem(user_id=user_id, **values)


def serialize_item(item: InventoryItem) -> dict:
    return {
        "id": item.id,
        "sku": item.sku,
        "product_name": item.product_name,
        "category": item.category,
        "subcategory": item.subcategory,
        "metal_type": item.metal_type,
        "purity": item.purity,
        "gross_weight": item.gross_weight,
        "stone_weight": item.stone_weight,
        "net_metal_weight": item.net_metal_weight,
        "making_charges": item.making_charges,
        "wastage_percentage": item.wastage_percentage,
        "stone_charges": item.stone_charges,
        "diamond_charges": item.diamond_charges,
        "purchase_price": item.purchase_price,
        "selling_price": item.selling_price,
        "hallmark_huid": item.hallmark_huid,
        "barcode": item.barcode,
        "qr_code": item.qr_code,
        "product_image": item.product_image,
        "supplier": item.supplier,
        "karigar": item.karigar,
        "status": item.status,
        "is_archived": item.is_archived,
        "created_at": item.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": item.updated_at.strftime("%Y-%m-%d %H:%M"),
    }


def get_item(item_id: int, user_id: int, db: Session) -> InventoryItem:
    item = db.query(InventoryItem).filter(
        InventoryItem.id == item_id,
        InventoryItem.user_id == user_id,
        InventoryItem.is_archived.is_(False),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item


def record_movement(item: InventoryItem, user_id: int, movement_type: str, db: Session, reference: str = "", notes: str = "") -> None:
    status_before = item.status
    if movement_type == "purchase" or movement_type == "return":
        if item.status not in ("Sold", "Under Repair") and movement_type == "purchase":
            raise HTTPException(status_code=409, detail="Only sold or under-repair items can be received as a purchase")
        status_after = "In Stock"
    elif movement_type == "sale" or movement_type == "exchange":
        if item.status != "In Stock":
            raise HTTPException(status_code=409, detail=f"Cannot {movement_type} an item with status {item.status}")
        status_after = "Sold"
    else:
        status_after = item.status

    item.status = status_after
    item.updated_at = datetime.utcnow()
    db.add(InventoryTransaction(
        inventory_item_id=item.id,
        user_id=user_id,
        movement_type=movement_type,
        quantity=1,
        status_before=status_before,
        status_after=status_after,
        reference=reference,
        notes=notes,
        created_at=datetime.utcnow(),
    ))


@router.get("")
def list_inventory(
    search: str = Query(""),
    category: str = Query(""),
    metal_type: str = Query(""),
    purity: str = Query(""),
    status: str = Query(""),
    sort_by: str = Query("updated_at"),
    sort_order: str = Query("desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(InventoryItem).filter(
        InventoryItem.user_id == current_user.id,
        InventoryItem.is_archived.is_(False),
    )
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter((InventoryItem.sku.ilike(pattern)) | (InventoryItem.product_name.ilike(pattern)))
    if category:
        query = query.filter(InventoryItem.category == category)
    if metal_type:
        query = query.filter(InventoryItem.metal_type == metal_type.title())
    if purity:
        query = query.filter(InventoryItem.purity == purity)
    if status:
        query = query.filter(InventoryItem.status == status)

    sortable = {
        "sku": InventoryItem.sku,
        "product_name": InventoryItem.product_name,
        "category": InventoryItem.category,
        "selling_price": InventoryItem.selling_price,
        "created_at": InventoryItem.created_at,
        "updated_at": InventoryItem.updated_at,
    }
    sort_column = sortable.get(sort_by, InventoryItem.updated_at)
    query = query.order_by(sort_column.asc() if sort_order.lower() == "asc" else sort_column.desc())
    items = query.all()
    return {"items": [serialize_item(item) for item in items], "count": len(items)}


@router.post("", status_code=201)
def create_inventory_item(
    item_data: InventoryItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    validate_item(item_data)
    duplicate = db.query(InventoryItem).filter(
        InventoryItem.user_id == current_user.id,
        InventoryItem.sku == item_data.sku.strip(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="SKU already exists for this store")

    item = to_model(item_data, current_user.id)
    db.add(item)
    db.flush()
    db.add(InventoryTransaction(
        inventory_item_id=item.id,
        user_id=current_user.id,
        movement_type="purchase",
        quantity=1,
        status_before="Not tracked",
        status_after=item.status,
        reference=item.sku,
        notes="Opening inventory item",
        created_at=datetime.utcnow(),
    ))
    db.commit()
    db.refresh(item)
    return {"message": "Jewellery item added successfully", "item": serialize_item(item)}


@router.get("/{item_id}")
def inventory_detail(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_item(item_id, current_user.id, db)
    return {"item": serialize_item(item)}


@router.put("/{item_id}")
def update_inventory_item(
    item_id: int,
    item_data: InventoryItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    validate_item(item_data)
    item = get_item(item_id, current_user.id, db)
    duplicate = db.query(InventoryItem).filter(
        InventoryItem.user_id == current_user.id,
        InventoryItem.sku == item_data.sku.strip(),
        InventoryItem.id != item.id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="SKU already exists for this store")

    old_status = item.status
    values = item_data.model_dump()
    values["metal_type"] = item_data.metal_type.title()
    values["net_metal_weight"] = item_data.net_metal_weight if item_data.net_metal_weight is not None else item_data.gross_weight - item_data.stone_weight
    for key, value in values.items():
        setattr(item, key, value)
    item.updated_at = datetime.utcnow()
    if old_status != item.status:
        db.add(InventoryTransaction(
            inventory_item_id=item.id,
            user_id=current_user.id,
            movement_type="adjustment",
            quantity=1,
            status_before=old_status,
            status_after=item.status,
            reference=item.sku,
            notes="Status changed while editing item",
            created_at=datetime.utcnow(),
        ))
    db.commit()
    db.refresh(item)
    return {"message": "Inventory item updated successfully", "item": serialize_item(item)}


@router.delete("/{item_id}")
def archive_inventory_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_item(item_id, current_user.id, db)
    item.is_archived = True
    item.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Inventory item archived successfully"}


@router.post("/{item_id}/movement")
def inventory_movement(
    item_id: int,
    movement: InventoryStockMovement,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if movement.movement_type not in INVENTORY_MOVEMENTS:
        raise HTTPException(status_code=422, detail=f"Movement must be one of: {', '.join(INVENTORY_MOVEMENTS)}")
    item = get_item(item_id, current_user.id, db)
    record_movement(item, current_user.id, movement.movement_type, db, movement.reference, movement.notes)
    db.commit()
    db.refresh(item)
    return {"message": "Stock movement recorded successfully", "item": serialize_item(item)}


@router.get("/{item_id}/history")
def inventory_history(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = get_item(item_id, current_user.id, db)
    history = db.query(InventoryTransaction).filter(
        InventoryTransaction.inventory_item_id == item.id,
        InventoryTransaction.user_id == current_user.id,
    ).order_by(InventoryTransaction.created_at.desc()).all()
    return {
        "item": serialize_item(item),
        "history": [
            {
                "id": entry.id,
                "movement_type": entry.movement_type,
                "quantity": entry.quantity,
                "status_before": entry.status_before,
                "status_after": entry.status_after,
                "reference": entry.reference,
                "notes": entry.notes,
                "created_at": entry.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for entry in history
        ],
    }
