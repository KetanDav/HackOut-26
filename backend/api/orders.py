from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
import models, schemas
from database import get_db

router = APIRouter(prefix="/orders", tags=["Orders"])

@router.post("/", response_model=schemas.OrderOut, status_code=201)
def place_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    # Validate user exists
    user = db.query(models.User).filter(models.User.id == order.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate order type
    if order.order_type not in ["sell", "buy"]:
        raise HTTPException(status_code=400, detail="order_type must be 'sell' or 'buy'")

    # Prosumers can only place sell orders (consumers only buy)
    if order.order_type == "sell" and user.role == "consumer":
        raise HTTPException(status_code=403, detail="Consumers cannot place sell orders. Register as prosumer.")

    db_order = models.Order(
        user_id=order.user_id,
        order_type=order.order_type,
        energy_kwh=order.energy_kwh,
        remaining_kwh=order.energy_kwh,   # initially all remaining
        price_per_kwh=order.price_per_kwh,
        time_block=order.time_block,
        node_id=order.node_id,
        status=models.OrderStatus.OPEN
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

@router.get("/", response_model=list[schemas.OrderOut])
def list_orders(
    time_block: Optional[str] = None,
    order_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(models.Order)
    if time_block:
        q = q.filter(models.Order.time_block == time_block)
    if order_type:
        q = q.filter(models.Order.order_type == order_type)
    if status:
        q = q.filter(models.Order.status == status)
    return q.order_by(models.Order.created_at.desc()).all()

@router.get("/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@router.delete("/{order_id}")
def cancel_order(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status == models.OrderStatus.FILLED:
        raise HTTPException(status_code=400, detail="Cannot cancel a filled order")
    order.status = models.OrderStatus.CANCELLED
    db.commit()
    return {"message": f"Order {order_id} cancelled"}
