from app.models.base_model import *
from app.utils import templates

class User(Base):
    __tablename__ = 'users'
    user_id = db.Column(BIGINT(unsigned=True), primary_key=True, nullable=False, autoincrement=False)
    username = db.Column(VARCHAR(32), nullable=False, unique=True)
    gender_code = db.Column(ENUM(*templates.gender_codes), nullable=True)
    description = db.Column(VARCHAR(1024), nullable=True)
    money = db.Column(INTEGER(unsigned=True), default=0)
    status = db.Column(VARCHAR(32), default='Человек')
    reputation = db.Column(INTEGER(), default=0)
    first_date = db.Column(DATETIME(), nullable=False, server_default=db.func.now())

    access_users = db.relationship('AccessUser', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.user_id}>'