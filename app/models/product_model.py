from app.models.base_model import *

class Product(Base):
    __tablename__ = 'products'
    __table_args__ = {'extend_existing': True}

    product_id = db.Column(INTEGER(unsigned=True), primary_key=True, nullable=False, autoincrement=True)
    account_limit = db.Column(INTEGER(unsigned=True), nullable=False, default=0, server_default="0")
    quantity = db.Column(INTEGER(unsigned=True), nullable=False, default=0, server_default="0")
    price = db.Column(INTEGER(unsigned=True), nullable=False, default=0, server_default="0")

    order = db.relationship('Order', back_populates='product', lazy='dynamic')

    def __repr__(self):
        return f'<Product {self.product_id}>'