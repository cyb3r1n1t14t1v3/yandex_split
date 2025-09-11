from app import db
from sqlalchemy.dialects.mysql import INTEGER, BIGINT, VARCHAR, ENUM, DATETIME
from app.utils import Logger
from enum import Enum

logger = Logger("BaseModel")

class BaseMethod(Enum):
    SAVE   = 0
    DELETE = 1
    COMMIT = 2

class Base(db.Model):
    __abstract__ = True

    def _execute(self, method: BaseMethod):
        """Выполняет операцию с базой данных.

        Args:
            method (BaseMethods, optional): Тип операции (SAVE или DELETE).

        :returns:
            Base or bool: Объект для SAVE, True для DELETE.

        Raises:
            RuntimeError: Если операция не удалась.
        """
        try:
            match method:
                case BaseMethod.SAVE:
                    db.session.add(self)
                case BaseMethod.DELETE:
                    db.session.delete(self)
            db.session.commit()
            logger.debug(f"Успешный {method} для {self.__class__.__name__}")
            return True if method == BaseMethod.DELETE else self
        except Exception as e:
            db.session.rollback()
            logger.error(f"Ошибка при {method} в {self.__class__.__name__}: {e}")
            raise RuntimeError(f"Error in {method} for {self.__class__.__name__}: {e}") from e

    def save(self):
        """Сохраняет объект в базе данных.

        Returns:
            self: Сохранённый объект.

        Raises:
            SQLAlchemyError: Если сохранение не удалось.
        """
        return self._execute(BaseMethod.SAVE)

    def delete(self):
        """Удаляет объект из базы данных.

        Returns:
            bool: True, если удаление успешно.

        Raises:
            RuntimeError: Если удаление не удалось.
        """
        return self._execute(BaseMethod.DELETE)

    def commit(self):
        """Коммитит изменения в базе данных.

        Returns:
            self: Объект после коммита.

        Raises:
            RuntimeError: Если коммит не удался.
        """
        return self._execute(BaseMethod.COMMIT)

__all__ = [
    "Base",
    "db",
    "INTEGER",
    "BIGINT",
    "VARCHAR",
    "ENUM",
    "DATETIME"
]
