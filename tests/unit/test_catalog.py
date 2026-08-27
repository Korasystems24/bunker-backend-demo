from pathlib import Path

import pytest
from pydantic import ValidationError
from src.config.settings import ApiSettings, Settings
from src.infrastructure.catalog import JsonCatalogProvider
from src.infrastructure.database.repositories.nodes import node_id_for_bunker


def test_catalog_builds_complete_typed_geometry() -> None:
    provider = JsonCatalogProvider(Path("catalog/bunkers.json"))

    geometry = provider.geometry_for("any/external-id")

    assert geometry.bunker_id == "any/external-id"
    assert len(geometry.beams) == 64
    assert geometry.beams[0].beam_name == "A1"
    assert geometry.beams[-1].beam_name == "H8"


def test_bunker_id_is_not_interpreted() -> None:
    assert node_id_for_bunker("bunker-001") == "bunker-001"
    assert node_id_for_bunker("plant/a/edge:anything") == "plant/a/edge:anything"


def test_production_rejects_default_token() -> None:
    with pytest.raises(ValidationError, match="production requires"):
        Settings(
            environment="production",
            api=ApiSettings(edge_auth_token="change-me-edge-token"),
        )
