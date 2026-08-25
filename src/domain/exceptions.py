"""Исключения домена."""


class DomainError(Exception):
    """Базовое исключение домена."""


class NotFoundError(DomainError):
    """Запрошенный объект отсутствует (маппится в 404 на границе API)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# Тексты совпадают с телами ошибок мока: latest → "No measurements",
# stats/buildup → "No data", неизвестный бункер → "Bunker not found".
class BunkerNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("Bunker not found")


class MeasurementsNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("No measurements")


class NoDataNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__("No data")
