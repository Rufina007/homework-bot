class InvalidResponseError(Exception):
    """Исключение для некорректного ответа API."""


class UnknownStatusError(Exception):
    """Исключение для неизвестного статуса домашней работы."""


class MissingTokenError(Exception):
    """Исключение при отсутствии обязательной переменной окружения."""
