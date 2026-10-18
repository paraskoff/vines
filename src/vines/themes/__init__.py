import json
from pathlib import Path

THEMES_DIR = Path(__file__).parent


def load_theme(theme_name: str) -> dict:
    """Load theme configuration by name from the themes directory."""
    theme_path = THEMES_DIR / f"{theme_name.lower()}.json"
    if not theme_path.exists():
        # Fallback to solarized if theme doesn't exist
        theme_path = THEMES_DIR / "solarized.json"

    with open(theme_path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_available_themes() -> list[str]:
    """Return a list of available theme names."""
    return [p.stem for p in THEMES_DIR.glob("*.json")]