"""
Estado persistente entre ejecuciones — vive en state/*.json, versionado en
git. Dos archivos:

  used_topics.json    — histórico de temas culturales, para el anti-repetición
                         y la rotación forzada de categoría (Fase 3 y Fase 6).
  recent_stories.json — historias de actualidad de los últimos N días, para
                         que la Fase 2 pueda detectar continuaciones.

Ambos son listas JSON simples, de más antiguo a más reciente. Se podan al
escribir para no crecer sin límite.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

RETENCION_RECENT_STORIES_DIAS = 14
RETENCION_USED_TOPICS_DIAS = 400  # ~13 meses; el anti-repetición mira todo el historial igual


def _leer_lista(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


def _escribir_lista(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def registrar_tema_cultural(path: Path, fecha: str, categoria: str, titulo: str) -> None:
    data = _leer_lista(path)
    data.append({"fecha": fecha, "categoria": categoria, "titulo": titulo})
    limite = (date.fromisoformat(fecha) - timedelta(days=RETENCION_USED_TOPICS_DIAS)).isoformat()
    data = [e for e in data if e.get("fecha", "0000-00-00") >= limite]
    data.sort(key=lambda e: e.get("fecha", ""))
    _escribir_lista(path, data)


def registrar_historias_recientes(path: Path, fecha: str, historias: list[dict]) -> None:
    """historias: [{"id", "titular_editorial", "resumen_factual"}, ...] —
    lo mínimo para que la Fase 2 detecte continuaciones sin tener que leer
    el texto redactado completo."""
    data = _leer_lista(path)
    for h in historias:
        data.append({
            "fecha": fecha,
            "id": h.get("id"),
            "titular": h.get("titular_editorial") or h.get("titular"),
            "resumen": h.get("resumen_factual") or h.get("texto", "")[:300],
        })
    limite = (date.fromisoformat(fecha) - timedelta(days=RETENCION_RECENT_STORIES_DIAS)).isoformat()
    data = [e for e in data if e.get("fecha", "0000-00-00") >= limite]
    data.sort(key=lambda e: e.get("fecha", ""))
    _escribir_lista(path, data)


def ya_publicado_hoy(briefings_dir: Path, fecha: str) -> bool:
    """Marca de idempotencia: si briefings/{fecha}.json ya existe, esta
    fecha ya se generó y (se asume) envió en un run anterior."""
    return (briefings_dir / f"{fecha}.json").exists()
