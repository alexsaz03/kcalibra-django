r"""
El check permanente del bug 015 (docs/bugs/015-tailwind-no-ve-las-plantillas.md).

Es a la vez el test que reproduce el bug y el test de regresión que lo vigila para que no
vuelva: recorre TODAS las plantillas del repo (no las que declare `@source` en
`assets/tailwind/input.css` — este check es un oráculo INDEPENDIENTE de esa lista, así una app
nueva sin declarar allí se detecta el mismo día, sin tener que acordarse de tocar este fichero),
extrae las clases usadas en sus atributos `class="…"` y falla nombrando cualquiera que no
exista en `static/css/tailwind.css`.

No puede depender del binario de Tailwind: no está en este repo (~80 MB, se descarga aparte,
ver AGENTS.md §1.6) ni en CI. Por eso compara texto contra texto — las clases que aparecen en
las plantillas contra los selectores que de verdad existen en el CSS ya compilado — en vez de
compilar nada.

Trampas ya pisadas al escribir esto (para quien lo toque después):

- Dentro de `class="…"` hay etiquetas de Django (`{% if %}`, `{{ var }}`) que hay que quitar
  ANTES de partir por espacios, si no cuentan como clases trozos como `endif` o `miembro.id`.
- El atributo `class` puede venir partido en varias líneas (ver `templates/base.html` y
  `progreso/templates/progreso/ver.html`): la extracción usa `re.S`.
- El CSS compilado escapa con una barra invertida los caracteres que Tailwind necesita escapar
  en un selector CSS (`:` de las variantes — `hover:bg-x` sale como `.hover\:bg-x:hover` —, `.`
  de los decimales, `/` de la opacidad, `[` `]` de los valores arbitrarios). Quitar esos backslashes
  del selector reconstruye EXACTAMENTE el texto de la clase tal y como aparece en la plantilla:
  no hace falta ninguna tabla de casos especiales por tipo de variante.
- Los selectores de utilidades "de grupo" (`space-y-*`, `divide-*`) no terminan en `{` sino en
  un combinador (`:where(.space-y-1>:not(:last-child)){…}`): el selector NO se puede exigir
  pegado a una `{`, basta con que la clase aparezca como selector válido en algún punto del CSS.
"""

import glob
import os
import re

from django.conf import settings
from django.test import SimpleTestCase

CSS_COMPILADO = os.path.join(settings.BASE_DIR, "static", "css", "tailwind.css")

# class="…" o class='…', con re.S porque el atributo puede venir partido en varias líneas.
_ATRIBUTO_CLASS_RE = re.compile(r"""class=(["'])(.*?)\1""", re.S)
# Etiquetas de Django dentro del atributo: se quitan antes de partir por espacios.
_ETIQUETA_DJANGO_RE = re.compile(r"\{%.*?%\}|\{\{.*?\}\}", re.S)
# Un selector de clase CSS: empieza tras un separador de selector (inicio de texto, '{', '}',
# ',', '(', ')', un combinador o un espacio) y consume caracteres de nombre de clase, donde un
# carácter puede ser normal (letra/dígito/guion) o "escapado" (\ seguido de cualquier cosa:
# así se cuelan ':' de variantes, '.' de decimales, '/' de opacidad y '[' ']' de valores
# arbitrarios sin necesitar un caso por tipo). No exige que el selector termine en '{': las
# utilidades de grupo (space-y-*, divide-*) terminan en un combinador, no en '{'.
_SELECTOR_CSS_RE = re.compile(r"(?:^|[{},():>+~\s])\.((?:\\.|[A-Za-z0-9_-])+)")
_DESESCAPAR_RE = re.compile(r"\\(.)")


def _directorios_de_plantillas():
    """Todas las carpetas `templates/` del repo: `templates/` en la raíz (compartida) y una
    por cada carpeta de primer nivel que tenga su propia `templates/`. Deliberadamente NO lee
    `assets/tailwind/input.css`: si lo hiciera, una app nueva que se olvide de declararse en
    `@source` desaparecería también de este check, exactamente el fallo que provocó el bug.

    ASIMETRÍA DE COBERTURA (a propósito, pero hay que saberla): `@source "../../**/templates"`
    en `assets/tailwind/input.css` cubre plantillas a CUALQUIER profundidad bajo la raíz del
    repo. Esta función solo mira el PRIMER NIVEL (`<carpeta>/templates`). Una futura carpeta de
    plantillas anidada (p. ej. `apps/x/templates`) se compilaría igual (el glob de Tailwind la
    alcanza) pero este check NO la vigilaría: si a esa carpeta anidada le faltara una clase, el
    CSS compilado la tendría igualmente ausente y nadie se enteraría por aquí. Quien añada
    plantillas anidadas debe saber que el check no llega ahí."""
    base = settings.BASE_DIR
    directorios = []
    raiz = os.path.join(base, "templates")
    if os.path.isdir(raiz):
        directorios.append(raiz)
    for nombre in sorted(os.listdir(base)):
        candidato = os.path.join(base, nombre, "templates")
        if os.path.isdir(candidato):
            directorios.append(candidato)
    return directorios


def _plantillas_html():
    ficheros = []
    for directorio in _directorios_de_plantillas():
        ficheros.extend(glob.glob(os.path.join(directorio, "**", "*.html"), recursive=True))
    return sorted(set(ficheros))


def _clases_usadas_en(ruta_plantilla):
    with open(ruta_plantilla, encoding="utf-8") as f:
        contenido = f.read()
    clases = set()
    for atributo in _ATRIBUTO_CLASS_RE.finditer(contenido):
        valor = _ETIQUETA_DJANGO_RE.sub(" ", atributo.group(2))
        for token in valor.split():
            token = token.strip()
            if token:
                clases.add(token)
    return clases


def _clases_en_css_compilado():
    with open(CSS_COMPILADO, encoding="utf-8") as f:
        css = f.read()
    return {_DESESCAPAR_RE.sub(r"\1", m.group(1)) for m in _SELECTOR_CSS_RE.finditer(css)}


class TailwindCubreTodasLasPlantillasTests(SimpleTestCase):
    """El check del bug 015: ninguna plantilla puede usar una clase de Tailwind que el CSS
    compilado no tenga. No toca la base de datos (SimpleTestCase): es una comparación de
    texto contra ficheros del repo."""

    databases = set()

    def test_no_desaparece_ninguna_carpeta_de_plantillas_conocida(self):
        """Comprobación de la propia comprobación: si la búsqueda de carpetas se rompiera (por
        ejemplo, apuntando a un sitio vacío) el test principal pasaría en falso -- "sin
        plantillas que mirar" es indistinguible de "todo correcto". NO fija un suelo cerrado
        (un `assertEqual` contra las diez de hoy pondría la suite en rojo el día que llegue la
        app nº 11, con un mensaje que diría lo contrario de lo ocurrido): comprueba que las
        diez carpetas conocidas siguen encontrándose SIEMPRE, sin prohibir que aparezcan más.
        Lo único que de verdad protege esta comprobación es que ninguna DESAPAREZCA."""
        directorios = _directorios_de_plantillas()
        rutas_relativas = {os.path.relpath(d, settings.BASE_DIR) for d in directorios}
        esperadas = {
            "templates",
            os.path.join("cierres", "templates"),
            os.path.join("cuentas", "templates"),
            os.path.join("despensa", "templates"),
            os.path.join("entrenos", "templates"),
            os.path.join("hogares", "templates"),
            os.path.join("paginas", "templates"),
            os.path.join("perfiles", "templates"),
            os.path.join("planes", "templates"),
            os.path.join("progreso", "templates"),
        }
        faltantes = esperadas - rutas_relativas
        self.assertLessEqual(
            esperadas,
            rutas_relativas,
            "la búsqueda de carpetas de plantillas ha dejado de encontrar carpetas que sí "
            f"debería (desaparecidas: {sorted(faltantes)}) -- si esto falla, el test de abajo "
            "podría estar pasando en falso por no mirar todo lo que debería",
        )

    def test_todas_las_clases_usadas_existen_en_el_css_compilado(self):
        compiladas = _clases_en_css_compilado()
        faltan = {}
        for ruta in _plantillas_html():
            ausentes = sorted(c for c in _clases_usadas_en(ruta) if c not in compiladas)
            if ausentes:
                faltan[os.path.relpath(ruta, settings.BASE_DIR)] = ausentes

        if faltan:
            detalle = "\n".join(
                f"  - {ruta}: {', '.join(clases)}" for ruta, clases in sorted(faltan.items())
            )
            self.fail(
                "Hay clases de Tailwind usadas en plantillas que NO existen en "
                "static/css/tailwind.css (falta recompilar el CSS, o falta declarar la "
                f"carpeta en @source de assets/tailwind/input.css):\n{detalle}"
            )
