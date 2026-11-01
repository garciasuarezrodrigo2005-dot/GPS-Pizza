"""Cifrado de datos sensibles del cliente (RNF-003).

Se usa Fernet (AES-128 en modo CBC + HMAC-SHA256): además de ocultar el dato, detecta si alguien
alteró los bytes guardados. La clave vive en GPIZZA_CLAVE_CIFRADO (.env) y nunca en la base de datos,
así que quien copie la base sin la clave solo ve bytes ilegibles.
"""
import os

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    clave = os.getenv('GPIZZA_CLAVE_CIFRADO')
    if not clave:
        raise RuntimeError('Falta GPIZZA_CLAVE_CIFRADO en el archivo .env (ver README).')
    return Fernet(clave.encode())


def cifrar(texto: str) -> bytes:
    return _fernet().encrypt(texto.encode('utf-8'))


def descifrar(datos: bytes) -> str:
    return _fernet().decrypt(bytes(datos)).decode('utf-8')
