"""Preferencias globales de navegador(es) para bots (lectura desde modelo)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.bot_global_config import BotGlobalConfig


def get_preferred_browsers_list(config: BotGlobalConfig | None) -> list[str]:
    """Lista ordenada de nombres; JSON tiene prioridad, luego columna legacy."""
    if not config:
        return []
    raw = (config.preferred_browsers_json or "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                out: list[str] = []
                seen: set[str] = set()
                for x in data:
                    s = str(x).strip()
                    if not s:
                        continue
                    key = s.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(s)
                return out
        except Exception:
            pass
    single = (config.preferred_browser or "").strip()
    return [single] if single else []
