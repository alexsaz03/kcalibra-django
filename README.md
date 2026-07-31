# KCalibra

App de nutrición y compra para un hogar: calcula cuántas calorías necesita cada día
cada persona contando sus entrenos, y genera con IA el menú y la lista de la compra
ajustados a lo que hay en la despensa.

## Stack

Django 5.2 LTS · Python 3.12 · PostgreSQL 17 · HTMX 2 + Alpine.js + Tailwind 4 (sin Node)
· admin con `django-unfold`.

## De dónde sale este repo

Es la **reescritura en Django** de una app previa en Node + Express + React, que sigue
funcionando y en uso mientras esta se construye. El porqué del cambio está escrito en
`docs/decisiones/001-reescribir-en-django.md` del meta-repo.

**Los planos mandan.** Las 18 actividades y los 93 requisitos están definidos, aprobados
y congelados, y son agnósticos a la tecnología: describen el negocio, no el código. Se
construye contra ellos.

- **Meta-repo (planos, método, decisiones):** https://github.com/alexsaz03/kcalibra-agents
- **Implementación de referencia (Node):** https://github.com/alexsaz03/kcalibra — se
  consulta, no se traduce línea a línea.

Todo el código y los comentarios van en **español**.
