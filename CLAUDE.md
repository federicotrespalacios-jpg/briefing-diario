# CLAUDE.md — convenciones de este proyecto

Contexto para cualquier sesión de Claude Code (interactiva o vía Actions) que trabaje en este repo.

## Qué es esto

Un sistema que genera y envía un briefing diario (actualidad + cultura general) por email, usando 3 skills de Claude Code en fases separadas y un validador programático que no negocia con el modelo. Ver README.md para el setup; este archivo es solo convenciones de trabajo dentro del repo.

## Reglas duras, no las rompas sin que Federico lo pida explícitamente

- **Las skills nunca escriben directamente el email o la web.** Solo producen JSON en `work/`. Todo el render vive en `src/render.py`, en Python, determinista.
- **El validador (`src/validate.py`) es la única autoridad sobre si algo se publica.** Si necesitas cambiar un umbral (longitud, número de fuentes, antigüedad), edítalo en `config.yaml`, nunca hardcodees un número nuevo en `validate.py`.
- **`schema.py` no tiene dependencias externas.** Debe poder importarse con solo la stdlib. Si necesitas una validación nueva, hazla con `dataclasses` + funciones simples, no añadas pydantic ni nada parecido.
- **Nunca bajes el modelo a Haiku para la redacción o verificación** sin que Federico lo pida — la Fase 5 (verificación) es la que evita que un dato inventado llegue al email, y necesita un modelo capaz de dudar de su propio texto.
- **La sección de cultura nunca se degrada.** Si algo falla ahí, el build entero falla (o se manda solo el email de aviso). Solo las historias de actualidad se pueden descartar individualmente en la política de degradación.

## Estilo de las skills (`.claude/skills/*/SKILL.md`)

- Prompts en español, tono directo, sin relleno.
- Cada skill declara `allowed-tools` explícitamente en el frontmatter — nunca dependas de que el modelo "adivine" qué herramientas tiene.
- El JSON de salida de cada skill es un contrato con la siguiente fase. Si cambias un campo del JSON, cambia también `schema.py` y el ejemplo de esquema dentro del SKILL.md correspondiente — deben quedarse en sync a mano, no hay generación automática entre ambos.
- La fecha del briefing se pasa **en el texto del prompt**, no por variable de entorno — la skill de investigación no tiene acceso a Bash, así que no puede leer `$BRIEFING_DATE` aunque esté en el entorno. Ver `src/cli.py::_run_skill` y el workflow para el patrón exacto.

## Python

- Target: Python 3.9 en local (es lo que hay en el Mac de Federico sin tocar el sistema), 3.12 en CI. Por eso todo módulo en `src/` empieza con `from __future__ import annotations` y evita sintaxis que no exista en 3.9 (nada de `match` con patrones complejos, cuidado con `X | Y` fuera de anotaciones diferidas).
- Sin dependencias que no estén en `requirements.txt`. Las tres son deliberadamente pocas: `PyYAML`, `Jinja2`, `pytest`.
- `src/cli.py` es el único punto de entrada. No añadas scripts sueltos en la raíz — si hace falta un comando nuevo, es un subcomando de `cli.py`.

## Tests

- `pytest tests/ -v` debe pasar siempre antes de tocar `validate.py` o `render.py`.
- Los fixtures sintéticos (`tests/fixtures.py`) generan briefings válidos por construcción — si añades una regla de validación nueva, añade también un test que la rompa a propósito (ver el patrón `test_falla_si_*` en `test_validate.py`).
- Nunca hagas que un test golpee red de verdad. `verificar_urls=False` en todos los tests de `validate.py`.

## Cosas que ya se decidieron y no hace falta repensar

- **Sonnet, no Opus**, por defecto (`config.yaml` → `modelo.nombre`) — la cuota de Claude Code Pro es compartida con el uso interactivo de Federico. Subir a Opus es una decisión suya, no una optimización automática.
- **Reintento = repetir las 3 skills una vez**, no reintentar fase por fase. Es una simplificación deliberada por cómo funciona `claude-code-action` en GitHub Actions (no hay forma limpia de reintentar un solo step de Action como unidad atómica sin duplicar el bloque completo).
- **Resend, no Gmail SMTP** — se intentó Gmail primero, pero la cuenta no tenía app passwords disponibles (2FA/Workspace). Resend sin dominio propio solo envía a la dirección de la propia cuenta, que es justo el único destinatario. Si algún día hay dominio propio, se puede ampliar sin cambiar de proveedor.
- **`--max-budget-usd`, no `--max-turns`** — la versión instalada del CLI (2.1.228) no expone `--max-turns`; el control de gasto real es `--max-budget-usd` en `config.yaml` → `modelo.max_budget_usd_*`. Si una guía o memoria antigua menciona `--max-turns`, está desactualizada — confirmar con `claude --help` antes de usarla.
- **Repo público** — el histórico no contiene nada sensible, y así Actions y Pages son gratis e ilimitados.

## Si algo se rompe en producción

1. Mira el artefacto `briefing-work-<run_id>` subido por el workflow — tiene el `work/research.json`, `draft.json`, `final.json` (los que existan) del run que falló.
2. El email de aviso de fallo trae el link directo al run.
3. La causa más probable, en orden de frecuencia esperada: (a) una skill se pasó del `max_turns` configurado, (b) una URL de fuente real dio 404 después de que Claude la citara (medios que borran o mueven artículos), (c) el tema cultural elegido resultó ser un solape no detectado con el histórico.
