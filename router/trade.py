from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from model import Customer, CustomerTransaction, GoldExchange, InventoryItem, InventoryTransaction, Purchase, User
from schemas import ExchangeCreate, PurchaseCreate
from security import get_current_user

router = APIRouter(prefix="/trade", tags=["Purchases and Exchange"])


def purity_percentage(purity: str) -> float:
    value = purity.strip().upper().replace("K", "")
    try:
        numeric_value = float(value)
        if numeric_value <= 24:
            percentage = numeric_value / 24 * 100
        elif numeric_value <= 100:
            percentage = numeric_value
        else:
            percentage = numeric_value / 10
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Purity must be a karat value such as 22K or 916") from error
    if not 0 < percentage <= 100:
        raise HTTPException(status_code=422, detail="Purity must be between 0 and 100")
    return percentage


def serialize_purchase(purchase: Purchase) -> dict:
    return {
        "id": purchase.id,
        "supplier": purchase.supplier,
        "product": purchase.product,
        "metal": purchase.metal,
        "purity": purchase.purity,
        "weight": purchase.weight,
        "rate": purchase.rate,
        "total_amount": purchase.total_amount,
        "purchase_date": purchase.purchase_date,
        "inventory_item_id": purchase.inventory_item_id,
    }


def serialize_exchange(exchange: GoldExchange) -> dict:
    return {
        "id": exchange.id,
        "customer_id": exchange.customer_id,
        "old_jewellery_weight": exchange.old_jewellery_weight,
        "old_purity": exchange.old_purity,
        "current_metal_rate": exchange.current_metal_rate,
        "exchange_value": exchange.exchange_value,
        "new_jewellery": exchange.new_jewellery,
        "new_jewellery_amount": exchange.new_jewellery_amount,
        "difference_amount": exchange.difference_amount,
        "exchange_date": exchange.exchange_date,
        "old_inventory_item_id": exchange.old_inventory_item_id,
        "new_inventory_item_id": exchange.new_inventory_item_id,
    }


@router.get("/purchases")
def list_purchases(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    purchases = db.query(Purchase).filter(Purchase.user_id == current_user.id).order_by(Purchase.id.desc()).all()
    return {"purchases": [serialize_purchase(purchase) for purchase in purchases]}


@router.post("/purchases", status_code=201)
def create_purchase(
    purchase_data: PurchaseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if purchase_data.weight <= 0 or purchase_data.rate < 0 or purchase_data.total_amount < 0:
        raise HTTPException(status_code=422, detail="Weight must be positive and amounts cannot be negative")
    metal = purchase_data.metal.strip().title()
    if metal not in ("Gold", "Silver", "Platinum"):
        raise HTTPException(status_code=422, detail="Metal must be Gold, Silver, or Platinum")
    sku = purchase_data.sku.strip() or f"PUR-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    if db.query(InventoryItem).filter(InventoryItem.user_id == current_user.id, InventoryItem.sku == sku).first():
        raise HTTPException(status_code=409, detail="SKU already exists for this store")
    item = InventoryItem(
        user_id=current_user.id, sku=sku, product_name=purchase_data.product.strip(), category=purchase_data.category.strip() or "Purchased jewellery",
        subcategory="Purchase", metal_type=metal, purity=purchase_data.purity.strip(), gross_weight=purchase_data.weight,
        stone_weight=0.0, net_metal_weight=purchase_data.weight, purchase_price=purchase_data.total_amount,
        selling_price=0.0, supplier=purchase_data.supplier.strip(), status="In Stock", created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
    )
    db.add(item)
    db.flush()
    purchase = Purchase(
        user_id=current_user.id, inventory_item_id=item.id, supplier=purchase_data.supplier.strip(), product=purchase_data.product.strip(),
        metal=metal, purity=purchase_data.purity.strip(), weight=purchase_data.weight, rate=purchase_data.rate,
        total_amount=purchase_data.total_amount, purchase_date=purchase_data.purchase_date, created_at=datetime.utcnow(),
    )
    db.add(purchase)
    db.add(InventoryTransaction(
        inventory_item_id=item.id, user_id=current_user.id, movement_type="purchase", quantity=1, status_before="Not tracked",
        status_after="In Stock", reference=sku, notes="Stock added from supplier purchase", created_at=datetime.utcnow(),
    ))
    db.commit()
    db.refresh(purchase)
    return {"message": "Purchase saved and inventory increased", "purchase": serialize_purchase(purchase)}


@router.get("/exchanges")
def list_exchanges(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    exchanges = db.query(GoldExchange).filter(GoldExchange.user_id == current_user.id).order_by(GoldExchange.id.desc()).all()
    return {"exchanges": [serialize_exchange(exchange) for exchange in exchanges]}


@router.post("/exchanges", status_code=201)
def create_exchange(
    exchange_data: ExchangeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if exchange_data.old_jewellery_weight <= 0 or exchange_data.current_metal_rate < 0 or exchange_data.new_jewellery_amount < 0:
        raise HTTPException(status_code=422, detail="Weight must be positive and amounts cannot be negative")
    customer = db.query(Customer).filter(Customer.id == exchange_data.customer_id, Customer.user_id == current_user.id, Customer.is_archived.is_(False)).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    old_item = None
    if exchange_data.old_inventory_item_id:
        old_item = db.query(InventoryItem).filter(InventoryItem.id == exchange_data.old_inventory_item_id, InventoryItem.user_id == current_user.id, InventoryItem.is_archived.is_(False)).first()
        if not old_item:
            raise HTTPException(status_code=404, detail="Old jewellery inventory item not found")
        if old_item.status not in ("Sold", "Under Repair"):
            raise HTTPException(status_code=409, detail="Old jewellery must be sold or under repair before exchange-in")
    new_item = None
    if exchange_data.new_inventory_item_id:
        new_item = db.query(InventoryItem).filter(InventoryItem.id == exchange_data.new_inventory_item_id, InventoryItem.user_id == current_user.id, InventoryItem.is_archived.is_(False)).first()
        if not new_item or new_item.status != "In Stock":
            raise HTTPException(status_code=409, detail="New jewellery must be available in inventory")
        new_amount = new_item.selling_price if new_item.selling_price > 0 else new_item.purchase_price
    else:
        new_amount = exchange_data.new_jewellery_amount
    exchange_value = exchange_data.old_jewellery_weight * exchange_data.current_metal_rate * purity_percentage(exchange_data.old_purity) / 100
    difference_amount = new_amount - exchange_value
    exchange = GoldExchange(
        user_id=current_user.id, customer_id=customer.id, old_inventory_item_id=old_item.id if old_item else None, new_inventory_item_id=new_item.id if new_item else None,
        old_jewellery_weight=exchange_data.old_jewellery_weight, old_purity=exchange_data.old_purity.strip(), current_metal_rate=exchange_data.current_metal_rate,
        exchange_value=round(exchange_value, 2), new_jewellery=exchange_data.new_jewellery.strip() or (new_item.product_name if new_item else "New jewellery"),
        new_jewellery_amount=round(new_amount, 2), difference_amount=round(difference_amount, 2), exchange_date=exchange_data.exchange_date, created_at=datetime.utcnow(),
    )
    db.add(exchange)
    if old_item:
        old_status = old_item.status
        old_item.status = "In Stock"
        old_item.updated_at = datetime.utcnow()
        db.add(InventoryTransaction(inventory_item_id=old_item.id, user_id=current_user.id, movement_type="return", quantity=1, status_before=old_status, status_after="In Stock", reference="EXCHANGE-IN", notes="Old jewellery received from customer", created_at=datetime.utcnow()))
    if new_item:
        new_item.status = "Sold"
        new_item.updated_at = datetime.utcnow()
        db.add(InventoryTransaction(inventory_item_id=new_item.id, user_id=current_user.id, movement_type="exchange", quantity=1, status_before="In Stock", status_after="Sold", reference="EXCHANGE-OUT", notes="New jewellery issued in customer exchange", created_at=datetime.utcnow()))
    db.add(CustomerTransaction(user_id=current_user.id, customer_id=customer.id, transaction_type="exchange", amount=round(exchange_value, 2), transaction_date=exchange_data.exchange_date, notes=f"Gold exchange: {exchange_data.old_jewellery_weight}g old jewellery for {exchange.new_jewellery}"))
    db.commit()
    db.refresh(exchange)
    return {"message": "Gold exchange saved successfully", "exchange": serialize_exchange(exchange)}