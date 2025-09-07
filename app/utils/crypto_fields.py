"""Utilidades de cifrado a nivel de aplicación.

Enfoque incremental: envelope encryption simplificado usando una "master key"
provista por entorno (APP_MASTER_KEY base64) y derivación HMAC por campo.

NOTA: Esto es un primer paso. En producción reemplazar por KMS/HSM y
rotación formal de llaves. El objetivo es permitir cifrar ciertos campos
sensibles (descripción, notas, acreedor) sin cambiar todavía todas las
consultas. Se genera también un blind index (HMAC) para búsquedas exactas.
"""
from __future__ import annotations

import base64
import os
import hmac
import hashlib
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_MASTER_KEY_ENV = "APP_MASTER_KEY"  # Versión legacy (v1)
_MIN_KEY_LEN = 32


def _load_master_key(version: int = 1) -> bytes:
    """Cargar llave maestra para una versión.

    Orden de búsqueda:
    1. APP_MASTER_KEY_<version>
    2. APP_MASTER_KEY (solo si version==1)
    3. Generar efímera (solo dev, version==1)
    """
    env_name = f"APP_MASTER_KEY_{version}" if version != 1 else _MASTER_KEY_ENV
    val = os.environ.get(env_name)
    if not val and version == 1:
        # Fallback legacy
        val = os.environ.get(_MASTER_KEY_ENV)
    if not val and version == 1:
        # Desarrollo: clave efímera (no persistir datos reales así)
        gen = base64.b64encode(os.urandom(32)).decode()
        os.environ[_MASTER_KEY_ENV] = gen
        val = gen
    if not val:
        raise RuntimeError(f"No se encontró llave maestra para versión {version} (variable {env_name})")
    try:
        raw = base64.b64decode(val)
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"Llave maestra v{version} inválida (base64)") from e
    if len(raw) < _MIN_KEY_LEN:
        raise RuntimeError(f"Llave maestra v{version} demasiado corta (>=32 bytes)")
    return raw


def _derive_subkey(purpose: str, field: str, version: int = 1) -> bytes:
    mk = _load_master_key(version)
    msg = f"{purpose}:{field}:v{version}".encode()
    return hmac.new(mk, msg, hashlib.sha256).digest()


def encrypt_field(value: Optional[str], field: str, version: int = 1) -> Optional[bytes]:
    """Cifrar un valor de texto. Devuelve bytes: nonce|ciphertext|tag.

    Se usa AES-256-GCM con subllave derivada. Si value es None/"" -> None.
    """
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    key = _derive_subkey("enc", field, version)
    aes = AESGCM(key)
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, value.encode(), None)  # incluye tag al final
    return nonce + ct


def decrypt_field(blob: Optional[bytes], field: str, version: int = 1) -> Optional[str]:
    if not blob:
        return None
    key = _derive_subkey("enc", field, version)
    aes = AESGCM(key)
    nonce, ct = blob[:12], blob[12:]
    try:
        pt = aes.decrypt(nonce, ct, None)
        return pt.decode()
    except Exception:  # pragma: no cover - corrupción / llave distinta
        return None


def blind_index(value: Optional[str], field: str, version: int = 1) -> Optional[str]:
    """Blind index (HMAC-SHA256) para búsquedas exactas por igualdad.

    No reversible. Normaliza a lower y recorta espacios.
    """
    if value is None:
        return None
    norm = value.strip().lower()
    if not norm:
        return None
    key = _derive_subkey("bidx", field, version)
    return hmac.new(key, norm.encode(), hashlib.sha256).hexdigest()


def dual_encrypt(value: Optional[str], field: str, version: int = 1):
    """Conveniencia: retorna (cipher_bytes, blind_index_hex)."""
    enc = encrypt_field(value, field, version)
    bidx = blind_index(value, field, version)
    return enc, bidx


def get_active_enc_version() -> int:
    """Versión de cifrado activa para nuevas filas (env APP_ENC_ACTIVE_VERSION)."""
    try:
        return int(os.environ.get('APP_ENC_ACTIVE_VERSION', '1'))
    except ValueError:  # pragma: no cover
        return 1
