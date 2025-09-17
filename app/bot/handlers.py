from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from .contexts.bot_context import YSContext
from app.utils import Logger, templates

logger = Logger("Handlers")

def handle_command(update, context):
    """Обработчик команд"""

    with YSContext(update) as bot:
        bot.handle()

def handle_text(update, context):
    """Обработчик текстовых сообщений от пользователей"""

    with YSContext(update) as bot:
        bot.text_handle()

def handle_callback(update, context):
    """Обработчик callback-методов от пользователей"""

    with YSContext(update) as bot:
        bot.callback_handle()

def handle_text_reply(update, context):
    """Обработчик текстовых ответов"""

    # with YSContext(update) as bot:
    #     bot.reply_method.handle()

def setup_handlers(dispatcher):
    dispatcher.add_handler(CallbackQueryHandler(handle_callback))
    dispatcher.add_handler(MessageHandler(Filters.command, handle_command))
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.reply, handle_text_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_text))
