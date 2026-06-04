import datetime
import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp Automation"])

@router.get("/messages", response_model=List[schemas.WhatsAppMessageOut])
def list_messages(
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    return db.query(models.WhatsAppMessage).order_by(models.WhatsAppMessage.timestamp.asc()).all()

@router.post("/send", response_model=schemas.WhatsAppMessageOut)
def send_message(
    payload: schemas.MockMessageSend,
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    db_msg = models.WhatsAppMessage(
        sender="Avocado Delivery",
        receiver=payload.phone,
        message=payload.message,
        direction="outgoing",
        is_automated=False
    )
    db.add(db_msg)
    db.commit()
    db.refresh(db_msg)
    return db_msg

@router.post("/simulate-incoming", response_model=List[schemas.WhatsAppMessageOut])
def simulate_incoming(
    payload: schemas.MockMessageSend,
    db: Session = Depends(get_db)
):
    # Save the incoming message
    incoming_msg = models.WhatsAppMessage(
        sender=payload.phone,
        receiver="Avocado Delivery",
        message=payload.message,
        direction="incoming",
        is_automated=False
    )
    db.add(incoming_msg)
    db.commit()
    db.refresh(incoming_msg)
    
    # Process with the auto-responder rules
    msg_clean = payload.message.lower().strip()
    reply_text = ""
    order_created = False
    
    if any(keyword in msg_clean for keyword in ["hola", "catalogo", "aguacate", "precio", "menú", "menu"]):
        # Fetch current products
        products = db.query(models.Product).all()
        if not products:
            reply_text = "🥑 ¡Hola! Bienvenido a *Avocado Delivery* 🥑. Por el momento nuestro inventario está vacío. Regresa pronto."
        else:
            prod_list = []
            for p in products:
                status_stock = f"({p.stock} disp.)" if p.stock > 0 else "(Agotado)"
                prod_list.append(f"• *ID {p.id}*: {p.name} - ${p.price} {status_stock}")
            
            reply_text = (
                "🥑 ¡Hola! Bienvenido a *Avocado Delivery* 🥑\n"
                "Te ofrecemos la mejor frescura a tu hogar. Este es nuestro catálogo:\n\n" +
                "\n".join(prod_list) + "\n\n"
                "👉 Si deseas comprar, responde escribiendo *comprar* o *pedido*."
            )
            
    elif "pedido" in msg_clean or "comprar" in msg_clean:
        # Give formatting instructions
        reply_text = (
            "📝 *Instrucciones para pedido automático:*\n\n"
            "Responde con este formato exacto:\n"
            "*PEDIDO: [PRODUCTO_ID]:[CANTIDAD], [DIRECCIÓN]*\n\n"
            "Ejemplo:\n"
            "*PEDIDO: 1:3, Calle Falsa 123, apto 202*"
        )
        
    elif msg_clean.startswith("pedido:"):
        # Attempt to parse order: "pedido: ID:QTY, ADDRESS"
        # Regex to capture "pedido: \s* (\d+) \s* : \s* (\d+) \s* , \s* (.+)"
        match = re.match(r"pedido:\s*(\d+)\s*:\s*(\d+)\s*,\s*(.+)", msg_clean, re.IGNORECASE)
        if match:
            prod_id = int(match.group(1))
            qty = int(match.group(2))
            address = match.group(3).strip()
            
            # Find or create a WhatsApp client user
            email_dummy = f"{payload.phone}@whatsapp.com"
            user = db.query(models.User).filter(models.User.email == email_dummy).first()
            if not user:
                # Create guest user
                # Trial is set to 10 years for WhatsApp guest users so they are never blocked
                trial_expires = datetime.datetime.utcnow() + datetime.timedelta(days=3650)
                user = models.User(
                    email=email_dummy,
                    hashed_password=auth.get_password_hash("whatsapp-guest-pass-1234"),
                    role="client",
                    name=f"Cliente WA ({payload.phone})",
                    phone=payload.phone,
                    trial_expires_at=trial_expires,
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                
            # Verify product and stock
            product = db.query(models.Product).filter(models.Product.id == prod_id).first()
            if not product:
                reply_text = f"❌ El producto con ID *{prod_id}* no existe en nuestro catálogo. Escribe *hola* para ver el catálogo disponible."
            elif product.stock < qty:
                reply_text = f"❌ Stock insuficiente para *{product.name}*. Solo nos quedan {product.stock} unidades."
            else:
                # Deduct stock
                product.stock -= qty
                total = product.price * qty
                
                # Create Order
                new_order = models.Order(
                    client_id=user.id,
                    status="pending",
                    total_price=total,
                    delivery_address=address,
                    delivery_notes="Pedido ingresado automáticamente vía WhatsApp Chatbot",
                    items=[
                        models.OrderItem(
                            product_id=product.id,
                            quantity=qty,
                            price_per_unit=product.price
                        )
                    ]
                )
                db.add(new_order)
                db.commit()
                db.refresh(new_order)
                order_created = True
                
                reply_text = (
                    f"✅ *¡Pedido Creado con Éxito!* 🥑\n\n"
                    f"• *Pedido ID*: #{new_order.id}\n"
                    f"• *Producto*: {product.name} (x{qty})\n"
                    f"• *Total*: ${total}\n"
                    f"• *Dirección*: {address}\n\n"
                    f"¡Gracias por tu compra! Tu pedido está pendiente de confirmación."
                )
        else:
            reply_text = "❌ Formato incorrecto. Recuerda usar: *PEDIDO: ID:CANTIDAD, DIRECCIÓN* (ej. *PEDIDO: 1:2, Av. Principal #10*)."
            
    else:
        # Default fallback response
        reply_text = (
            "🤖 *Asistente Virtual Avocado Delivery*\n"
            "No entendí tu mensaje. Escribe:\n"
            "• *hola* para ver el catálogo.\n"
            "• *pedido* para saber cómo ordenar."
        )

    # Save and commit automated response
    automated_reply = models.WhatsAppMessage(
        sender="Avocado Delivery",
        receiver=payload.phone,
        message=reply_text,
        direction="outgoing",
        is_automated=True
    )
    db.add(automated_reply)
    db.commit()
    db.refresh(automated_reply)
    
    return [incoming_msg, automated_reply]
