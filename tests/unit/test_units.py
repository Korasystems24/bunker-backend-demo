from datetime import UTC, datetime

from src.application.ingestion.units import mm_to_m, packet_to_meters
from src.domain.entities.telemetry_packet import TelemetryPacket
from src.domain.value_objects.beam import Beam


def test_mm_to_m_scales_and_keeps_none() -> None:
    assert mm_to_m(3140) == 3.14
    assert mm_to_m(None) is None


def test_packet_to_meters_converts_level_and_beam_heights() -> None:
    first = Beam(height=2010, raw_status=None, status=())
    rest = [Beam(height=None, raw_status=None, status=()) for _ in range(63)]
    packet = TelemetryPacket(
        ts=datetime(2026, 8, 25, 10, 0, tzinfo=UTC),
        avg_level=3140,
        mass=1187.4,
        volume=1425.8,
        beams=[first, *rest],
    )

    converted = packet_to_meters(packet)

    assert converted.avg_level == 3.14
    assert converted.mass == 1187.4
    assert converted.volume == 1425.8
    assert converted.beams[0].height == 2.01
    assert converted.beams[1].height is None
