"""Contraseñas del personal (RN-018, RNF-003).

Se guardan con Argon2id, el algoritmo de hash recomendado actualmente: es lento a propósito y
usa memoria, así que probar millones de contraseñas contra un hash robado es muy costoso.
"""
import re
from datetime import date, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from gpizza import reglas

_hasher = PasswordHasher()


def politica(contrasena: str) -> str | None:
    """RN-018: mínimo 8 caracteres, con letras y números. Devuelve el problema o None si cumple."""
    if len(contrasena) < reglas.CONTRASENA_MIN_CARACTERES:
        return f'La contraseña debe tener al menos {reglas.CONTRASENA_MIN_CARACTERES} caracteres.'
    if not re.search(r'[A-Za-zÁÉÍÓÚÑáéíóúñ]', contrasena) or not re.search(r'\d', contrasena):
        return 'La contraseña debe incluir letras y números.'
    return None


def generar_hash(contrasena: str) -> str:
    problema = politica(contrasena)
    if problema:
        raise ValueError(problema)
    return _hasher.hash(contrasena)


def verificar(hash_guardado: str, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, contrasena)
    except (VerificationError, InvalidHashError):
        return False


def vencida(fecha_cambio: date, hoy: date) -> bool:
    """RN-018: la contraseña vence a los 90 días."""
    return hoy - fecha_cambio >= timedelta(days=reglas.CONTRASENA_VIGENCIA_DIAS)
