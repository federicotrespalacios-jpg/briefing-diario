from datetime import date
from pathlib import Path

from fixtures import construir_briefing_valido

from render import (
    fecha_larga_es,
    render_email_html,
    render_email_text,
    render_index_html,
    render_markdown,
    render_web_html,
)
from schema import Briefing

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def _briefing(config, n_historias=3) -> Briefing:
    research, final = construir_briefing_valido(config, n_historias=n_historias)
    return Briefing.from_dicts(final, research)


def test_fecha_larga_es_formatea_en_espanol():
    assert fecha_larga_es(date(2026, 8, 13)) == "jueves, 13 de agosto de 2026"
    assert fecha_larga_es(date(2026, 1, 1)) == "jueves, 1 de enero de 2026"


def test_render_email_html_incluye_secciones_clave(config):
    briefing = _briefing(config)
    html = render_email_html(briefing, config, TEMPLATES_DIR, url_historial="https://example.com/index.html")

    assert "Actualidad" in html
    assert briefing.cultura.titulo in html
    assert briefing.cultura.dato_sobremesa in html
    assert "https://example.com/index.html" in html
    # email-safe: nada de <script>, todo con estilos inline vía tabla
    assert "<script" not in html
    assert "<table" in html
    # tema oscuro presente
    assert "prefers-color-scheme: dark" in html


def test_render_email_html_incluye_todas_las_historias(config):
    briefing = _briefing(config, n_historias=4)
    html = render_email_html(briefing, config, TEMPLATES_DIR, url_historial="#")
    for h in briefing.actualidad.historias:
        assert h.titular_editorial in html


def test_render_email_text_es_texto_plano_legible(config):
    briefing = _briefing(config)
    texto = render_email_text(briefing, config)

    assert "<" not in texto  # sin marcado HTML
    assert briefing.cultura.titulo in texto
    assert "FUENTES" in texto
    for h in briefing.actualidad.historias:
        for f in h.fuentes:
            assert f.url in texto


def test_render_web_html_referencia_assets_relativos(config):
    briefing = _briefing(config)
    html = render_web_html(briefing, config, TEMPLATES_DIR)

    assert "../assets/styles.css" in html
    assert briefing.cultura.titulo in html
    assert "<script" in html  # el toggle de tema sí es legítimo aquí (no es email)


def test_render_markdown_tiene_estructura_de_archivo(config):
    briefing = _briefing(config)
    md = render_markdown(briefing, config)

    assert md.startswith("# Briefing —")
    assert "## Actualidad" in md
    assert "## Cultura general" in md
    assert "## Fuentes" in md
    for h in briefing.actualidad.historias:
        assert f"### {h.titular_editorial}" in md


def test_render_index_html_lista_briefings_y_filtra_por_categoria(config):
    historial = [
        {"fecha": "2026-08-12", "fecha_larga": "miércoles, 12 de agosto de 2026",
         "categoria": "historia", "titulo_cultura": "Tema de ayer", "url": "b/2026-08-12.html"},
        {"fecha": "2026-08-13", "fecha_larga": "jueves, 13 de agosto de 2026",
         "categoria": "ciencia", "titulo_cultura": "Tema de hoy", "url": "b/2026-08-13.html"},
    ]
    html = render_index_html(historial, config, TEMPLATES_DIR)

    assert "Tema de ayer" in html
    assert "Tema de hoy" in html
    assert '<option value="ciencia">ciencia</option>' in html
    assert '<option value="historia">historia</option>' in html
    assert "2 briefings en el histórico" in html


def test_fuentes_deduplicadas_por_url_en_email(config):
    research, final = construir_briefing_valido(config, n_historias=2)
    # dos historias comparten exactamente la misma URL de fuente
    url_compartida = research["actualidad"]["historias"][0]["fuentes"][0]["url"]
    research["actualidad"]["historias"][1]["fuentes"][0]["url"] = url_compartida
    briefing = Briefing.from_dicts(final, research)

    html = render_email_html(briefing, config, TEMPLATES_DIR, url_historial="#")
    assert html.count(f'href="{url_compartida}"') == 1
