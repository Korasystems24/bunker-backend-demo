"""Юнит-тест чистой функции min/max по надёжным лучам (без БД)."""

from src.application.ingestion.levels import compute_min_max_levels
from src.domain.value_objects.beam import Beam
from src.domain.value_objects.beam_status import BeamStatus


def _beam(height: float | None, *statuses: BeamStatus) -> Beam:
    return Beam(height=height, raw_status=None, status=statuses)


def test_min_max_ignores_flagged_and_missing_heights() -> None:
    beams = [
        _beam(None),  # без значения
        _beam(1.0),
        _beam(5.0, BeamStatus.WEAK_SIGNAL),
        _beam(9.0, BeamStatus.HEIGHT_SIMULATED),
    ]

    assert compute_min_max_levels(beams) == (1.0, 1.0)


def test_not_used_beams_excluded() -> None:
    """Перебой питания лидара: все лучи NotUsed -> уровней нет."""
    beams = [_beam(None, BeamStatus.NOT_USED) for _ in range(64)]

    assert compute_min_max_levels(beams) == (None, None)


def test_bounds_over_reliable_beams() -> None:
    beams = [_beam(float(position)) for _axis in "AB" for position in range(1, 9)]

    assert compute_min_max_levels(beams) == (1.0, 8.0)
