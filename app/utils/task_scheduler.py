import threading
import time
from typing import Callable
from . import Logger

logger = Logger("TaskScheduler")

class TaskScheduler:
    """Класс для управления фоновыми задачами (демонами)"""

    def __init__(self):
        self.threads = {}  # Словарь: {task_id: (thread, stop_event)}
        self.lock = threading.Lock()  # Для безопасного доступа к threads

    def start_task(self, task: Callable, interval_seconds: int, task_id: str):
        """Запускает задачу в отдельном потоке с заданным интервалом и идентификатором"""
        stop_event = threading.Event()
        thread = threading.Thread(
            target=self._run_scheduler,
            args=(task, interval_seconds, stop_event),
            daemon=True
        )
        with self.lock:
            self.threads[task_id] = (thread, stop_event)
        thread.start()
        logger.info(f"Запущена задача {task.__name__} с ID {task_id} и интервалом {interval_seconds} секунд")

    def stop_task(self, task_id: str):
        """Останавливает задачу по её ID"""
        with self.lock:
            if task_id in self.threads:
                thread, stop_event = self.threads[task_id]
                stop_event.set()  # Сигнализируем потоку остановиться
                thread.join()  # Ждём завершения потока
                del self.threads[task_id]
                logger.info(f"Задача с ID {task_id} остановлена")
            else:
                logger.warn(f"Задача с ID {task_id} не найдена")

    @staticmethod
    def _run_scheduler(task: Callable, interval_seconds: int, stop_event: threading.Event):
        """Запускает задачу по расписанию, пока не будет установлен stop_event"""
        while not stop_event.is_set():
            try:
                task()
            except Exception as e:
                logger.error(f"Ошибка в планировщике задачи {task.__name__}: {e}")
            # Спим интервал, но проверяем stop_event каждую секунду
            for _ in range(int(interval_seconds)):
                if stop_event.is_set():
                    break
                time.sleep(1)

    def stop_all(self):
        """Останавливает все активные задачи"""
        with self.lock:
            task_ids = list(self.threads.keys())
            for task_id in task_ids:
                self.stop_task(task_id)
        logger.info("Все задачи остановлены")