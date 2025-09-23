import requests
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass
import threading
from ..config import Config
from . import Logger

logger = Logger("CryptoBotAPI")

@dataclass
class ExchangeRate:
    """Класс для представления обменного курса"""
    is_valid: bool
    is_crypto: bool
    is_fiat: bool
    source: str
    target: str
    rate: float
    timestamp: datetime

    def __post_init__(self):
        self.rate = float(self.rate)
        self.timestamp = datetime.fromisoformat(self.timestamp) if isinstance(self.timestamp, str) else self.timestamp


@dataclass
class CurrencyPair:
    """Класс для пары валют с курсами в обе стороны"""
    source: str
    target: str
    forward_rate: Optional[float] = None  # source -> target
    reverse_rate: Optional[float] = None  # target -> source
    last_updated: Optional[datetime] = None
    is_valid: bool = True


class CurrencyCache:
    """Кэш для курсов валют с TTL"""

    def __init__(self, ttl_minutes: int = 1):
        self.cache: Dict[str, ExchangeRate] = {}
        self.pairs: Dict[str, CurrencyPair] = {}
        self.ttl_minutes = ttl_minutes
        self.last_full_update = None

    def is_expired(self, rate: ExchangeRate) -> bool:
        """Проверяет, истек ли TTL для курса"""
        if not self.last_full_update:
            return True
        return datetime.now() - rate.timestamp > timedelta(minutes=self.ttl_minutes)

    def get_pair(self, source: str, target: str) -> Optional[CurrencyPair]:
        """Получает пару валют из кэша"""
        key = f"{source}_{target}"
        return self.pairs.get(key)

    def update_pair(self, source: str, target: str, rate: ExchangeRate) -> CurrencyPair:
        """Обновляет пару валют в кэше"""
        key = f"{source}_{target}"
        if key not in self.pairs:
            self.pairs[key] = CurrencyPair(source=source, target=target)

        pair = self.pairs[key]
        pair.forward_rate = rate.rate if rate.is_valid else None
        pair.last_updated = rate.timestamp
        pair.is_valid = rate.is_valid

        return pair

    def get_rate(self, source: str, target: str) -> Optional[float]:
        """Получает актуальный курс из кэша"""
        pair = self.get_pair(source, target)
        if pair and pair.forward_rate and pair.is_valid:
            return pair.forward_rate
        return None

    def update_from_api(self, rates: List[Dict[str, Any]]) -> None:
        """Обновляет кэш из ответа API"""
        self.last_full_update = datetime.now()

        for rate_data in rates:
            try:
                rate = ExchangeRate(
                    is_valid=rate_data['is_valid'],
                    is_crypto=rate_data['is_crypto'],
                    is_fiat=rate_data['is_fiat'],
                    source=rate_data['source'],
                    target=rate_data['target'],
                    rate=rate_data['rate'],
                    timestamp=datetime.now()
                )

                # Обновляем кэш только валидными курсами
                if rate.is_valid:
                    self.cache[f"{rate.source}_{rate.target}"] = rate
                    self.update_pair(rate.source, rate.target, rate)

            except (KeyError, ValueError) as e:
                logger.warn(f"Ошибка парсинга курса {rate_data}: {e}")
                continue

    def get_all_valid_rates(self) -> List[ExchangeRate]:
        """Возвращает все валидные курсы из кэша"""
        return [
            rate for rate in self.cache.values()
            if rate.is_valid and not self.is_expired(rate)
        ]


@dataclass
class Invoice:
    """Класс для представления инвойса"""
    invoice_id: int
    hash: str
    status: str
    currency_type: Optional[str] = None
    asset: Optional[str] = None
    amount: Optional[float] = None
    pay_url: Optional[str] = None
    bot_invoice_url: Optional[str] = None
    mini_app_invoice_url: Optional[str] = None
    web_app_invoice_url: Optional[str] = None
    created_at: Optional[str] = None
    allow_comments: Optional[bool] = True
    allow_anonymous: Optional[bool] = True

    # Добавьте другие поля по необходимости

    def __post_init__(self):
        if self.amount:
            self.amount = float(self.amount)

class InvoiceManager:
    """Менеджер для отслеживания и отмены инвойсов по времени"""

    def __init__(self, api):
        self.api = api
        self.invoices: Dict[int, Invoice] = {}  # invoice_id -> Invoice
        self.expiry_timers: Dict[int, threading.Timer] = {}  # invoice_id -> Timer
        self.lock = threading.Lock()

    def add_invoice(self, invoice_data: Dict[str, Any], auto_cancel_seconds: Optional[int] = None) -> Invoice:
        """Добавляет инвойс в менеджер и устанавливает таймер отмены если нужно"""
        invoice = Invoice(**invoice_data)

        with self.lock:
            self.invoices[invoice.invoice_id] = invoice

            if auto_cancel_seconds:
                self._schedule_cancellation(invoice.invoice_id, auto_cancel_seconds)

        return invoice

    def _schedule_cancellation(self, invoice_id: int, seconds: int):
        """Планирует отмену инвойса через указанное время"""
        if invoice_id in self.expiry_timers:
            self.expiry_timers[invoice_id].cancel()

        timer = threading.Timer(seconds, self._cancel_invoice, args=(invoice_id,))
        timer.daemon = True
        timer.start()

        self.expiry_timers[invoice_id] = timer
        logger.info(f"Запланирована отмена инвойса {invoice_id} через {seconds} секунд")

    def _cancel_invoice(self, invoice_id: int):
        """Отменяет инвойс по таймауту"""
        with self.lock:
            if invoice_id not in self.invoices:
                return

            invoice = self.invoices[invoice_id]
            if invoice.status != "active":
                logger.info(f"Инвойс {invoice_id} уже не активен, отмена не требуется")
                return

        success = self.api.delete_invoice(invoice_id)
        if success:
            logger.info(f"Инвойс {invoice_id} отменен по таймауту")
            with self.lock:
                if invoice_id in self.invoices:
                    self.invoices[invoice_id].status = "expired"  # Или "cancelled"
                if invoice_id in self.expiry_timers:
                    del self.expiry_timers[invoice_id]
        else:
            logger.error(f"Ошибка отмены инвойса {invoice_id} по таймауту")

    def check_invoice_status(self, invoice_id: int, update_from_api: bool = True) -> Optional[Invoice]:
        """Проверяет статус инвойса"""
        with self.lock:
            if invoice_id in self.invoices:
                invoice = self.invoices[invoice_id]

                if not update_from_api:
                    return invoice

                # Обновляем из API
                updated_data = self.api.get_invoices(invoice_ids=str(invoice_id))
                if updated_data and updated_data[0]:
                    updated_invoice = Invoice(**updated_data[0])
                    self.invoices[invoice_id] = updated_invoice
                    return updated_invoice

                return invoice

        return None

    def is_paid(self, invoice_id: int) -> bool:
        """Проверяет, оплачен ли инвойс"""
        invoice = self.check_invoice_status(invoice_id)
        return invoice.status == "paid" if invoice else False

    def remove_invoice(self, invoice_id: int):
        """Удаляет инвойс из менеджера"""
        with self.lock:
            if invoice_id in self.expiry_timers:
                self.expiry_timers[invoice_id].cancel()
                del self.expiry_timers[invoice_id]
            if invoice_id in self.invoices:
                del self.invoices[invoice_id]


class CryptoBotAPI:
    def __init__(self, cache_ttl_minutes: int = 1, auto_cancel_default_seconds: int = 3600):
        self.url = "https://pay.crypt.bot/api/"
        self.headers = {
            "Crypto-Pay-API-Token": Config.CRYPTO_BOT_TOKEN
        }
        self.currency_cache = CurrencyCache(ttl_minutes=cache_ttl_minutes)
        self.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
        self.last_error_time = None
        self.error_streak = 0
        self.invoice_manager = InvoiceManager(self)
        self.auto_cancel_default = auto_cancel_default_seconds  # По умолчанию 1 час

        # Запускаем фоновую проверку инвойсов
        self._start_invoice_checker()

    def _start_invoice_checker(self):
        """Запускает планировщик для периодической проверки инвойсов"""

        def check_invoices():
            with self.invoice_manager.lock:
                active_ids = [inv.invoice_id for inv in self.invoice_manager.invoices.values()
                              if inv.status == "active"]

            if active_ids:
                logger.info(f"Проверка {len(active_ids)} активных инвойсов")
                updated = self.get_invoices(invoice_ids=','.join(map(str, active_ids)),
                                            status="active")

                if updated:
                    for data in updated:
                        inv = Invoice(**data)
                        self.invoice_manager.invoices[inv.invoice_id] = inv
                        if inv.status == "paid":
                            logger.info(f"Инвойс {inv.invoice_id} оплачен!")
                        elif inv.status == "expired":
                            logger.info(f"Инвойс {inv.invoice_id} истек")

        # Проверяем каждые 5 минут
        threading.Thread(target=self._run_scheduler, args=(check_invoices, 10), daemon=True).start()

    def _run_scheduler(self, task, interval_seconds: int):
        """Запускает задачу по расписанию"""
        while True:
            try:
                task()
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
            time.sleep(interval_seconds)

    def _execute(self, method: str, params: Optional[Dict[str, Any]] = None,
                 use_get: bool = False) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]], bool]]:
        """Выполняет HTTP запрос с улучшенной обработкой ошибок"""

        # Проверка rate limiting
        if not self.rate_limiter.allow_request():
            logger.warn(f"Превышен лимит запросов для {method}")
            return None

        # Параметры по умолчанию
        if params is None:
            params = {}

        try:
            # Подготавливаем запрос
            if use_get:
                response = requests.get(
                    f"{self.url}{method}",
                    headers=self.headers,
                    params=params,
                    timeout=10
                )
            else:
                response = requests.post(
                    f"{self.url}{method}",
                    headers=self.headers,
                    data=params,
                    timeout=10
                )

            data = response.json()
            logger.debug(f"Ответ на запрос {method}: {data}")

            response.raise_for_status()

            # Проверяем ответ API
            if data.get("ok"):
                logger.debug(f"Успешный запрос: {method}")
                self.error_streak = 0  # Сбрасываем счетчик ошибок
                result = data.get("result")
                if isinstance(result, bool):  # Для deleteInvoice
                    return result
                return result
            else:
                error = data.get("error", {})
                logger.error(f"API ошибка {method}: {error.get('name', 'Unknown')} - {error.get('description', '')}")
                self._handle_api_error()
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Таймаут запроса {method}")
            self._handle_request_error("timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка сети {method}: {e}")
            self._handle_request_error("network")
            return None
        except ValueError as e:
            logger.error(f"Ошибка парсинга JSON {method}: {e}")
            self._handle_request_error("json")
            return None

    def _handle_api_error(self):
        """Обработка ошибок API"""
        self.error_streak += 1
        if self.error_streak >= 3:
            logger.warn(f"Серия из {self.error_streak} ошибок API")

    def _handle_request_error(self, error_type: str):
        """Обработка технических ошибок"""
        self.error_streak += 1
        self.last_error_time = datetime.now()
        logger.warn(f"Техническая ошибка ({error_type}), серия: {self.error_streak}")

    # === КУРСЫ ВАЛЮТ ===

    def get_exchange_rates(self, force_refresh: bool = False) -> Optional[List[ExchangeRate]]:
        """
        Получает курсы валют с кэшированием

        Args:
            force_refresh: Принудительно обновить кэш

        Returns:
            Список ExchangeRate или None при ошибке
        """
        # Проверяем кэш
        if not force_refresh:
            cached_rates = self.currency_cache.get_all_valid_rates()
            if cached_rates:
                logger.debug(f"Используем кэш: {len(cached_rates)} курсов")
                return cached_rates

        # Делаем запрос к API
        logger.info("Обновление курсов валют")
        result = self._execute("getExchangeRates", use_get=True)

        if result:
            try:
                # Обновляем кэш
                self.currency_cache.update_from_api(result)

                # Возвращаем актуальные курсы
                fresh_rates = self.currency_cache.get_all_valid_rates()
                logger.info(f"Получено {len(fresh_rates)} валидных курсов")

                # Логируем ключевые курсы
                usd_rates = {r.target: r.rate for r in fresh_rates
                             if r.source == "USDT" and r.is_valid}
                if usd_rates:
                    logger.debug(f"USD курсы: {usd_rates}")

                return fresh_rates

            except Exception as e:
                logger.error(f"Ошибка обработки курсов: {e}")
                return None

        # Fallback к кэшу при ошибке
        stale_rates = [r for r in self.currency_cache.cache.values()
                       if not self.currency_cache.is_expired(r)]
        if stale_rates:
            logger.warn(f"Используем устаревший кэш: {len(stale_rates)} курсов")
            return stale_rates

        return None

    def get_exchange_rate(self, source: str, target: str,
                          force_refresh: bool = False) -> Optional[ExchangeRate]:
        """
        Получает конкретный курс обмена

        Args:
            source: Исходная валюта (USDT, BTC, ETH и т.д.)
            target: Целевая валюта (USD, RUB, EUR и т.д.)
            force_refresh: Принудительно обновить

        Returns:
            ExchangeRate или None
        """
        # Сначала проверяем кэш
        cached_rate = self.currency_cache.get_rate(source, target)
        if cached_rate and not force_refresh:
            logger.debug(f"Курс {source}->{target} из кэша: {cached_rate}")
            return ExchangeRate(
                is_valid=True,
                is_crypto=True,  # USDT -> крипта
                is_fiat=target in ["USD", "EUR", "RUB"],  # Целевая - фиат
                source=source,
                target=target,
                rate=cached_rate,
                timestamp=datetime.now()
            )

        # Получаем все курсы
        rates = self.get_exchange_rates(force_refresh=force_refresh)
        if not rates:
            return None

        # Ищем нужную пару
        for rate in rates:
            if rate.source == source and rate.target == target:
                logger.info(f"Курс {source}->{target}: {rate.rate}")
                return rate

        logger.warn(f"Курс {source}->{target} не найден")
        return None

    def convert_amount(self, amount: float, from_currency: str, to_currency: str,
                       force_refresh: bool = False) -> Optional[float]:
        """
        Конвертирует сумму из одной валюты в другую

        Args:
            amount: Сумма для конвертации
            from_currency: Исходная валюта
            to_currency: Целевая валюта
            force_refresh: Принудительно обновить курс

        Returns:
            Конвертированная сумма или None
        """
        if from_currency == to_currency:
            return amount

        # Для USD используем USDT как прокси
        if from_currency == "USD":
            from_currency = "USDT"

        rate = self.get_exchange_rate(from_currency, to_currency, force_refresh)

        if not rate:
            rate = self.get_exchange_rate(to_currency, from_currency, force_refresh)
            if rate:
                rate.rate = 1 / rate.rate

        if not rate:
            logger.error(f"Не удалось получить курс {from_currency}->{to_currency}")
            return None

        try:
            converted = amount * rate.rate
            logger.info(f"Конвертация: {amount} {from_currency} = {converted:.2f} {to_currency} "
                        f"(курс: {rate.rate})")
            return converted
        except (ValueError, TypeError) as e:
            logger.error(f"Ошибка конвертации: {e}")
            return None

    def get_usd_to_rub_rate(self, force_refresh: bool = False) -> Optional[float]:
        """Удобный метод для получения курса USD -> RUB"""
        rate = self.get_exchange_rate("USDT", "RUB", force_refresh)
        return rate.rate if rate else None

    def convert_usd_to_rub(self, usd_amount: float, force_refresh: bool = False) -> Optional[float]:
        """Удобный метод для конвертации USD -> RUB"""
        return self.convert_amount(usd_amount, "USD", "RUB", force_refresh)

    # === ИНВОЙСЫ ===

    def create_invoice(self, asset: str, amount: float,
                       fiat: Optional[str] = None,
                       description: Optional[str] = None,
                       expires_in: Optional[int] = None,
                       auto_cancel_seconds: Optional[int] = None,
                       **kwargs) -> Optional[Invoice]:
        """
        Создает инвойс с поддержкой фиатных валют и автоотменой

        Args:
            asset: Криптовалюта (если currency_type=crypto)
            amount: Сумма
            fiat: Фиатная валюта (если currency_type=fiat)
            description: Описание инвойса
            expires_in: Время истечения в секундах (API параметр)
            auto_cancel_seconds: Локальное время для отмены (если expires_in не указан)
            **kwargs: Дополнительные параметры createInvoice
        """
        params = {
            "amount": f"{amount:.8f}".rstrip('0').rstrip('.'),
        }

        if fiat:
            # Фиатный инвойс
            params.update({
                "currency_type": "fiat",
                "fiat": fiat
            })
        else:
            # Крипто инвойс
            params.update({
                "currency_type": "crypto",
                "asset": asset
            })

        if description:
            params["description"] = description

        if expires_in:
            params["expires_in"] = str(expires_in)

        # Добавляем дополнительные параметры
        params.update(kwargs)

        logger.info(f"Создание инвойса: {amount} {fiat or asset}")
        result = self._execute("createInvoice", params)

        if result:
            # Добавляем в менеджер
            auto_cancel = auto_cancel_seconds or (expires_in if expires_in else self.auto_cancel_default)
            invoice = self.invoice_manager.add_invoice(result, auto_cancel_seconds=auto_cancel)
            return invoice

        return None

    def create_usd_invoice(self, usd_amount: float,
                           description: Optional[str] = None,
                           accepted_assets: Optional[str] = None,
                           expires_in: Optional[int] = None,
                           auto_cancel_seconds: Optional[int] = None,
                           **kwargs) -> Optional[Invoice]:
        """
        Создает инвойс в USD с автоматическим расчетом

        Args:
            usd_amount: Сумма в USD
            description: Описание
            accepted_assets: Принимаемые криптовалюты (через запятую)
            expires_in: Время истечения
            auto_cancel_seconds: Локальное время отмены
            **kwargs: Дополнительные параметры
        """
        params = {
            "currency_type": "fiat",
            "fiat": "USD",
            "amount": f"{usd_amount:.2f}",
            "description": description or f"Оплата {usd_amount} USD",
        }

        if accepted_assets:
            params["accepted_assets"] = accepted_assets

        if expires_in:
            params["expires_in"] = str(expires_in)

        params.update(kwargs)

        logger.info(f"Создание USD инвойса: {usd_amount} USD")
        result = self._execute("createInvoice", params)

        if result:
            auto_cancel = auto_cancel_seconds or (expires_in if expires_in else self.auto_cancel_default)
            invoice = self.invoice_manager.add_invoice(result, auto_cancel_seconds=auto_cancel)
            return invoice

        return None

    def get_invoices(self, asset: Optional[str] = None,
                     fiat: Optional[str] = None,
                     invoice_ids: Optional[str] = None,
                     status: Optional[str] = None,
                     offset: int = 0,
                     count: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Получает список инвойсов"""
        params = {
            "offset": str(offset),
            "count": str(count)
        }
        if asset:
            params["asset"] = asset
        if fiat:
            params["fiat"] = fiat
        if invoice_ids:
            params["invoice_ids"] = invoice_ids
        if status:
            params["status"] = status

        return self._execute("getInvoices", params, use_get=True)["items"]

    def delete_invoice(self, invoice_id: int) -> bool:
        """Удаляет инвойс"""
        params = {"invoice_id": str(invoice_id)}
        result = self._execute("deleteInvoice", params)
        if result:
            self.invoice_manager.remove_invoice(invoice_id)
        return bool(result)

    def check_invoice_paid(self, invoice_id: int) -> bool:
        """Проверяет оплату инвойса"""
        return self.invoice_manager.is_paid(invoice_id)

    # === ТРАНЗАКЦИИ (TRANSFER) ===

    def transfer(self, user_id: int, asset: str, amount: float,
                 spend_id: str, comment: Optional[str] = None,
                 disable_notification: bool = False) -> Optional[Dict[str, Any]]:
        """
        Совершает транзакцию (отправку средств пользователю)

        Args:
            user_id: ID пользователя Telegram
            asset: Криптовалюта
            amount: Сумма
            spend_id: Уникальный ID для идемпотентности
            comment: Комментарий
            disable_notification: Не отправлять уведомление
        """
        params = {
            "user_id": str(user_id),
            "asset": asset,
            "amount": f"{amount:.8f}".rstrip('0').rstrip('.'),
            "spend_id": spend_id
        }

        if comment:
            params["comment"] = comment
        if disable_notification:
            params["disable_send_notification"] = "true"

        logger.info(f"Совершение трансфера: {amount} {asset} пользователю {user_id}")
        return self._execute("transfer", params)

    def get_transfers(self, asset: Optional[str] = None,
                      transfer_ids: Optional[str] = None,
                      spend_id: Optional[str] = None,
                      offset: int = 0,
                      count: int = 100) -> Optional[List[Dict[str, Any]]]:
        """Получает список трансферов"""
        params = {
            "offset": str(offset),
            "count": str(count)
        }
        if asset:
            params["asset"] = asset
        if transfer_ids:
            params["transfer_ids"] = transfer_ids
        if spend_id:
            params["spend_id"] = spend_id

        return self._execute("getTransfers", params, use_get=True)

    # === УТИЛИТЫ ===

    def get_balance(self) -> Optional[List[Dict[str, Any]]]:
        """Получает баланс приложения"""
        return self._execute("getBalance", use_get=True)

    def get_currencies(self) -> Optional[List[str]]:
        """Получает список поддерживаемых валют"""
        result = self._execute("getCurrencies", use_get=True)
        return result if result else None


class RateLimiter:
    """Простой rate limiter"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []

    def allow_request(self) -> bool:
        """Проверяет, можно ли выполнить запрос"""
        now = time.time()

        # Удаляем старые запросы
        self.requests = [req for req in self.requests if now - req < self.window_seconds]

        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True

        return False