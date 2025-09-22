import json
import logging
from .base_context import BaseContext
from app.utils import Logger, CryptoBotAPI, templates, keyboard
from app.models import User, Product, Order

logger = Logger("YSContext")

class YSContext(BaseContext):
    def __init__(self, update):
        super().__init__(update)

        _user = None
        self._create_user()
        self.crypto_bot = CryptoBotAPI(cache_ttl_minutes=templates.get("vars", "cache_ttl_minutes"),
                                       auto_cancel_default_seconds=templates.get("vars", "auto_cancel_default_seconds"))

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
        logger.debug(keyboard.general)
        return self.get_keyboard(keyboard.general)

    def get_inline_keyboard(self, actions : list):
        keys = [key for key in keyboard.inline
                if key["callback_data"]["action"] in actions]

        logger.debug(keys)
        return self.get_keyboard(keys)

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

    def select_qty(self, message_id):
        logger.log_function_call("YSContext.select_qty")

        text = templates.get("bot", "select_qty")

        self.edit_message_text(message_id, text, reply_markup =
        self.get_inline_keyboard(actions=["select_qty", "back_to_product"]))

    def set_order(self, message_id):
        logger.log_function_call("YSContext.set_order")

        choices = self._user.choice.split("/")
        product_id = choices[0].split("?")[1]
        quantity = choices[1].split("?")[1]
        asset_id = choices[2].split("?")[1]

        type_of_asset = ""
        for key in keyboard.inline:
            if (key["callback_data"]["action"] == "select_asset" and
                key["callback_data"]["id"] == asset_id):
                type_of_asset = key["text"]

        product = Product.query.get(int(product_id))
        if product is None:
            logger.error(f"Товар с идентификатором {product_id} не найден")

        new_order = Order(
            user = self._user,
            product = product,
            quantity = quantity,
        )
        new_order.save()
        logger.info(f"Заказ #{new_order.order_id} успешно создан на общую сумму {new_order.total_price}р")

        price_in_asset = self.crypto_bot.convert_amount(product.price, "RUB", type_of_asset)
        time_to_pay = str(round(int(templates.get("vars", "auto_cancel_default_seconds")) / 60))
        kwargs = {
            "order_id" : new_order.order_id,
            "acc_limit" : product.account_limit,
            "quantity" : quantity,
            "price_in_rub" : product.price,
            "type_of_asset" : type_of_asset,
            "price_in_asset" : price_in_asset,
            "time_to_pay" : time_to_pay,
            "telegram_username" : templates.get("vars", "support_username")
        }

        text = templates.get("bot", "set_order", **kwargs)
        self.edit_message_text(message_id, text, reply_markup =
        self.get_inline_keyboard(actions=["select_order_action"]))

    def select_asset(self, message_id):
        logger.log_function_call("YSContext.select_asset")
        text = templates.get("bot", "select_asset")

        self.edit_message_text(message_id, text, reply_markup
        = self.get_inline_keyboard(actions=["select_asset", "back_to_qty"]))

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
            case "Товар":
                self.get_product()
            case "Поддержка":
                self.get_support()
            case "Гарантия/Правила":
                self.get_info()
            case _:
                return False


        logger.info(f"Успешный ответ на сообщение [\"{text}\"] пользователя [\"{self.user_id}\"].")
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
        choices = 0

        if json_data["action"] != "select_order":
            choices = self._user.choice.split("/")

        match json_data["action"]:
            case "select_order":
                if self._user.choice:
                    self._user.choice = None
                self._user.choice = f"select_order?{json_data['id']}/"
                self._user.commit()

                self.select_qty(message_id)
            case "select_qty":
                if len(choices) >= 2:
                    self._user.choice = "/".join(choices[:-1]) + "/"
                self._user.choice = self._user.choice + f"select_qty?{json_data['id']}/"
                self._user.commit()

                self.select_asset(message_id)
            case "select_asset":
                if len(choices) >= 3:
                    self._user.choice = "/".join(choices[:-1]) + "/"
                self._user.choice = self._user.choice + f"select_asset?{json_data['id']}/"
                self._user.commit()

                self.set_order(message_id)
            case "back_to_product":
                self.get_product(message_id)
            case "back_to_qty":
                self.select_qty(message_id)
            case "back_to_asset":
                self.select_asset(message_id)
            case _:
                logger.warn(f"Неизвестный callback-метод [\"{query.data}\"].")
                return False

        logger.info(f"Успешный ответ на callback-метод [\"{query.data}\"] пользователя [\"{self.user_id}\"].")
        return True