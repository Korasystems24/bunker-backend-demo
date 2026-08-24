"""Итог сохранения батча: принято / вставлено / погашено как дубли."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SaveStats:
    received: int
    inserted: int
    duplicates: int
