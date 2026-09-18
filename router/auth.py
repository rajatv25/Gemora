from fastapi import APIRouter, Depends, HTTPException
from schemas import UserCreate, UserLogin, UserResponse
from sqlalchemy.orm import Session
from database import get_db
from model import User
from security import hash_password, verify_password,create_acces_token,get_current_user


router = APIRouter()



@router.post("/register", response_model=UserResponse)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    # check if user already exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    # hashing the password
    hashed_password_value = hash_password(user.password)

    # create new user
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        hash_password=hashed_password_value,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # returning the ORM object is valid because response_model has from_attributes=True
    return new_user

@router.post("/login")
def login_user(user: UserLogin, db: Session = Depends(get_db)):
    # check if user exists
    existing_user = db.query(User).filter(User.email == user.email).first()
    if not existing_user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # verify password
    if not verify_password(user.password, existing_user.hash_password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    # TOKEN GENERATION LOGIC WILL BE HERE
    data = {"sub":user.email}
    acces_token = create_acces_token(data)
    return {"message": "Login successful",'acces_token':acces_token}
    
@router.get("/profile")
def profile(current_user:User=Depends(get_current_user)):
    return {
        "id": current_user.id,
        "full_name": current_user.full_name,
        "email": current_user.email,
    }
    






    


