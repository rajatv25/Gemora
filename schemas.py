from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: str
    password: str


class ExpenseCreate(BaseModel):
    title: str
    category: str
    amount: float
    date: str
    notes: str = ""


class BudgetCreate(BaseModel):
    category: str
    limit: float
    month: str


class ExpenseResponse(BaseModel):
    id: int
    title: str
    category: str
    amount: float
    date: str
    notes: str
    model_config = ConfigDict(from_attributes=True)


class MetalRateCreate(BaseModel):
    metal_name: str
    rate_per_gram: float
    purity_percentage: float = 100.0


class PriceCalculationCreate(BaseModel):
    item_name: str = "Jewellery item"
    metal_name: str = "Gold"
    purity: str = "22K"
    custom_purity_percentage: float | None = None
    gross_weight: float | None = None
    stone_weight: float = 0.0
    net_weight: float | None = None
    metal_rate: float | None = None
    making_charge_per_gram: float = 0.0
    making_charge_percentage: float = 0.0
    wastage_percentage: float = 0.0
    stone_charges: float = 0.0
    diamond_charges: float = 0.0
    discount_amount: float = 0.0
    gst_percent: float = 3.0
    weight_grams: float | None = None
    purity_percentage: float | None = None


class CalculationSave(BaseModel):
    record_type: str
    customer_id: int | None = None
    calculation: PriceCalculationCreate


class BillItemCreate(BaseModel):
    product_name: str
    inventory_sku: str = ""
    metal_name: str
    weight_grams: float
    purity_percentage: float
    making_charge: float = 0.0
    gst_percent: float = 3.0


class BillCreate(BaseModel):
    customer_name: str = "Walk-in customer"
    customer_id: int | None = None
    issue_date: str
    notes: str = ""
    items: list[BillItemCreate]


class MetalRateResponse(BaseModel):
    id: int
    metal_name: str
    rate_per_gram: float
    purity_percentage: float
    model_config = ConfigDict(from_attributes=True)


class BillResponse(BaseModel):
    id: int
    bill_number: str
    customer_name: str
    issue_date: str
    subtotal: float
    making_charge: float
    gst_amount: float
    total_amount: float
    notes: str
    model_config = ConfigDict(from_attributes=True)


class CustomerCreate(BaseModel):
    name: str
    mobile_number: str
    email: str = ""
    address: str = ""
    city: str = ""
    gstin: str = ""
    notes: str = ""


class CustomerPaymentCreate(BaseModel):
    amount: float
    payment_date: str
    payment_method: str = "Cash"
    bill_id: int | None = None
    notes: str = ""


class CustomerTransactionCreate(BaseModel):
    transaction_type: str
    amount: float = 0.0
    transaction_date: str
    bill_id: int | None = None
    notes: str = ""


class PurchaseCreate(BaseModel):
    supplier: str
    product: str
    metal: str
    purity: str
    weight: float
    rate: float
    total_amount: float
    purchase_date: str
    sku: str = ""
    category: str = "Purchased jewellery"


class ExchangeCreate(BaseModel):
    customer_id: int
    old_jewellery_weight: float
    old_purity: str
    current_metal_rate: float
    new_jewellery: str
    new_jewellery_amount: float = 0.0
    old_inventory_item_id: int | None = None
    new_inventory_item_id: int | None = None
    exchange_date: str


INVENTORY_STATUSES = ("In Stock", "Sold", "Reserved", "Under Repair")
INVENTORY_MOVEMENTS = ("purchase", "sale", "return", "exchange", "adjustment")


class InventoryItemCreate(BaseModel):
    sku: str
    product_name: str
    category: str
    subcategory: str = ""
    metal_type: str
    purity: str
    gross_weight: float
    stone_weight: float = 0.0
    net_metal_weight: float | None = None
    making_charges: float = 0.0
    wastage_percentage: float = 0.0
    stone_charges: float = 0.0
    diamond_charges: float = 0.0
    purchase_price: float = 0.0
    selling_price: float = 0.0
    hallmark_huid: str = ""
    barcode: str = ""
    qr_code: str = ""
    product_image: str = ""
    supplier: str = ""
    karigar: str = ""
    status: str = "In Stock"


class InventoryItemUpdate(InventoryItemCreate):
    pass


class InventoryStockMovement(BaseModel):
    movement_type: str
    reference: str = ""
    notes: str = ""
