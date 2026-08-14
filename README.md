# briefing-diario

Cada mañana a las 06:05 (hora de Madrid) llega un email con dos secciones:

- **Actualidad** (4 min) — 3-5 historias globales seleccionadas por importancia real, no por ruido mediático. Directo a los datos, sin relleno.
- **Cultura general** (8 min) — un tema con valor educativo real (historia, arte, economía, ciencia, deporte...), contado con un ángulo raro, con rotación forzada de categoría y anti-repetición.

Cada afirmación factual pasa por una fase de verificación separada antes de publicarse. El histórico completo vive en una web navegable con buscador.

Este README asume que dentro de tres meses no te acordarás de nada de esto. Sigue los pasos en orden.

---

## Cómo funciona, en una frase

GitHub Actions dispara cada mañana un pipeline de 3 llamadas a Claude Code (investigación → redacción → verificación, cada una con contexto limpio), un validador en Python que **no** es negociable por el modelo, y un envío por email. El coste marginal es **0 €**: usa tu suscripción de Claude Pro (no la API de pago) y la capa gratuita de Resend.

```
GitHub Actions (cron 06:05 Madrid)
  → /briefing-research   (Claude Code, skill)  → work/research.json
  → /briefing-write      (Claude Code, skill)  → work/draft.json
  → /briefing-verify     (Claude Code, skill)  → work/final.json
  → src/cli.py finalize  (Python puro)
      → valida (rompe el build si algo no cumple)
      → renderiza (email + web + markdown)
      → persiste en briefings/, docs/, state/
      → envía el email por la API de Resend
      → (el workflow hace el commit + push)
```

---

## Setup — hazlo una sola vez

### 1. Crear el repositorio en GitHub

Público (para minutos de Actions y GitHub Pages gratis e ilimitados — el histórico no contiene nada sensible).

```bash
cd ~/briefing-diario
git init
git add -A
git commit -m "Setup inicial del briefing diario"
gh repo create briefing-diario --public --source=. --remote=origin --push
```

Si no tienes `gh` instalado: `brew install gh && gh auth login`, o crea el repo a mano en github.com y añade el remoto tú mismo.

### 2. Token de Claude Code (usa tu suscripción Pro, no la API)

En tu terminal, con `claude` ya instalado y logueado con tu cuenta Pro:

```bash
claude setup-token
```

Esto genera un token largo (`sk-ant-oat01-...`). Cópialo — no se vuelve a mostrar.

### 3. API key de Resend

Se usa Resend en vez de Gmail SMTP porque las app passwords de Google no
estaban disponibles en la cuenta (ni verificación en dos pasos completa, ni
Workspace). Sin dominio propio, Resend solo permite enviar **a la propia
dirección de la cuenta** — que es exactamente el único destinatario que
necesitas.

1. Crea una cuenta en https://resend.com **usando la misma dirección** que
   tienes en `config.yaml` → `entrega.destinatarios` (`federico.trespalacios@gmail.com`).
   Es un requisito real de Resend sin dominio verificado: sin domino, solo
   se puede enviar a la dirección con la que te registraste.
2. En el dashboard, ve a **API Keys** → **Create API Key**. Nombre libre
   (ej. "briefing-diario"), permiso "Sending access" basta.
3. Copia la clave, empieza por `re_...` — no se vuelve a mostrar completa.

Capa gratuita: 100 emails/día, 3.000/mes — de sobra para 1 al día.

Si más adelante verificas un dominio propio en Resend, puedes enviar a
cualquier destinatario y cambiar el remitente en `src/mailer.py` →
`REMITENTE_RESEND_DEV`.

### 4. Secretos en GitHub

En el repo → **Settings → Secrets and variables → Actions → New repository secret**. Crea exactamente estos dos:

| Nombre | Valor |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | El token del paso 2 |
| `RESEND_API_KEY` | La API key del paso 3 (`re_...`) |

Nunca van en el repo, solo en Secrets.

### 5. Activar GitHub Pages

Repo → **Settings → Pages** → Source: **Deploy from a branch** → Branch: `main`, carpeta `/docs` → Save.

La URL será `https://<tu-usuario>.github.io/briefing-diario/`. Cuando la tengas, ponla en `config.yaml` → `web.url_base` (sin barra final) y haz commit — así el email enlaza bien al histórico.

### 6. Primer run

Repo → **Actions** → "Briefing diario" → **Run workflow** (botón manual, no hace falta esperar al cron). Tarda entre 10 y 25 minutos. Si algo falla, te llega un email corto avisando — no silencio.

---

## Uso local — iterar sin gastar cuota de verdad

Requiere `claude` instalado y logueado en tu Mac (usa tu sesión interactiva, no gasta el token de CI).

```bash
cd ~/briefing-diario
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python src/cli.py generate --dry-run
```

Esto corre las 3 skills de verdad (consume tu cuota de Claude Pro, la compartida con tu uso normal de Claude Code) y abre el email y la web resultantes en Safari. **No** envía nada ni toca git ni state/. Los archivos quedan en `work/preview/`.

Para iterar solo sobre validador/render sin gastar ninguna llamada a Claude, usa datos sintéticos:

```bash
python -c "
import sys, json; sys.path += ['src','tests']
import yaml
from fixtures import construir_briefing_valido
config = yaml.safe_load(open('config.yaml'))
research, final = construir_briefing_valido(config, n_historias=4)
json.dump(research, open('work/research.json','w'), ensure_ascii=False, indent=2)
json.dump(final, open('work/final.json','w'), ensure_ascii=False, indent=2)
"
python src/cli.py finalize --dry-run
```

Correr los tests:

```bash
pytest tests/ -v
```

---

## Ajustar el sistema sin tocar código

Todo vive en `config.yaml`: hora de entrega, rangos de longitud, ejes de actualidad, medios preferidos/vetados, categorías culturales, umbrales de validación, política de fallo. Cambios ahí no requieren tocar Python ni las skills.

Los prompts viven en `.claude/skills/briefing-{research,write,verify}/SKILL.md` — en texto plano, versionados, pensados para iterarlos mucho. Edítalos directamente y prueba con `generate --dry-run`.

---

## Coste

- **Claude Code**: tu suscripción Pro/Max, la misma cuota que tu uso interactivo (`support.claude.com` → "usage limits are shared across Claude and Claude Code"). No hay facturación aparte por token — pero sí consume del mismo cupo que usas a diario, así que el número de abajo importa.
- **GitHub Actions**: gratis e ilimitado en repos públicos.
- **Resend**: gratis (capa gratuita, 100 emails/día).
- **GitHub Pages**: gratis.

**Coste real medido** (run del 2026-08-12, a precio de lista — así se compara, aunque en Pro/Max no se facture aparte):

| Fase | Coste |
|---|---|
| Investigación | ~$2.34 |
| Redacción | ~$1.66 |
| Verificación | ~$3.08 (sin tope — motivó el ajuste de abajo) |
| **Total sin topes** | **~$7.08/día** |

Ese número es alto frente a la referencia de Anthropic de ~$13/día para un desarrollador activo medio — casi medio "día normal" de uso, solo para el briefing. Por eso `config.yaml` → `modelo.max_budget_usd_*` pone un tope real de gasto por fase (`--max-budget-usd`, el mecanismo que Claude Code aplica de verdad — `--max-turns` no existe en la versión actual del CLI, pese a lo que digan guías antiguas), y `briefing-verify/SKILL.md` prioriza qué verifica en vez de rebuscar todo desde cero.

**Recomendación real: no lo dejes en diario sin medir primero tu propia cadencia.** Corre `python src/cli.py generate --dry-run` un par de veces, mira el coste que imprime al final, y decide con ese dato si el cron diario te vale o prefieres cada 2 días — es un cambio de una línea en `daily.yml` (el segundo `cron:` cambia a `*/2` en el campo de día).

Total en dinero real: **0 €/mes** siempre — lo que varía es cuánto de tu cupo de suscripción se lleva, no cuánto pagas aparte.

---

## Cómo falla (a propósito)

- **Idempotencia**: si el workflow corre dos veces el mismo día, la segunda vez no hace nada — mira si `briefings/AAAA-MM-DD.json` ya existe.
- **Guard de horario**: el cron dispara dos veces al día (una por cada huso posible de las 06:05 en Madrid); un guard descarta la que no toca.
- **Reintento**: si la validación falla, el pipeline entero (investigación→redacción→verificación) se repite una vez más.
- **Degradación**: si tras el reintento sigue fallando pero el problema son historias concretas (no la sección de cultura), esas historias se descartan y se publica el resto — nunca se publica un dato no verificado.
- **Fallo total**: si ni así hay nada publicable, llega un email corto avisando en vez de silencio.

---

## Estructura del repo

```
config.yaml                      # toda la configuración ajustable
.claude/skills/                  # los 3 prompts, en Markdown
src/
  schema.py                      # el contrato de datos del briefing
  validate.py                    # Fase 6 — validador programático
  render.py                      # Fase 7 — email/web/markdown
  mailer.py                      # envío vía API de Resend
  state.py                       # histórico de temas y continuaciones
  cli.py                         # orquestador (generate / finalize)
templates/                       # Jinja2 (email, web, índice) + CSS/JS
state/used_topics.json           # anti-repetición cultural
state/recent_stories.json        # detección de continuaciones
briefings/AAAA-MM-DD.{json,md}   # archivo de cada día (json = fuente de verdad)
docs/                            # la web (GitHub Pages sirve esto)
.github/workflows/daily.yml      # el cron
tests/                           # pytest — validador y render
```
