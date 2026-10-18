import json
from pathlib import Path

STATIC_DIR = Path(__file__).parent / "static"


def generate_app_js(search_index: list, graph_data: dict) -> str:
    """Load JS template and inject runtime data."""
    js_template = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    return js_template.replace(
        "__SEARCH_INDEX__", json.dumps(search_index)
    ).replace(
        "__GRAPH_DATA__", json.dumps(graph_data)
    )