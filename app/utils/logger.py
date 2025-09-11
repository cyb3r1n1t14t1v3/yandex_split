import logging
import sys
import os
from datetime import datetime
from app.config import Config

class Logger:
    """Класс для логирования в консоль и файл с разными уровнями сообщений"""

    _instances = {}
    MAX_LOG_FILES = 10

    def __new__(cls, name="Bot", level=logging.INFO):
        if name not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[name] = instance
        return cls._instances[name]

    def __init__(self, name="Bot", level=logging.INFO):
        if hasattr(self, 'logger'):
            return

        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        if self.logger.handlers:
            self.logger.handlers.clear()

        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s',
            datefmt='%H:%M:%S'
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Инициализация данных для файла
        self._current_date = None
        self._file_handler = None
        self._update_file_handler()  # Создаём первый файл при инициализации

        self.info(f"Логгер инициализирован с именем {name} и уровнем {logging.getLevelName(level)}")

    @property
    def level(self):
        return self.logger.level

    def _update_file_handler(self):
        """Обновляет FileHandler для нового дня"""
        new_date = datetime.now().strftime("%Y-%m-%d")
        if self._current_date != new_date:
            # Закрываем старый FileHandler, если он существует
            if self._file_handler:
                self._file_handler.close()
                self.logger.removeHandler(self._file_handler)

            # Создаём новую директорию и путь к файлу
            os.makedirs(Config.LOGS_DIR_PATH, exist_ok=True)
            log_file = f"log_{new_date}.log"
            log_path = os.path.join(Config.LOGS_DIR_PATH, log_file)

            # Создаём новый FileHandler
            self._file_handler = logging.FileHandler(log_path, encoding='utf-8')
            self._file_handler.setFormatter(logging.Formatter(
                '[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s',
                datefmt='%H:%M:%S'
            ))
            self.logger.addHandler(self._file_handler)

            # Обновляем текущую дату
            self._current_date = new_date

            # Управление количеством файлов
            self._manage_log_files()

    def _manage_log_files(self):
        """Проверяет количество файлов логов и удаляет старые, если их больше MAX_LOG_FILES"""
        log_files = [f for f in os.listdir(Config.LOGS_DIR_PATH) if f.startswith("log_") and f.endswith(".log")]
        log_files = [os.path.join(Config.LOGS_DIR_PATH, f) for f in log_files]

        if len(log_files) > self.MAX_LOG_FILES:
            log_files.sort(key=os.path.getmtime)
            files_to_delete = log_files[:len(log_files) - self.MAX_LOG_FILES]
            for file in files_to_delete:
                try:
                    os.remove(file)
                except OSError as e:
                    self.logger.warning(f"Ошибка при удалении старого лог-файла {file}: {e}")

    def _log(self, level, message, *args, **kwargs):
        """Общая логика для всех уровней с проверкой даты"""
        self._update_file_handler()  # Проверяем и обновляем файл перед записью
        self.logger.log(level, message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        self._log(logging.DEBUG, message, *args, **kwargs)

    def info(self, message, *args, **kwargs):
        self._log(logging.INFO, message, *args, **kwargs)

    def warn(self, message, *args, **kwargs):
        self._log(logging.WARN, message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self._log(logging.ERROR, message, *args, **kwargs)

    def log_function_call(self, func_name):
        self.debug(f"Вызов функции {func_name}")