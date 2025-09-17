from app.models.base_model import *
from app.utils import templates

class User(Base):
    __tablename__ = 'users'
    user_id = db.Column(BIGINT(unsigned=True), primary_key=True, nullable=False, autoincrement=False)

    def __repr__(self):
        return f'<User {self.user_id}>'