from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/api/users", tags=["Users Administration"])

@router.get("", response_model=List[schemas.UserOut])
def list_users(
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    return db.query(models.User).order_by(models.User.created_at.desc()).all()

@router.put("/{user_id}/trial", response_model=schemas.UserOut)
def update_user_trial(
    user_id: int,
    trial_in: schemas.UserUpdateTrial,
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
        
    user.trial_expires_at = trial_in.trial_expires_at
    db.commit()
    db.refresh(user)
    return user

@router.put("/{user_id}/toggle-active", response_model=schemas.UserOut)
def toggle_user_active(
    user_id: int,
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
        
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes desactivar tu propia cuenta."
        )
        
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user

@router.put("/{user_id}/role", response_model=schemas.UserOut)
def update_user_role(
    user_id: int,
    role: str,
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
        
    if role not in ["admin", "client", "driver"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rol no válido. Opciones: admin, client, driver"
        )
        
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol."
        )
        
    user.role = role
    db.commit()
    db.refresh(user)
    return user
