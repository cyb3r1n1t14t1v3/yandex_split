import json
from .base_context import BaseContext
from app.utils import Logger, CryptoBotAPI, templates, keyboard
from app.models import Product, Order, StatusType

logger = Logger("YSContext")

class YSContext(BaseContext):
    def __init__(self, update):
        super().__init__(update)

        self._create_user()
        self.crypto_bot = CryptoBotAPI(cache_ttl_minutes=templates.get("vars", "cache_ttl_minutes"),
                                       auto_cancel_default_seconds=templates.get("vars", "auto_cancel_default_seconds"))
        self.support_username = templates.get("vars", "support_username")


    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logger.error(f"Ошибка в YSContext: {exc_type.__name__}: {exc_value}")

    def start(self):
        logger.log_function_call("YSContext.start")
        text = templates.get("bot", "start",
                             support_username = self.support_username)

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
                             support_username = self.support_username)

        self.send_message(text)

    def get_info(self):
        logger.log_function_call("YSContext.get_info")
        text = templates.get("bot", "get_info",
                             support_username = self.support_username)

        self.send_message(text)

    def get_stock(self):
        logger.log_function_call("YSContext.get_stock")

        self.send_message(str(self.update))

    def select_qty(self, message_id):
        logger.log_function_call("YSContext.select_qty")

        text = templates.get("bot", "select_qty")

        self.edit_message_text(message_id, text, reply_markup =
        self.get_inline_keyboard(actions=["select_qty", "back_to_product"]))

    def check_product_qty(self, message_id):
        logger.log_function_call("YSContext._check_product_qty")

        choice = self._choice
        product_id = choice[0]
        selected_quantity = choice[1]
        product = Product.query.get(product_id)
        if not product:
            logger.error(f"Товар с идентификатором {product_id} не найден")
            return False

        product_qty = product.quantity

        if selected_quantity > product_qty:
            text = templates.get("bot", "insufficient_quantity",
                                 quantity = selected_quantity,
                                 available_quantity = product_qty,
                                 support_username = self.support_username)

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
                key["callback_data"]["id"] == str(asset_id)):
                type_of_asset = key["text"]

        product = Product.query.get(product_id)
        if product is None:
            logger.error(f"Товар с идентификатором {product_id} не найден")
            return None

        self.check_payment()
        self.cancel_order()

        price_in_rub = product.price * quantity
        time_to_pay = str(round(int(templates.get("vars", "auto_cancel_default_seconds")) / 60))

        price_in_asset = self.crypto_bot.convert_amount(price_in_rub, "RUB", type_of_asset)
        if not price_in_asset:
            logger.error(f"Валюта {type_of_asset} не найдена")
            return None

        new_invoice = self.crypto_bot.create_invoice(asset=type_of_asset, amount=price_in_asset)

        new_order = Order(
            user       = self._user,
            product    = product,
            quantity   = quantity,
            invoice_id = new_invoice.invoice_id,
            message_id = message_id
        )
        product.quantity -= quantity
        product.commit()
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
            "support_username" : self.support_username
        }

        text = templates.get("bot", "set_order", **kwargs)
        self.edit_message_text(message_id, text, reply_markup =
        self.get_inline_keyboard(actions=["select_order_action"], urls = { "1" : new_invoice.pay_url }))

    def cancel_order(self):
        logger.log_function_call("YSContext.cancel_order")

        if not self.past_order:
            return

        self.past_order.status = StatusType.CANCELLED
        self.past_order.product.quantity += self.past_order.quantity
        self.past_order.commit()

        self.crypto_bot.delete_invoice(self.past_order.invoice_id)
        logger.info(f"Заказ #{self.past_order.order_id} успешно отменен")

        self.edit_message_text(self.past_order.message_id, templates.get("bot", "cancel_order",
                                                         order_id = self.past_order.order_id,
                                                         support_username = self.support_username))

    def successful_payment(self):
        logger.log_function_call("YSContext.successful_payment")

        if not self.past_order:
            return

        self.past_order.status = StatusType.PAID
        self.past_order.commit()

        logger.info(f"Заказ #{self.past_order.order_id} успешно оплачен: "
                    f"user_id[{self.past_order.user_id}] "
                    f"username[\"{self.username}\"]"
                    f"total_amount[{self.past_order.total_price}]")

        self.edit_message_text(self.past_order.message_id, templates.get("bot", "successful_payment",
                                                         order_id=self.past_order.order_id,
                                                         support_username = self.support_username))

    def check_payment(self):
        logger.log_function_call("YSContext.check_payment")

        if not self.past_order:
            return

        result = self.crypto_bot.check_invoice_paid(self.past_order.invoice_id)

        if result:
            self.successful_payment()
        elif result is None:
            self.cancel_order()

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
                logger.warn(f"Неизвестная команда [\"/{command}\"] "
                            f"от пользователя [{self.user_id}] с именем [\"{self.username}\"].")
                return False

        logger.info(f"Успешное выполнение команды [\"/{command}\"] "
                    f"пользователя [{self.user_id}] с именем [\"{self.username}\"].")
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
            case "Товары в наличии":
                pass
            case _:
                return False

        logger.info(f"Успешный ответ на сообщение [\"{text}\"] "
                    f"пользователя [{self.user_id}] с именем [\"{self.username}\"].")
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
                if self.check_product_qty(message_id):
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
                        self.check_payment()
                        self.cancel_order()
                    case "3":
                        self.check_payment()
            case _:
                logger.warn(f"Неизвестный callback-метод [\"{query.data}\"].")
                return False
        logger.info(f"Успешный ответ на callback-метод [\"{query.data}\"] "
                    f"пользователя [{self.user_id}] с именем [\"{self.username}\"].")
        return True
