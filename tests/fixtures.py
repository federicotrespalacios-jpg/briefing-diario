"""Constructores de datos de prueba — briefings sintéticos válidos (y
variantes rotas a propósito) para test_validate.py y test_render.py."""

from conftest import texto_de_n_palabras


def fuente(
    url: str,
    medio: str = "Reuters",
    fecha_publicacion: str = "2026-08-12",
    tipo: str = "primaria",
) -> dict:
    return {
        "medio": medio,
        "url": url,
        "fecha_publicacion": fecha_publicacion,
        "tipo": tipo,
        "titular_fuente": f"Titular original de {medio}",
    }


def _mitad(rango: dict) -> int:
    return (rango["min"] + rango["max"]) // 2


def construir_briefing_valido(config: dict, n_historias: int = 3) -> tuple[dict, dict]:
    """Devuelve (research_dict, final_dict) coherentes entre sí, dentro de
    todos los rangos de config.yaml, sin tocar la red al validar."""
    fecha = "2026-08-12"

    objetivo_actualidad = _mitad(config["longitud"]["actualidad"])
    arranque_palabras = 40
    radar_palabras = 20
    restante = objetivo_actualidad - arranque_palabras - radar_palabras
    por_historia = restante // n_historias

    historias_research = []
    historias_final = []
    for i in range(n_historias):
        hid = f"h{i + 1}"
        historias_research.append({
            "id": hid,
            "titular": f"Titular de investigación {i + 1}",
            "eje": "geopolitica",
            "resumen_factual": f"Resumen factual de la historia {i + 1}.",
            "fuentes": [
                fuente(f"https://reuters.com/historia-{i + 1}", medio="Reuters"),
                fuente(f"https://apnews.com/historia-{i + 1}", medio="AP News"),
            ],
        })
        historias_final.append({
            "id": hid,
            "titular_editorial": f"Titular editorial {i + 1}",
            "texto": texto_de_n_palabras(por_historia, semilla=f"h{i}palabra"),
        })

    objetivo_cultura = _mitad(config["longitud"]["cultura"])
    tirar_del_hilo_palabras = 30
    cultura_palabras = objetivo_cultura - tirar_del_hilo_palabras

    research = {
        "fecha": fecha,
        "generado_en": "2026-08-12T05:00:00Z",
        "actualidad": {"historias": historias_research, "descartados": [], "radar": ["a", "b"]},
        "cultura": {
            "categoria": "historia",
            "titulo_provisional": "Por qué los romanos lavaban la ropa con orina",
            "angulo": "detalle raro",
        },
    }

    final = {
        "fecha": fecha,
        "actualidad": {
            "arranque": texto_de_n_palabras(arranque_palabras, semilla="arranque"),
            "historias_texto": historias_final,
            "radar_texto": texto_de_n_palabras(radar_palabras, semilla="radar"),
            "palabras": objetivo_actualidad,
        },
        "cultura": {
            "titulo": "Por qué los romanos lavaban la ropa con orina",
            "categoria": "historia",
            "texto": texto_de_n_palabras(cultura_palabras, semilla="cultura"),
            "dato_sobremesa": "Los romanos pagaban impuestos por recoger orina pública.",
            "tirar_del_hilo_texto": texto_de_n_palabras(tirar_del_hilo_palabras, semilla="hilo"),
            "palabras": objetivo_cultura,
        },
        "verificacion": {
            "afirmaciones_revisadas": 5,
            "verificadas": 5,
            "dudosas": 0,
            "no_verificables_eliminadas": 0,
            "detalle": [],
            "alucinaciones_plausibles_detectadas": [],
            "historias_eliminadas": [],
        },
    }

    return research, final
