"""
Fase 7 (parte 1) — Render. Convierte un Briefing validado en:
  - HTML del email (email-safe, tablas, estilos inline, claro/oscuro)
  - Texto plano del email (fallback multipart)
  - HTML de la página web individual del día
  - HTML del índice del histórico (docs/index.html)
  - Markdown de archivo (briefings/AAAA-MM-DD.md)

No decide nada editorial — solo formatea lo que ya pasó la Fase 6.
Usa Jinja2 (única dependencia no-stdlib de este módulo, junto con PyYAML
para la config, que carga el llamador).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from schema import Briefing

DIAS_ES = [
    "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
]
MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def fecha_larga_es(fecha) -> str:
    """'2026-08-13' -> 'jueves, 13 de agosto de 2026'. Sin dependencia de
    locale del sistema — CI y local no siempre tienen es_ES instalado."""
    dia_semana = DIAS_ES[fecha.weekday()]
    mes = MESES_ES[fecha.month - 1]
    return f"{dia_semana}, {fecha.day} de {mes} de {fecha.year}"


def _parrafos(texto: str) -> list[str]:
    """Divide en párrafos por doble salto de línea. Si el redactor no usó
    dobles saltos, cae a un único párrafo con el texto completo."""
    partes = [p.strip() for p in re.split(r"\n\s*\n", texto.strip()) if p.strip()]
    return partes or [texto.strip()]


@dataclass
class FuenteRender:
    medio: str
    url: str
    fecha_publicacion: str


def _fuentes_unicas(briefing: Briefing) -> list[FuenteRender]:
    vistas: dict[str, FuenteRender] = {}
    for h in briefing.actualidad.historias:
        for f in h.fuentes:
            if f.url not in vistas:
                vistas[f.url] = FuenteRender(medio=f.medio, url=f.url, fecha_publicacion=f.fecha_publicacion)
    return sorted(vistas.values(), key=lambda f: f.medio.lower())


def _get_env(templates_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _contexto_comun(briefing: Briefing, config: dict) -> dict:
    fecha = briefing.fecha_date
    historias = [
        {"titular_editorial": h.titular_editorial, "parrafos": _parrafos(h.texto)}
        for h in briefing.actualidad.historias
    ]
    return {
        "fecha_larga": fecha_larga_es(fecha),
        "arranque": briefing.actualidad.arranque,
        "historias": historias,
        "radar_texto": briefing.actualidad.radar_texto,
        "minutos_actualidad": config["longitud"]["actualidad"]["minutos_lectura"],
        "categoria_cultura": briefing.cultura.categoria,
        "titulo_cultura": briefing.cultura.titulo,
        "cultura_parrafos": _parrafos(briefing.cultura.texto),
        "dato_sobremesa": briefing.cultura.dato_sobremesa,
        "tirar_del_hilo_texto": briefing.cultura.tirar_del_hilo_texto,
        "minutos_cultura": config["longitud"]["cultura"]["minutos_lectura"],
        "fuentes": [f.__dict__ for f in _fuentes_unicas(briefing)],
    }


def render_email_html(briefing: Briefing, config: dict, templates_dir: Path, url_historial: str) -> str:
    env = _get_env(templates_dir)
    tpl = env.get_template("email.html.j2")
    ctx = _contexto_comun(briefing, config)
    asunto = config["entrega"]["asunto"].format(fecha_larga=ctx["fecha_larga"])
    ctx.update({
        "titulo_email": asunto,
        "preheader": f"{briefing.cultura.titulo} · {ctx['minutos_actualidad'] + ctx['minutos_cultura']} min de lectura",
        "url_historial": url_historial,
    })
    return tpl.render(**ctx)


def render_email_text(briefing: Briefing, config: dict) -> str:
    """Fallback de texto plano para el multipart. Sin plantilla — es
    deliberadamente simple, no necesita mantenerse en sync visualmente
    con el HTML, solo ser legible."""
    ctx = _contexto_comun(briefing, config)
    lineas = [
        ctx["fecha_larga"].upper(),
        "=" * len(ctx["fecha_larga"]),
        "",
        "ACTUALIDAD",
        "-" * 10,
        "",
        ctx["arranque"],
        "",
    ]
    for h in ctx["historias"]:
        lineas.append(h["titular_editorial"])
        lineas.append("")
        lineas.extend(h["parrafos"])
        lineas.append("")
    lineas.append("EN EL RADAR")
    lineas.append(ctx["radar_texto"])
    lineas.append("")
    lineas.append("")
    lineas.append(f"CULTURA GENERAL — {ctx['categoria_cultura'].upper()}")
    lineas.append(ctx["titulo_cultura"])
    lineas.append("-" * 10)
    lineas.append("")
    lineas.extend(ctx["cultura_parrafos"])
    lineas.append("")
    lineas.append(f'Para la sobremesa: "{ctx["dato_sobremesa"]}"')
    if ctx["tirar_del_hilo_texto"]:
        lineas.append("")
        lineas.append("Si quieres tirar del hilo:")
        lineas.append(ctx["tirar_del_hilo_texto"])
    lineas.append("")
    lineas.append("")
    lineas.append("FUENTES")
    for f in ctx["fuentes"]:
        lineas.append(f"- {f['medio']} ({f['fecha_publicacion']}): {f['url']}")
    lineas.append("")
    lineas.append(f"Histórico completo: {config['web'].get('url_base', '')}")
    return "\n".join(lineas)


def render_web_html(briefing: Briefing, config: dict, templates_dir: Path) -> str:
    env = _get_env(templates_dir)
    tpl = env.get_template("web.html.j2")
    ctx = _contexto_comun(briefing, config)
    ctx.update({
        "sitio_titulo": config["web"]["titulo"],
        "meta_descripcion": f"{briefing.cultura.titulo} — {ctx['fecha_larga']}",
        "ruta_assets": "../assets",
        "ruta_raiz": "../",
    })
    return tpl.render(**ctx)


def render_index_html(historial: list[dict], config: dict, templates_dir: Path) -> str:
    """historial: lista de dicts con fecha, fecha_larga, categoria,
    titulo_cultura, url — ya ordenada de más reciente a más antigua."""
    env = _get_env(templates_dir)
    tpl = env.get_template("index.html.j2")
    categorias = sorted({b["categoria"] for b in historial})
    for b in historial:
        b["titulo_busqueda"] = f"{b['titulo_cultura']} {b['categoria']}".lower()
    return tpl.render(
        sitio_titulo=config["web"]["titulo"],
        sitio_descripcion=config["web"]["descripcion"],
        briefings=historial,
        categorias=categorias,
        total_briefings=len(historial),
    )


def render_markdown(briefing: Briefing, config: dict) -> str:
    fecha = briefing.fecha_date
    fecha_larga = fecha_larga_es(fecha)
    partes = [
        f"# Briefing — {fecha_larga}",
        "",
        "## Actualidad",
        "",
        briefing.actualidad.arranque,
        "",
    ]
    for h in briefing.actualidad.historias:
        partes.append(f"### {h.titular_editorial}")
        partes.append("")
        partes.append(h.texto)
        partes.append("")
    partes.append("**En el radar.** " + briefing.actualidad.radar_texto)
    partes.append("")
    partes.append(f"## Cultura general — {briefing.cultura.categoria}")
    partes.append("")
    partes.append(f"### {briefing.cultura.titulo}")
    partes.append("")
    partes.append(briefing.cultura.texto)
    partes.append("")
    partes.append(f"> {briefing.cultura.dato_sobremesa}")
    if briefing.cultura.tirar_del_hilo_texto:
        partes.append("")
        partes.append("**Si quieres tirar del hilo.** " + briefing.cultura.tirar_del_hilo_texto)
    partes.append("")
    partes.append("## Fuentes")
    partes.append("")
    for f in _fuentes_unicas(briefing):
        partes.append(f"- [{f.medio}]({f.url}) — {f.fecha_publicacion}")
    partes.append("")
    return "\n".join(partes)
