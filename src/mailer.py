"""
Envío de correo — API de Resend, vía HTTP puro (stdlib `urllib`, sin
dependencias nuevas). Se eligió Resend en vez de Gmail SMTP porque la
cuenta de Federico no tiene contraseñas de aplicación disponibles (ni
verificación en dos pasos completa, ni Workspace) y depurar esa
restricción de Google no valía la pena frente a la alternativa.

Sin dominio propio verificado, Resend solo permite:
  - remitente: onboarding@resend.dev (la dirección de pruebas de Resend)
  - destinatario: únicamente la propia dirección de la cuenta de Resend

Eso encaja exactamente con este caso — el único destinatario del briefing
es Federico mismo. Si algún día se verifica un dominio propio, solo hay
que cambiar `remitente_email` en config.yaml y añadir más destinatarios.

Dos funciones públicas, mismo contrato que antes:
  enviar_briefing()       — el email completo, HTML con fallback de texto.
  enviar_aviso_de_fallo() — email corto cuando el pipeline falla del todo.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

logger = logging.getLogger("briefing.mailer")

RESEND_API_URL = "https://api.resend.com/emails"
REMITENTE_RESEND_DEV = "onboarding@resend.dev"  # dirección de pruebas, sin dominio propio


class MailerError(RuntimeError):
    """Fallo de envío tras agotar los reintentos configurados."""


def _con_reintentos(fn, *, intentos: int, base_espera: float = 2.0):
    ultimo_error: Exception | None = None
    for intento in range(1, intentos + 2):  # +1 intento inicial + reintentos
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 — cualquier fallo de red/API cuenta como reintentable
            ultimo_error = e
            if intento <= intentos:
                espera = base_espera * (2 ** (intento - 1))
                logger.warning("envío falló (intento %d): %s — reintento en %.0fs", intento, e, espera)
                time.sleep(espera)
    raise MailerError(f"envío falló tras {intentos + 1} intento(s): {ultimo_error}") from ultimo_error


def _post_resend(api_key: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Sin esto, urllib manda "Python-urllib/3.x" como User-Agent, que
            # el Cloudflare delante de la API de Resend bloquea directamente
            # (error 1010 -- "browser signature banned"). Con un User-Agent
            # normal la petición pasa sin problema.
            "User-Agent": "briefing-diario/1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", errors="replace")
        raise MailerError(f"Resend devolvió {e.code}: {detalle}") from e


def enviar_briefing(
    *,
    asunto: str,
    html: str,
    texto_plano: str,
    destinatarios: list[str],
    remitente_nombre: str,
    resend_api_key: str,
    remitente_email: str = REMITENTE_RESEND_DEV,
    reintentos: int = 1,
) -> None:
    payload = {
        "from": f"{remitente_nombre} <{remitente_email}>",
        "to": destinatarios,
        "subject": asunto,
        "html": html,
        "text": texto_plano,
    }
    resultado = _con_reintentos(lambda: _post_resend(resend_api_key, payload), intentos=reintentos)
    logger.info("briefing enviado a %s (id Resend: %s)", ", ".join(destinatarios), resultado.get("id"))


def enviar_aviso_de_fallo(
    *,
    motivo: str,
    detalle: str,
    destinatarios: list[str],
    remitente_nombre: str,
    resend_api_key: str,
    remitente_email: str = REMITENTE_RESEND_DEV,
    url_logs: str = "",
    reintentos: int = 1,
) -> None:
    """Se dispara cuando el pipeline no consigue producir un briefing
    publicable, ni siquiera degradado. Corto a propósito: es una alerta,
    no un briefing."""
    cuerpo = (
        f"<p>El briefing de hoy no se pudo generar.</p>"
        f"<p><b>Motivo:</b> {motivo}</p>"
        f"<pre style=\"white-space: pre-wrap; font-size: 13px;\">{detalle}</pre>"
    )
    if url_logs:
        cuerpo += f'<p><a href="{url_logs}">Logs del run</a></p>'

    payload = {
        "from": f"{remitente_nombre} <{remitente_email}>",
        "to": destinatarios,
        "subject": "Briefing diario — no se pudo generar hoy",
        "html": cuerpo,
        "text": f"El briefing de hoy no se pudo generar.\n\nMotivo: {motivo}\n\n{detalle}\n{url_logs}",
    }
    _con_reintentos(lambda: _post_resend(resend_api_key, payload), intentos=reintentos)
    logger.info("aviso de fallo enviado a %s", ", ".join(destinatarios))
