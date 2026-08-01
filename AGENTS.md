# AGENTS.md — KCalibra (código Django)

Este es el repositorio de código de KCalibra. Aquí solo vive la aplicación Django: el
pensamiento del proyecto (requisitos, decisiones, unidades de trabajo) vive en el meta-repo
que lo orquesta, no aquí.

Este fichero es el que cualquier agente (o cualquier persona) necesita leer para levantar el
proyecto **desde cero**, sin redescubrir nada. Todos los comandos están probados uno a uno.

## 0. Antes de nada: dos trampas de este portátil concreto

- **`python3` a secas NO sirve.** En este portátil es el intérprete de Anaconda (más nuevo de
  lo que este proyecto usa, y con `CONDA_DEFAULT_ENV=base` activo). El entorno virtual se crea
  explícitamente con el Python 3.12 de Homebrew (ver paso 1). Si en algún comando de aquí
  abajo ves `python` a secas, es porque el entorno virtual ya está activado y ESE `python` sí
  es el correcto (el del `.venv`).
- **`pg_config` tampoco sirve** (también lo tapa Anaconda). No hace falta: el conector de
  PostgreSQL se instala como rueda binaria (`psycopg[binary]`), que no compila nada y no lo
  necesita. Si alguna vez ves un error de compilación críptico al instalar el conector de
  Postgres, la causa casi segura es que algo intentó usar ese `pg_config` equivocado.

## 1. Levantar el entorno (una sola vez)

### 1.1. Requisitos que este repo NO instala por ti

- **Python 3.12**, en concreto el de Homebrew:
  `/opt/homebrew/opt/python@3.12/bin/python3.12` (instálalo con
  `brew install python@3.12` si no lo tienes).
- **PostgreSQL 17**, instalado y arrancado como servicio (Homebrew: `brew install
  postgresql@17 && brew services start postgresql@17`). Es *keg-only*: sus binarios viven en
  `/opt/homebrew/opt/postgresql@17/bin`, fuera del `PATH` por defecto.

Si algo de esto falta, instálalo tú (fuera de este repositorio) antes de seguir — este
`AGENTS.md` no lo hace por ti.

### 1.2. Entorno virtual de Python

```bash
/opt/homebrew/opt/python@3.12/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Comprobación: `python --version` debe decir `Python 3.12.x` (NO 3.13).

### 1.3. La base de datos

El superusuario de PostgreSQL en este portátil es tu propio usuario del sistema (autenticación
`trust` en local: no pide contraseña). Crea la base del proyecto una sola vez:

```bash
/opt/homebrew/opt/postgresql@17/bin/createdb kcalibra_dev
```

Comprobación: `/opt/homebrew/opt/postgresql@17/bin/psql -l | grep kcalibra_dev` debe listarla.

### 1.4. Variables de entorno

```bash
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Pega el resultado del segundo comando como valor de `DJANGO_SECRET_KEY` dentro de `.env`. Los
valores de `DB_*` que trae `.env.example` ya coinciden con la base creada en el paso 1.3; no
hace falta tocarlos en local. El fichero `.env` **nunca** se sube a git.

### 1.5. Migraciones

```bash
python manage.py migrate
```

### 1.6. Los estilos (Tailwind, sin Node)

El binario autónomo de Tailwind **no** entra en git (pesa ~80 MB y es específico de cada
sistema operativo). Descárgalo una vez, para macOS con chip Apple Silicon (arm64):

```bash
curl -sSL -o tailwindcss \
  "https://github.com/tailwindlabs/tailwindcss/releases/download/v4.3.3/tailwindcss-macos-arm64"
chmod +x tailwindcss
./tailwindcss --help   # comprobación: debe imprimir "tailwindcss v4.3.3"
```

(Si tu Mac es Intel, cambia `macos-arm64` por `macos-x64` en la URL.)

Para generar el CSS a partir de las plantillas:

```bash
./tailwindcss -i ./assets/tailwind/input.css -o ./static/css/tailwind.css --minify
```

Repite este comando cada vez que uses una clase de Tailwind nueva en una plantilla que antes
no usabas (o añade `--watch` al final mientras desarrollas, para que se regenere solo).

### 1.7. HTMX y Alpine

Ya están vendidos dentro del repo (`static/js/htmx.min.js` y `static/js/alpine.min.js`),
versión fijada, así que no hace falta ningún paso más. Si algún día hay que actualizarlos, así
es como se obtuvieron (versiones **2.0.10** y **3.15.12** respectivamente):

```bash
curl -sSL -o static/js/htmx.min.js "https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js"
curl -sSL -o static/js/alpine.min.js "https://unpkg.com/alpinejs@3.15.12/dist/cdn.min.js"
```

Al subir de versión: quedarse en htmx **2.x** (la 4 está en beta a fecha de esta unidad).

## 2. Los tests (tienen que salir en verde)

```bash
python manage.py test
```

## 3. Arrancar la app para probarla a mano

```bash
python manage.py runserver
```

Abre `http://127.0.0.1:8000/` en el navegador. Si el puerto 8000 estuviera ocupado por otra
cosa en tu máquina, arranca en otro con `python manage.py runserver 8001` (o el que prefieras)
y ajusta la URL.

Deberías ver la portada de KCalibra con los estilos de Tailwind aplicados, y un botón
"Comprobar hora del servidor" que, al pulsarlo, cambia el texto de debajo **sin recargar la
página** (eso es HTMX pidiendo un trozo de plantilla al servidor y sustituyéndolo).

## Cómo está organizado el código

| dónde | qué hay | por qué |
|---|---|---|
| `kcalibra/` | configuración del proyecto (`settings.py`, `urls.py`) | lo que genera `django-admin startproject`, sin nada exótico |
| `paginas/` | la app con la portada y sus vistas | punto de entrada de lo que ve el usuario en el navegador |
| `templates/` | plantillas compartidas entre apps (`base.html`) | la base con Tailwind, HTMX y Alpine ya cargados; cada app extiende esto |
| `paginas/templates/paginas/` | plantillas propias de la app `paginas` | convención estándar de Django: cada app guarda las suyas bajo su propio nombre, para que no choquen nombres entre apps |
| `servicios/` | la capa de servicios (cálculos, lógica de negocio) | **vacía a propósito** en esta unidad; la lógica llega en la unidad 004. Las vistas deben LLAMAR a esta capa, nunca calcular ellas mismas |
| `assets/tailwind/input.css` | el fichero de entrada de Tailwind | de aquí sale `static/css/tailwind.css` al compilar (paso 1.6) |
| `static/` | CSS generado + HTMX y Alpine vendidos | todo lo que Tailwind necesita servir sin depender de Node ni de una CDN |

## Variables de entorno obligatorias

Si falta cualquiera de estas, la app **se niega a arrancar** y dice cuál falta (no arranca con
valores por defecto inseguros): `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
`DB_HOST`, `DB_PORT`. Ver `.env.example` para el detalle de cada una.
