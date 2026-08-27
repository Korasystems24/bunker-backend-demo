"""Единые правила идентификации и надёжности 64 лучей радара."""

from collections.abc import Iterable
from typing import Final

from src.domain.constants import BEAM_COUNT
from src.domain.value_objects.beam_status import BeamStatus

AXES: Final[tuple[str, ...]] = tuple("ABCDEFGH")
POSITIONS_PER_AXIS: Final = BEAM_COUNT // len(AXES)
HARD_UNRELIABLE_STATUSES: Final[frozenset[BeamStatus]] = frozenset(
    {
        BeamStatus.DISABLED,
        BeamStatus.DISTANCE_NOT_UPDATING,
        BeamStatus.NOT_USED,
        BeamStatus.UNKNOWN,
    }
)


def beam_coordinates(index: int) -> tuple[str, int]:
    if not 0 <= index < BEAM_COUNT:
        raise ValueError(f"beam index must be in [0, {BEAM_COUNT}), got {index}")
    return AXES[index // POSITIONS_PER_AXIS], index % POSITIONS_PER_AXIS + 1


def beam_name(index: int) -> str:
    axis, position = beam_coordinates(index)
    return f"{axis}{position}"


def format_beam_statuses(statuses: Iterable[BeamStatus]) -> str:
    return ", ".join(status.value for status in statuses)


def is_hard_unreliable(statuses: Iterable[BeamStatus]) -> bool:
    return not HARD_UNRELIABLE_STATUSES.isdisjoint(statuses)
