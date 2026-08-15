#!/usr/bin/env python3
"""
Orquestador del briefing diario.

  python src/cli.py generate --dry-run
      Uso local. Invoca las 3 skills de Claude Code por subprocess (usando
      tu login interactivo de `claude`), luego corre validate+render y abre
      el resultado en el navegador. No envía email ni escribe en briefings/,
      docs/ ni state/ — todo va a work/preview/.

  python src/cli.py finalize [--dry-run]
      Fases 6+7. Asume que work/research.json y work/final.json ya existen
      (los escriben las skills, vía subprocess local o vía GitHub Actions).
      Valida, degrada si hace falta, renderiza, persiste, actualiza estado
      y envía el email. Es idempotente: si el briefing de hoy ya existe en
      briefings/, no hace nada y termina en 0.

  python src/cli.py failure-notice --motivo "..." --detalle "..."
      Envía el email corto de aviso cuando el pipeline no pudo producir
      nada publicable, ni siquiera degradado.

  python src/cli.py already-done
      Imprime "true" o "false". Lo usa el workflow para saltarse los pasos
      de Claude Code cuando el briefing de hoy ya se generó.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
import zoneinfo
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))

import mailer  # noqa: E402
import render  # noqa: E402
import state  # noqa: E402
from schema import Briefing  # noqa: E402
from validate import validar_con_degradacion  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.yaml"
WORK_DIR = ROOT / "work"
BRIEFINGS_DIR = ROOT / "briefings"
DOCS_DIR = ROOT / "docs"
STATE_DIR = ROOT / "state"
TEMPLATES_DIR = ROOT / "templates"
PREVIEW_DIR = WORK_DIR / "preview"

RESEARCH_PATH = WORK_DIR / "research.json"
DRAFT_PATH = WORK_DIR / "draft.json"
FINAL_PATH = WORK_DIR / "final.json"
USED_TOPICS_PATH = STATE_DIR / "used_topics.json"
RECENT_STORIES_PATH = STATE_DIR / "recent_stories.json"

ZONA_MADRID = zoneinfo.ZoneInfo("Europe/Madrid")


def cargar_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def fecha_briefing() -> str:
    """La fecha del briefing es la del día en curso en Madrid, no en UTC —
    importante porque el cron corre en UTC y a las 04-06h UTC ya puede ser
    el día siguiente en España o no, según la época del año."""
    override = os.environ.get("BRIEFING_DATE")
    if override:
        return override
    return datetime.now(ZONA_MADRID).date().isoformat()


def log(msg: str) -> None:
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# generate — orquestación local vía subprocess de `claude`
# ---------------------------------------------------------------------------

def _run_skill(nombre_skill: str, fecha: str, max_budget_usd: float) -> float:
    """Ejecuta la skill vía `claude -p` con tu login interactivo (no gasta
    el token de CI). `--max-budget-usd` es un tope real de gasto que Claude
    Code aplica en vivo -- no existe `--max-turns` en la version actual del
    CLI (2.1.228), pese a lo que digan guias antiguas. Devuelve el coste
    estimado por Claude Code para esta llamada (a precio de lista -- igual
    que `/usage`, no es una factura real en un plan de suscripcion, pero es
    el numero mas honesto disponible para comparar fases entre si)."""
    log(f"→ ejecutando /{nombre_skill} ... (tope ${max_budget_usd:.2f}, puede tardar varios minutos)")
    # La fecha viaja en el propio texto del prompt, no solo por variable de
    # entorno: la skill de investigación no tiene acceso a Bash (allowed-tools
    # no lo incluye), así que leer $BRIEFING_DATE del entorno no es fiable.
    # BRIEFING_DATE se deja también en el entorno por si una skill futura
    # con Bash lo necesita, pero el prompt es la fuente de verdad.
    prompt = f"/{nombre_skill}\n\nFecha del briefing (Europe/Madrid): {fecha}."
    env = os.environ.copy()
    env["BRIEFING_DATE"] = fecha
    resultado = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "json", "--max-budget-usd", str(max_budget_usd)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if resultado.returncode != 0:
        log(resultado.stderr)
        raise SystemExit(f"'{nombre_skill}' terminó con código {resultado.returncode}")

    coste = 0.0
    try:
        payload = json.loads(resultado.stdout)
        coste = float(payload.get("total_cost_usd") or 0.0)
        resumen = str(payload.get("result", "")).strip()
        if resumen:
            log(f"  {resumen.splitlines()[-1][:200]}")
        log(f"  coste estimado de esta fase: ${coste:.4f}")
        if coste >= max_budget_usd:
            log(f"  ⚠ tocó o superó el tope de ${max_budget_usd:.2f} — puede haber cortado antes de terminar")
    except (json.JSONDecodeError, TypeError, ValueError):
        log("  (no se pudo leer el coste estimado de la salida JSON — no bloquea el run)")
    return coste


def cmd_generate(args: argparse.Namespace) -> int:
    fecha = fecha_briefing()
    if state.ya_publicado_hoy(BRIEFINGS_DIR, fecha) and not args.force:
        log(f"El briefing del {fecha} ya existe en briefings/. Usa --force para regenerar.")
        return 0

    config = cargar_config()
    presupuestos = {
        "briefing-research": config["modelo"]["max_budget_usd_research"],
        "briefing-write": config["modelo"]["max_budget_usd_write"],
        "briefing-verify": config["modelo"]["max_budget_usd_verify"],
    }

    WORK_DIR.mkdir(exist_ok=True)
    coste_total = 0.0
    for skill, presupuesto in presupuestos.items():
        coste_total += _run_skill(skill, fecha, presupuesto)

    log(f"\nCoste estimado total del run (a precio de lista, informativo): ${coste_total:.4f}")
    log("(En un plan Pro/Max esto no se factura aparte — consume tu cupo de suscripción,")
    log(" no dinero adicional. El número sirve para comparar, no es una factura real.)\n")

    return cmd_finalize(argparse.Namespace(dry_run=args.dry_run))


# ---------------------------------------------------------------------------
# finalize — fases 6 y 7
# ---------------------------------------------------------------------------

def _copiar_assets(destino: Path) -> None:
    import shutil
    origen = TEMPLATES_DIR / "assets"
    destino.mkdir(parents=True, exist_ok=True)
    for f in origen.iterdir():
        shutil.copy2(f, destino / f.name)


def _construir_historial(fecha_actual: str) -> list[dict]:
    """Lee todos los briefings/*.json existentes (más el de hoy, aunque
    todavía no se haya escrito a disco, para que el índice lo incluya sin
    tener que releerlo) y arma la lista para docs/index.html."""
    entradas = []
    for p in sorted(BRIEFINGS_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        entradas.append(d)

    historial = []
    for d in entradas:
        f = d["fecha"]
        cultura = d.get("cultura", {})
        fecha_dt = datetime.strptime(f, "%Y-%m-%d").date()
        historial.append({
            "fecha": f,
            "fecha_larga": render.fecha_larga_es(fecha_dt),
            "categoria": cultura.get("categoria", ""),
            "titulo_cultura": cultura.get("titulo", ""),
            "url": f"b/{f}.html",
        })
    historial.sort(key=lambda e: e["fecha"], reverse=True)
    return historial


def cmd_finalize(args: argparse.Namespace) -> int:
    config = cargar_config()
    fecha = fecha_briefing()
    dry_run = args.dry_run

    if not dry_run and state.ya_publicado_hoy(BRIEFINGS_DIR, fecha):
        log(f"El briefing del {fecha} ya está publicado. Nada que hacer (idempotencia).")
        return 0

    if not RESEARCH_PATH.exists() or not FINAL_PATH.exists():
        log(f"Faltan {RESEARCH_PATH.name} o {FINAL_PATH.name} en work/. ¿Corrieron las skills?")
        _fallo(config, "Faltan los archivos de trabajo de las skills", dry_run)
        return 1  # finalize no produjo un briefing -- falla siempre, sin importar si el aviso se envió

    resultado, briefing = validar_con_degradacion(
        FINAL_PATH, RESEARCH_PATH, USED_TOPICS_PATH, config,
        verificar_urls=not dry_run,  # en dry-run local no golpeamos la red por cada iteración
    )
    log(resultado.render_reporte())

    if not resultado.ok or briefing is None:
        if dry_run:
            log("\n[dry-run] Validación fallida. No se envía nada.")
            return 1
        _fallo(config, "La validación (con degradación) falló", dry_run, detalle=resultado.render_reporte())
        return 1  # idem -- el build falló, independientemente de si el email de aviso salió bien

    if dry_run:
        return _render_preview(briefing, config)

    return _publicar(briefing, config, fecha, resultado)


def _render_preview(briefing: Briefing, config: dict) -> int:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    html_email = render.render_email_html(briefing, config, TEMPLATES_DIR, url_historial="#")
    html_web = render.render_web_html(briefing, config, TEMPLATES_DIR)
    md = render.render_markdown(briefing, config)

    (PREVIEW_DIR / "email.html").write_text(html_email, encoding="utf-8")
    (PREVIEW_DIR / "email.txt").write_text(render.render_email_text(briefing, config), encoding="utf-8")
    (PREVIEW_DIR / "web.html").write_text(html_web, encoding="utf-8")
    (PREVIEW_DIR / "briefing.md").write_text(md, encoding="utf-8")
    _copiar_assets(PREVIEW_DIR / "assets")
    # el preview del email usa rutas ../assets (como docs/b/*.html);
    # para que abra bien de forma aislada, lo servimos desde una subcarpeta.
    (PREVIEW_DIR / "b").mkdir(exist_ok=True)
    (PREVIEW_DIR / "b" / "web.html").write_text(html_web, encoding="utf-8")

    log(f"\n[dry-run] Generado en {PREVIEW_DIR}")
    webbrowser.open((PREVIEW_DIR / "email.html").resolve().as_uri())
    webbrowser.open((PREVIEW_DIR / "b" / "web.html").resolve().as_uri())
    return 0


def _publicar(briefing: Briefing, config: dict, fecha: str, resultado) -> int:
    BRIEFINGS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "b").mkdir(parents=True, exist_ok=True)

    url_base = config["web"].get("url_base") or ""
    url_historial = f"{url_base.rstrip('/')}/index.html" if url_base else "index.html"

    # 1. Persistir el JSON final (= la marca de idempotencia) y el markdown.
    (BRIEFINGS_DIR / f"{fecha}.json").write_text(
        json.dumps(_briefing_a_dict(briefing), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (BRIEFINGS_DIR / f"{fecha}.md").write_text(render.render_markdown(briefing, config), encoding="utf-8")

    # 2. Renderizar y escribir la web.
    html_web = render.render_web_html(briefing, config, TEMPLATES_DIR)
    (DOCS_DIR / "b" / f"{fecha}.html").write_text(html_web, encoding="utf-8")
    _copiar_assets(DOCS_DIR / "assets")
    historial = _construir_historial(fecha)
    (DOCS_DIR / "index.html").write_text(render.render_index_html(historial, config, TEMPLATES_DIR), encoding="utf-8")

    # 3. Actualizar estado (temas usados, historias recientes para continuaciones).
    state.registrar_tema_cultural(USED_TOPICS_PATH, fecha, briefing.cultura.categoria, briefing.cultura.titulo)
    research_raw = json.loads(RESEARCH_PATH.read_text(encoding="utf-8"))
    ids_publicados = {h.id for h in briefing.actualidad.historias}
    historias_para_estado = [
        h for h in research_raw.get("actualidad", {}).get("historias", [])
        if h.get("id") in ids_publicados
    ]
    state.registrar_historias_recientes(RECENT_STORIES_PATH, fecha, historias_para_estado)

    # 4. Enviar el email.
    html_email = render.render_email_html(briefing, config, TEMPLATES_DIR, url_historial=url_historial)
    texto_email = render.render_email_text(briefing, config)
    asunto = config["entrega"]["asunto"].format(fecha_larga=render.fecha_larga_es(briefing.fecha_date))

    resend_api_key = _env_o_falla("RESEND_API_KEY")
    mailer.enviar_briefing(
        asunto=asunto,
        html=html_email,
        texto_plano=texto_email,
        destinatarios=config["entrega"]["destinatarios"],
        remitente_nombre=config["entrega"]["remitente_nombre"],
        resend_api_key=resend_api_key,
        reintentos=config["fallo"]["reintentos_por_fase"],
    )

    if resultado.historias_descartadas:
        log(f"Publicado con degradación. Historias descartadas: {resultado.historias_descartadas}")
    log(f"Briefing del {fecha} publicado y enviado.")
    return 0


def _briefing_a_dict(briefing: Briefing) -> dict:
    return {
        "fecha": briefing.fecha,
        "actualidad": {
            "arranque": briefing.actualidad.arranque,
            "historias_texto": [
                {"id": h.id, "titular_editorial": h.titular_editorial, "texto": h.texto}
                for h in briefing.actualidad.historias
            ],
            "radar_texto": briefing.actualidad.radar_texto,
            "palabras": briefing.actualidad.palabras,
        },
        "cultura": {
            "titulo": briefing.cultura.titulo,
            "categoria": briefing.cultura.categoria,
            "texto": briefing.cultura.texto,
            "dato_sobremesa": briefing.cultura.dato_sobremesa,
            "tirar_del_hilo_texto": briefing.cultura.tirar_del_hilo_texto,
            "palabras": briefing.cultura.palabras,
        },
    }


def _env_o_falla(nombre: str) -> str:
    valor = os.environ.get(nombre)
    if not valor:
        raise SystemExit(f"falta la variable de entorno {nombre}")
    return valor


def _fallo(config: dict, motivo: str, dry_run: bool, detalle: str = "") -> int:
    """Envía el email corto de aviso. El valor de retorno describe SOLO si
    el aviso se mandó bien (0) o no (1) -- no dice nada sobre si el build en
    sí falló, porque eso ya lo sabe el llamador por definición (por algo
    está llamando a esta función). `cmd_finalize` ignora este valor a
    propósito y siempre devuelve 1 en sus propios call sites: un email de
    aviso enviado con éxito no convierte un build fallido en un éxito."""
    log(f"\nFALLO: {motivo}")
    if dry_run:
        log("[dry-run] no se envía email de aviso.")
        return 1
    resend_api_key = os.environ.get("RESEND_API_KEY")
    if not resend_api_key:
        log("(tampoco hay credencial de Resend para avisar por email — solo queda este log)")
        return 1
    mailer.enviar_aviso_de_fallo(
        motivo=motivo,
        detalle=detalle,
        destinatarios=config["entrega"]["destinatarios"],
        remitente_nombre=config["entrega"]["remitente_nombre"],
        resend_api_key=resend_api_key,
        url_logs=os.environ.get("GITHUB_RUN_URL", ""),
        reintentos=config["fallo"]["reintentos_por_fase"],
    )
    log("aviso de fallo enviado correctamente.")
    return 0


# ---------------------------------------------------------------------------
# comandos auxiliares
# ---------------------------------------------------------------------------

def cmd_already_done(args: argparse.Namespace) -> int:
    fecha = fecha_briefing()
    print("true" if state.ya_publicado_hoy(BRIEFINGS_DIR, fecha) else "false")
    return 0


def cmd_failure_notice(args: argparse.Namespace) -> int:
    config = cargar_config()
    return _fallo(config, args.motivo, dry_run=False, detalle=args.detalle or "")


# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="comando", required=True)

    p_generate = sub.add_parser("generate", help="Orquesta las 3 skills + finalize. Uso local.")
    p_generate.add_argument("--dry-run", action="store_true")
    p_generate.add_argument("--force", action="store_true", help="regenerar aunque ya exista el briefing de hoy")
    p_generate.set_defaults(func=cmd_generate)

    p_finalize = sub.add_parser("finalize", help="Fases 6+7: valida, renderiza, publica, envía.")
    p_finalize.add_argument("--dry-run", action="store_true")
    p_finalize.set_defaults(func=cmd_finalize)

    p_done = sub.add_parser("already-done", help="Imprime true/false. Para el guard del workflow.")
    p_done.set_defaults(func=cmd_already_done)

    p_fail = sub.add_parser("failure-notice", help="Envía el email corto de aviso de fallo.")
    p_fail.add_argument("--motivo", required=True)
    p_fail.add_argument("--detalle", default="")
    p_fail.set_defaults(func=cmd_failure_notice)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
