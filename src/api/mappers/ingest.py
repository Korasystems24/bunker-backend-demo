"""HTTP DTO → доменные модели. Уровни и высоты лучей уже в метрах."""

from src.api.schemas.ingest import EventIn, HealthRequest, TelemetryPacketIn
from src.domain.entities.edge_event import EdgeEvent
from src.domain.entities.health_snapshot import HealthSnapshot
from src.domain.entities.telemetry_packet import TelemetryPacket
from src.domain.value_objects.beam import Beam


def telemetry_packet_to_domain(packet: TelemetryPacketIn) -> TelemetryPacket:
    return TelemetryPacket(
        event_id=packet.event_id,
        ts=packet.ts,
        avg_level=packet.avg_level,
        mass=packet.mass,
        volume=packet.volume,
        beams=[
            Beam(
                height=beam.height,
                raw_status=beam.raw_status,
                status=beam.status,
            )
            for beam in packet.beams
        ],
    )


def event_to_domain(event: EventIn) -> EdgeEvent:
    return EdgeEvent.model_validate(event.model_dump(mode="python"))


def health_to_domain(request: HealthRequest) -> HealthSnapshot:
    return HealthSnapshot.model_validate(
        request.model_dump(mode="python", exclude={"bunker_id"})
    )
