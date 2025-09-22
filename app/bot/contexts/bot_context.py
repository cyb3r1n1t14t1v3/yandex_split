import json
import logging
from .base_context import BaseContext
from app.utils import Logger, CryptoBotAPI, templates, keyboard
from app.models import User, Product, Order, StatusType

logger = Logger("YSContext")

class YSContext(BaseContext):
    def __init__(self, update):
        super().__init__(update)

        _user = None
        self._create_user()
        self.crypto_bot = CryptoBotAPI(cache_ttl_minutes=templates.get("vars", "cache_ttl_minutes"),
                                       auto_cancel_default_seconds=templates.get("vars", "auto_cancel_default_seconds"))
        self.telegram_username = templates.get("vars", "support_username")


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

    def get_inline_keyboard(self, actions: list, urls: dict = None):
        keys = [key for key in keyboard.inline
                if key["callback_data"]["action"] in actions]

        logger.debug(keys)
        return self.get_keyboard(keys, urls)

    def start(self):
        logger.log_function_call("YSContext.start")
        text = templates.get("bot", "start",
                             telegram_username = self.telegram_username)

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
                             telegram_username = self.telegram_username)

        self.send_message(text)

    def get_info(self):
        logger.log_function_call("YSContext.get_info")
        text = templates.get("bot", "get_info",
                             telegram_username = self.telegram_username)

        self.send_message(text)

    def select_qty(self, message_id):
        logger.log_function_call("YSContext.select_qty")

        text = templates.get("bot", "select_qty")

        self.edit_message_text(message_id, text, reply_markup =
        self.get_inline_keyboard(actions=["select_qty", "back_to_product"]))

    @property
    def _choice(self):
        choices = self._user.choice.split("/")[:-1]
        check_index = lambda index: 0 <= index < len(choices)

        product_id = int(choices[0].split("?")[1]) if check_index(0) else None
        qty_id = int(choices[1].split("?")[1]) if check_index(1) else None
        asset_id = int(choices[2].split("?")[1]) if check_index(2) else None

        return product_id, qty_id, asset_id

    def _check_product_qty(self, message_id):
        logger.log_function_call("YSContext._check_product_qty")

        choice = self._choice
        product_id = choice[0]
        selected_quantity = choice[1]
        product = Product.query.get(product_id)
        if not product: return False

        product_qty = product.quantity

        if selected_quantity > product_qty:
            text = templates.get("bot", "insufficient_quantity",
                                 quantity = selected_quantity,
                                 available_quantity = product_qty,
                                 telegram_username = self.telegram_username)

            self.edit_message_text(message_id, text, reply_markup=
            self.get_inline_keyboard(["back_to_qty"]))

        return product_qty >= selected_quantity

    def set_order(self, message_id):
        logger.log_function_call("YSContext.set_order")

        choice = self._choice
        product_id = choice[0]
        quantity = choice[1]
        asset_id = choice[2]

        type_of_asset = ""
        for key in keyboard.inline:
            if (key["callback_data"]["action"] == "select_asset" and
                key["callback_data"]["id"] == asset_id):
                type_of_asset = key["text"]

        product = Product.query.get(product_id)
        if product is None:
            logger.error(f"Товар с идентификатором {product_id} не найден")
            return None

        self.cancel_order()

        price_in_rub = product.price * quantity
        time_to_pay = str(round(int(templates.get("vars", "auto_cancel_default_seconds")) / 60))

        price_in_asset = self.crypto_bot.convert_amount(price_in_rub, "RUB", type_of_asset)
        new_invoice = self.crypto_bot.create_invoice(asset=type_of_asset, amount=price_in_asset)

        new_order = Order(
            user       = self._user,
            product    = product,
            quantity   = quantity,
            invoice_id = new_invoice.invoice_id,
            message_id = message_id
        )
        new_order.save()
        logger.info(f"Заказ #{new_order.order_id} успешно создан на общую сумму {price_in_rub}р")

        kwargs = {
            "order_id"          : new_order.order_id,
            "acc_limit"         : product.account_limit,
            "quantity"          : quantity,
            "price_in_rub"      : price_in_rub,
            "type_of_asset"     : type_of_asset,
            "price_in_asset"    : round(price_in_asset, 2),
            "time_to_pay"       : time_to_pay,
            "telegram_username" : self.telegram_username
        }

        text = templates.get("bot", "set_order", **kwargs)
        self.edit_message_text(message_id, text, reply_markup =
        self.get_inline_keyboard(actions=["select_order_action"], urls = { "1" : new_invoice.pay_url }))

    @property
    def past_order(self):
        query = Order.query.order_by(Order.order_id.desc())
        order = query.filter_by(user_id = self._user.user_id,
                                status  = StatusType.PENDING).first()

        return order if order else None

    def cancel_order(self):
        logger.log_function_call("YSContext.cancel_order")

        self.check_payment()

        past_order = self.past_order
        if not past_order:
            return

        past_order.status = StatusType.CANCELLED
        past_order.commit()
        self.crypto_bot.delete_invoice(past_order.invoice_id)
        logger.info(f"Заказ #{past_order.order_id} успешно отменен")

        self.edit_message_text(past_order.message_id, templates.get("bot", "cancel_order",
                                                         order_id = past_order.order_id,
                                                         telegram_username = self.telegram_username))

    def successful_payment(self):
        logger.log_function_call("YSContext.successful_payment")

        past_order = self.past_order
        if not past_order:
            return

        past_order.status = StatusType.PAID
        past_order.commit()
        logger.info(f"Заказ #{past_order.order_id} успешно оплачен: "
                    f"user_id[{past_order.user_id}] total_amount[{past_order.total_price}]")

        self.edit_message_text(past_order.message_id, templates.get("bot", "successful_payment",
                                                         order_id=past_order.order_id,
                                                         telegram_username = self.telegram_username))

    def check_payment(self):
        logger.log_function_call("YSContext.check_payment")

        result = self.crypto_bot.check_invoice_paid(33790001)

        if result:
            return self.successful_payment()
        elif result is None:
            return self.cancel_order()
        return result

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

    def choice_update(self, stage, choices, action, action_id):
        if stage == 1:
            if self._user.choice:
                self._user.choice = ""
        else:
            if len(choices) >= stage:
                self._user.choice = "/".join(choices[:-1]) + "/"
        self._user.choice += f"{action}?{action_id}/"
        self._user.commit()

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
        action = json_data["action"]
        action_id = json_data["id"] if "id" in json_data else None
        choices = 0

        if action != "select_order":
            choices = self._user.choice.split("/")[:-1]

        match action:
            case "select_order":
                self.choice_update(1, choices, action, action_id)
                self.select_qty(message_id)
            case "select_qty":
                self.choice_update(2, choices, action, action_id)
                if self._check_product_qty(message_id):
                    self.select_asset(message_id)
            case "select_asset":
                self.choice_update(3, choices, action, action_id)
                self.set_order(message_id)
            case "back_to_product":
                self.get_product(message_id)
            case "back_to_qty":
                self.select_qty(message_id)
            case "back_to_asset":
                self.select_asset(message_id)
            case "select_order_action":
                match json_data["id"]:
                    case "2":
                        self.cancel_order()
                    case "3":
                        self.check_payment()
            case _:
                logger.warn(f"Неизвестный callback-метод [\"{query.data}\"].")
                return False

        logger.info(f"Успешный ответ на callback-метод [\"{query.data}\"] пользователя [\"{self.user_id}\"].")
        return True