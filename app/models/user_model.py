from sqlalchemy import JSON
from app.models.base_model import *

class User(Base):
    __tablename__ = 'users'
    user_id = db.Column(BIGINT(unsigned=True), primary_key=True, nullable=False, autoincrement=False)
    choice = db.Column(JSON(), nullable=True, default=None, server_default=None)

    order = db.relationship('Order', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.user_id}>'