from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models
import schemas
import auth

router = APIRouter(prefix="/api/orders", tags=["Orders Management"])

@router.post("", response_model=schemas.OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    order_in: schemas.OrderCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    # Only clients or admins can create orders through this endpoint
    if current_user.role not in ["client", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los clientes o administradores pueden crear pedidos."
        )

    # Process and validate items
    total_price = 0.0
    order_items = []

    for item in order_in.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Producto con ID {item.product_id} no encontrado"
            )
        
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stock insuficiente para {product.name}. Disponible: {product.stock}, Solicitado: {item.quantity}"
            )
        
        # Deduct stock
        product.stock -= item.quantity
        
        # Calculate item price
        item_total = product.price * item.quantity
        total_price += item_total
        
        # Keep track of item object
        order_items.append(
            models.OrderItem(
                product_id=product.id,
                quantity=item.quantity,
                price_per_unit=product.price
            )
        )

    # Create Order
    db_order = models.Order(
        client_id=current_user.id,
        status="pending",
        total_price=total_price,
        delivery_address=order_in.delivery_address,
        delivery_notes=order_in.delivery_notes,
        items=order_items
    )
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@router.get("", response_model=List[schemas.OrderOut])
def list_orders(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "admin":
        return db.query(models.Order).order_by(models.Order.created_at.desc()).all()
    elif current_user.role == "driver":
        # Return orders assigned to this driver, or preparing orders that drivers can pick up
        return db.query(models.Order).filter(
            (models.Order.driver_id == current_user.id) | 
            ((models.Order.status == "preparing") & (models.Order.driver_id == None))
        ).order_by(models.Order.created_at.desc()).all()
    else:  # client
        return db.query(models.Order).filter(models.Order.client_id == current_user.id).order_by(models.Order.created_at.desc()).all()

@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order_details(
    order_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )
        
    # Check permissions
    if current_user.role != "admin" and order.client_id != current_user.id and order.driver_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver este pedido"
        )
        
    return order

@router.put("/{order_id}/status", response_model=schemas.OrderOut)
def update_order_status(
    order_id: int,
    status_in: schemas.OrderUpdateStatus,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )

    # Validate status transitions
    allowed_statuses = ["pending", "preparing", "shipped", "delivered", "cancelled"]
    if status_in.status not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estado no válido. Opciones: {allowed_statuses}"
        )

    # Permission check
    if current_user.role == "client":
        if order.client_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso para modificar este pedido."
            )
        if status_in.status != "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los clientes solo pueden cancelar pedidos."
            )
        if order.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo puedes cancelar pedidos que estén 'pendientes'."
            )
            
    elif current_user.role == "driver":
        if order.driver_id != current_user.id:
            # Check if driver is picking up an unassigned order
            if order.status == "preparing" and status_in.status == "shipped":
                order.driver_id = current_user.id
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Este pedido no te está asignado."
                )
        if status_in.status not in ["shipped", "delivered"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los repartidores solo pueden cambiar el estado a 'shipped' (en ruta) o 'delivered' (entregado)."
            )

    # If the order is cancelled, return the stock to inventory
    if status_in.status == "cancelled" and order.status != "cancelled":
        for item in order.items:
            product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
            if product:
                product.stock += item.quantity

    order.status = status_in.status
    db.commit()
    db.refresh(order)
    return order

@router.put("/{order_id}/assign", response_model=schemas.OrderOut)
def assign_order_driver(
    order_id: int,
    assign_in: schemas.OrderUpdateDriver,
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido no encontrado"
        )
        
    if assign_in.driver_id:
        driver = db.query(models.User).filter(models.User.id == assign_in.driver_id, models.User.role == "driver").first()
        if not driver:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El repartidor especificado no existe o no tiene el rol de repartidor."
            )
        order.driver_id = driver.id
        # Automatically move to preparing if it was pending
        if order.status == "pending":
            order.status = "preparing"
    else:
        order.driver_id = None
        
    db.commit()
    db.refresh(order)
    return order
