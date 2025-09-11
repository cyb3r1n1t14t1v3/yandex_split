from app.models.base_model import *
from enum import Enum
from sqlalchemy import Enum as SQLAlchemyEnum

class AccessMethod(Enum):
    CHANGE_USERNAME    = "change_username"
    CHANGE_GENDER      = "change_gender"
    CHANGE_DESCRIPTION = "change_description"

class AccessUser(Base):
    __tablename__ = 'access_users'
    chat_id = db.Column(BIGINT(), nullable=False)
    allowed_user_id = db.Column(BIGINT(unsigned=True), db.ForeignKey('users.user_id'), nullable=False)
    message_id = db.Column(BIGINT(unsigned=True), nullable=False)
    method = db.Column(SQLAlchemyEnum(AccessMethod), nullable=False)

    __table_args__ = (
        db.PrimaryKeyConstraint('chat_id', 'message_id'),
    )

    user = db.relationship('User', back_populates='access_users')

    def __repr__(self):
        return f'<AccessUser {self.allowed_user_id}/{self.method.value}>'
