from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, Float, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    hash_password: Mapped[str] = mapped_column(String(100), nullable=False)
    create_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    update_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    customers: Mapped[list["Customer"]] = relationship(back_populates="user")


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (Index("ix_customer_user_mobile", "user_id", "mobile_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    customer_code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    address: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    city: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    gstin: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    notes: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user: Mapped["User"] = relationship(back_populates="customers")
    bills: Mapped[list["Bill"]] = relationship(back_populates="customer")
    payments: Mapped[list["CustomerPayment"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    transactions: Mapped[list["CustomerTransaction"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    exchanges: Mapped[list["GoldExchange"]] = relationship(back_populates="customer")


class MetalRate(Base):
    __tablename__ = "metal_rates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    metal_name: Mapped[str] = mapped_column(String(40), nullable=False)
    rate_per_gram: Mapped[float] = mapped_column(Float, nullable=False)
    purity_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    limit: Mapped[float] = mapped_column(Float, nullable=False)
    month: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Bill(Base):
    __tablename__ = "bills"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    bill_number: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_date: Mapped[str] = mapped_column(String(30), nullable=False)
    subtotal: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    making_charge: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gst_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gross_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stone_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    metal_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    purity_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    making_charge_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wastage_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stone_charges: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    diamond_charges: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gst_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    customer: Mapped["Customer | None"] = relationship(back_populates="bills")
    payments: Mapped[list["CustomerPayment"]] = relationship(back_populates="bill")
    transactions: Mapped[list["CustomerTransaction"]] = relationship(back_populates="bill")


class CalculatorRecord(Base):
    __tablename__ = "calculator_records"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    record_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metal_name: Mapped[str] = mapped_column(String(30), nullable=False)
    purity_label: Mapped[str] = mapped_column(String(20), nullable=False)
    purity_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    gross_weight: Mapped[float] = mapped_column(Float, nullable=False)
    stone_weight: Mapped[float] = mapped_column(Float, nullable=False)
    net_weight: Mapped[float] = mapped_column(Float, nullable=False)
    metal_rate: Mapped[float] = mapped_column(Float, nullable=False)
    purity_adjusted_rate: Mapped[float] = mapped_column(Float, nullable=False)
    making_charge_per_gram: Mapped[float] = mapped_column(Float, nullable=False)
    making_charge_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    wastage_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    stone_charges: Mapped[float] = mapped_column(Float, nullable=False)
    diamond_charges: Mapped[float] = mapped_column(Float, nullable=False)
    discount_amount: Mapped[float] = mapped_column(Float, nullable=False)
    gst_percent: Mapped[float] = mapped_column(Float, nullable=False)
    net_metal_value: Mapped[float] = mapped_column(Float, nullable=False)
    wastage_amount: Mapped[float] = mapped_column(Float, nullable=False)
    making_charges: Mapped[float] = mapped_column(Float, nullable=False)
    taxable_amount: Mapped[float] = mapped_column(Float, nullable=False)
    gst_amount: Mapped[float] = mapped_column(Float, nullable=False)
    final_amount: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class CustomerPayment(Base):
    __tablename__ = "customer_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_date: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), default="Cash", nullable=False)
    notes: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    customer: Mapped["Customer"] = relationship(back_populates="payments")
    bill: Mapped["Bill | None"] = relationship(back_populates="payments")


class CustomerTransaction(Base):
    __tablename__ = "customer_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    bill_id: Mapped[int | None] = mapped_column(ForeignKey("bills.id"), nullable=True, index=True)
    transaction_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    transaction_date: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    customer: Mapped["Customer"] = relationship(back_populates="transactions")
    bill: Mapped["Bill | None"] = relationship(back_populates="transactions")


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), nullable=False, index=True)
    supplier: Mapped[str] = mapped_column(String(120), nullable=False)
    product: Mapped[str] = mapped_column(String(120), nullable=False)
    metal: Mapped[str] = mapped_column(String(30), nullable=False)
    purity: Mapped[str] = mapped_column(String(20), nullable=False)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, nullable=False)
    purchase_date: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class GoldExchange(Base):
    __tablename__ = "gold_exchanges"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False, index=True)
    old_inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_items.id"), nullable=True, index=True)
    new_inventory_item_id: Mapped[int | None] = mapped_column(ForeignKey("inventory_items.id"), nullable=True, index=True)
    old_jewellery_weight: Mapped[float] = mapped_column(Float, nullable=False)
    old_purity: Mapped[str] = mapped_column(String(20), nullable=False)
    current_metal_rate: Mapped[float] = mapped_column(Float, nullable=False)
    exchange_value: Mapped[float] = mapped_column(Float, nullable=False)
    new_jewellery: Mapped[str] = mapped_column(String(120), nullable=False)
    new_jewellery_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    difference_amount: Mapped[float] = mapped_column(Float, nullable=False)
    exchange_date: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    customer: Mapped["Customer"] = relationship(back_populates="exchanges")


class BillItem(Base):
    __tablename__ = "bill_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("bills.id"), nullable=False)
    product_name: Mapped[str] = mapped_column(String(120), nullable=False)
    metal_name: Mapped[str] = mapped_column(String(40), nullable=False)
    weight_grams: Mapped[float] = mapped_column(Float, nullable=False)
    purity_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    rate_per_gram: Mapped[float] = mapped_column(Float, nullable=False)
    making_charge: Mapped[float] = mapped_column(Float, nullable=False)
    gst_percent: Mapped[float] = mapped_column(Float, nullable=False)
    item_total: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    __table_args__ = (Index("ix_inventory_user_sku", "user_id", "sku", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    sku: Mapped[str] = mapped_column(String(60), nullable=False)
    product_name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    subcategory: Mapped[str] = mapped_column(String(60), default="", nullable=False)
    metal_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    purity: Mapped[str] = mapped_column(String(20), nullable=False)
    gross_weight: Mapped[float] = mapped_column(Float, nullable=False)
    stone_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    net_metal_weight: Mapped[float] = mapped_column(Float, nullable=False)
    making_charges: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wastage_percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stone_charges: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    diamond_charges: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selling_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    hallmark_huid: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    barcode: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    qr_code: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    product_image: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    supplier: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    karigar: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="In Stock", index=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False, default=1)
    status_before: Mapped[str] = mapped_column(String(30), nullable=False)
    status_after: Mapped[str] = mapped_column(String(30), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    notes: Mapped[str] = mapped_column(String(250), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

