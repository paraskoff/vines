import importlib
from pathlib import Path

THEMES_DIR = Path(__file__).parent


def load_theme(theme_name: str) -> dict:
    """Load theme configuration by importing the theme Python module."""
    theme_name = theme_name.lower()
    try:
        module = importlib.import_module(f".{theme_name}", package="vines.themes")
        return getattr(module, "THEME_CONFIG", {})
    except (ImportError, AttributeError):
        # Fallback to solarized if module doesn't exist
        module = importlib.import_module(".solarized", package="vines.themes")
        return getattr(module, "THEME_CONFIG", {})


def list_available_themes() -> list[str]:
    """Return a list of available theme names."""
    return [p.stem for p in THEMES_DIR.glob("*.py") if p.stem != "__init__"]