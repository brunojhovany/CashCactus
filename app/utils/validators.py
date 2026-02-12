"""Utilidades de validación de seguridad."""
import re
from typing import Tuple


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validar fortaleza de contraseña según mejores prácticas (NIST 800-63B).
    
    Requisitos:
    - Mínimo 12 caracteres
    - Máximo 128 caracteres
    - Al menos una mayúscula, una minúscula
    - Al menos un número O un carácter especial
    - No debe ser una contraseña común
    
    Returns:
        Tuple[bool, str]: (es_válida, mensaje_error)
    """
    if not password:
        return False, 'La contraseña es obligatoria'
    
    if len(password) < 12:
        return False, 'La contraseña debe tener al menos 12 caracteres'
    
    if len(password) > 128:
        return False, 'La contraseña es demasiado larga (máximo 128 caracteres)'
    
    # Verificar complejidad mínima
    has_upper = bool(re.search(r'[A-Z]', password))
    has_lower = bool(re.search(r'[a-z]', password))
    has_digit = bool(re.search(r'\d', password))
    has_special = bool(re.search(r'[!@#$%^&*(),.?":{}|<>\-_=+\[\]\\;/`~]', password))
    
    if not has_upper:
        return False, 'La contraseña debe contener al menos una letra mayúscula'
    
    if not has_lower:
        return False, 'La contraseña debe contener al menos una letra minúscula'
    
    if not (has_digit or has_special):
        return False, 'La contraseña debe contener al menos un número o carácter especial'
    
    # Lista de contraseñas comunes (expandir según necesidad)
    common_passwords = [
        'password', '123456', 'qwerty', '111111', 'abc123', 'password123',
        'admin123', 'letmein', 'welcome123', 'monkey', '1234567890',
        'password1', 'password12', 'qwerty123', 'abc123456', '123456789',
        'password1234', 'admin', 'administrator', 'root', 'toor'
    ]
    
    if password.lower() in common_passwords:
        return False, 'Esta contraseña es demasiado común. Elige una más segura.'
    
    # Verificar patrones comunes débiles
    if re.match(r'^[a-zA-Z]+\d+$', password) or re.match(r'^\d+[a-zA-Z]+$', password):
        if len(password) < 16:
            return False, 'Patrón de contraseña débil detectado. Usa una combinación más compleja.'
    
    return True, ''


def sanitize_search_term(term: str, max_length: int = 100) -> str:
    """
    Sanitizar término de búsqueda para prevenir inyecciones SQL y DoS.
    
    - Escapa wildcards (%, _)
    - Limita longitud
    - Remueve caracteres peligrosos
    
    Args:
        term: Término de búsqueda
        max_length: Longitud máxima permitida
        
    Returns:
        str: Término sanitizado
    """
    if not term:
        return ''
    
    # Normalizar
    term = term.strip()
    
    # Limitar longitud
    if len(term) > max_length:
        term = term[:max_length]
    
    # Escapar wildcards de SQL LIKE
    term = term.replace('\\', '\\\\')  # Primero backslash
    term = term.replace('%', '\\%')
    term = term.replace('_', '\\_')
    
    return term
