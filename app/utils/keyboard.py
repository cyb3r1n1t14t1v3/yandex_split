import json
from pathlib import Path
from . import Logger

logger = Logger("Keyboard")

class Keyboard:
    """Единый класс для работы с клавишами из keyboard.json."""

    def __init__(self):
        # Загружаем шаблоны из JSON
        with open(Path(__file__).parents[2] / "keyboard.json", "r", encoding="utf-8") as f:
            self.keyboard = json.load(f)

    def update_keyboard_config(self, product_model):
        for key in self.keyboard["inline"]:
            if key["callback_data"]["action"] == "select_order":
                product = product_model.query.get(int(key["callback_data"]["id"]))
                limit = product.account_limit
                price = product.price
                quantity = product.quantity

                key["text"] = key["text"].format(
                    limit_label = f"{limit: }",
                    price_label = f"{price: }",
                    quantity_label = f"{quantity: }"
                )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logger.error(f"Ошибка в Templates: {exc_type.__name__}: {exc_value}")

    @property
    def general(self):
        return self.keyboard["general"]

    @property
    def inline(self):
        return self.keyboard["inline"]

keyboard = Keyboard()