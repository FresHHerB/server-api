"""
Modelos de dados da aplicação

Contém os schemas Pydantic para validação de entrada e saída da API.
Todos os modelos incluem validações robustas e exemplos de uso.
"""

from .schemas import (
    VideoRequest, 
    VideoResponse, 
    VideoData, 
    ErrorResponse,
    SessionStatusResponse,
    SessionRefreshResponse,
    HealthCheckResponse
)

__all__ = [
    "VideoRequest", 
    "VideoResponse", 
    "VideoData", 
    "ErrorResponse",
    "SessionStatusResponse",
    "SessionRefreshResponse", 
    "HealthCheckResponse"
]

# Versão dos modelos para compatibilidade
__version__ = "3.0.0"
