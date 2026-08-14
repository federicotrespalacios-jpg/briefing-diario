"""
Fase 6 — Validación programática. Código, no modelo.

Este módulo es el guardián: si algo aquí falla, el build se detiene y no se
envía nada (o se degrada, según config.fallo). Ninguna de estas reglas es
negociable por el modelo — por diseño, el modelo no puede "convencer" al
validador de nada, porque el validador no lee prosa, solo cuenta y comprueba.

Comprobaciones (todas de config.yaml, ninguna hardcodeada):
  1. Conteo de palabras dentro de rango, por sección.
  2. Cada historia de actualidad tiene >= fuentes_por_historia_min fuentes.
  3. Cada URL de fuente responde con código no fatal (404/410 sí rompen;
     403/429 solo avisan — muchos medios bloquean IPs de datacenter).
  4. Ninguna fuente de actualidad supera antiguedad_maxima_horas.
  5. El tema cultural no está ya en el histórico de used_topics.json.
  6. No falta ningún campo requerido del esquema (delegado a schema.py).

Dos funciones públicas:
  validar()               — estricta. Un solo error tumba el build.
  validar_con_degradacion() — política "reintentar y degradar": si el único
    problema son historias concretas de actualidad, las descarta y revalida
    el resto en vez de fallar el briefing entero. Nunca degrada la sección
    de cultura (no hay nada que recortar ahí sin dejarla coja) ni el
    conteo de palabras global si tras descartar historias sigue fuera de
    rango.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from schema import Briefing, SchemaError

_RE_HISTORIA_ID = re.compile(r"^historia '([^']+)':")


@dataclass
class ValidationResult:
    ok: bool
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    historias_descartadas: list[str] = field(default_factory=list)

    def render_reporte(self) -> str:
        lineas = []
        if self.historias_descartadas:
            lineas.append(f"DEGRADADO — historias descartadas: {', '.join(self.historias_descartadas)}")
        if self.errores:
            lineas.append(f"ERRORES ({len(self.errores)}) — el build falla:")
            lineas += [f"  - {e}" for e in self.errores]
        if self.avisos:
            lineas.append(f"AVISOS ({len(self.avisos)}) — no bloquean:")
            lineas += [f"  - {a}" for a in self.avisos]
        if not self.errores and not self.avisos and not self.historias_descartadas:
            lineas.append("Sin errores ni avisos. Validación limpia.")
        return "\n".join(lineas)


def contar_palabras(texto: str) -> int:
    """Recuento simple por espacios en blanco. Coincide con el criterio que
    se les pide a las skills de redacción/verificación en sus prompts."""
    return len(texto.split())


def _checar_url(url: str, timeout: int, codigos_fatales: set[int]) -> Optional[str]:
    """Devuelve un mensaje de error si la URL es inaccesible de forma fatal,
    o None si está bien (incluye "bien" = bloqueada por el servidor pero
    probablemente viva, ej. 403/429 desde una IP de datacenter de CI)."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 (briefing-diario validator)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            codigo = resp.status
    except urllib.error.HTTPError as e:
        codigo = e.code
        if codigo in (405, 501):
            # Algunos servidores no soportan HEAD. Reintenta con GET.
            try:
                req_get = urllib.request.Request(
                    url, method="GET", headers={"User-Agent": "Mozilla/5.0 (briefing-diario validator)"}
                )
                with urllib.request.urlopen(req_get, timeout=timeout) as resp2:
                    codigo = resp2.status
            except urllib.error.HTTPError as e2:
                codigo = e2.code
            except Exception:
                return f"{url}: no responde (tras reintento GET)"
    except Exception as e:
        return f"{url}: no responde ({type(e).__name__}: {e})"

    if codigo in codigos_fatales:
        return f"{url}: código {codigo} (fatal)"
    return None


def _parse_dt(fecha_str: str) -> Optional[datetime]:
    """Acepta 'AAAA-MM-DD' o ISO-8601 completo. Devuelve datetime con tz UTC."""
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(fecha_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _normalizar(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _validar_estructura(
    briefing: Briefing,
    config: dict,
    used_topics: list[dict],
    *,
    verificar_urls: bool,
    ahora: datetime,
) -> ValidationResult:
    """Valida un Briefing ya construido. No toca disco salvo para las
    comprobaciones de URL (red). Separado de validar() para que la
    degradación pueda revalidar tras descartar historias sin releer
    ni reparsear JSON."""
    errores: list[str] = []
    avisos: list[str] = []

    # --- Regla 1: conteo de palabras ---
    long_cfg = config["longitud"]
    palabras_actualidad = contar_palabras(briefing.actualidad.arranque)
    palabras_actualidad += sum(contar_palabras(h.texto) for h in briefing.actualidad.historias)
    palabras_actualidad += contar_palabras(briefing.actualidad.radar_texto)

    palabras_cultura = contar_palabras(briefing.cultura.texto)
    if briefing.cultura.tirar_del_hilo_texto:
        palabras_cultura += contar_palabras(briefing.cultura.tirar_del_hilo_texto)

    ra = long_cfg["actualidad"]
    if not (ra["min"] <= palabras_actualidad <= ra["max"]):
        errores.append(
            f"actualidad: {palabras_actualidad} palabras, fuera de rango [{ra['min']}, {ra['max']}]"
        )

    rc = long_cfg["cultura"]
    if not (rc["min"] <= palabras_cultura <= rc["max"]):
        errores.append(
            f"cultura: {palabras_cultura} palabras, fuera de rango [{rc['min']}, {rc['max']}]"
        )

    # --- Regla 2: mínimo de fuentes por historia ---
    min_fuentes = config["actualidad"]["fuentes_por_historia_min"]
    for h in briefing.actualidad.historias:
        if len(h.fuentes) < min_fuentes:
            errores.append(
                f"historia '{h.id}': {len(h.fuentes)} fuente(s), mínimo {min_fuentes}"
            )

    # --- Regla 4: antigüedad máxima de las fuentes de actualidad ---
    max_horas = config["actualidad"]["antiguedad_maxima_horas"]
    limite = ahora - timedelta(hours=max_horas)
    for h in briefing.actualidad.historias:
        for f in h.fuentes:
            dt = _parse_dt(f.fecha_publicacion)
            if dt is None:
                avisos.append(f"historia '{h.id}': fecha de fuente ilegible ({f.fecha_publicacion})")
                continue
            if dt < limite:
                errores.append(
                    f"historia '{h.id}': fuente '{f.medio}' publicada {f.fecha_publicacion}, "
                    f"supera el límite de {max_horas}h"
                )

    # --- Regla 3: URLs de fuentes responden ---
    if verificar_urls:
        codigos_fatales = set(config["validacion"]["url_codigos_fatales"])
        timeout = config["validacion"]["url_timeout_segundos"]
        vistas: set[str] = set()
        for h in briefing.actualidad.historias:
            for f in h.fuentes:
                if f.url in vistas:
                    continue
                vistas.add(f.url)
                err = _checar_url(f.url, timeout, codigos_fatales)
                if err:
                    errores.append(f"historia '{h.id}': URL inaccesible — {err}")

    # --- Regla 5: tema cultural no repetido + rotación de categoría ---
    if config["validacion"]["fallar_si_tema_repetido"]:
        titulo_normalizado = _normalizar(briefing.cultura.titulo)
        for entrada in used_topics:
            existente = _normalizar(entrada.get("titulo", ""))
            if existente and existente == titulo_normalizado:
                errores.append(
                    f"tema cultural '{briefing.cultura.titulo}' ya publicado el {entrada.get('fecha', '?')}"
                )
                break

        if used_topics:
            ultimo = max(used_topics, key=lambda e: e.get("fecha", ""))
            dias_bloqueo = config["cultura"]["dias_bloqueo_categoria"]
            fecha_ultimo = _parse_dt(ultimo.get("fecha", ""))
            if fecha_ultimo and (briefing.fecha_date - fecha_ultimo.date()).days < dias_bloqueo:
                if ultimo.get("categoria") == briefing.cultura.categoria:
                    errores.append(
                        f"categoría '{briefing.cultura.categoria}' repetida dentro de la ventana de "
                        f"{dias_bloqueo} días (último uso: {ultimo.get('fecha')})"
                    )

    return ValidationResult(ok=(len(errores) == 0), errores=errores, avisos=avisos)


def _cargar(final_path: Path, research_path: Path) -> tuple[dict, dict, Optional[Briefing], Optional[str]]:
    try:
        final_raw = json.loads(final_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return {}, {}, None, f"no se pudo leer {final_path.name}: {e}"

    try:
        research_raw = json.loads(research_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return {}, {}, None, f"no se pudo leer {research_path.name}: {e}"

    try:
        briefing = Briefing.from_dicts(final_raw, research_raw)
    except SchemaError as e:
        return final_raw, research_raw, None, f"esquema inválido: {e}"

    return final_raw, research_raw, briefing, None


def _cargar_used_topics(used_topics_path: Path) -> tuple[list[dict], list[str]]:
    if not used_topics_path.exists():
        return [], []
    try:
        data = json.loads(used_topics_path.read_text(encoding="utf-8"))
        return (data if isinstance(data, list) else []), []
    except json.JSONDecodeError:
        return [], [f"{used_topics_path.name}: JSON corrupto, se trata como vacío"]


def validar(
    final_path: Path,
    research_path: Path,
    used_topics_path: Path,
    config: dict,
    *,
    verificar_urls: bool = True,
    ahora: Optional[datetime] = None,
) -> tuple[ValidationResult, Optional[Briefing]]:
    """Validación estricta: cualquier error tumba el build entero."""
    ahora = ahora or datetime.now(timezone.utc)
    _, _, briefing, error_carga = _cargar(final_path, research_path)
    if error_carga:
        return ValidationResult(ok=False, errores=[error_carga]), None

    used_topics, avisos_carga = _cargar_used_topics(used_topics_path)
    resultado = _validar_estructura(briefing, config, used_topics, verificar_urls=verificar_urls, ahora=ahora)
    resultado.avisos = avisos_carga + resultado.avisos
    return resultado, briefing


def validar_con_degradacion(
    final_path: Path,
    research_path: Path,
    used_topics_path: Path,
    config: dict,
    *,
    verificar_urls: bool = True,
    ahora: Optional[datetime] = None,
) -> tuple[ValidationResult, Optional[Briefing]]:
    """Política 'reintentar y degradar': si la validación estricta falla
    únicamente por errores achacables a historias concretas de actualidad,
    las descarta y revalida. Nunca toca la sección de cultura — no hay
    forma honesta de "recortar" un tema cultural roto, así que un fallo
    ahí tumba el build igual que en modo estricto.

    Si tras descartar historias el número de historias restantes cae por
    debajo de config.fallo.minimo_historias, o el conteo de palabras de
    actualidad sigue fuera de rango, la degradación falla y se propaga el
    resultado de la validación estricta original."""
    resultado, briefing = validar(
        final_path, research_path, used_topics_path, config,
        verificar_urls=verificar_urls, ahora=ahora,
    )
    if resultado.ok or briefing is None:
        return resultado, briefing

    ids_defectuosos = {
        m.group(1) for e in resultado.errores if (m := _RE_HISTORIA_ID.match(e))
    }
    # Si hay errores que NO son achacables a una historia concreta (fallo
    # de esquema, cultura, tema repetido, conteo global irreparable), la
    # degradación no puede arreglarlos por sí sola.
    errores_no_localizables = [
        e for e in resultado.errores if not _RE_HISTORIA_ID.match(e)
    ]

    if not ids_defectuosos:
        # Nada que degradar — el fallo no viene de historias sueltas.
        return resultado, briefing

    historias_restantes = [h for h in briefing.actualidad.historias if h.id not in ids_defectuosos]
    minimo = config["fallo"]["minimo_historias"]
    if len(historias_restantes) < minimo:
        resultado.avisos.append(
            f"degradación descartada: quedarían {len(historias_restantes)} historias, "
            f"mínimo publicable {minimo}"
        )
        return resultado, briefing

    briefing.actualidad.historias = historias_restantes
    used_topics, _ = _cargar_used_topics(used_topics_path)
    ahora = ahora or datetime.now(timezone.utc)
    revalidacion = _validar_estructura(
        briefing, config, used_topics, verificar_urls=False, ahora=ahora
    )
    # Las URLs de las historias descartadas ya no aplican; las que quedan
    # ya se comprobaron en la pasada estricta anterior, así que no hace
    # falta repetir la comprobación de red.

    if errores_no_localizables:
        revalidacion.errores = list(dict.fromkeys(errores_no_localizables + revalidacion.errores))
        revalidacion.ok = False

    revalidacion.historias_descartadas = sorted(ids_defectuosos)
    return revalidacion, briefing
