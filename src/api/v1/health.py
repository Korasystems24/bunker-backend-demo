"""GET /api/v1/health — состояние edge-узлов."""

from fastapi import APIRouter

from src.api.deps import ContainerDep
from src.api.schemas.query import EdgeHealthOut, EdgePcOut

router = APIRouter(prefix="/api/v1/health", tags=["query"])


@router.get("")
async def get_edge_health(container: ContainerDep) -> EdgeHealthOut:
    nodes = await container.query.list_edge_nodes()
    return EdgeHealthOut(
        edge_pcs=[
            EdgePcOut(
                node_id=n.node_id,
                online=n.online,
                last_pulse=n.last_seen_at,
                cpu=n.cpu,
                ram=n.ram,
                disk=n.disk,
            )
            for n in nodes
        ]
    )
