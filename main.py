from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from database import Base, engine, ensure_legacy_columns
from router import auth, customer, expense, inventory, jewellery, trade

app = FastAPI()

app.include_router(auth.router)
app.include_router(expense.router)
app.include_router(inventory.router)
app.include_router(jewellery.router)
app.include_router(customer.router)
app.include_router(trade.router)
app.mount("/static", StaticFiles(directory="static"), name="static")
Base.metadata.create_all(bind=engine)
ensure_legacy_columns()


@app.get("/")
def root():
    return FileResponse("static/index.html")


@app.get("/home")
def home():
    return {"message": "Welcome to the jewellery management system"}


@app.get("/about")
def about():
    return {
        "name": "Gemora Jewellery Management",
        "purpose": "Track jewellery inventory, sales, and monthly targets",
    }