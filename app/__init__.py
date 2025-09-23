from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from telegram import Bot
from telegram.ext import Dispatcher
from .config import Config
from .routes import webhook_bp
from .utils import Logger
from .utils import TaskScheduler, keyboard, templates
import requests
import random

db = SQLAlchemy()
logger = Logger("App")

def create_app():
    logger.debug("Создание приложения")
    app = Flask(__name__)
    scheduler = TaskScheduler()
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

    from .models import User, Product
    with app.app_context():
        db.create_all()

        keyboard.update_inline_keyboard(Product)
        logger.info("Клавиатурный конфиг успешно обновлен")

        def stock_auto_update():
            with app.app_context():
                products = Product.query.all()
                random_products = templates.get("vars", "stock_auto_update_is_random_products")
                random_qty = templates.get("vars", "stock_auto_update_range_qty")
                max_qty = templates.get("vars", "stock_auto_update_max_qty")

                for product in products:
                    index = product.product_id - 1
                    if product.quantity < max_qty[index]:
                        product.quantity += 0 if random_products and random.getrandbits(1) else (
                            random.randint(*random_qty[index]))

                db.session.commit()

        stock_auto_update_time = random.randint(*templates.get("vars", "stock_auto_update_range_seconds"))
        scheduler.start_task(stock_auto_update, stock_auto_update_time, task_id="stock_auto_update")

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