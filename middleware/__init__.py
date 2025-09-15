"""
Middleware da aplicação

Contém middleware personalizado para autenticação, rate limiting e segurança.
Sistema robusto com proteção contra ataques e monitoramento de tentativas.
"""

from .auth import (
    verify_token, 
    get_bearer_token, 
    AuthenticationError,
    AuthenticationService,
    auth_service,
    secure_token_compare,
    generate_secure_token,
    validate_token_strength,
    get_auth_stats
)

__all__ = [
    "verify_token", 
    "get_bearer_token", 
    "AuthenticationError",
    "AuthenticationService",
    "auth_service",
    "secure_token_compare",
    "generate_secure_token",
    "validate_token_strength",
    "get_auth_stats"
]

# Versão do middleware
__version__ = "3.0.0"
