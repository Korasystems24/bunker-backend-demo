"""Юнит-тесты эвристики buildup v1: математика синхронна с computeBuildupZones мока."""

import pytest
from src.application.buildup.detector import RadialSlopeDeviationDetector
from src.domain.beam_rules import AXES, POSITIONS_PER_AXIS
from src.domain.value_objects.beam import Beam
from src.domain.value_objects.beam_status import BeamStatus

THRESHOLD = 0.35


def make_detector() -> RadialSlopeDeviationDetector:
    return RadialSlopeDeviationDetector(
        outer_position_threshold=6, deviation_threshold_m=THRESHOLD
    )


def empty_beams() -> list[Beam]:
    return [Beam(height=None, raw_status=None, status=()) for _ in range(64)]


def set_beam(
    beams: list[Beam],
    axis: str,
    position: int,
    height: float,
    *statuses: BeamStatus,
) -> None:
    index = AXES.index(axis) * POSITIONS_PER_AXIS + position - 1
    beams[index] = Beam(height=height, raw_status=None, status=statuses)


def flat_axis(axis: str) -> list[Beam]:
    """Ровный склон без аномалии: высота 2.0 на всех позициях."""
    beams = empty_beams()
    for position in range(1, 9):
        set_beam(beams, axis, position, 2.0)
    return beams


class TestDetect:
    def test_flat_slope_has_no_zones(self) -> None:
        # Зоны отдаются всегда по всем осям (контракт мока), даже без лучей.
        zones = {z.axis: z for z in make_detector().detect(flat_axis("A"))}
        assert len(zones) == 8
        zone = zones["A"]
        assert zone.severity == "none"
        assert zone.score == 0.0
        assert zone.affected_positions == ()

    def test_outer_bump_is_detected(self) -> None:
        # Внутренние позиции задают уклон ~ -0.1/шаг; внешние подняты на +1.0 м.
        beams = empty_beams()
        for position in range(1, 6):
            set_beam(beams, "C", position, 3.0 - 0.1 * (position - 1))
        for position in range(6, 9):
            set_beam(beams, "C", position, 3.0 - 0.1 * (position - 1) + 1.0)

        zone = {z.axis: z for z in make_detector().detect(beams)}["C"]

        assert zone.severity == "high"  # отклонение 1.0 > 0.35 * 2.5
        assert sorted(zone.affected_positions) == [6, 7, 8]
        assert zone.deviation_m == pytest.approx(1.0, abs=1e-3)
        assert 0.9 < zone.score <= 1.0

    def test_small_deviation_below_threshold_is_ignored(self) -> None:
        # Внешние выше склона на 0.2 < порога 0.35 — зоны нет.
        beams = empty_beams()
        for position in range(1, 6):
            set_beam(beams, "B", position, 2.5 - 0.05 * (position - 1))
        for position in range(6, 9):
            set_beam(beams, "B", position, 2.5 - 0.05 * (position - 1) + 0.2)

        zone = {z.axis: z for z in make_detector().detect(beams)}["B"]

        assert zone.severity == "none"
        assert zone.affected_positions == ()
        assert zone.deviation_m == pytest.approx(0.2, abs=1e-3)

    def test_hard_unreliable_beams_excluded(self) -> None:
        beams = flat_axis("D")
        set_beam(beams, "E", 1, 50.0, BeamStatus.DISABLED)
        set_beam(beams, "D", 1, 50.0, BeamStatus.NOT_USED)

        zones = {z.axis: z for z in make_detector().detect(beams)}

        assert zones["D"].severity == "none"
        assert all(z.severity == "none" for axis, z in zones.items() if axis != "D")

    def test_all_eight_axes_always_reported(self) -> None:
        beams = empty_beams()
        for axis in AXES:
            for position in range(1, 9):
                set_beam(beams, axis, position, 2.0)

        zones = make_detector().detect(beams)

        assert [z.axis for z in zones] == list("ABCDEFGH")
        assert all(z.severity == "none" for z in zones)

    def test_too_few_inner_positions_gives_none(self) -> None:
        # Только один надёжный внутренний луч → регрессия невозможна.
        beams = empty_beams()
        set_beam(beams, "A", 1, 2.0)
        set_beam(beams, "A", 6, 2.0)
        set_beam(beams, "A", 7, 5.0)

        zone = make_detector().detect(beams)[0]

        assert zone.severity == "none"
