from telegram.ext import CommandHandler, MessageHandler, Filters
from .contexts.command_context import CommandContext
from app.utils import Logger, templates

logger = Logger("Handlers")

def handle_command(update, context):
    """Обработчик команд"""

    with CommandContext(update) as command:
        command.handle()

def handle_text(update, context):
    """Обработчик текстовых сообщений от пользователей"""
    pass

def handle_text_reply(update, context):
    """Обработчик текстовых ответов"""
    # with UserContext(update) as user:
    #     user.reply_method.handle()

def setup_handlers(dispatcher):
    dispatcher.add_handler(MessageHandler(Filters.command, handle_command))
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.reply, handle_text_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_text))
