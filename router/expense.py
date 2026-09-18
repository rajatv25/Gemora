from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from model import Budget, Expense, User
from security import get_current_user
from schemas import BudgetCreate, ExpenseCreate

router = APIRouter(prefix="/expenses", tags=["Jewellery Management"])


@router.get("/dashboard")
def dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inventory = (
        db.query(Expense)
        .filter(Expense.user_id == current_user.id)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .all()
    )
    targets = db.query(Budget).filter(Budget.user_id == current_user.id).all()

    total_inventory_value = round(sum(item.amount for item in inventory), 2)
    monthly_target = sum(target.limit for target in targets)
    remaining_to_target = round(monthly_target - total_inventory_value, 2)

    by_category = {}
    for item in inventory:
        by_category[item.category] = by_category.get(item.category, 0) + item.amount

    inventory_data = [
        {
            "id": item.id,
            "title": item.title,
            "category": item.category,
            "amount": item.amount,
            "date": item.date,
            "notes": item.notes,
        }
        for item in inventory
    ]

    targets_data = [
        {
            "id": target.id,
            "category": target.category,
            "limit": target.limit,
            "month": target.month,
        }
        for target in targets
    ]

    return {
        "user": {
            "id": current_user.id,
            "full_name": current_user.full_name,
            "email": current_user.email,
        },
        "stats": {
            "total_inventory_value": total_inventory_value,
            "monthly_target": monthly_target,
            "remaining_to_target": remaining_to_target,
            "inventory_count": len(inventory),
        },
        "inventory": inventory_data,
        "expenses": inventory_data,
        "budgets": targets_data,
        "targets": targets_data,
        "category_totals": {key: round(value, 2) for key, value in by_category.items()},
    }


@router.post("/add")
def add_inventory_item(
    item: ExpenseCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inventory_item = Expense(
        user_id=current_user.id,
        title=item.title,
        category=item.category,
        amount=item.amount,
        date=item.date,
        notes=item.notes,
        created_at=datetime.utcnow(),
    )
    db.add(inventory_item)
    db.commit()
    db.refresh(inventory_item)
    return {"message": "Jewellery item added successfully", "expense": inventory_item.id}


@router.post("/budgets")
def add_target(
    budget_data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = Budget(
        user_id=current_user.id,
        category=budget_data.category,
        limit=budget_data.limit,
        month=budget_data.month,
        created_at=datetime.utcnow(),
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    return {"message": "Sales target added successfully", "budget": target.id}


@router.delete("/delete/{expense_id}")
def delete_inventory_item(
    expense_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    inventory_item = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.user_id == current_user.id)
        .first()
    )
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Jewellery item not found")

    db.delete(inventory_item)
    db.commit()
    return {"message": "Jewellery item deleted successfully"}
