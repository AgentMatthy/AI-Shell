#!/usr/bin/env python

"""
Centralized theme system for AI Shell.

Provides a configurable color palette used across the entire application.
Colors are loaded from config.yaml under the 'theme' key, with sensible defaults.
"""

from rich.console import Console
from rich.theme import Theme as RichTheme

DEFAULT_THEME = {
    "accent": "#0066cc",
    "accent_alt": "#00cc66",
    "fg": "white",
    "fg_alt": "#aaaaaa",
    "muted": "#555555",
    "block": "grey11",
    "block_alt": "grey15",
    "error": "#ff5555",
    "warning": "#e5c07b",
    "success": "#00cc66",
}


def get_theme(config: dict) -> dict:
    """Resolve theme colors from config, falling back to defaults."""
    theme = dict(DEFAULT_THEME)
    theme.update(config.get("theme", {}))
    return theme


def build_rich_theme(theme: dict) -> RichTheme:
    """Create a Rich Theme from the resolved theme dict.

    Styles are defined *without* bold so callers can compose freely:
    ``[bold accent]Title[/bold accent]`` or ``[accent]normal text[/accent]``.
    """
    return RichTheme({
        "accent": theme["accent"],
        "accent_alt": theme["accent_alt"],
        "fg": theme["fg"],
        "fg_alt": theme["fg_alt"],
        "muted": theme["muted"],
        "error": theme["error"],
        "warning": theme["warning"],
        "success": theme["success"],
    })


def create_console(config: dict | None = None, **kwargs) -> Console:
    """Create a Rich Console with the application theme applied.

    If *config* is ``None`` (e.g. during the setup wizard before a config
    exists), a Console with the default theme is returned.
    """
    theme = get_theme(config or {})
    rich_theme = build_rich_theme(theme)
    return Console(theme=rich_theme, **kwargs)
