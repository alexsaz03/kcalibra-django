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
valores de `DB_*` que trae `.env.example` ya coinciden con la base creada en el paso 1.3 **en
este portátil**: `DB_USER` es literalmente el usuario del sistema que ejecutó `createdb` (así
funciona la autenticación `trust` local), no un valor fijo del proyecto. En otra máquina,
comprueba con `whoami` y ajusta `DB_USER` si hace falta. El fichero `.env` **nunca** se sube a
git.

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

Deberías ver la portada de KCalibra con los estilos de Tailwind aplicados y, si no tienes
sesión, los enlaces de "Entrar" y "Crear cuenta" (unidad 003).

## 4. Crear una cuenta de prueba y recorrer el camino de las dos personas (unidad 003)

Con el registro abierto en tu `.env` (`DJANGO_REGISTRO_ABIERTO=True` — si no lo pones, la app
rechaza cualquier alta a propósito, R12) y `python manage.py runserver` corriendo:

### 4.1. Una sola persona

1. Entra en `http://127.0.0.1:8000/cuentas/signup/` y crea una cuenta con tu correo y una
   contraseña (deja el campo "Código de hogar" en blanco). Desde la unidad 004 el formulario
   pide TAMBIÉN tus datos físicos, tu actividad, tu objetivo y tus manías (ver el punto 4.4
   más abajo si quieres usar unos valores concretos para comprobar las calorías a mano).
2. La app te lleva a `/cuentas/esperando-verificacion/`, con el aviso de que te ha mandado un
   correo. **En este portátil el correo no sale a ningún sitio: se imprime en la terminal
   donde corre `manage.py runserver`.** Búscalo ahí: es un bloque de texto con
   `Subject: [KCalibra] Confirma tu correo en KCalibra` y, dentro, una línea
   `http://127.0.0.1:8000/cuentas/confirm-email/.../`.
3. Copia esa URL y ábrela en el navegador (o pégala en la misma pestaña donde te registraste:
   tiene que ser el MISMO navegador/sesión para que te deje entrar directamente, ver
   `allauth.account.internal.flows.email_verification.login_on_verification`). Te deja dentro
   sin pedirte la contraseña otra vez, en `/hogares/mi-hogar/`, con el código de tu hogar a la
   vista.

### 4.2. El camino de las dos personas (R5, el corazón de la unidad)

1. Repite el paso 4.1 para una PRIMERA persona (p. ej. `alejandro@example.com`) y apunta el
   código de su hogar que aparece en `/hogares/mi-hogar/`.
2. Abre una ventana de incógnito (o cierra sesión) y repite el alta para una SEGUNDA persona
   (p. ej. `euridice@example.com`), pero esta vez rellenando el campo "Código de hogar" con el
   código del paso 1.
3. Verifica el correo de la segunda persona (paso 4.1.3). En vez de ver el hogar, la deja en
   `/hogares/mi-hogar/` con el mensaje "Esperando a que te acepten": **hasta este momento, la
   primera persona no sabía nada de ella** (la petición no existía hasta que verificó, R5).
4. Vuelve a la sesión de la primera persona y entra en `/hogares/mi-hogar/`: ahora aparece la
   petición pendiente, con botones de "Aceptar" y "Rechazar".
5. Pulsa "Aceptar". Si vuelves a la sesión de la segunda persona y recargas
   `/hogares/mi-hogar/`, ya ve el hogar compartido con las dos personas dentro.

Si en vez de aceptar dejas pasar más de una hora (o rechazas), la segunda persona se queda con
su propia cuenta y su propio hogar (R7, R8) — para probar la caducidad sin esperar una hora de
verdad, hazlo desde `manage.py shell` retrasando a mano el campo `creada_en` de la
`SolicitudEntrada` correspondiente (así es como lo hace `hogares/tests.py`).

### 4.3. Dónde mirar si algo no cuadra

- El correo (enlaces de verificación, avisos): la terminal de `runserver`, nunca un buzón de
  verdad — no hay ningún servicio de envío conectado en esta unidad (ver la sección de
  variables de entorno más abajo).
- Las contraseñas en la base de datos: `psql kcalibra_dev -c "SELECT email, password FROM
  cuentas_usuario;"` — deben salir como `pbkdf2_sha256$...`, nunca en claro (R10).

### 4.4. Crear una cuenta con datos físicos y ver tus calorías (unidad 004)

El paso 4.1 ya crea el perfil (es el mismo formulario de alta, que ahora también pide sexo,
fecha de nacimiento, altura, peso, actividad, objetivo y manías). Para comprobar que las
calorías salen bien con un caso conocido, usa los datos de uno de los dos episodios reales de
los planos al rellenar el alta:

| Campo | Euridice (R1) | Alejandro (R2) |
|---|---|---|
| Sexo | Mujer | Hombre |
| Fecha de nacimiento | 29/06/1997 | 03/11/1998 |
| Altura | 167 cm | 190 cm |
| Peso | 62 kg | 93 kg |
| Actividad | Actividad moderada | Actividad ligera |
| Objetivo | Perder grasa | Recomposición corporal |
| Ajuste manual | (en blanco: usa el −10 % de fábrica) | (en blanco: usa el +10 % de fábrica) |
| Calorías que debe enseñar `/perfiles/` | **1.894 kcal** (136 g proteína, 59 g grasa, 205 g carbohidratos) | **3.006 kcal** (205 g proteína, 94 g grasa, 336 g carbohidratos) |

Tras verificar el correo (paso 4.1.3), entra en `http://127.0.0.1:8000/perfiles/` ("Tus
datos" en la barra de arriba): debe enseñar esas calorías y esos macros ya calculados. Cambia
el "Objetivo" del formulario y pulsa "Guardar": los números de la tarjeta de abajo se
actualizan al momento, sin recargar la página (HTMX) — y el "Ajuste manual" vuelve él solo al
de fábrica del objetivo nuevo (R5).

Para ver el perfil de otra persona de tu hogar (R9: se ve, pero no se puede cambiar), entra en
`/hogares/mi-hogar/` y pulsa "Ver datos" junto a su correo, o ve directamente a
`/perfiles/<su-id>/`.

## Cómo está organizado el código

| dónde | qué hay | por qué |
|---|---|---|
| `kcalibra/` | configuración del proyecto (`settings.py`, `urls.py`) | lo que genera `django-admin startproject`, sin nada exótico |
| `paginas/` | la app con la portada y sus vistas | punto de entrada de lo que ve el usuario en el navegador |
| `cuentas/` | el modelo de usuario propio (`Usuario`, correo como identificador), el formulario de alta, el adaptador de `allauth` y las pantallas que `allauth` no trae hechas (esperar la verificación, pedir otro correo, corregir la dirección) | unidad 003 — "quién eres y cómo entras" |
| `hogares/` | `Hogar`, `SolicitudEntrada`, la base abstracta `ModeloDeHogar` (el aislamiento reutilizable) y la puerta única de acceso (`hogares/acceso.py`) | unidad 003 — "con quién compartes y quién ve qué"; toda unidad futura con datos del hogar (despensa, recetas, calendario) hereda de `ModeloDeHogar` en vez de reinventar el aislamiento |
| `templates/` | plantillas compartidas entre apps (`base.html`, y las de `allauth` que se han sobrescrito bajo `templates/account/`) | la base con Tailwind, HTMX y Alpine ya cargados; cada app extiende esto |
| `paginas/templates/paginas/`, `cuentas/templates/cuentas/`, `hogares/templates/hogares/` | plantillas propias de cada app | convención estándar de Django: cada app guarda las suyas bajo su propio nombre, para que no choquen nombres entre apps |
| `servicios/` | la capa de servicios: cálculos del dominio nutricional, en funciones puras | **estrenada en la unidad 004** (`servicios/metabolismo.py`): metabolismo basal, gasto diario, objetivo calórico y macros (fórmula Mifflin-St Jeor). Funciones puras — reciben datos y devuelven números, sin tocar la base de datos ni saber qué es una petición HTTP — para que se prueben solas y sirvan el día que haya una app nativa. La lógica de cuentas y hogares sigue viviendo DENTRO de sus propias apps (`hogares/logica.py`, `perfiles/logica.py`): esta carpeta es solo para cálculo puro, no un cajón general |
| `perfiles/` | los datos físicos, la actividad, el objetivo, el ajuste y las manías de cada persona (`Perfil`), y sus mediciones de peso (`MedicionPeso`); la pantalla de "tus datos" con las calorías y macros del día | unidad 004 — "cuenta quién eres y la app te dice cuántas calorías y qué macros te tocan". El cálculo en sí NO vive aquí (R8): `perfiles/logica.py` reúne los datos (perfil + media de peso de 7 días) y llama a `servicios/metabolismo.py`; las vistas (`perfiles/views.py`) solo llaman a `perfiles/logica.py`. El peso NO es un campo editable de `Perfil` (R7/G-61): es el resultado de las `MedicionPeso`, y el perfil no hereda de `hogares.ModeloDeHogar` porque es un dato DE LA PERSONA, no del hogar (G-43) — `perfiles/acceso.py` es la puerta: todo el hogar VE cualquier perfil, solo su dueña lo CAMBIA |
| `assets/tailwind/input.css` | el fichero de entrada de Tailwind | de aquí sale `static/css/tailwind.css` al compilar (paso 1.6). Incluye los estilos base de los formularios (`@layer base`) para que cualquier campo de `allauth` salga con aspecto consistente sin tocarlo campo a campo |
| `static/` | CSS generado + HTMX y Alpine vendidos | todo lo que Tailwind necesita servir sin depender de Node ni de una CDN |

## Variables de entorno obligatorias

Si falta cualquiera de estas, la app **se niega a arrancar** y dice cuál falta (no arranca con
valores por defecto inseguros): `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`,
`DB_HOST`, `DB_PORT`. Ver `.env.example` para el detalle de cada una.

### Variables opcionales de la unidad 003 (con valor por defecto seguro si no las pones)

| Variable | Por defecto | Qué hace |
|---|---|---|
| `DJANGO_REGISTRO_ABIERTO` | `False` (cerrado) | R12: con el registro cerrado, nadie puede crear una cuenta. Ponla a `True` en tu `.env` local para poder probar el alta |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` | Por dónde salen los correos de verificación. En este portátil, por la consola — ver el punto 4.3 |
| `DJANGO_DEFAULT_FROM_EMAIL` | `no-responder@kcalibra.app` | El remitente de esos correos |

**Deuda pendiente, importante:** en producción hace falta cambiar `DJANGO_EMAIL_BACKEND` a un
servicio de envío de verdad (no elegido todavía, fuera del alcance de la unidad 003). **Sin
eso, el día del despliegue nadie podrá registrarse** — el enlace de verificación no llegará a
ningún sitio real.
