import io
import csv
import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
import models
import auth

router = APIRouter(prefix="/api/export", tags=["Reports & Export"])

@router.get("/sales")
def export_sales(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    query = db.query(models.Order)
    
    # Apply date filters if provided
    if start_date:
        try:
            start_dt = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(models.Order.created_at >= start_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de start_date incorrecto. Usar AAAA-MM-DD")
            
    if end_date:
        try:
            # Set time to end of day
            end_dt = datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
            query = query.filter(models.Order.created_at <= end_dt)
        except ValueError:
            raise HTTPException(status_code=400, detail="Formato de end_date incorrecto. Usar AAAA-MM-DD")

    orders = query.order_by(models.Order.created_at.desc()).all()

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "ID Pedido", "Cliente Correo", "Cliente Nombre", "Total Venta", 
        "Estado", "Direccion", "Notas", "Repartidor Asignado", 
        "Fecha Creacion", "Productos Comprados"
    ])
    
    for order in orders:
        driver_name = order.driver.name if order.driver else "Sin repartidor"
        
        # Format products as "ProdName (xQty), ProdName (xQty)"
        products_str = ", ".join([f"{item.product.name} (x{item.quantity})" for item in order.items])
        
        writer.writerow([
            order.id,
            order.client.email,
            order.client.name,
            order.total_price,
            order.status,
            order.delivery_address,
            order.delivery_notes or "",
            driver_name,
            order.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            products_str
        ])
        
    output.seek(0)
    
    # Return CSV as streaming file response
    filename = f"reporte_ventas_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    
    # Return response
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/inventory")
def export_inventory(
    current_user: models.User = Depends(auth.get_required_role(["admin"])),
    db: Session = Depends(get_db)
):
    products = db.query(models.Product).order_by(models.Product.id.asc()).all()

    # Generate CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(["ID Producto", "Nombre", "Categoria", "Precio Unitario", "Stock Disponible", "Descripcion"])
    
    for prod in products:
        writer.writerow([
            prod.id,
            prod.name,
            prod.category,
            prod.price,
            prod.stock,
            prod.description or ""
        ])
        
    output.seek(0)
    
    filename = f"reporte_inventario_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
