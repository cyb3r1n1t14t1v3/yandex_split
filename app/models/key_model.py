from app.models.base_model import *

class Key(Base):
    __tablename__ = 'keys'
    key_id = db.Column(INTEGER(unsigned=True), primary_key=True, autoincrement=True)
    callback_data = db.Column(VARCHAR(256), nullable=False, unique=True)
    text_data = db.Column(VARCHAR(256), nullable=False, unique=True)

    def __repr__(self):
        return f'<Key {self.key_id}>'