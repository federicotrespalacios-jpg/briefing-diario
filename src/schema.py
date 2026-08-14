"""
Esquema del briefing diario — el contrato de datos que atraviesa todo el
pipeline. Sin dependencias externas a propósito: el runner del sistema
(python del sistema en local, python 3.12 en CI) no puede dar por hecho
pydantic instalado antes de que corra `pip install`.

Cada clase valida su propia forma en __post_init__. Un dato mal formado
lanza SchemaError con un mensaje que dice exactamente qué campo y qué
esperaba — así el fallo del build en GitHub Actions es legible sin abrir
el JSON a mano.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


class SchemaError(ValueError):
    """Error de validación de esquema. El mensaje debe bastar para arreglarlo
    sin tener que abrir el JSON."""


def _require(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise SchemaError(mensaje)


def _str_no_vacio(valor: object, campo: str) -> str:
    _require(isinstance(valor, str) and valor.strip() != "", f"{campo}: falta o está vacío")
    return valor  # type: ignore[return-value]


def _fecha_iso(valor: object, campo: str) -> str:
    s = _str_no_vacio(valor, campo)
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError as e:
        raise SchemaError(f"{campo}: '{s}' no es una fecha AAAA-MM-DD válida") from e
    return s


TIPOS_FUENTE = {"primaria", "referencia"}
ESTADOS_VERIFICACION = {"VERIFICADA", "DUDOSA", "NO VERIFICABLE"}
CONFIANZAS = {"alta", "media", "baja"}


@dataclass
class Fuente:
    medio: str
    url: str
    fecha_publicacion: str
    tipo: str  # "primaria" | "referencia"
    titular_fuente: Optional[str] = None

    def __post_init__(self) -> None:
        self.medio = _str_no_vacio(self.medio, "fuente.medio")
        self.url = _str_no_vacio(self.url, "fuente.url")
        _require(
            self.url.startswith("http://") or self.url.startswith("https://"),
            f"fuente.url: '{self.url}' no parece una URL http(s)",
        )
        _fecha_iso(self.fecha_publicacion, "fuente.fecha_publicacion")
        _require(
            self.tipo in TIPOS_FUENTE,
            f"fuente.tipo: '{self.tipo}' debe ser uno de {sorted(TIPOS_FUENTE)}",
        )

    @staticmethod
    def from_dict(d: dict) -> "Fuente":
        _require(isinstance(d, dict), "fuente: debe ser un objeto")
        return Fuente(
            medio=d.get("medio"),
            url=d.get("url"),
            fecha_publicacion=d.get("fecha_publicacion"),
            tipo=d.get("tipo"),
            titular_fuente=d.get("titular_fuente"),
        )


@dataclass
class Historia:
    id: str
    titular_editorial: str
    texto: str
    fuentes: list[Fuente] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.id = _str_no_vacio(self.id, "historia.id")
        self.titular_editorial = _str_no_vacio(self.titular_editorial, "historia.titular_editorial")
        self.texto = _str_no_vacio(self.texto, "historia.texto")

    @staticmethod
    def from_dict(d: dict, fuentes_por_id: dict[str, list[Fuente]]) -> "Historia":
        _require(isinstance(d, dict), "historia: debe ser un objeto")
        hid = d.get("id")
        return Historia(
            id=hid,
            titular_editorial=d.get("titular_editorial"),
            texto=d.get("texto"),
            fuentes=fuentes_por_id.get(hid, []),
        )


@dataclass
class SeccionActualidad:
    arranque: str
    historias: list[Historia]
    radar_texto: str
    palabras: int

    def __post_init__(self) -> None:
        self.arranque = _str_no_vacio(self.arranque, "actualidad.arranque")
        self.radar_texto = _str_no_vacio(self.radar_texto, "actualidad.radar_texto")
        _require(isinstance(self.historias, list) and len(self.historias) > 0,
                 "actualidad.historias: no puede estar vacío")

    @staticmethod
    def from_dict(d: dict) -> "SeccionActualidad":
        _require(isinstance(d, dict), "actualidad: debe ser un objeto")
        historias_raw = d.get("historias_texto", [])
        _require(isinstance(historias_raw, list), "actualidad.historias_texto: debe ser una lista")

        # Las fuentes reales viven en research.json, no en draft/final —
        # el merge lo hace el llamador (validate.py) antes de construir esto.
        fuentes_por_id = d.get("_fuentes_por_id", {})

        historias = [Historia.from_dict(h, fuentes_por_id) for h in historias_raw]
        return SeccionActualidad(
            arranque=d.get("arranque"),
            historias=historias,
            radar_texto=d.get("radar_texto"),
            palabras=d.get("palabras", 0),
        )


@dataclass
class SeccionCultura:
    titulo: str
    categoria: str
    texto: str
    dato_sobremesa: str
    palabras: int
    tirar_del_hilo_texto: Optional[str] = None

    def __post_init__(self) -> None:
        self.titulo = _str_no_vacio(self.titulo, "cultura.titulo")
        self.categoria = _str_no_vacio(self.categoria, "cultura.categoria")
        self.texto = _str_no_vacio(self.texto, "cultura.texto")
        self.dato_sobremesa = _str_no_vacio(self.dato_sobremesa, "cultura.dato_sobremesa")

    @staticmethod
    def from_dict(d: dict) -> "SeccionCultura":
        _require(isinstance(d, dict), "cultura: debe ser un objeto")
        return SeccionCultura(
            titulo=d.get("titulo"),
            categoria=d.get("categoria"),
            texto=d.get("texto"),
            dato_sobremesa=d.get("dato_sobremesa"),
            palabras=d.get("palabras", 0),
            tirar_del_hilo_texto=d.get("tirar_del_hilo_texto"),
        )


@dataclass
class Briefing:
    """El briefing final, listo para render. Se construye a partir de
    work/final.json (texto) fusionado con work/research.json (fuentes)."""

    fecha: str
    actualidad: SeccionActualidad
    cultura: SeccionCultura

    def __post_init__(self) -> None:
        _fecha_iso(self.fecha, "fecha")

    @staticmethod
    def from_dicts(final: dict, research: dict) -> "Briefing":
        _require(isinstance(final, dict), "final.json: debe ser un objeto raíz")
        _require(isinstance(research, dict), "research.json: debe ser un objeto raíz")

        fecha_final = final.get("fecha")
        fecha_research = research.get("fecha")
        _require(
            fecha_final == fecha_research,
            f"fecha inconsistente entre final.json ({fecha_final}) y research.json ({fecha_research})",
        )

        # Construir el mapa historia.id -> [Fuente] desde research.json,
        # que es donde vive la investigación de fuentes original.
        fuentes_por_id: dict[str, list[Fuente]] = {}
        for h in research.get("actualidad", {}).get("historias", []):
            hid = h.get("id")
            fuentes_raw = h.get("fuentes", [])
            _require(isinstance(fuentes_raw, list), f"research.actualidad.historias[{hid}].fuentes: debe ser una lista")
            fuentes_por_id[hid] = [Fuente.from_dict(f) for f in fuentes_raw]

        actualidad_dict = dict(final.get("actualidad", {}))
        actualidad_dict["_fuentes_por_id"] = fuentes_por_id

        return Briefing(
            fecha=fecha_final,
            actualidad=SeccionActualidad.from_dict(actualidad_dict),
            cultura=SeccionCultura.from_dict(final.get("cultura", {})),
        )

    @property
    def fecha_date(self) -> date:
        return datetime.strptime(self.fecha, "%Y-%m-%d").date()
