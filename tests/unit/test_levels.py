"""Юнит-тест чистой функции min/max по достоверным лучам (без БД)."""

from src.application.ingestion.levels import compute_min_max_levels, sanitize_avg_level
from src.domain.value_objects.beam import Beam
from src.domain.value_objects.beam_status import BeamStatus


def _beam(height: float | None, *statuses: BeamStatus) -> Beam:
    return Beam(height=height, raw_status=None, status=statuses)


def test_min_max_ignores_hard_flags_and_missing_heights() -> None:
    # Правило мока (isBeamReliable): исключаются только «жёсткие» флаги
    # Disabled/DistanceNotUpdating/NotUsed/Unknown и лучи без высоты.
    beams = [
        _beam(None),  # без значения
        _beam(1.0),
        _beam(0.5, BeamStatus.DISABLED),
        _beam(0.4, BeamStatus.NOT_USED),
        _beam(0.3, BeamStatus.UNKNOWN),
    ]

    assert compute_min_max_levels(beams) == (1.0, 1.0)


def test_zero_height_is_not_a_level() -> None:
    """height=0 — нет эха, даже при мягком флаге вроде OutOfReposeAngle."""
    beams = [
        _beam(0.0, BeamStatus.OUT_OF_REPOSE_ANGLE),
        _beam(0.0),
        _beam(1.7),
        _beam(2.2),
    ]

    assert compute_min_max_levels(beams) == (1.7, 2.2)


def test_sanitize_avg_level_drops_zero() -> None:
    assert sanitize_avg_level(None) is None
    assert sanitize_avg_level(0.0) is None
    assert sanitize_avg_level(-0.1) is None
    assert sanitize_avg_level(1.96) == 1.96


def test_soft_flags_do_not_exclude_beam() -> None:
    """WeakSignal/*Simulated не «жёсткие»: луч остаётся достоверным, как в моке."""
    beams = [
        _beam(1.0),
        _beam(5.0, BeamStatus.WEAK_SIGNAL),
        _beam(9.0, BeamStatus.HEIGHT_SIMULATED),
        _beam(2.0, BeamStatus.OUT_OF_REPOSE_ANGLE, BeamStatus.TOO_SHORT),
    ]

    assert compute_min_max_levels(beams) == (1.0, 9.0)


def test_not_used_beams_excluded() -> None:
    """Перебой питания лидара: все лучи NotUsed -> уровней нет."""
    beams = [_beam(None, BeamStatus.NOT_USED) for _ in range(64)]

    assert compute_min_max_levels(beams) == (None, None)


def test_bounds_over_reliable_beams() -> None:
    beams = [_beam(float(position)) for _axis in "AB" for position in range(1, 9)]

    assert compute_min_max_levels(beams) == (1.0, 8.0)
