import json
import string
from pathlib import Path
from . import Logger

logger = Logger("Templates")

class Templates:
    """Единый класс для работы с шаблонами из templates.json."""
    def __init__(self):
        # Загружаем шаблоны из JSON
        with open(Path(__file__).parents[2] / "templates.json", "r", encoding="utf-8") as f:
            self.templates = json.load(f)

        # Преобразуем шаблоны в string.Template
        for context in self.templates:
            for key, value in self.templates[context].items():
                if isinstance(value, list):
                    # Для массивов (например, profile) объединяем в одну строку
                    self.templates[context][key] = string.Template("\n".join(value))
                elif isinstance(value, str):
                    self.templates[context][key] = string.Template(value)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            logger.error(f"Ошибка в Templates: {exc_type.__name__}: {exc_value}")

    def get(self, context, template_key, **kwargs):
        """Получает отформатированный шаблон.

        Args:
            context (str): Контекст шаблона (например, "user", "inventory").
            template_key (str): Ключ шаблона (например, "profile", "change_field").
            **kwargs: Дополнительные аргументы для подстановки (user_id, username, field, etc.).

        Returns:
            str: Форматированная строка.

        Raises:
            KeyError: Если cont ext или template_key отсутствуют.
            ValueError: Если требуемые параметры отсутствуют.
        """
        if context not in self.templates:
            raise KeyError(f"Контекст '{context}' не найден в templates.json")
        if template_key not in self.templates[context]:
            raise KeyError(f"Шаблон '{template_key}' не найден в контексте '{context}'")

        template = self.templates[context][template_key]

        if isinstance(template, int):
            return template

        try:
            return template.substitute(**kwargs)
        except KeyError as e:
            raise KeyError(f"Параметр {str(e)} не предоставлен для шаблона '{template_key}' в контексте '{context}'")

templates = Templates()