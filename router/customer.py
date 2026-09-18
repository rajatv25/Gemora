from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from model import Bill, Customer, CustomerPayment, CustomerTransaction, User
from schemas import CustomerCreate, CustomerPaymentCreate, CustomerTransactionCreate
from security import get_current_user

router = APIRouter(prefix="/customers", tags=["Customers"])
TRANSACTION_TYPES = {"udhaar", "return", "exchange"}


def get_customer(customer_id: int, user_id: int, db: Session) -> Customer:
    customer = db.query(Customer).filter(
        Customer.id == customer_id,
        Customer.user_id == user_id,
        Customer.is_archived.is_(False),
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


def serialize_customer(customer: Customer, db: Session) -> dict:
    purchases = sum(bill.total_amount for bill in customer.bills)
    payments = sum(payment.amount for payment in customer.payments)
    udhaar = sum(item.amount for item in customer.transactions if item.transaction_type == "udhaar")
    returns = sum(item.amount for item in customer.transactions if item.transaction_type == "return")
    return {
        "id": customer.id,
        "customer_id": customer.customer_code,
        "name": customer.name,
        "mobile_number": customer.mobile_number,
        "email": customer.email,
        "address": customer.address,
        "city": customer.city,
        "gstin": customer.gstin,
        "notes": customer.notes,
        "created_at": customer.created_at.strftime("%Y-%m-%d"),
        "total_purchases": round(purchases, 2),
        "total_payments": round(payments, 2),
        "outstanding_balance": round(purchases + udhaar - payments - returns, 2),
    }


def serialize_bill(bill: Bill) -> dict:
    return {
        "id": bill.id,
        "bill_number": bill.bill_number,
        "issue_date": bill.issue_date,
        "total_amount": bill.total_amount,
        "customer_name": bill.customer_name,
    }


@router.get("")
def list_customers(
    search: str = Query(""),
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Customer).filter(Customer.user_id == current_user.id)
    if not include_archived:
        query = query.filter(Customer.is_archived.is_(False))
    if search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(
            Customer.name.ilike(pattern)
            | Customer.mobile_number.ilike(pattern)
            | Customer.customer_code.ilike(pattern)
            | Customer.email.ilike(pattern)
        )
    customers = query.order_by(Customer.name.asc()).all()
    return {"customers": [serialize_customer(customer, db) for customer in customers], "count": len(customers)}


@router.post("", status_code=201)
def create_customer(
    customer_data: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not customer_data.name.strip() or not customer_data.mobile_number.strip():
        raise HTTPException(status_code=422, detail="Name and mobile number are required")
    existing = db.query(Customer).filter(
        Customer.user_id == current_user.id,
        Customer.mobile_number == customer_data.mobile_number.strip(),
        Customer.is_archived.is_(False),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A customer with this mobile number already exists")

    sequence = db.query(Customer).filter(Customer.user_id == current_user.id).count() + 1
    customer = Customer(
        user_id=current_user.id,
        customer_code=f"CUST-{sequence:04d}",
        name=customer_data.name.strip(),
        mobile_number=customer_data.mobile_number.strip(),
        email=customer_data.email.strip(),
        address=customer_data.address.strip(),
        city=customer_data.city.strip(),
        gstin=customer_data.gstin.strip(),
        notes=customer_data.notes.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return {"message": "Customer added successfully", "customer": serialize_customer(customer, db)}


@router.get("/payments/all")
def list_payments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    payments = db.query(CustomerPayment).filter(CustomerPayment.user_id == current_user.id).order_by(CustomerPayment.id.desc()).all()
    return {
        "payments": [
            {
                "id": payment.id,
                "customer": payment.customer.name if payment.customer else f"Customer #{payment.customer_id}",
                "customer_id": payment.customer_id,
                "amount": payment.amount,
                "payment_date": payment.payment_date,
                "payment_method": payment.payment_method,
                "bill_id": payment.bill_id,
                "notes": payment.notes,
            }
            for payment in payments
        ]
    }


@router.get("/{customer_id}")
def customer_profile(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = get_customer(customer_id, current_user.id, db)
    profile = serialize_customer(customer, db)
    bills = sorted(customer.bills, key=lambda bill: bill.id, reverse=True)
    payments = sorted(customer.payments, key=lambda payment: payment.id, reverse=True)
    transactions = sorted(customer.transactions, key=lambda transaction: transaction.id, reverse=True)
    profile.update({
        "purchase_history": [serialize_bill(bill) for bill in bills],
        "bills": [serialize_bill(bill) for bill in bills],
        "returns": [serialize_transaction(item) for item in transactions if item.transaction_type == "return"],
        "exchanges": [serialize_transaction(item) for item in transactions if item.transaction_type == "exchange"],
        "payment_history": [serialize_payment(payment) for payment in payments],
        "udhaar_transactions": [serialize_transaction(item) for item in transactions if item.transaction_type == "udhaar"],
    })
    return profile


def serialize_payment(payment: CustomerPayment) -> dict:
    return {
        "id": payment.id,
        "amount": payment.amount,
        "payment_date": payment.payment_date,
        "payment_method": payment.payment_method,
        "bill_id": payment.bill_id,
        "notes": payment.notes,
    }


def serialize_transaction(transaction: CustomerTransaction) -> dict:
    return {
        "id": transaction.id,
        "transaction_type": transaction.transaction_type,
        "amount": transaction.amount,
        "transaction_date": transaction.transaction_date,
        "bill_id": transaction.bill_id,
        "notes": transaction.notes,
    }


@router.put("/{customer_id}")
def update_customer(
    customer_id: int,
    customer_data: CustomerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = get_customer(customer_id, current_user.id, db)
    duplicate = db.query(Customer).filter(
        Customer.user_id == current_user.id,
        Customer.mobile_number == customer_data.mobile_number.strip(),
        Customer.id != customer.id,
        Customer.is_archived.is_(False),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="A customer with this mobile number already exists")
    for field in ("name", "mobile_number", "email", "address", "city", "gstin", "notes"):
        setattr(customer, field, getattr(customer_data, field).strip())
    db.commit()
    db.refresh(customer)
    return {"message": "Customer updated successfully", "customer": serialize_customer(customer, db)}


@router.delete("/{customer_id}")
def archive_customer(
    customer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = get_customer(customer_id, current_user.id, db)
    customer.is_archived = True
    db.commit()
    return {"message": "Customer archived successfully"}


@router.post("/{customer_id}/payments", status_code=201)
def add_payment(
    customer_id: int,
    payment_data: CustomerPaymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = get_customer(customer_id, current_user.id, db)
    if payment_data.amount <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero")
    if payment_data.bill_id:
        bill = db.query(Bill).filter(Bill.id == payment_data.bill_id, Bill.user_id == current_user.id).first()
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        if bill.customer_id != customer.id:
            raise HTTPException(status_code=400, detail="Bill is not linked to this customer")
    payment = CustomerPayment(
        user_id=current_user.id,
        customer_id=customer.id,
        bill_id=payment_data.bill_id,
        amount=payment_data.amount,
        payment_date=payment_data.payment_date,
        payment_method=payment_data.payment_method.strip() or "Cash",
        notes=payment_data.notes.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return {"message": "Payment recorded successfully", "payment": serialize_payment(payment)}


@router.post("/{customer_id}/transactions", status_code=201)
def add_transaction(
    customer_id: int,
    transaction_data: CustomerTransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    customer = get_customer(customer_id, current_user.id, db)
    transaction_type = transaction_data.transaction_type.lower().strip()
    if transaction_type not in TRANSACTION_TYPES:
        raise HTTPException(status_code=422, detail="Transaction type must be udhaar, return, or exchange")
    if transaction_data.amount < 0:
        raise HTTPException(status_code=422, detail="Amount cannot be negative")
    if transaction_data.bill_id:
        bill = db.query(Bill).filter(Bill.id == transaction_data.bill_id, Bill.user_id == current_user.id).first()
        if not bill:
            raise HTTPException(status_code=404, detail="Bill not found")
        if bill.customer_id != customer.id:
            raise HTTPException(status_code=400, detail="Bill is not linked to this customer")
    transaction = CustomerTransaction(
        user_id=current_user.id,
        customer_id=customer.id,
        bill_id=transaction_data.bill_id,
        transaction_type=transaction_type,
        amount=transaction_data.amount,
        transaction_date=transaction_data.transaction_date,
        notes=transaction_data.notes.strip(),
        created_at=datetime.utcnow(),
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return {"message": "Customer transaction recorded successfully", "transaction": serialize_transaction(transaction)}
