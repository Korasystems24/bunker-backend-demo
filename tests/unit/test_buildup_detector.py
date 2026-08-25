"""Юнит-тесты эвристики buildup v1: математика синхронна с computeBuildupZones мока."""

import pytest
from src.application.buildup.detector import RadialSlopeDeviationDetector
from src.domain.value_objects.beam_reading import BeamReading

THRESHOLD = 0.35


def make_detector() -> RadialSlopeDeviationDetector:
    return RadialSlopeDeviationDetector(
        outer_position_threshold=6, deviation_threshold_m=THRESHOLD
    )


def beam(name: str, height: float, status: str = "") -> BeamReading:
    return BeamReading(beam_name=name, height=height, status=status)


def flat_axis(axis: str) -> list[BeamReading]:
    """Ровный склон без аномалии: высота 2.0 на всех позициях."""
    return [beam(f"{axis}{p}", 2.0) for p in range(1, 9)]


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
        beams = [beam(f"C{p}", 3.0 - 0.1 * (p - 1)) for p in range(1, 6)]
        beams += [beam(f"C{p}", 3.0 - 0.1 * (p - 1) + 1.0) for p in range(6, 9)]

        zone = {z.axis: z for z in make_detector().detect(beams)}["C"]

        assert zone.severity == "high"  # отклонение 1.0 > 0.35 * 2.5
        assert sorted(zone.affected_positions) == [6, 7, 8]
        assert zone.deviation_m == pytest.approx(1.0, abs=1e-3)
        assert 0.9 < zone.score <= 1.0

    def test_small_deviation_below_threshold_is_ignored(self) -> None:
        # Внешние выше склона на 0.2 < порога 0.35 — зоны нет.
        beams = [beam(f"B{p}", 2.5 - 0.05 * (p - 1)) for p in range(1, 6)]
        beams += [beam(f"B{p}", 2.5 - 0.05 * (p - 1) + 0.2) for p in range(6, 9)]

        zone = {z.axis: z for z in make_detector().detect(beams)}["B"]

        assert zone.severity == "none"
        assert zone.affected_positions == ()
        assert zone.deviation_m == pytest.approx(0.2, abs=1e-3)

    def test_hard_unreliable_beams_excluded(self) -> None:
        beams = flat_axis("D")
        beams += [
            beam("D9", 99.0),  # не существует по маске — игнорируется regex'ом
            beam("E1", 50.0, "Disabled"),  # чужая ось не попадает в зону D
            beam("D1", 50.0, "NotUsed"),  # ненадёжный луч D1 выбрасывается из fit
        ]

        zones = {z.axis: z for z in make_detector().detect(beams)}

        assert zones["D"].severity == "none"
        assert all(z.severity == "none" for axis, z in zones.items() if axis != "D")

    def test_all_eight_axes_always_reported(self) -> None:
        beams = [beam(f"{axis}{p}", 2.0) for axis in "ABCDEFGH" for p in range(1, 9)]

        zones = make_detector().detect(beams)

        assert [z.axis for z in zones] == list("ABCDEFGH")
        assert all(z.severity == "none" for z in zones)

    def test_too_few_inner_positions_gives_none(self) -> None:
        # Только один надёжный внутренний луч → регрессия невозможна.
        beams = [beam("A1", 2.0), beam("A6", 2.0), beam("A7", 5.0)]

        zone = make_detector().detect(beams)[0]

        assert zone.severity == "none"
