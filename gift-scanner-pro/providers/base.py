class GiftMissing(Exception):
    """Подарка с таким slug не существует (или он ещё не улучшен)."""


class ProviderUnavailable(Exception):
    """Источник не настроен или временно недоступен."""
