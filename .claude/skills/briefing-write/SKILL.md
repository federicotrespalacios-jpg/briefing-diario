---
name: briefing-write
description: Fase 4 del briefing diario. Redacta las dos secciones (actualidad y cultura general) a partir de work/research.json, en el tono definido — coloquial, como un amigo muy leído contándolo en un bar. Escribe work/draft.json.
allowed-tools: Read, Write, Glob
---

# Redacción del briefing diario

Lee `work/research.json` — ahí está toda la investigación, ya verificada en su
fase de fuentes. Tu trabajo es **contarlo bien**. No investigues nada nuevo: si
falta un dato, trabaja con lo que hay en el JSON.

Lee también `config.yaml` para los rangos de longitud exactos.

## El lector

Una persona en España, culta, con curiosidad amplia y poco tiempo. Lee esto en
el móvil, normalmente en el desayuno. Quiere salir sabiendo algo que no sabía y
poder contarlo esa misma noche. Si el texto suena a deberes, has fracasado
aunque los datos sean correctos.

## Tono — reglas duras

- Coloquial, como un amigo muy leído que te lo cuenta en un bar. Cero lenguaje
  corporativo o académico.
- **Prohibido**: "en el vertiginoso mundo de", "cabe destacar", "en resumen",
  "sin duda", "es importante señalar", "profundicemos", y cualquier muletilla
  de ese registro. Si una frase podría estar en un informe de consultoría,
  reescríbela.
- Nada de emojis decorativos. Nada de listas donde un párrafo cuenta mejor la
  historia — usa listas solo cuando de verdad hay una enumeración (el radar,
  las recomendaciones de "tirar del hilo").
- Frases cortas mezcladas con largas. Que tenga ritmo, no cadencia uniforme.
- Se permite el humor, la ironía suave, la pregunta directa al lector.
- Si aparece un tecnicismo inevitable (spread, inflación subyacente, entropía),
  explícalo en la misma frase con una analogía cotidiana. No en una nota aparte.
- Nunca opiniones políticas propias. En temas polarizados: los hechos, quién
  dice qué, y por qué les importa a las partes. Tú no tomas partido.
- Español de España, neutro y natural.

## Sección 1 — Actualidad (700-850 palabras)

Regla general de esta sección, no negociable: **directo a los datos**. Nada
de arrancar una historia con contexto general o ambientación — la primera
frase de cada historia lleva el hecho concreto (qué pasó, cifra, quién,
cuándo). El contexto que haga falta va después, en una frase, no en un
párrafo.

**Arranque (2-3 frases, no más).** La promesa "si solo lees esto hoy, esto es
lo que pasa en el mundo". Debe funcionar sola, como si el lector no leyera
nada más.

**Cada historia, en 3-4 frases y un único párrafo** (usa las de
`research.json`, en el orden de importancia que tú decidas, no
necesariamente el del JSON):

- Frase 1: el hecho, con su cifra o dato concreto. Sin rodeos.
- Frase 2: el contexto mínimo imprescindible, si hace falta.
- Frase 3: por qué importa — a quién afecta y cómo, en una frase, no en un
  párrafo.
- Frase 4 (opcional): qué puede pasar ahora.
- Si `es_continuacion` es true: la frase de contexto se sustituye por "esto
  viene de..." + solo qué cambió. No repitas el contexto que ya se contó en
  un briefing anterior.

Si una historia te está saliendo en dos párrafos, está mal — recórtala.
Elige el dato más fuerte de `research.json` y descarta el resto; no intentes
meter todos los datos que investigaste.

No trates las historias como una lista de viñetas independientes si hay una
conexión real entre ellas — dilo en una frase, no le dediques un párrafo.

**Cierre — "en el radar".** 1-2 líneas cortas sobre qué puede mover la aguja
en los próximos días. Usa las entradas de `radar` en `research.json`, pero
compactadas — nombra la cosa, no la expliques otra vez.

## Sección 2 — Cultura general (1400-1700 palabras)

**Aritmética que tienes que cuadrar de verdad**: 1400-1700 palabras en
gancho + desarrollo + cierre significa, con la estructura de abajo,
párrafos de **200-280 palabras cada uno** (4-6 frases con desarrollo real,
no 2-3 frases sueltas). Un párrafo de 100 palabras es la mitad de corto de
lo que hace falta — si te quedas ahí, el texto entero se va a quedar corto
sin que lo notes hasta el final. Piensa en cada párrafo como un mini-bloque
con espacio para plantear algo, desarrollarlo con un dato o una escena, y
cerrarlo — no una frase-titular seguida de la siguiente.

**Gancho (1 párrafo, ~200 palabras).** Una escena, una pregunta imposible, o
un dato que descoloque. **Nunca una definición.** Nunca "hoy vamos a hablar
de...". Usa el `angulo` de `research.json` como punto de entrada, y dale
espacio real a la escena — no la resumas en una frase y pases a lo
siguiente.

**Desarrollo narrativo, en 4-5 párrafos de ~220-280 palabras cada uno.**
Cuenta una historia, no expliques un tema — pero cada párrafo tiene que
ganarse el sitio: si un párrafo es color o textura sin aportar un hecho
nuevo o mover la historia, fuera. Si hay personajes (`personajes` en el
JSON), dales voz y tensión con desarrollo real, no en una frase de
biografía. Sigue el `hilo_narrativo` como esqueleto, pero cada beat
necesita su párrafo completo, no una mención de paso.

Integra los `datos_clave` con naturalidad en la narración — no los sueltes
como una ficha técnica y no te pares a comentar cada uno. Cada cifra o
afirmación fuerte que uses debe venir de `datos_clave` o `personajes` en el
JSON; no inventes ni redondees datos que no estén ahí.

**Cierre — "por qué esto te importa hoy" + dato de sobremesa, en un único
párrafo final de ~200 palabras.** La conexión con el presente (usa
`por_que_importa_hoy`) seguida directamente de la frase que el lector
podría soltar literalmente en una cena esa misma noche (parte de
`dato_sobremesa_propuesto`, pulida). No los separes en dos párrafos — es un
cierre, no dos, pero dale desarrollo real antes de la frase final, no la
sueltes en frío.

**Si quieres tirar del hilo** (opcional, inclúyelo si `research.json` trae
recomendaciones): 1-2 líneas con las recomendaciones de `tirar_del_hilo`,
sin desarrollarlas — esto va aparte del recuento de arriba.

Al terminar, si el total te sale por debajo de 1400, casi siempre es porque
uno o más párrafos se quedaron en 100-150 palabras en vez de 220-280 —
vuelve a esos párrafos concretos y dales el desarrollo que les falta, no
añadas un párrafo nuevo de relleno.

Si el borrador te está saliendo por encima de 1700 palabras, el problema casi
siempre es el mismo: demasiados párrafos de "textura" o de contexto
histórico que no cambian lo que el lector entiende al final. Corta esos
antes de tocar el gancho o el cierre.

## Longitud — orienta por sensación, no cuentes palabra por palabra

Los rangos de `config.yaml` son estrictos, pero **quien los hace cumplir es
un validador de código que corre después de ti** (Fase 6), no tú. No tienes
Bash, así que no intentes contar palabras con un script — ni tampoco a mano,
frase por frase, que es lento y no cambia nada si el validador va a
recalcularlo de todas formas. Guíate por sensación de longitud (un párrafo
de 4-5 frases ronda 80-120 palabras) y por la propia disciplina de "3-4
frases por historia" / "3-4 párrafos de desarrollo" de arriba — si sigues
esas reglas de estructura, el conteo cae solo dentro de rango casi siempre.

- Si notas que te estás alargando (muchos párrafos, muchas frases por
  historia), recorta — nunca entregues largo a propósito.
- Si notas que te has quedado muy escueto, añade sustancia real (un dato
  más, un párrafo más de desarrollo), nunca relleno de transición.
- Si el validador rechaza tu borrador por longitud, la fase de verificación
  o un reintento posterior lo ajustará — no es un fallo grave, es esperado
  de vez en cuando.

Rellena igualmente el campo `palabras` de la salida con tu mejor estimación
(útil para depurar), pero no le dediques turnos a precisarlo.

## Sin archivos sueltos

Escribe **directamente** `work/draft.json` en un solo `Write`, sin pasos
intermedios. No crees `work/_borrador.txt`, `work/_h1.txt` ni ningún otro
archivo de trabajo — cuestan turnos y presupuesto sin aportar nada que no
puedas resolver redactando cada campo mentalmente antes de escribir el JSON
completo de una vez.

## Salida

Escribe **exclusivamente** `work/draft.json`:

```json
{
  "fecha": "AAAA-MM-DD",
  "actualidad": {
    "arranque": "...",
    "historias_texto": [
      {
        "id": "h1",
        "titular_editorial": "Titular propio, no el de la fuente",
        "texto": "El cuerpo completo de esta historia, en prosa."
      }
    ],
    "radar_texto": "El párrafo o lista corta de cierre.",
    "palabras": 0
  },
  "cultura": {
    "titulo": "Título final de la pieza",
    "categoria": "historia",
    "texto": "El texto completo de la sección cultural, de gancho a cierre, en un único bloque de prosa con saltos de párrafo naturales (\\n\\n).",
    "dato_sobremesa": "La frase final pulida.",
    "tirar_del_hilo_texto": "El párrafo corto de recomendaciones, o null si no aplica.",
    "palabras": 0
  }
}
```

`palabras` es tu recuento real de cada sección completa (arranque + historias
+ radar para actualidad; todo el bloque para cultura). El validador
programático que corre después usará su propio contador y fallará el build si
te desvías del rango — así que sé exacto, no optimista.

Cuando termines, di en una línea el recuento de palabras de cada sección.
Nada más.
