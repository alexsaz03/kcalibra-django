"""Alcanzabilidad: comprobar que algo de la pantalla SE PUEDE USAR, no solo que está escrito.

Esto no es un ayudante más. Es lo que quedó de **siete vueltas de revisión sobre seis líneas de
plantilla** en la unidad 056, donde aparecieron DIEZ agujeros seguidos y **ninguno estaba en el
código**: todos estaban en el test, y todos eran la misma frase con distinto disfraz — *se
comprobaba algo más pequeño que lo que se prometía*.

Vive aquí, y no copiado en cada fichero de tests, por una razón medida: la unidad 053 copió este
patrón a mano y se dejó cuatro de sus ocho piezas, lo que abrió **siete agujeros nuevos** que su
revisión demostró uno a uno. Un patrón que hay que copiar bien ocho veces se copia mal a la
primera. Si le añades una pieza, la añades AQUÍ y la ganan todos.

Las ocho piezas, con la vuelta que las trajo:

1. La cadena de ancestros se recorre **parseando el HTML**, no buscando hacia atrás en el texto:
   `rindex("<div")` encuentra el propio elemento y jamás sube a quien lo envuelve (3ª vuelta).
2. Se guardan **todas** las coincidencias, no la primera: un señuelo sin tapar contestaba por el
   elemento de verdad (4ª vuelta).
3. El emparejado **tolera lo que el navegador tolera y nada más** (espacios, comilla simple o
   doble) y **falla CERRADO**: cualquier otra forma da ROJO, no verde (5ª y 6ª vueltas). Un falso
   rojo se ve y se arregla en dos minutos; un falso verde no se ve nunca.
4. Ningún ancestro puede ser `<template>`: su contenido **no entra al DOM vivo** por sí solo, así
   que el elemento no existe en la página aunque esté escrito (7ª vuelta, el más grave).
5. Ni el elemento ni **ninguno de sus ancestros** puede estar tapado por clase o por estilo
   (2ª y 3ª vueltas), `pointer-events:none` incluido — que no esconde nada y lo rompe todo.
6. El elemento no puede estar fuera del teclado ni del árbol de accesibilidad
   (`tabindex="-1"`, `aria-hidden="true"`): "se puede usar" no es "se puede ver" (7ª vuelta).
7. Un control y lo que abre tienen que colgar del **mismo** `x-data`, y ese `x-data` tiene que
   declarar la variable: renombrarla una letra los deja perfectos por separado y muertos juntos
   (7ª vuelta).
8. Y se comprueba sobre **cada elemento que hay que poder usar**, no solo sobre el contenedor:
   un menú alcanzable con los destinos tapados sigue siendo un menú inútil.

LO QUE ESTO NO PUEDE HACER, y está escrito para que nadie lo olvide: mira **HTML renderizado**. No
ejecuta JavaScript. Borrando el `<script>` que carga Alpine, todo esto sigue verde y en el
navegador no se abre nada. Cerrar esa última grieta pide un navegador de verdad; mientras no lo
haya, esa promesa no está cubierta y se dice, no se disimula.
"""

import re
from html.parser import HTMLParser


# alterna `display`). La lista es NEGRA y por tanto nunca completa — pero la grieta que la hacía
# inútil no era la lista, era DÓNDE se miraba: hasta la 3ª revisión solo se miraba la etiqueta del
# propio menú, así que envolverlo en un `<div class="hidden">` lo escondía con el test en verde.
# Ahora se recorre la cadena de ANCESTROS de verdad, parseando el HTML.
TAPADERAS_DE_CLASE = ("hidden", "invisible", "opacity-0", "pointer-events-none", "sr-only",
                       "w-0", "h-0", "scale-0")
TAPADERAS_DE_ESTILO = ("display:none", "visibility:hidden", "opacity:0",
                        "pointer-events:none")  # heredable: deja el menú visible e inclicable (6ª rev.)
SIN_CIERRE = {"br", "img", "input", "meta", "link", "hr", "source", "path", "circle", "area"}

# El menú se identifica por su `x-show`, y se identifica FALLANDO EN ROJO ante cualquier forma que
# no sea la canónica. La 5ª revisión enseñó por qué: `x-show=" ajustesAbierto "` (un espacio dentro
# de las comillas) es para Alpine EXACTAMENTE la misma expresión —la evalúa como JavaScript, y el
# espacio no significa nada—, pero para una comparación de texto es otra cosa. Con eso, un señuelo
# escrito de forma exacta se llevaba la única coincidencia y el menú de verdad, tapado, no llegaba
# ni a inspeccionarse.
#
# Se tolera lo que Alpine considera igual (espacios alrededor, comilla simple o doble) y NADA MÁS.
# Una expresión equivalente pero escrita de otro modo (`!!ajustesAbierto`, por ejemplo) no cuenta
# como el menú: el test se pone ROJO diciendo que no lo encuentra. Falla cerrado, que es lo único
# aceptable en una red — un falso rojo se ve y se arregla; un falso verde no se ve nunca.
def re_de_atributo(atributo, valor):
    """Expresión que reconoce `atributo="valor"` tolerando lo que el navegador tolera.

    Espacios dentro de las comillas y comilla simple o doble; NADA más. Cualquier otra forma de
    escribirlo no cuenta como ese elemento y el test se pone ROJO diciendo que no lo encuentra
    (5ª vuelta de la 056: `x-show=" ajustesAbierto "` es para Alpine la MISMA expresión, porque la
    evalúa como JavaScript, pero para una comparación de texto era otra cosa).
    """
    return re.compile(r"""%s\s*=\s*(?P<c>["'])\s*%s\s*(?P=c)""" % (re.escape(atributo), re.escape(valor)))


class CadenaDeAncestros(HTMLParser):
    """Para cada elemento que cumple `coincide`, su cadena de ancestros MÁS él mismo.

    Hace falta un parser de verdad y no buscar hacia atrás en el texto: `rindex("<div")` encuentra
    la etiqueta más cercana, que es el propio elemento, y jamás sube a quien lo envuelve (3ª
    revisión). Y se guardan TODAS las coincidencias, no la primera: quedarse con la primera deja
    que un señuelo sin tapar conteste por el elemento de verdad (4ª revisión).
    """

    def __init__(self, coincide):
        super().__init__(convert_charrefs=True)
        self.coincide = coincide
        self.pila = []
        self.cadenas = []

    def handle_starttag(self, etiqueta, atributos):
        attrs = dict(atributos)
        if self.coincide(etiqueta, attrs):
            self.cadenas.append(list(self.pila) + [(etiqueta, attrs)])
        if etiqueta not in SIN_CIERRE:
            self.pila.append((etiqueta, attrs))

    def handle_endtag(self, etiqueta):
        for k in range(len(self.pila) - 1, -1, -1):
            if self.pila[k][0] == etiqueta:
                del self.pila[k:]
                return


def cadena_unica(caso, contenido, coincide, nombre):
    """La cadena del único elemento que cumple `coincide`. Falla si no hay o si hay más de uno."""
    lector = CadenaDeAncestros(coincide)
    lector.feed(contenido)
    if not lector.cadenas:
        raise AssertionError(f"no hay ningún {nombre} en la página: el test no prueba nada")
    caso.assertEqual(
        len(lector.cadenas), 1,
        f"hay {len(lector.cadenas)} elementos que pasan por «{nombre}»: uno puede ser un señuelo "
        f"sin tapar que conteste por el de verdad.",
    )
    return lector.cadenas[0]


def _como_entero(valor):
    """El entero que vería el navegador, o `None` si ahí no hay un entero.

    Recorta espacios y acepta ceros a la izquierda o un `+` delante, como las "rules for parsing
    integers" de WHATWG. Lo que no encaja devuelve `None` — y `None` nunca es igual a `-1`, así que
    un atributo raro NO se da por bueno como "está fuera del teclado": se ignora, que es lo mismo
    que hace el navegador con un `tabindex` que no sabe leer.
    """
    if valor is None:
        return None
    try:
        return int(valor.strip())
    except (ValueError, AttributeError):
        return None


def nada_lo_tapa(caso, contenido, coincide, nombre):
    """Falla si el elemento, o CUALQUIERA de sus ancestros, lo deja inalcanzable.

    Cubre tres familias, y las tres las trajo una revisión distinta:
      · escondido por clase o por estilo (2ª y 3ª: `hidden`, `invisible`, `opacity-0`…),
      · escondido por un ANCESTRO y no por él mismo (3ª),
      · y dentro de un `<template>`, que en HTML estándar NUNCA entra al DOM vivo por sí solo —
        `<template x-if="false">` alrededor del enlace lo borra de la página de verdad y el test
        no se enteraba (6ª revisión, el más grave de todos).
    """
    cadena = cadena_unica(caso, contenido, coincide, nombre)
    for etiqueta, attrs in cadena:
        caso.assertNotEqual(
            etiqueta, "template",
            f"«{nombre}» vive dentro de un <template>: su contenido no entra al DOM por sí solo, "
            f"así que en un navegador de verdad no existe",
        )
        clases = (attrs.get("class") or "").split()
        estilo = (attrs.get("style") or "").replace(" ", "")
        quien = "el propio elemento" if (etiqueta, attrs) == cadena[-1] else f"un ancestro <{etiqueta}>"
        for tapadera in TAPADERAS_DE_CLASE:
            caso.assertNotIn(tapadera, clases, f"{quien} tapa «{nombre}» con la clase '{tapadera}'")
        for tapadera in TAPADERAS_DE_ESTILO:
            caso.assertNotIn(tapadera, estilo, f"{quien} tapa «{nombre}» con el estilo '{tapadera}'")

    propio = cadena[-1][1]
    # Y no basta con que se vea: quien navega con teclado o con lector de pantalla también tiene
    # que llegar. R4 dice "se puede usar", no "se puede ver" (6ª revisión, agujero 4).
    # `==` de texto NO sirve aquí, y la 7ª vuelta de la 056 lo midió: `tabindex="-1 "` (un espacio
    # dentro de las comillas) y `tabindex="-01"` dejaban el test verde y el enlace fuera del
    # teclado. El navegador no compara cadenas: para `tabindex` aplica las "rules for parsing
    # integers" de WHATWG, que recortan espacios y aceptan ceros a la izquierda. Es la lección de
    # la pieza 3 —tolerar lo que el navegador tolera— que no había llegado a esta pieza 6.
    caso.assertNotEqual(
        _como_entero(propio.get("tabindex")), -1,
        f"«{nombre}» está fuera del orden de tabulación: con teclado no se llega",
    )
    caso.assertNotEqual(
        (propio.get("aria-hidden") or "").strip().lower(), "true",
        f"«{nombre}» está fuera del árbol de accesibilidad: un lector de pantalla no lo anuncia",
    )
    return cadena


def el_estado_es_compartido(caso, contenido, es_el_control, es_lo_que_abre, variable,
                            nombre_control="el control", nombre_abierto="lo que abre"):
    """El botón y el menú tienen que colgar del MISMO `x-data` que declara `ajustesAbierto`.

    Si el botón alterna una variable y el menú mira otra —un `x-data` renombrado, un `x-data`
    nuevo intercalado—, los dos siguen escritos igual de bien por separado y el menú no abre
    jamás. Lo trajo la 6ª revisión.
    """
    def _duenos(cadena):
        return [(t, a) for t, a in cadena if "x-data" in a]

    rueda = cadena_unica(caso, contenido, es_el_control, nombre_control)
    menu = cadena_unica(caso, contenido, es_lo_que_abre, nombre_abierto)
    dueno_rueda, dueno_menu = _duenos(rueda), _duenos(menu)
    caso.assertTrue(dueno_rueda, f"{nombre_control} no cuelga de ningún x-data")
    caso.assertEqual(
        dueno_rueda, dueno_menu,
        f"{nombre_control} y {nombre_abierto} no cuelgan del mismo x-data: cada uno alternaría "
        f"su propia variable y no se abriría nunca",
    )
    caso.assertIn(
        variable, dueno_rueda[-1][1].get("x-data", ""),
        f"el x-data del que cuelgan no declara `{variable}`: la variable no existe y `x-show` "
        f"no se enciende jamás",
    )


