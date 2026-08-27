"""RadialSlopeDeviationDetector: эвристика v1 налипания на стенках.

Для каждой оси: линейная регрессия высоты по внутренним позициям (< порога),
экстраполяция на внешние (>= порога). Внешние лучи, сидящие заметно выше
предсказанного уклона, — признак налипания на стенке.

Критерий не утверждён заказчиком, поэтому реализация versioned:
результат размечается algorithm_version, замена стратегии не меняет контракт.
Чистая функция O(64) — вызывается на ингесте; GET /buildup читает таблицу.
"""

import re
from collections.abc import Sequence

from src.domain.constants import HARD_UNRELIABLE_BEAM_FLAGS
from src.domain.value_objects.axis_zone import AxisZone, Severity
from src.domain.value_objects.beam_reading import BeamReading

_BEAM_NAME_RE = re.compile(r"^([A-H])([1-8])$")
_AXES = tuple("ABCDEFGH")


class RadialSlopeDeviationDetector:
    def __init__(
        self,
        *,
        outer_position_threshold: int,
        deviation_threshold_m: float,
        algorithm_version: str = "radial-slope-v1",
    ) -> None:
        self._outer_from = outer_position_threshold
        self._threshold = deviation_threshold_m
        self.algorithm_version = algorithm_version

    def detect(self, beams: Sequence[BeamReading]) -> list[AxisZone]:
        by_axis: dict[str, list[tuple[int, float]]] = {axis: [] for axis in _AXES}
        for beam in beams:
            match = _BEAM_NAME_RE.match(beam.beam_name)
            if match is None or self._is_hard_unreliable(beam.status):
                continue
            if beam.height is None:
                continue
            by_axis[match.group(1)].append((int(match.group(2)), beam.height))

        return [self._detect_axis(axis, by_axis[axis]) for axis in _AXES]

    def _detect_axis(self, axis: str, points: list[tuple[int, float]]) -> AxisZone:
        inner = [(p, h) for p, h in points if p < self._outer_from]
        outer = [(p, h) for p, h in points if p >= self._outer_from]

        if len(inner) < 2 or not outer:
            return AxisZone(axis=axis, severity="none", score=0.0, deviation_m=0.0)

        slope, intercept = _linear_fit(inner)
        affected: list[int] = []
        max_deviation = 0.0
        for position, height in outer:
            expected = intercept + slope * position
            deviation = height - expected
            if deviation > self._threshold:
                affected.append(position)
            max_deviation = max(max_deviation, deviation)

        score = max(0.0, min(1.0, max_deviation / (self._threshold * 3)))
        severity = self._severity(max_deviation)

        return AxisZone(
            axis=axis,
            severity=severity,
            score=round(score, 3),
            deviation_m=round(max_deviation, 4),
            affected_positions=tuple(affected),
        )

    def _severity(self, max_deviation: float) -> Severity:
        if max_deviation > self._threshold * 2.5:
            return "high"
        if max_deviation > self._threshold * 1.5:
            return "medium"
        if max_deviation > self._threshold:
            return "low"
        return "none"

    @staticmethod
    def _is_hard_unreliable(status: str) -> bool:
        flags: set[str] = {flag.strip() for flag in status.split(",")} if status else set()
        return bool(flags & HARD_UNRELIABLE_BEAM_FLAGS)


def _linear_fit(points: list[tuple[int, float]]) -> tuple[float, float]:
    """МНК-прямая height(position); при вырожденном знаменателе — горизонталь."""
    n = len(points)
    sum_x = sum(p for p, _ in points)
    sum_y = sum(h for _, h in points)
    sum_xy = sum(p * h for p, h in points)
    sum_xx = sum(p * p for p, _ in points)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0, sum_y / n
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept
