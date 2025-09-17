import json
from sqlalchemy import func, asc, or_
from .base_context import BaseContext
from app.utils import Logger, templates
from app.models import User, Key

logger = Logger("YSContext")

class YSContext(BaseContext):
    def __init__(self, update):
        super().__init__(update)

        _user = None
        self._create_user()

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logger.error(f"Ошибка в YSContext: {exc_type.__name__}: {exc_value}")

    def _create_user(self) -> None:
        """Получает или создаёт пользователя в базе данных."""
        logger.log_function_call("UserContext._create_user")
        user = User.query.get(self.user_id)

        if user is None:
            logger.info(f"Создание нового пользователя: user_id[{self.user_id}]")
            user = User(
                user_id=self.user_id,
            )
            try:
                user.save()
                logger.info(f"Новый пользователь успешно создан: "
                            f"user_id[{self.user_id}]")
            except Exception as e:
                logger.error(f"Ошибка создания пользователя: {e}")
                raise

        self._user = user

    @property
    def general_keyboard(self):
        keys = Key.query.filter_by(general=True).all()
        logger.debug(keys)
        return self.get_keyboard([key.text_data for key in keys])

    def get_inline_keyboard(self, actions : list):
        keys = Key.query.filter(
            func.json_unquote(func.json_extract(Key.callback_data, '$.action')).in_(actions)
        ).order_by(asc(Key.order_position)).all()

        logger.debug(keys)

        text_data, callback_data = [], []
        for key in keys:
            text_data.append(key.text_data)
            callback_data.append(json.dumps(key.callback_data))

        return self.get_keyboard(text_data, callback_data)

    def start(self):
        logger.log_function_call("YSContext.start")
        text = templates.get("bot", "start",
                             telegram_username = templates.get("vars", "support_username"))

        self.send_message(text = text, reply_markup = self.general_keyboard)

    def get_product(self, message_id = None):
        logger.log_function_call("YSContext.get_product")
        text = templates.get("bot", "get_product")
        if message_id:
            self.edit_message_text(message_id, text,
                                   reply_markup = self.get_inline_keyboard(actions=["select_order"]))
        else:
            self.send_message(text, reply_markup = self.get_inline_keyboard(actions=["select_order"]))

    def get_support(self):
        logger.log_function_call("YSContext.get_support")
        text = templates.get("bot", "get_support",
                             telegram_username = templates.get("vars", "support_username"))

        self.send_message(text)

    def get_info(self):
        logger.log_function_call("YSContext.get_info")
        text = templates.get("bot", "get_info",
                             telegram_username = templates.get("vars", "support_username"))

        self.send_message(text)

    def set_order(self, message_id):
        logger.log_function_call("YSContext.set_order")
        text = templates.get("bot", "set_order")

        self.edit_message_text(message_id, text, reply_markup =
        self.get_inline_keyboard(actions=["select_qty", "back_to_asset"]))

    def select_asset(self, message_id):
        logger.log_function_call("YSContext.select_asset")
        text = templates.get("bot", "select_asset")

        self.edit_message_text(message_id, text, reply_markup
        = self.get_inline_keyboard(actions=["select_asset", "back_to_product"]))

    def handle(self):
        """Обрабатывает команду пользователя.

        Returns:
            bool: True, если обработка успешна.
        """
        logger.log_function_call("YSContext.handle")
        text = self.message.text
        index = text.find("@")
        end_index = None if index == -1 else index
        command = text[1:end_index].lower()

        match command:
            case "start":
                self.start()
            case _:
                logger.warn(f"Неизвестная команда [\"/{command}\"] от пользователя [\"{self.user_id}\"].")
                return False

        logger.info(f"Успешное выполнение команды [\"/{command}\"] пользователя [\"{self.user_id}\"].")
        return True

    def text_handle(self):
        """Обрабатывает текстовой запрос пользователя.

        Returns:
            bool: True, если обработка успешна.
        """

        logger.log_function_call("YSContext.text_handle")
        text = self.message.text

        match text:
            case "Товар | Product":
                self.get_product()
            case "Поддержка | Support":
                self.get_support()
            case "Гарантия/Правила | Warranty/Rules":
                self.get_info()

        logger.info(f"Успешный ответ на сообщение [\"/{text}\"] пользователя [\"{self.user_id}\"].")
        return True

    def callback_handle(self):
        """Обрабатывает callback-метод пользователя.

        Returns:
            bool: True, если обработка успешна.
        """

        logger.log_function_call("YSContext.callback_handle")
        query = self.update.callback_query
        query.answer()

        message_id = query.message.message_id
        cb_data = query.data
        json_data = json.loads(cb_data)

        match json_data["action"]:
            case "select_order":
                self.select_asset(message_id)
            case "select_asset":
                self.set_order(message_id)
            case "back_to_product":
                self.get_product(message_id)
            case _:
                logger.warn(f"Неизвестный callback-метод [\"/{query.data}\"].")

        logger.info(f"Успешный ответ на callback-метод [\"/{query.data}\"] пользователя [\"{self.user_id}\"].")
        return True