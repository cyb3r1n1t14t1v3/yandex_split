from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from telegram import Bot
from telegram.ext import Dispatcher
from .config import Config
from .routes import webhook_bp
from .utils import Logger
import requests

db = SQLAlchemy()
logger = Logger("App")

def create_app():
    logger.debug("Создание приложения")
    app = Flask(__name__)
    app.config['TELEGRAM_TOKEN'] = Config.TELEGRAM_TOKEN
    app.config['WEBHOOK_URL'] = Config.WEBHOOK_URL
    app.config['SQLALCHEMY_DATABASE_URI'] \
        = 'mysql+pymysql://{0}:{1}@{2}/{3}?charset=utf8mb4'.format(
        Config.MYSQL_USER, Config.MYSQL_PASSWORD, Config.MYSQL_HOST, Config.MYSQL_DATABASE
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 600,
        'pool_size': 5,
        'max_overflow': 10,
    }

    db.init_app(app)

    from .models import User
    with app.app_context():
        db.create_all()

    # Initialize Telegram bot
    bot = Bot(token=app.config['TELEGRAM_TOKEN'])

    # Initialize Dispatcher
    dispatcher = Dispatcher(bot, None, workers=0)

    # Setup handlers
    from .bot import setup_handlers
    setup_handlers(dispatcher)

    # Register webhook blueprint
    app.register_blueprint(webhook_bp)

    # Store bot and dispatcher
    app.bot = bot
    app.dispatcher = dispatcher

    # Set webhook using requests
    logger.debug(f"Установка веб-хука на {app.config['WEBHOOK_URL']}")
    webhook_url = app.config['WEBHOOK_URL']
    response = requests.post(
        f"https://api.telegram.org/bot{app.config['TELEGRAM_TOKEN']}/setWebhook",
        json={"url": webhook_url}
    )
    if response.status_code == 200:
        logger.info("Веб-хук успешно установлен")
    else:
        logger.warning("Ошибка при установке веб-хука: {response.text}")

    logger.info("Приложение успешно создано")

    return app

__all__ = ['create_app', 'db']