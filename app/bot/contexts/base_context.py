import logging
from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.parsemode import ParseMode
from telegram.message import Message
from flask import current_app as app
from app.utils import Logger
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
        self.message = update.message if update.message else update.callback_query.message
        self.chat_id = self.message.chat_id
        self.user_id = self.message.from_user.id
        self.telegram_username = self.message.from_user.username
        
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

    def get_keyboard(self, text_data: list[str], callback_data: list[str] = None, to_generate = True) -> ReplyKeyboardMarkup or InlineKeyboardMarkup:
        if to_generate:
            return self._generate_keyboard(text_data, callback_data)


    @staticmethod
    def _generate_keyboard(text_data: list[str], callback_data: list[str] = None) -> ReplyKeyboardMarkup or InlineKeyboardMarkup:
        """Генерирует клавиатуру отталкиваясь от длины текста и количества кнопок в строке"""
        general_keyboard_max_line_length = 32
        inline_keyboard_max_line_length = 6
        max_key_qty = 5
        keyboard = []
        i = 0

        while i < len(text_data):
            line = []
            line_length = 0
            for text in text_data[i:]:
                if callback_data:
                    line.append(InlineKeyboardButton(text, callback_data=callback_data[i]))
                else:
                    line.append(KeyboardButton(text))
                line_length += len(text)
                i += 1
                if (line_length >= inline_keyboard_max_line_length if callback_data else
                    line_length >= general_keyboard_max_line_length) or (len(line) >= max_key_qty):
                    break
            keyboard.append(line)

        return InlineKeyboardMarkup(
            keyboard
        ) if callback_data else ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
            one_time_keyboard=False
        )

__all__ = ['BaseContext']