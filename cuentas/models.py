"""
El modelo de usuario propio (ver "Cómo" de la especificación de la unidad 003).

Se crea AHORA, aunque de momento apenas añada campos, porque la documentación oficial de
Django es explícita: cambiar el modelo de usuario a mitad de proyecto es de las cosas más
caras que hay (obliga a rehacer migraciones y tablas ya en uso). Los datos físicos (peso,
altura, objetivo, manías) NO van aquí: son de la unidad 004, en su propio modelo de perfil.
Este modelo es solo "quién eres y cómo entras".
"""

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


class UsuarioManager(BaseUserManager):
    """
    `AbstractUser` trae de serie un manager que espera un `username`. Como aquí no hay
    username (el correo es el identificador, ver `Usuario` más abajo), hace falta este
    manager propio para que `create_user` y `create_superuser` sepan crear cuentas sin él.
    """

    use_in_migrations = True

    def _crear_usuario(self, email, password, **extra_fields):
        if not email:
            raise ValueError("El usuario necesita un correo.")
        email = self.normalize_email(email)
        usuario = self.model(email=email, **extra_fields)
        usuario.set_password(password)
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._crear_usuario(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Un superusuario necesita is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Un superusuario necesita is_superuser=True.")
        return self._crear_usuario(email, password, **extra_fields)


class Usuario(AbstractUser):
    """
    `AbstractUser` de Django, con dos cambios: sin `username` (el correo hace ese papel) y con
    la pertenencia a un hogar.
    """

    # Fuera el username: nadie en KCalibra va a teclear un nombre de usuario, todo el mundo
    # entra con su correo (R1-R15, "Cómo" de la especificación).
    username = None
    email = models.EmailField("correo electrónico", unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # createsuperuser ya pide el email por ser USERNAME_FIELD

    objects = UsuarioManager()

    # El hogar de esta persona. Puede estar VACÍO (`null`) en un único momento del ciclo de
    # vida: mientras espera que alguien del hogar al que pidió entrar la acepte (R5, estado
    # "esperando que le acepten" del mapa) — antes de eso no tiene ninguno, y en cuanto se
    # resuelve (aceptada, rechazada o caducada) siempre vuelve a tener uno. `PROTECT` porque
    # un hogar con gente dentro no se puede borrar por accidente al borrar a alguien más.
    hogar = models.ForeignKey(
        "hogares.Hogar",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="miembros",
    )

    # Código de hogar que se metió al registrarse, SOLO si ese código existía (R5/R6). Se
    # guarda aquí porque la petición de entrada no se crea hasta que la persona verifica su
    # correo (G-37), y puede pasar un buen rato entre el alta y esa verificación: hace falta
    # un sitio donde ese código sobreviva mientras tanto. Se vacía en cuanto se procesa (ver
    # `hogares.logica.procesar_codigo_al_verificar`).
    codigo_hogar_pendiente = models.CharField(max_length=20, blank=True, default="")

    def __str__(self):
        return self.email
