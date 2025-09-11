import logging
from telegram.parsemode import ParseMode
from flask import current_app as app
from app.utils import Logger
from telegram.message import Message
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
        self.message = update.message
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
                        disable_web_page_preview=self._disable_web_page_preview)
                case _:
                    message = app.bot.send_message(
                        chat_id=params["chat_id"], text=params["text"],
                        reply_to_message_id = params["message_id"] if method == APIMethod.REPLY_TO_MESSAGE else None,
                        parse_mode=self._parse_mode,
                        disable_web_page_preview=self._disable_web_page_preview)

            logger.info(f"Успешное выполнение команды {method}: {data_pattern}")
            return message if message else True
        except Exception as e:
            logger.error(f"Ошибка при выполнении команды {method}: {data_pattern}: {e}")
            raise e

    def send_message(self, text) -> Message:
        """Отправляет сообщение пользователю."""
        logger.log_function_call("BaseContext.send_message")
        return self._execute(APIMethod.SEND_MESSAGE, text=text)

    def delete_message(self, message_id) -> bool:
        """Удаляет сообщение по message_id."""
        logger.log_function_call("BaseContext.delete_message")
        return self._execute(APIMethod.DELETE_MESSAGE, message_id=message_id)

    def reply_to_message(self, message_id, text) -> Message:
        """Отвечает на сообщение по message_id."""
        logger.log_function_call("BaseContext.reply_to_message")
        return self._execute(APIMethod.REPLY_TO_MESSAGE, message_id=message_id, text=text)

    def edit_message_text(self, message_id, text) -> Message:
        """Редактирует текстовое сообщение по message_id."""
        logger.log_function_call("BaseContext.edit_message_text")
        return self._execute(APIMethod.EDIT_MESSAGE_TEXT, message_id=message_id, text=text)

__all__ = ['BaseContext']