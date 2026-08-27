"""Перевод единиц EdgePC → домен/Query API.

Радар шлёт уровни и высоты лучей в миллиметрах. Контракт фронта — метры.
Масса и объём приходят уже в т / м³ и не трогаются.
"""

from src.domain.constants import MM_PER_M
from src.domain.entities.telemetry_packet import TelemetryPacket
from src.domain.value_objects.beam import Beam


def mm_to_m(value_mm: float | None) -> float | None:
    if value_mm is None:
        return None
    return value_mm / MM_PER_M


def _beam_to_meters(beam: Beam) -> Beam:
    return beam.model_copy(update={"height": mm_to_m(beam.height)})


def packet_to_meters(packet: TelemetryPacket) -> TelemetryPacket:
    return packet.model_copy(
        update={
            "avg_level": mm_to_m(packet.avg_level),
            "beams": [_beam_to_meters(beam) for beam in packet.beams],
        }
    )
