"""
Utilitários da aplicação

Funções auxiliares e helpers utilizados em toda a aplicação.
Inclui utilitários para validação, formatação e operações comuns.
"""

import os
import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pathlib import Path

def format_file_size(size_bytes: int) -> str:
    """
    Formata tamanho de arquivo em formato legível
    
    Args:
        size_bytes: Tamanho em bytes
        
    Returns:
        str: Tamanho formatado (ex: "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"

def format_duration(seconds: float) -> str:
    """
    Formata duração em formato legível
    
    Args:
        seconds: Duração em segundos
        
    Returns:
        str: Duração formatada (ex: "2m 30s")
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

def extract_youtube_id(url: str) -> Optional[str]:
    """
    Extrai ID do vídeo de uma URL do YouTube
    
    Args:
        url: URL do YouTube
        
    Returns:
        Optional[str]: ID do vídeo ou None se inválido
    """
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def validate_youtube_url(url: str) -> bool:
    """
    Valida se URL é do YouTube
    
    Args:
        url: URL para validar
        
    Returns:
        bool: True se válida
    """
    return extract_youtube_id(url) is not None

def clean_filename(filename: str) -> str:
    """
    Limpa nome de arquivo removendo caracteres inválidos
    
    Args:
        filename: Nome do arquivo
        
    Returns:
        str: Nome limpo
    """
    # Remover caracteres especiais
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Remover espaços extras
    filename = re.sub(r'\s+', ' ', filename).strip()
    # Limitar tamanho
    if len(filename) > 100:
        filename = filename[:97] + "..."
    
    return filename or "arquivo"

def ensure_directory_exists(path: str) -> bool:
    """
    Garante que diretório existe
    
    Args:
        path: Caminho do diretório
        
    Returns:
        bool: True se criado/existe
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except Exception:
        return False

def get_client_ip(request) -> str:
    """
    Extrai IP real do cliente considerando proxies
    
    Args:
        request: Objeto Request do FastAPI
        
    Returns:
        str: IP do cliente
    """
    # Verificar headers de proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback para IP direto
    return request.client.host if request.client else "unknown"

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Trunca texto mantendo palavras completas
    
    Args:
        text: Texto para truncar
        max_length: Tamanho máximo
        suffix: Sufixo para texto truncado
        
    Returns:
        str: Texto truncado
    """
    if len(text) <= max_length:
        return text
    
    # Truncar e encontrar última palavra completa
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + suffix

def calculate_estimated_time(items_processed: int, total_items: int, 
                           start_time: datetime) -> Optional[str]:
    """
    Calcula tempo estimado de conclusão
    
    Args:
        items_processed: Itens já processados
        total_items: Total de itens
        start_time: Hora de início
        
    Returns:
        Optional[str]: Tempo estimado ou None
    """
    if items_processed == 0:
        return None
    
    elapsed = datetime.now() - start_time
    rate = items_processed / elapsed.total_seconds()
    
    if rate <= 0:
        return None
    
    remaining_items = total_items - items_processed
    estimated_seconds = remaining_items / rate
    
    return format_duration(estimated_seconds)

def create_safe_dict(data: Dict[str, Any], 
                    safe_keys: List[str]) -> Dict[str, Any]:
    """
    Cria dicionário apenas com chaves seguras
    
    Args:
        data: Dicionário original
        safe_keys: Chaves permitidas
        
    Returns:
        Dict[str, Any]: Dicionário filtrado
    """
    return {key: data[key] for key in safe_keys if key in data}

async def run_with_timeout(coro, timeout_seconds: float):
    """
    Executa corrotina com timeout
    
    Args:
        coro: Corrotina para executar
        timeout_seconds: Timeout em segundos
        
    Returns:
        Resultado da corrotina
        
    Raises:
        asyncio.TimeoutError: Se timeout
    """
    return await asyncio.wait_for(coro, timeout=timeout_seconds)

def mask_sensitive_data(data: str, mask_char: str = "*", 
                       show_chars: int = 4) -> str:
    """
    Mascara dados sensíveis mostrando apenas alguns caracteres
    
    Args:
        data: Dados para mascarar
        mask_char: Caractere da máscara
        show_chars: Quantos caracteres mostrar
        
    Returns:
        str: Dados mascarados
    """
    if len(data) <= show_chars * 2:
        return mask_char * len(data)
    
    start = data[:show_chars]
    end = data[-show_chars:]
    middle = mask_char * (len(data) - show_chars * 2)
    
    return f"{start}{middle}{end}"

# Constantes úteis
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB
SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.m4a', '.aac', '.ogg']
DEFAULT_TIMEOUT = 300  # 5 minutos

__all__ = [
    "format_file_size",
    "format_duration", 
    "extract_youtube_id",
    "validate_youtube_url",
    "clean_filename",
    "ensure_directory_exists",
    "get_client_ip",
    "truncate_text",
    "calculate_estimated_time",
    "create_safe_dict",
    "run_with_timeout",
    "mask_sensitive_data",
    "MAX_FILE_SIZE",
    "SUPPORTED_AUDIO_FORMATS",
    "DEFAULT_TIMEOUT"
]
