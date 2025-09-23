import json
import logging
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.parsemode import ParseMode
from telegram.message import Message
from flask import current_app as app
from app.utils import Logger, keyboard
from app.models import Product, User, Order, StatusType
from enum import Enum

logger = Logger("BaseContext")

class APIMethod(Enum):
    SEND_MESSAGE = 0
    DELETE_MESSAGE = 1
    REPLY_TO_MESSAGE = 2
    EDIT_MESSAGE_TEXT = 3

class BaseContext:
    def __init__(self, update):
        """Инициализация базового контекста на основе обновления от Telegram."""
        self.update = update
        source = update.message or update.callback_query
        self.message = source.message if hasattr(source, 'message') else source
        self.user_id = source.from_user.id
        self.telegram_username = source.from_user.username
        self.chat_id = self.message.chat_id

        self._user = None
        self._past_order = None

        self._parse_mode = ParseMode.HTML
        self._disable_web_page_preview = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logger.error(f"Ошибка в BaseContext: {exc_type.__name__}: {exc_value}")

    def _execute(self, method : APIMethod, **kwargs):
        """Осуществляет выполнение определенного API-метода.

        args:
            method(APIMethods, optional): Тип метода.

        :returns:
            Bool or Message: bool для метода DELETE_MESSAGE,
            Message для SEND_MESSAGE, REPLY_TO_MESSAGE, EDIT_MESSAGE_TEXT.

        Raises:
            Exception: Если операция не удалась.
        """
        params = kwargs.copy()
        params["user_id"] = self.user_id
        params["chat_id"] = self.chat_id

        data_pattern = " ".join([
            f"{k}[{v}]" for k, v in list(params.items())[::-1] if k != "text"
        ])
        message = None

        if logger.level == logging.DEBUG:
            text_pattern = f"text[\"{params['text']}\"]" if 'text' in params else ''
            logger.debug(f"Выполнение команды {method}: {data_pattern} {text_pattern}")

        try:
            match method:
                case APIMethod.DELETE_MESSAGE:
                    app.bot.delete_message(chat_id=params["chat_id"], message_id=params["message_id"])
                case APIMethod.EDIT_MESSAGE_TEXT:
                    message = app.bot.edit_message_text(
                        chat_id=params["chat_id"], text=params["text"],
                        message_id=params["message_id"],
                        parse_mode=self._parse_mode,
                        disable_web_page_preview=self._disable_web_page_preview,
                        reply_markup=params["reply_markup"])
                case _:
                    message = app.bot.send_message(
                        chat_id=params["chat_id"], text=params["text"],
                        reply_to_message_id = params["message_id"] if method == APIMethod.REPLY_TO_MESSAGE else None,
                        parse_mode=self._parse_mode,
                        disable_web_page_preview=self._disable_web_page_preview,
                        reply_markup=params["reply_markup"])

            logger.info(f"Успешное выполнение команды {method}: {data_pattern}")
            return message if message else True
        except Exception as e:
            logger.error(f"Ошибка при выполнении команды {method}: {data_pattern}: {e}")
            raise e

    def send_message(self, text, reply_markup = None) -> Message:
        """Отправляет сообщение пользователю. Если задан reply_markup, то создает клавиатуру"""
        logger.log_function_call("BaseContext.send_message")
        return self._execute(APIMethod.SEND_MESSAGE, text=text, reply_markup=reply_markup)

    def delete_message(self, message_id) -> bool:
        """Удаляет сообщение по message_id."""
        logger.log_function_call("BaseContext.delete_message")
        return self._execute(APIMethod.DELETE_MESSAGE, message_id=message_id)

    def reply_to_message(self, message_id, text) -> Message:
        """Отвечает на сообщение по message_id."""
        logger.log_function_call("BaseContext.reply_to_message")
        return self._execute(APIMethod.REPLY_TO_MESSAGE, message_id=message_id, text=text)

    def edit_message_text(self, message_id, text, reply_markup = None) -> Message:
        """Редактирует текстовое сообщение по message_id. Если задан reply_markup, то создает клавиатуру"""
        logger.log_function_call("BaseContext.edit_message_text")
        return self._execute(APIMethod.EDIT_MESSAGE_TEXT,
                             message_id=message_id, text=text, reply_markup=reply_markup)

    @staticmethod
    def get_keyboard(key_data: list[list] or list[dict], urls: dict = None) -> ReplyKeyboardMarkup or InlineKeyboardMarkup:
        if isinstance(key_data[0], list):
            return ReplyKeyboardMarkup(
                keyboard=key_data,
                resize_keyboard=True,
                one_time_keyboard=False
            )

        max_row_p = 0
        max_row_n = 0
        for key in key_data:
            row = key["position"]["row"]
            if row > max_row_p:
                max_row_p = row
            elif row < 0 and abs(row) > max_row_n:
                max_row_n = abs(row)

        keyboard = [[] for i in range(max_row_p)]
        bottom_keys = [[] for i in range(max_row_n)]

        for key in key_data:
            row = key["position"]["row"]
            column = key["position"]["column"]
            if urls and key["callback_data"]["id"] in urls.keys():
                inline_key = InlineKeyboardButton(key["text"], url=urls[key["callback_data"]["id"]])
            else:
                inline_key = InlineKeyboardButton(key["text"], callback_data=json.dumps(key["callback_data"]))

            if row < 0:
                bottom_keys[abs(row) - 1].insert(abs(column) - 1, inline_key)
                continue

            keyboard[row - 1].insert(column - 1, inline_key)

        for bottom_key in bottom_keys:
            keyboard.append(bottom_key)

        return InlineKeyboardMarkup(keyboard)

    @property
    def general_keyboard(self):
        logger.debug(keyboard.general)
        return self.get_keyboard(keyboard.general)

    def get_inline_keyboard(self, actions: list, urls: dict = None):
        keyboard.update_inline_keyboard(Product)
        keys = [key for key in keyboard.inline
                if key["callback_data"]["action"] in actions]

        logger.debug(keys)
        return self.get_keyboard(keys, urls)

    def _create_user(self) -> None:
        """Получает или создаёт пользователя в базе данных."""
        logger.log_function_call("BaseContext._create_user")
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
    def past_order(self):
        if not self._past_order:
            query = Order.query.order_by(Order.order_id.desc())
            order = query.filter_by(user_id = self._user.user_id,
                                    status  = StatusType.PENDING).first()

            self._past_order = order

        return self._past_order if self._past_order else None

    @property
    def _choice(self):
        choices = self._user.choice.split("/")
        check_index = lambda index: 0 <= index + 1 < len(choices)

        product_id = int(choices[0].split("?")[1]) if check_index(0) else None
        qty_id = int(choices[1].split("?")[1]) if check_index(1) else None
        asset_id = int(choices[2].split("?")[1]) if check_index(2) else None

        return product_id, qty_id, asset_id

    def choice_update(self, stage, choices, action, action_id):
        if stage == 1:
            if self._user.choice:
                self._user.choice = ""
        else:
            if len(choices) >= stage:
                self._user.choice = "/".join(choices[:-1]) + "/"
        self._user.choice += f"{action}?{action_id}/"
        self._user.commit()

__all__ = ['BaseContext']