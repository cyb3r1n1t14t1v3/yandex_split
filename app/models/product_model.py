from app.models.base_model import *

class Product(Base):
    __tablename__ = 'products'

    product_id = db.Column(INTEGER(unsigned=True), primary_key=True, nullable=False, autoincrement=True)
    account_limit = db.Column(INTEGER(unsigned=True), nullable=False, default=0, server_default="0")
    quantity = db.Column(INTEGER(unsigned=True), nullable=False, default=0, server_default="0")
    price = db.Column(INTEGER(unsigned=True), nullable=False, default=0, server_default="0")

    orders = db.relationship('Order', back_populates='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.product_id}>'