from .base_context import BaseContext
from app.utils import Logger, templates

logger = Logger("CommandContext")

class CommandContext(BaseContext):
    def __init__(self, update):
        super().__init__(update)

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logger.error(f"Ошибка в CommandContext: {exc_type.__name__}: {exc_value}")

    def start_command(self):
        logger.info(f"start_command от {self.user_id} в {self.chat_id}")

        self.send_message(templates.get("command", "start",
                                        telegram_username = templates.get("vars", "support_username")))

    def handle(self):
        """Обрабатывает команду пользователя.

        Returns:
            bool: True, если обработка успешна.
        """
        logger.log_function_call("CommandContext.handle")
        text = self.message.text
        index = text.find("@")
        end_index = None if index == -1 else index
        command = text[1:end_index].lower()

        match command:
            case "start":
                self.start_command()
            case _:
                logger.warn(f"Неизвестная команда [\"/{command}\"] от пользователя [\"{self.user_id}\"].")
                return False