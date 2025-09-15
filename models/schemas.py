from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
import re

class VideoRequest(BaseModel):
    """Modelo para requisição de transcrição de vídeos"""
    video_urls: List[str] = Field(
        ...,
        description="Lista de URLs de vídeos do YouTube",
        example=[
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=OqsvA8xcb80"
        ],
        min_items=1,
        max_items=10
    )

    @field_validator('video_urls')
    @classmethod
    def validate_youtube_urls(cls, v):
        """Valida se as URLs são do YouTube"""
        youtube_pattern = re.compile(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})'
        )
        
        valid_urls = []
        for url in v:
            if youtube_pattern.match(url):
                valid_urls.append(url)
            else:
                raise ValueError(f"URL inválida do YouTube: {url}")
        
        return valid_urls

    class Config:
        json_schema_extra = {
            "example": {
                "video_urls": [
                    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "https://www.youtube.com/watch?v=OqsvA8xcb80"
                ]
            }
        }

class VideoData(BaseModel):
    """Modelo para dados de um vídeo processado"""
    titulo: str = Field(
        ...,
        description="Título do vídeo extraído do YouTube",
        example="Rick Astley - Never Gonna Give You Up (Official Video)"
    )
    transcricao: str = Field(
        ...,
        description="Transcrição completa do áudio do vídeo",
        example="Never gonna give you up, never gonna let you down, never gonna run around and desert you..."
    )
    num_char: int = Field(
        ...,
        description="Número total de caracteres na transcrição",
        example=1247,
        ge=0
    )

    @field_validator('titulo')
    @classmethod
    def titulo_not_empty(cls, v):
        """Valida que o título não está vazio"""
        if not v or v.strip() == "":
            return "Título não disponível"
        return v.strip()

    @field_validator('transcricao')
    @classmethod
    def transcricao_not_empty(cls, v):
        """Valida que a transcrição não está vazia"""
        if not v or v.strip() == "":
            return "Transcrição não disponível"
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "titulo": "Como Programar em Python - Aula 1",
                "transcricao": "Bem-vindos ao curso de Python. Hoje vamos aprender os fundamentos da linguagem...",
                "num_char": 1234
            }
        }

class VideoResponse(BaseModel):
    """Modelo para resposta da API"""
    success: bool = Field(
        ...,
        description="Indica se a operação foi bem-sucedida",
        example=True
    )
    message: str = Field(
        ...,
        description="Mensagem explicativa sobre o resultado",
        example="Processados 2 vídeo(s) com sucesso"
    )
    data: List[VideoData] = Field(
        ...,
        description="Lista com dados dos vídeos processados"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Processados 2 vídeo(s) com sucesso",
                "data": [
                    {
                        "titulo": "Rick Astley - Never Gonna Give You Up",
                        "transcricao": "Never gonna give you up, never gonna let you down...",
                        "num_char": 1247
                    },
                    {
                        "titulo": "Como Programar em Python",
                        "transcricao": "Bem-vindos ao curso de Python...",
                        "num_char": 2156
                    }
                ]
            }
        }

class ErrorResponse(BaseModel):
    """Modelo para resposta de erro"""
    success: bool = Field(
        default=False,
        description="Sempre False para indicar erro"
    )
    message: str = Field(
        ...,
        description="Mensagem de erro detalhada",
        example="Token de acesso inválido"
    )
    error_code: Optional[str] = Field(
        None,
        description="Código interno do erro para debugging",
        example="AUTH_001"
    )
    details: Optional[dict] = Field(
        None,
        description="Detalhes adicionais sobre o erro"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "message": "Token de acesso inválido",
                "error_code": "AUTH_001",
                "details": {
                    "provided_token_length": 10,
                    "expected_token_format": "Bearer <token>"
                }
            }
        }

class SessionStatusResponse(BaseModel):
    """Modelo para resposta do status da sessão"""
    success: bool = Field(
        ...,
        description="Status da operação"
    )
    session_status: dict = Field(
        ...,
        description="Informações detalhadas da sessão persistente"
    )
    detailed_status: Optional[dict] = Field(
        None,
        description="Status detalhado adicional"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "session_status": {
                    "is_active": True,
                    "is_healthy": True,
                    "session_start_time": "2025-09-15T10:30:00",
                    "last_activity": "2025-09-15T11:45:23",
                    "refresh_count": 15,
                    "session_age_minutes": 75.4
                },
                "detailed_status": {
                    "background_tasks": {
                        "health_check": True,
                        "auto_refresh": True
                    },
                    "page_info": {
                        "url": "https://www.youtube.com",
                        "title": "YouTube"
                    }
                }
            }
        }

class SessionRefreshResponse(BaseModel):
    """Modelo para resposta do refresh da sessão"""
    success: bool = Field(
        ...,
        description="Indica se o refresh foi bem-sucedido"
    )
    message: str = Field(
        ...,
        description="Mensagem sobre o resultado do refresh"
    )
    session_status: dict = Field(
        ...,
        description="Status da sessão após o refresh"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Sessão atualizada com sucesso",
                "session_status": {
                    "is_active": True,
                    "is_healthy": True,
                    "last_activity": "2025-09-15T11:50:00",
                    "refresh_count": 16
                }
            }
        }

class HealthCheckResponse(BaseModel):
    """Modelo para resposta do health check"""
    status: str = Field(
        ...,
        description="Status geral da aplicação",
        example="healthy"
    )
    version: str = Field(
        ...,
        description="Versão da API",
        example="3.0.0"
    )
    persistent_session: dict = Field(
        ...,
        description="Informações sobre a sessão persistente"
    )
    services: dict = Field(
        ...,
        description="Status dos serviços"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "3.0.0",
                "persistent_session": {
                    "enabled": True,
                    "active": True,
                    "details": {
                        "is_healthy": True,
                        "session_age_minutes": 45.2
                    }
                },
                "services": {
                    "whisper": True,
                    "youtube": True
                }
            }
        }
