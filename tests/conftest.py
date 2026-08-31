import tempfile
from pathlib import Path

import pytest

from table_nine.domain.models import EpisodeDocument
from table_nine.storage.markdown import deserialize_episode


@pytest.fixture
def traffic_cone_path(tmp_path: Path) -> Path:
    """Provide a temporary traffic cone workbench document for tests."""
    # Create a minimal valid DispatchWorkbench markdown fixture
    lines = [
        "---\n",
        "episode_id: traffic-cone-uncle\n",
        "featured_uncle: UncleTraffic\n",
        "working_title: Traffic Cone Uncle\n",
        "registry_number: 10001\n",
        "status: developed\n",
        "table_nine_schema: 2\n",
        "---\n",
        "\n",
        "# Dispatch Workbench\n",
        "\n",
        "## Dossier\n",
        "\n",
        "### Observed behaviour\n",
        "\n",
        "> An Uncle operates a traffic control station in deep space.\n",
        "\n",
        "### Central artifact\n",
        "\n",
        "A classification card identifying the traffic pattern.\n",
        "\n",
        "### Human stakes\n",
        "\n",
        "Preventing orbital collision with debris.\n",
        "\n",
        "### AI-era problem\n",
        "\n",
        "Managing automated collision avoidance.\n",
        "\n",
        "## Beat Board\n",
        "\n",
        "- Beat 1: Introduction [10s]\n",
        "- Beat 2: Incident [30s]\n",
        "- Beat 3: Resolution [20s]\n",
        "\n",
        "## Inquiry\n",
        "\n",
        "### Opening question\n",
        "What is the root cause of the debris field?\n",
        "\n",
        "### Hinge candidates\n",
        "- manual-hinge-1\n",
        "\n",
        "### Comparator sightings\n",
        "- None yet\n",
        "\n",
        "### Station assignment\n",
        "Station 42\n",
        "\n",
        "### Final button\n",
        "Confirm\n",
        "\n",
        "### Permanent archive addition\n",
        "None\n",
        "\n",
        "## Beat 1: Introduction\n",
        "\n",
        "UNCLE_ONE: Welcome to the station.\n",
        "[pause 1.0]\n",
        "\n",
        "- Beat 2: Incident\n",
        "\n",
        "UNCLE_TWO: Debris detected!\n",
        "[robot processing 2.0]\n",
        "\n",
        "- Beat 3: Resolution\n",
        "\n",
        "UNCLE_ONE: Course corrected.\n",
        "\n",
        "# End Document\n",
    ]
    workbench_path = tmp_path / "TrafficConeUncle-DispatchWorkbench_UIS_v01.md"
    workbench_path.write_text("".join(lines), encoding="utf-8")
    return workbench_path


@pytest.fixture
def traffic_cone_document(traffic_cone_path: Path) -> EpisodeDocument:
    return deserialize_episode(traffic_cone_path.read_text(encoding="utf-8"))