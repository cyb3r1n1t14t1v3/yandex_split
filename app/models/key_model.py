from sqlalchemy.orm import validates
from app.models.base_model import *
from sqlalchemy import BOOLEAN, JSON

class Key(Base):
    __tablename__ = 'keys'
    key_id = db.Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    callback_data = db.Column(JSON(), nullable=True)
    text_data = db.Column(VARCHAR(64), nullable=False)
    order_position = db.Column(INTEGER(unsigned=True), nullable=False)
    general = db.Column(BOOLEAN(), nullable=False, default=0, server_default='0')

    @validates('callback_data')
    def validate_callback_data(self, key, value):
        if not self.general and value is None:
            raise ValueError('callback_data must be provided when general is False')
        return value

    def __repr__(self):
        return f'<Key {self.key_id}>'