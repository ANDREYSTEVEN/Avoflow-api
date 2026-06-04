import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=schemas.UserOut)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta con este correo electrónico"
        )
    
    # Calculate default trial expiration (e.g., 7 days from now)
    trial_days = 7
    # For admin users, let's set a far future trial date, just in case, but they are exempt anyway
    if user_in.role == "admin":
        trial_days = 3650  # 10 years
        
    trial_expires = datetime.datetime.utcnow() + datetime.timedelta(days=trial_days)
    
    hashed_pwd = auth.get_password_hash(user_in.password)
    
    db_user = models.User(
        email=user_in.email,
        hashed_password=hashed_pwd,
        role=user_in.role or "client",
        name=user_in.name,
        phone=user_in.phone,
        trial_expires_at=trial_expires,
        is_active=True
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=schemas.Token)
def login(login_data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == login_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Correo electrónico o contraseña incorrectos"
        )
        
    if not auth.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Correo electrónico o contraseña incorrectos"
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ACCOUNT_DISABLED: Tu cuenta ha sido desactivada por el administrador."
        )
        
    # Check trial period for non-admins at login time
    if user.role != "admin":
        now = datetime.datetime.utcnow()
        if user.trial_expires_at < now:
            # We allow them to login but they will get blocked on protected endpoints.
            # However, to improve UX we can let them login so the UI shows the "Trial Expired" modal
            # and they can see their details. So we generate the token, and the individual endpoints/router guards will lock down.
            pass

    access_token = auth.create_access_token(
        data={"sub": user.email, "role": user.role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role
    }

@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user
