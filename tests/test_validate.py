from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fixtures import construir_briefing_valido

from validate import validar, validar_con_degradacion, contar_palabras


AHORA = datetime(2026, 8, 12, 12, 0, tzinfo=timezone.utc)


def _escribir(tmp_path: Path, research: dict, final: dict, used_topics: list | None = None):
    research_path = tmp_path / "research.json"
    final_path = tmp_path / "final.json"
    used_topics_path = tmp_path / "used_topics.json"
    research_path.write_text(json.dumps(research), encoding="utf-8")
    final_path.write_text(json.dumps(final), encoding="utf-8")
    used_topics_path.write_text(json.dumps(used_topics or []), encoding="utf-8")
    return research_path, final_path, used_topics_path


def test_contar_palabras_es_por_espacios():
    assert contar_palabras("una dos tres") == 3
    assert contar_palabras("") == 0
    assert contar_palabras("  con   espacios   raros  ") == 3


def test_briefing_valido_pasa_sin_errores(tmp_path, config):
    research, final = construir_briefing_valido(config)
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, briefing = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert resultado.ok, resultado.render_reporte()
    assert briefing is not None
    assert len(briefing.actualidad.historias) == 3


def test_falla_si_faltan_fuentes(tmp_path, config):
    research, final = construir_briefing_valido(config)
    research["actualidad"]["historias"][0]["fuentes"] = research["actualidad"]["historias"][0]["fuentes"][:1]
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, _ = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert any("mínimo" in e for e in resultado.errores)


def test_falla_si_palabras_actualidad_fuera_de_rango(tmp_path, config):
    research, final = construir_briefing_valido(config)
    final["actualidad"]["arranque"] = "solo unas pocas palabras"
    for h in final["actualidad"]["historias_texto"]:
        h["texto"] = "texto muy corto"
    final["actualidad"]["radar_texto"] = "corto"
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, _ = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert any("actualidad" in e and "fuera de rango" in e for e in resultado.errores)


def test_falla_si_palabras_cultura_fuera_de_rango(tmp_path, config):
    research, final = construir_briefing_valido(config)
    final["cultura"]["texto"] = "texto de cultura demasiado corto para el mínimo exigido"
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, _ = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert any("cultura" in e and "fuera de rango" in e for e in resultado.errores)


def test_falla_si_fuente_supera_antiguedad_maxima(tmp_path, config):
    research, final = construir_briefing_valido(config)
    research["actualidad"]["historias"][0]["fuentes"][0]["fecha_publicacion"] = "2026-08-01"
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, _ = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert any("supera el límite" in e for e in resultado.errores)


def test_falla_si_tema_cultural_repetido(tmp_path, config):
    research, final = construir_briefing_valido(config)
    used_topics = [{"fecha": "2026-01-01", "categoria": "ciencia", "titulo": final["cultura"]["titulo"]}]
    rp, fp, utp = _escribir(tmp_path, research, final, used_topics=used_topics)

    resultado, _ = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert any("ya publicado" in e for e in resultado.errores)


def test_falla_si_categoria_repetida_dentro_de_ventana(tmp_path, config):
    research, final = construir_briefing_valido(config)
    # misma categoría ('historia') que el briefing de ayer -> viola rotación forzada
    used_topics = [{"fecha": "2026-08-11", "categoria": "historia", "titulo": "otro tema distinto"}]
    rp, fp, utp = _escribir(tmp_path, research, final, used_topics=used_topics)

    resultado, _ = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert any("repetida dentro de la ventana" in e for e in resultado.errores)


def test_esquema_invalido_da_un_solo_error_legible(tmp_path, config):
    rp, fp, utp = _escribir(tmp_path, {"fecha": "2026-08-12"}, {"fecha": "2026-08-12"})

    resultado, briefing = validar(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert briefing is None
    assert len(resultado.errores) == 1
    assert "esquema inválido" in resultado.errores[0]


# --- degradación ---

def test_degradacion_descarta_historia_defectuosa_y_publica_el_resto(tmp_path, config):
    # 6 historias de 180 palabras: el total (1140) cabe en [950, 1150] y,
    # al descartar una defectuosa, el resto (960) también — para que la
    # degradación tenga margen real donde funcionar en vez de tumbar por
    # conteo de palabras, que es un caso ya cubierto por otro test.
    # Rangos vigentes desde 2026-08-12: actualidad [700,850], cultura [1400,1700].
    from fixtures import fuente
    from conftest import texto_de_n_palabras

    n, palabras_por_historia = 7, 110
    historias_research, historias_final = [], []
    for i in range(n):
        hid = f"h{i + 1}"
        fuentes = [fuente(f"https://reuters.com/h{i + 1}", medio="Reuters")]
        if i != 0:  # solo h1 queda con una única fuente (defectuosa)
            fuentes.append(fuente(f"https://apnews.com/h{i + 1}", medio="AP News"))
        historias_research.append({"id": hid, "titular": f"T{i}", "eje": "geopolitica",
                                    "resumen_factual": "...", "fuentes": fuentes})
        historias_final.append({"id": hid, "titular_editorial": f"Titular {i + 1}",
                                 "texto": texto_de_n_palabras(palabras_por_historia, semilla=f"h{i}p")})

    research = {
        "fecha": "2026-08-12", "generado_en": "2026-08-12T05:00:00Z",
        "actualidad": {"historias": historias_research, "descartados": [], "radar": ["a"]},
        "cultura": {"categoria": "historia", "titulo_provisional": "Tema válido"},
    }
    final = {
        "fecha": "2026-08-12",
        "actualidad": {
            "arranque": texto_de_n_palabras(40, semilla="arranque"),
            "historias_texto": historias_final,
            "radar_texto": texto_de_n_palabras(20, semilla="radar"),
            "palabras": 60 + n * palabras_por_historia,
        },
        "cultura": {
            "titulo": "Tema válido", "categoria": "historia",
            "texto": texto_de_n_palabras(1500, semilla="cultura"),
            "dato_sobremesa": "Dato de sobremesa.",
            "tirar_del_hilo_texto": None, "palabras": 1500,
        },
    }
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, briefing = validar_con_degradacion(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert resultado.ok, resultado.render_reporte()
    assert resultado.historias_descartadas == ["h1"]
    assert [h.id for h in briefing.actualidad.historias] == [f"h{i}" for i in range(2, n + 1)]


def test_degradacion_falla_si_quedan_menos_del_minimo_publicable(tmp_path, config):
    research, final = construir_briefing_valido(config, n_historias=3)
    for h in research["actualidad"]["historias"][:2]:
        h["fuentes"] = h["fuentes"][:1]
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, briefing = validar_con_degradacion(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    # config.fallo.minimo_historias = 2; quedaría 1 -> degradación no viable
    assert not resultado.ok
    assert briefing is not None  # se devuelve para poder inspeccionar, pero no está ok


def test_degradacion_no_arregla_fallo_de_cultura(tmp_path, config):
    research, final = construir_briefing_valido(config)
    final["cultura"]["texto"] = "demasiado corto"
    rp, fp, utp = _escribir(tmp_path, research, final)

    resultado, _ = validar_con_degradacion(fp, rp, utp, config, verificar_urls=False, ahora=AHORA)

    assert not resultado.ok
    assert not resultado.historias_descartadas
    assert any("cultura" in e for e in resultado.errores)
