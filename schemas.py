from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

class LoginRequest(BaseModel):
    email: str
    password: str

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    name: str
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str
    role: Optional[str] = "client"  # admin, client, driver

class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None

class UserUpdateTrial(BaseModel):
    trial_expires_at: datetime

class UserOut(UserBase):
    id: int
    role: str
    trial_expires_at: datetime
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

# --- Product (Inventory) Schemas ---
class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: float = Field(..., gt=0)
    stock: int = Field(..., ge=0)
    category: str
    image_url: Optional[str] = None

class ProductCreate(ProductBase):
    pass

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    category: Optional[str] = None
    image_url: Optional[str] = None

class ProductOut(ProductBase):
    id: int

    class Config:
        from_attributes = True

# --- Order Item Schemas ---
class OrderItemBase(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0)

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    price_per_unit: float
    product: ProductOut

    class Config:
        from_attributes = True

# --- Order Schemas ---
class OrderBase(BaseModel):
    delivery_address: str
    delivery_notes: Optional[str] = None

class OrderCreate(OrderBase):
    items: List[OrderItemCreate]

class OrderUpdateStatus(BaseModel):
    status: str  # pending, preparing, shipped, delivered, cancelled

class OrderUpdateDriver(BaseModel):
    driver_id: Optional[int] = None

class OrderOut(OrderBase):
    id: int
    client_id: int
    driver_id: Optional[int] = None
    status: str
    total_price: float
    created_at: datetime
    updated_at: datetime
    client: UserOut
    driver: Optional[UserOut] = None
    items: List[OrderItemOut]

    class Config:
        from_attributes = True

# --- WhatsApp Schemas ---
class WhatsAppMessageCreate(BaseModel):
    sender: str
    receiver: str
    message: str
    direction: str  # incoming, outgoing
    is_automated: Optional[bool] = False

class WhatsAppMessageOut(BaseModel):
    id: int
    sender: str
    receiver: str
    message: str
    timestamp: datetime
    direction: str
    is_automated: bool

    class Config:
        from_attributes = True

class MockMessageSend(BaseModel):
    phone: str
    message: str
