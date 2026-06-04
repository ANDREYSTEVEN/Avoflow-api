import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, SessionLocal, Base
import models
import auth
from routers import auth as auth_router, products, orders, users, whatsapp, export

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="AvoFlow API",
    description="Backend API for Avocado Delivery Management Platform",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for easier testing & Vercel deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Seed database with initial data (Admin and Products)
def seed_db():
    db = SessionLocal()
    try:
        # Check if default admin exists
        admin_email = "admin@avoflow.com"
        admin = db.query(models.User).filter(models.User.email == admin_email).first()
        if not admin:
            hashed_pwd = auth.get_password_hash("admin123")
            trial_expires = datetime.datetime.utcnow() + datetime.timedelta(days=3650)
            admin_user = models.User(
                email=admin_email,
                hashed_password=hashed_pwd,
                role="admin",
                name="Administrador AvoFlow",
                phone="+57 300 123 4567",
                trial_expires_at=trial_expires,
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("Default admin user seeded: admin@avoflow.com / admin123")

        # Check if default products exist
        product_count = db.query(models.Product).count()
        if product_count == 0:
            default_products = [
                models.Product(
                    name="Aguacate Hass Premium (Caja 10kg)",
                    description="Aguacate de exportación seleccionado a mano. Textura cremosa y maduración perfecta.",
                    price=45.0,
                    stock=120,
                    category="Hass",
                    image_url="hass_premium.jpg"
                ),
                models.Product(
                    name="Aguacate Fuerte de Primera (Caja 10kg)",
                    description="Excelente para ensaladas y guacamole. Sabor suave con cáscara delgada y verde brillante.",
                    price=38.0,
                    stock=80,
                    category="Fuerte",
                    image_url="fuerte_primera.jpg"
                ),
                models.Product(
                    name="Aguacate Orgánico Criollo (Malla 2kg)",
                    description="Cultivado sin pesticidas químicos. Sabor tradicional del campo.",
                    price=12.5,
                    stock=250,
                    category="Boxes",
                    image_url="criollo_organico.jpg"
                ),
                models.Product(
                    name="Aceite de Aguacate Extra Virgen (250ml)",
                    description="Prensado en frío, 100% puro. Ideal para cocinar a altas temperaturas y aderezos saludables.",
                    price=15.0,
                    stock=60,
                    category="Wholesale",
                    image_url="aceite_aguacate.jpg"
                )
            ]
            db.add_all(default_products)
            db.commit()
            print("Default products catalog seeded")

        # Also add a default driver for easy testing
        driver_email = "driver@avoflow.com"
        driver = db.query(models.User).filter(models.User.email == driver_email).first()
        if not driver:
            hashed_pwd = auth.get_password_hash("driver123")
            trial_expires = datetime.datetime.utcnow() + datetime.timedelta(days=7) # 7 days trial
            driver_user = models.User(
                email=driver_email,
                hashed_password=hashed_pwd,
                role="driver",
                name="Repartidor Carlos",
                phone="+57 311 987 6543",
                trial_expires_at=trial_expires,
                is_active=True
            )
            db.add(driver_user)
            db.commit()
            print("Default driver seeded: driver@avoflow.com / driver123")
            
        # Clean up any invalid emails with spaces that were created previously
        invalid_users = db.query(models.User).filter(models.User.email.like("% %")).all()
        for u in invalid_users:
            old_email = u.email
            new_email = old_email.replace(" ", "")
            # Check if new email already exists
            exists = db.query(models.User).filter(models.User.email == new_email).first()
            if exists:
                # Re-link orders to the existing user and delete this invalid user
                db.query(models.Order).filter(models.Order.client_id == u.id).update({models.Order.client_id: exists.id})
                db.delete(u)
            else:
                u.email = new_email
        db.commit()
            
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        db.close()

seed_db()

# Include Routers
app.include_router(auth_router.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(users.router)
app.include_router(whatsapp.router)
app.include_router(export.router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "message": "AvoFlow API is running smoothly.",
        "docs_url": "/docs"
    }
