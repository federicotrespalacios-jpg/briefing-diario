import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

import pytest
import yaml


@pytest.fixture(scope="session")
def config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def texto_de_n_palabras(n: int, semilla: str = "palabra") -> str:
    """Genera texto determinista de exactamente n palabras, en párrafos
    de ~20 palabras separados por doble salto de línea (para que
    render._parrafos tenga algo real que dividir)."""
    palabras = [f"{semilla}{i}" for i in range(n)]
    lineas = []
    for i in range(0, len(palabras), 20):
        lineas.append(" ".join(palabras[i:i + 20]))
    return "\n\n".join(lineas)
