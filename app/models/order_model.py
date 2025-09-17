from app.models.base_model import *
from enum import Enum
from sqlalchemy import Enum as SQLAlchemyEnum, event

class StatusType(Enum):
    PENDING = "pending"
    CANCELLED = "cancelled"
    DELIVERED = "delivered"

class Order(Base):
    __tablename__ = 'products'
    order_id = db.Column(INTEGER(unsigned=True), primary_key=True, nullable=False, autoincrement=True)
    user_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('users.user_id'), nullable=False)
    product_id = db.Column(INTEGER(unsigned=True), db.ForeignKey('products.product_id'), nullable=False)
    quantity = db.Column(INTEGER(unsigned=True), default=1, server_default="1", nullable=False)
    order_date = db.Column(DATETIME(), nullable=False, server_default=db.func.now())
    total_price = db.Column(db.DECIMAL(10, 2), nullable=False, default=0.00, server_default="0.00")
    status = db.Column(SQLAlchemyEnum(StatusType), nullable=False, default=StatusType.PENDING, server_default=str(StatusType.PENDING))

    product = db.relationship('Product', back_populates='order')
    user = db.relationship('User', back_populates='order')

    def __repr__(self):
        return f'<Product {self.product_id}>'

@event.listens_for(Order, 'before_insert')
@event.listens_for(Order, 'before_update')
def calculate_total_price(mapper, connection, target):
    if target.product and target.quantity:
        target.total_price = target.quantity * target.product.price