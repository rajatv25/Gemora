from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from model import Bill, BillItem, CalculatorRecord, Customer, CustomerPayment, CustomerTransaction, InventoryItem, InventoryTransaction, MetalRate, Purchase, User
from security import get_current_user
from schemas import BillCreate, CalculationSave, MetalRateCreate, PriceCalculationCreate

router = APIRouter(prefix="/jewellery", tags=["Jewellery Management"])

DEFAULT_RATES = {
    "Gold": 7200.0,
    "Silver": 85.0,
    "Platinum": 3600.0,
}
PURITY_PERCENTAGES = {"24K": 100.0, "22K": 91.6, "18K": 75.0, "14K": 58.5}


def calculate_metal_value(weight_grams: float, rate_per_gram: float, purity_percentage: float) -> float:
    effective_rate = rate_per_gram * (purity_percentage / 100)
    return weight_grams * effective_rate


def money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def calculate_breakdown(calculation: PriceCalculationCreate, rates: list[MetalRate]) -> dict:
    metal_name = calculation.metal_name.strip().title()
    if metal_name not in DEFAULT_RATES:
        raise HTTPException(status_code=422, detail="Metal must be Gold, Silver, or Platinum")

    purity_label = calculation.purity.strip().upper()
    if purity_label == "CUSTOM":
        purity_percentage = calculation.custom_purity_percentage
        if purity_percentage is None:
            raise HTTPException(status_code=422, detail="Custom purity percentage is required")
    else:
        purity_percentage = PURITY_PERCENTAGES.get(purity_label)
        if purity_percentage is None:
            raise HTTPException(status_code=422, detail="Purity must be 24K, 22K, 18K, 14K, or Custom")
    if not 0 < purity_percentage <= 100:
        raise HTTPException(status_code=422, detail="Purity percentage must be between 0 and 100")

    gross_weight = calculation.gross_weight if calculation.gross_weight is not None else calculation.weight_grams
    if gross_weight is None or gross_weight <= 0:
        raise HTTPException(status_code=422, detail="Gross weight must be greater than zero")
    if calculation.stone_weight < 0 or calculation.stone_weight > gross_weight:
        raise HTTPException(status_code=422, detail="Stone weight must be between zero and gross weight")
    net_weight = calculation.net_weight if calculation.net_weight is not None else gross_weight - calculation.stone_weight
    if net_weight < 0 or net_weight > gross_weight:
        raise HTTPException(status_code=422, detail="Net weight must be between zero and gross weight")
    numeric_fields = ("making_charge_per_gram", "making_charge_percentage", "wastage_percentage", "stone_charges", "diamond_charges", "discount_amount", "gst_percent")
    if any(getattr(calculation, field) < 0 for field in numeric_fields):
        raise HTTPException(status_code=422, detail="Charges, discount, and GST cannot be negative")

    rates_by_name = {rate.metal_name.lower(): rate for rate in rates}
    live_rate = rates_by_name.get(metal_name.lower())
    if not live_rate:
        raise HTTPException(status_code=400, detail=f"No live rate found for {metal_name}")
    metal_rate = calculation.metal_rate if calculation.metal_rate is not None else live_rate.rate_per_gram
    if metal_rate < 0:
        raise HTTPException(status_code=422, detail="Metal rate cannot be negative")

    net = Decimal(str(net_weight))
    rate = Decimal(str(metal_rate))
    purity = Decimal(str(purity_percentage)) / Decimal("100")
    adjusted_rate = rate * purity
    net_metal_value = net * adjusted_rate
    wastage_amount = net_metal_value * Decimal(str(calculation.wastage_percentage)) / Decimal("100")
    making_charges = net * Decimal(str(calculation.making_charge_per_gram)) + net_metal_value * Decimal(str(calculation.making_charge_percentage)) / Decimal("100")
    taxable_amount = net_metal_value + wastage_amount + making_charges + Decimal(str(calculation.stone_charges)) + Decimal(str(calculation.diamond_charges)) - Decimal(str(calculation.discount_amount))
    taxable_amount = max(taxable_amount, Decimal("0"))
    gst_amount = taxable_amount * Decimal(str(calculation.gst_percent)) / Decimal("100")
    final_amount = taxable_amount + gst_amount
    return {
        "item_name": calculation.item_name,
        "metal_name": metal_name,
        "purity": "Custom" if purity_label == "CUSTOM" else purity_label,
        "custom_purity_percentage": money(Decimal(str(purity_percentage))) if purity_label == "CUSTOM" else None,
        "purity_percentage": money(Decimal(str(purity_percentage))),
        "gross_weight": money(Decimal(str(gross_weight))),
        "stone_weight": money(Decimal(str(calculation.stone_weight))),
        "net_weight": money(Decimal(str(net_weight))),
        "metal_rate": money(rate),
        "purity_adjusted_rate": money(adjusted_rate),
        "making_charge_per_gram": money(Decimal(str(calculation.making_charge_per_gram))),
        "making_charge_percentage": money(Decimal(str(calculation.making_charge_percentage))),
        "wastage_percentage": money(Decimal(str(calculation.wastage_percentage))),
        "stone_charges": money(Decimal(str(calculation.stone_charges))),
        "diamond_charges": money(Decimal(str(calculation.diamond_charges))),
        "discount_amount": money(Decimal(str(calculation.discount_amount))),
        "gst_percent": money(Decimal(str(calculation.gst_percent))),
        "net_metal_value": money(net_metal_value),
        "wastage_amount": money(wastage_amount),
        "making_charges": money(making_charges),
        "taxable_amount": money(taxable_amount),
        "gst_amount": money(gst_amount),
        "final_amount": money(final_amount),
    }


def get_or_create_default_rates(current_user: User, db: Session) -> list[MetalRate]:
    rates = db.query(MetalRate).filter(MetalRate.user_id == current_user.id).all()
    existing_names = {rate.metal_name.lower() for rate in rates}
    added = False

    for metal_name, rate_per_gram in DEFAULT_RATES.items():
        if metal_name.lower() not in existing_names:
            db.add(MetalRate(
                user_id=current_user.id,
                metal_name=metal_name,
                rate_per_gram=rate_per_gram,
                purity_percentage=100.0,
                last_updated=datetime.utcnow(),
            ))
            added = True

    if added:
        db.commit()
        rates = db.query(MetalRate).filter(MetalRate.user_id == current_user.id).all()
    return rates


def find_rate(item_name: str, rates: list[MetalRate]) -> MetalRate:
    item_text = item_name.lower()
    rates_by_name = {rate.metal_name.lower(): rate for rate in rates}
    for metal_name in DEFAULT_RATES:
        if metal_name.lower() in item_text:
            rate = rates_by_name.get(metal_name.lower())
            if rate:
                return rate
    rate = rates_by_name.get("gold")
    if rate:
        return rate
    if rates:
        return rates[0]
    raise HTTPException(status_code=400, detail="No metal rates are available")


@router.get("/dashboard")
def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metal_rates = get_or_create_default_rates(current_user, db)
    bills = db.query(Bill).filter(Bill.user_id == current_user.id).order_by(Bill.id.desc()).all()
    customers = db.query(Customer).filter(Customer.user_id == current_user.id, Customer.is_archived.is_(False)).all()
    inventory = db.query(InventoryItem).filter(InventoryItem.user_id == current_user.id, InventoryItem.is_archived.is_(False)).all()
    payments = db.query(CustomerPayment).filter(CustomerPayment.user_id == current_user.id).all()
    customer_transactions = db.query(CustomerTransaction).filter(CustomerTransaction.user_id == current_user.id).all()
    today = datetime.utcnow().date().isoformat()
    today_sales = sum(bill.total_amount for bill in bills if bill.issue_date == today)
    outstanding_amount = sum(
        sum(bill.total_amount for bill in customer.bills)
        + sum(item.amount for item in customer.transactions if item.transaction_type == "udhaar")
        - sum(payment.amount for payment in customer.payments)
        - sum(item.amount for item in customer.transactions if item.transaction_type == "return")
        for customer in customers
    )
    active_inventory = [item for item in inventory if item.status != "Sold"]
    inventory_by_metal = {}
    for item in active_inventory:
        entry = inventory_by_metal.setdefault(item.metal_type, {"items": 0, "weight": 0.0})
        entry["items"] += 1
        entry["weight"] += item.net_metal_weight
    sales_by_day = []
    for offset in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=offset)).date().isoformat()
        sales_by_day.append({"date": day, "label": datetime.strptime(day, "%Y-%m-%d").strftime("%d %b"), "amount": round(sum(bill.total_amount for bill in bills if bill.issue_date == day), 2)})
    recent_transactions = []
    for bill in bills:
        recent_transactions.append({"type": "Sale", "label": bill.bill_number, "detail": bill.customer_name, "amount": bill.total_amount, "date": bill.issue_date, "created_at": bill.created_at})
    for payment in payments:
        recent_transactions.append({"type": "Payment", "label": payment.payment_method, "detail": f"Customer #{payment.customer_id}", "amount": payment.amount, "date": payment.payment_date, "created_at": payment.created_at})
    for purchase in db.query(Purchase).filter(Purchase.user_id == current_user.id).all():
        recent_transactions.append({"type": "Purchase", "label": purchase.product, "detail": purchase.supplier, "amount": purchase.total_amount, "date": purchase.purchase_date, "created_at": purchase.created_at})
    for transaction in customer_transactions:
        recent_transactions.append({"type": transaction.transaction_type.title(), "label": f"Customer #{transaction.customer_id}", "detail": transaction.notes, "amount": transaction.amount, "date": transaction.transaction_date, "created_at": transaction.created_at})
    recent_transactions.sort(key=lambda item: item["created_at"], reverse=True)

    rates_map = {rate.metal_name.lower(): rate for rate in metal_rates}
    total_sales = sum(bill.total_amount for bill in bills)

    return {
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
        },
        "rates": [
            {
                "id": rate.id,
                "metal_name": rate.metal_name,
                "rate_per_gram": rate.rate_per_gram,
                "purity_percentage": rate.purity_percentage,
                "last_updated": rate.last_updated.strftime("%d %b %Y"),
            }
            for rate in metal_rates
        ],
        "sales_summary": {
            "bill_count": len(bills),
            "total_sales": round(total_sales, 2),
            "latest_bill": bills[0].total_amount if bills else 0,
            "today_sales": round(today_sales, 2),
        },
        "kpis": {
            "today_sales": round(today_sales, 2),
            "total_customers": len(customers),
            "inventory_items": len(active_inventory),
            "outstanding_amount": round(outstanding_amount, 2),
            "gold_stock": round(inventory_by_metal.get("Gold", {}).get("weight", 0.0), 3),
        },
        "charts": {
            "sales": sales_by_day,
            "inventory_by_metal": [{"metal": metal, **values, "weight": round(values["weight"], 3)} for metal, values in inventory_by_metal.items()],
            "recent_transactions": [{key: value for key, value in item.items() if key != "created_at"} for item in recent_transactions[:8]],
        },
        "bills": [
            {
                "id": bill.id,
                "bill_number": bill.bill_number,
                "customer_name": bill.customer_name,
                "issue_date": bill.issue_date,
                "total_amount": bill.total_amount,
            }
            for bill in bills
        ],
        "live_rates": {
            metal: {
                "rate_per_gram": rate.rate_per_gram,
                "purity_percentage": rate.purity_percentage,
            }
            for metal, rate in rates_map.items()
        },
    }


@router.post("/calculate")
def calculate_price(
    calculation: PriceCalculationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rates = get_or_create_default_rates(current_user, db)
    return calculate_breakdown(calculation, rates)


@router.get("/reports")
def reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bills = db.query(Bill).filter(Bill.user_id == current_user.id).order_by(Bill.issue_date.desc(), Bill.id.desc()).all()
    inventory = db.query(InventoryItem).filter(InventoryItem.user_id == current_user.id, InventoryItem.is_archived.is_(False)).order_by(InventoryItem.updated_at.desc()).all()
    customers = db.query(Customer).filter(Customer.user_id == current_user.id, Customer.is_archived.is_(False)).all()
    return {
        "sales_report": [{"bill_number": bill.bill_number, "date": bill.issue_date, "customer": bill.customer_name, "amount": bill.total_amount} for bill in bills],
        "inventory_report": [{"sku": item.sku, "product": item.product_name, "metal": item.metal_type, "purity": item.purity, "weight": item.net_metal_weight, "status": item.status, "value": item.purchase_price} for item in inventory],
        "customer_outstanding_report": [
            {
                "customer_id": customer.customer_code,
                "customer": customer.name,
                "mobile": customer.mobile_number,
                "outstanding": round(
                    sum(bill.total_amount for bill in customer.bills)
                    + sum(item.amount for item in customer.transactions if item.transaction_type == "udhaar")
                    - sum(payment.amount for payment in customer.payments)
                    - sum(item.amount for item in customer.transactions if item.transaction_type == "return"), 2,
                ),
            }
            for customer in customers
        ],
    }


@router.post("/calculate/save")
def save_calculation(
    save_data: CalculationSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record_type = save_data.record_type.strip().lower()
    if record_type not in ("estimate", "bill"):
        raise HTTPException(status_code=422, detail="Record type must be Estimate or Bill")
    customer = None
    if save_data.customer_id:
        customer = db.query(Customer).filter(Customer.id == save_data.customer_id, Customer.user_id == current_user.id, Customer.is_archived.is_(False)).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
    breakdown = calculate_breakdown(save_data.calculation, get_or_create_default_rates(current_user, db))
    bill = None
    if record_type == "bill":
        bill_number = f"JWL-{datetime.now().strftime('%d%m%Y')}-{db.query(Bill).filter(Bill.user_id == current_user.id).count() + 1:04d}"
        bill = Bill(
            user_id=current_user.id, customer_id=customer.id if customer else None,
            bill_number=bill_number, customer_name=customer.name if customer else "Walk-in customer",
            issue_date=datetime.now().strftime("%Y-%m-%d"), subtotal=breakdown["net_metal_value"],
            making_charge=breakdown["making_charges"], gst_amount=breakdown["gst_amount"], total_amount=breakdown["final_amount"],
            gross_weight=breakdown["gross_weight"], stone_weight=breakdown["stone_weight"], net_weight=breakdown["net_weight"],
            metal_rate=breakdown["metal_rate"], purity_percentage=breakdown["purity_percentage"], making_charge_percentage=breakdown["making_charge_percentage"],
            wastage_amount=breakdown["wastage_amount"], stone_charges=breakdown["stone_charges"], diamond_charges=breakdown["diamond_charges"],
            discount_amount=breakdown["discount_amount"], gst_percent=breakdown["gst_percent"], notes="Saved from jewellery calculator",
        )
        db.add(bill)
        db.flush()
        db.add(BillItem(bill_id=bill.id, product_name=breakdown["item_name"], metal_name=breakdown["metal_name"], weight_grams=breakdown["net_weight"], purity_percentage=breakdown["purity_percentage"], rate_per_gram=breakdown["metal_rate"], making_charge=breakdown["making_charges"], gst_percent=breakdown["gst_percent"], item_total=breakdown["final_amount"], created_at=datetime.utcnow()))
    record = CalculatorRecord(user_id=current_user.id, customer_id=customer.id if customer else None, bill_id=bill.id if bill else None, record_type=record_type, item_name=breakdown["item_name"], metal_name=breakdown["metal_name"], purity_label=breakdown["purity"], **{key: breakdown[key] for key in ("purity_percentage", "gross_weight", "stone_weight", "net_weight", "metal_rate", "purity_adjusted_rate", "making_charge_per_gram", "making_charge_percentage", "wastage_percentage", "stone_charges", "diamond_charges", "discount_amount", "gst_percent", "net_metal_value", "wastage_amount", "making_charges", "taxable_amount", "gst_amount", "final_amount")})
    db.add(record)
    db.commit()
    return {"message": f"{record_type.title()} saved successfully", "record_id": record.id, "bill_number": bill.bill_number if bill else None, "breakdown": breakdown}


@router.post("/rates")
def set_metal_rate(
    rate_data: MetalRateCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(MetalRate)
        .filter(
            MetalRate.user_id == current_user.id,
            func.lower(MetalRate.metal_name) == rate_data.metal_name.lower(),
        )
        .first()
    )

    if existing:
        existing.rate_per_gram = rate_data.rate_per_gram
        existing.purity_percentage = rate_data.purity_percentage
        existing.last_updated = datetime.utcnow()
        db.commit()
        return {"message": "Metal rate updated successfully"}

    metal_rate = MetalRate(
        user_id=current_user.id,
        metal_name=rate_data.metal_name,
        rate_per_gram=rate_data.rate_per_gram,
        purity_percentage=rate_data.purity_percentage,
        last_updated=datetime.utcnow(),
    )
    db.add(metal_rate)
    db.commit()
    db.refresh(metal_rate)
    return {"message": "Metal rate added successfully", "rate_id": metal_rate.id}


@router.post("/bill/preview")
def preview_bill(
    bill_data: BillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    metal_rates = get_or_create_default_rates(current_user, db)
    rates_map = {rate.metal_name.lower(): rate for rate in metal_rates}

    items = []
    subtotal = 0.0
    total_making = 0.0
    total_gst = 0.0

    for item in bill_data.items:
        rate = rates_map.get(item.metal_name.lower())
        if not rate:
            raise HTTPException(status_code=400, detail=f"Live rate not found for {item.metal_name}")

        metal_value = calculate_metal_value(item.weight_grams, rate.rate_per_gram, item.purity_percentage)
        item_total = metal_value + item.making_charge
        gst = item_total * (item.gst_percent / 100)
        full_total = item_total + gst

        subtotal += metal_value
        total_making += item.making_charge
        total_gst += gst

        items.append({
            "product_name": item.product_name,
            "metal_name": item.metal_name,
            "weight_grams": item.weight_grams,
            "purity_percentage": item.purity_percentage,
            "rate_per_gram": rate.rate_per_gram,
            "making_charge": item.making_charge,
            "gst_percent": item.gst_percent,
            "metal_value": round(metal_value, 2),
            "gst_amount": round(gst, 2),
            "item_total": round(full_total, 2),
        })

    total_amount = round(subtotal + total_making + total_gst, 2)

    return {
        "customer_name": bill_data.customer_name,
        "issue_date": bill_data.issue_date,
        "subtotal": round(subtotal, 2),
        "making_charge": round(total_making, 2),
        "gst_amount": round(total_gst, 2),
        "total_amount": total_amount,
        "items": items,
    }


@router.post("/bill/create")
def create_bill(
    bill_data: BillCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preview = preview_bill(bill_data, current_user, db)

    customer = None
    if bill_data.customer_id:
        customer = db.query(Customer).filter(
            Customer.id == bill_data.customer_id,
            Customer.user_id == current_user.id,
            Customer.is_archived.is_(False),
        ).first()
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

    bill_number = f"JWL-{datetime.now().strftime('%d%m%Y')}-{len(db.query(Bill).filter(Bill.user_id == current_user.id).all()) + 1:04d}"
    bill = Bill(
        user_id=current_user.id,
        bill_number=bill_number,
        customer_name=customer.name if customer else bill_data.customer_name,
        customer_id=customer.id if customer else None,
        issue_date=bill_data.issue_date,
        subtotal=preview["subtotal"],
        making_charge=preview["making_charge"],
        gst_amount=preview["gst_amount"],
        total_amount=preview["total_amount"],
        notes=bill_data.notes,
        created_at=datetime.utcnow(),
    )
    db.add(bill)
    db.flush()
    db.refresh(bill)

    for item in bill_data.items:
        rate = db.query(MetalRate).filter(
            MetalRate.user_id == current_user.id,
            func.lower(MetalRate.metal_name) == item.metal_name.lower(),
        ).first()
        if not rate:
            raise HTTPException(status_code=400, detail=f"Live rate not found for {item.metal_name}")

        metal_value = calculate_metal_value(item.weight_grams, rate.rate_per_gram, item.purity_percentage)
        item_total = metal_value + item.making_charge
        gst = item_total * (item.gst_percent / 100)

        db.add(BillItem(
            bill_id=bill.id,
            product_name=item.product_name,
            metal_name=item.metal_name,
            weight_grams=item.weight_grams,
            purity_percentage=item.purity_percentage,
            rate_per_gram=rate.rate_per_gram,
            making_charge=item.making_charge,
            gst_percent=item.gst_percent,
            item_total=round(item_total + gst, 2),
            created_at=datetime.utcnow(),
        ))

        inventory_sku = item.inventory_sku.strip() or item.product_name.strip()
        inventory_item = db.query(InventoryItem).filter(
            InventoryItem.user_id == current_user.id,
            InventoryItem.sku == inventory_sku,
            InventoryItem.is_archived.is_(False),
        ).first()
        if inventory_item:
            if inventory_item.status != "In Stock":
                raise HTTPException(status_code=409, detail=f"Inventory item {inventory_item.sku} is {inventory_item.status}")
            inventory_item.status = "Sold"
            inventory_item.updated_at = datetime.utcnow()
            db.add(InventoryTransaction(
                inventory_item_id=inventory_item.id,
                user_id=current_user.id,
                movement_type="sale",
                quantity=1,
                status_before="In Stock",
                status_after="Sold",
                reference=bill.bill_number,
                notes="Automatically marked sold from bill",
                created_at=datetime.utcnow(),
            ))

    db.commit()
    return {"message": "Bill created successfully", "bill_number": bill.bill_number, "total_amount": preview["total_amount"]}


@router.get("/bill/{bill_id}/download")
def download_bill(
    bill_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bill = db.query(Bill).filter(Bill.id == bill_id, Bill.user_id == current_user.id).first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    items = db.query(BillItem).filter(BillItem.bill_id == bill.id).all()
    content = [
        "Gemora Jewellery Management",
        "========================",
        f"Bill No: {bill.bill_number}",
        f"Customer: {bill.customer_name}",
        f"Date: {bill.issue_date}",
        "",
        "Item Details:",
    ]

    for idx, item in enumerate(items, start=1):
        content.append(
            f"{idx}. {item.product_name} | {item.metal_name} | {item.weight_grams}g | Rate: ₹{item.rate_per_gram}/g | Total: ₹{item.item_total}"
        )

    content.extend([
        "",
        f"Subtotal: ₹{bill.subtotal}",
        f"Making Charge: ₹{bill.making_charge}",
        f"GST: ₹{bill.gst_amount}",
        f"Total: ₹{bill.total_amount}",
        f"Notes: {bill.notes or 'N/A'}",
    ])

    buffer = BytesIO("\n".join(content).encode("utf-8"))
    return StreamingResponse(
        buffer,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="bill_{bill.bill_number}.txt"'},
    )
