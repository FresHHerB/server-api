import os
import logging
import hashlib
import time
from fastapi import HTTPException, status
from typing import Optional

logger = logging.getLogger(__name__)

class AuthenticationError(Exception):
    """Exceção personalizada para erros de autenticação"""

    def __init__(self, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class AuthenticationService:
    """Serviço de autenticação com rate limiting e segurança avançada"""
    
    def __init__(self):
        self.failed_attempts = {}  # IP -> (count, last_attempt_time)
        self.max_attempts = 5
        self.lockout_duration = 300  # 5 minutos em segundos
        
    def is_ip_locked_out(self, client_ip: str) -> bool:
        """Verifica se IP está em lockout"""
        if client_ip not in self.failed_attempts:
            return False
            
        count, last_attempt = self.failed_attempts[client_ip]
        
        # Se passou o tempo de lockout, reset
        if time.time() - last_attempt > self.lockout_duration:
            del self.failed_attempts[client_ip]
            return False
            
        return count >= self.max_attempts
    
    def record_failed_attempt(self, client_ip: str):
        """Registra tentativa de autenticação falhada"""
        current_time = time.time()
        
        if client_ip in self.failed_attempts:
            count, _ = self.failed_attempts[client_ip]
            self.failed_attempts[client_ip] = (count + 1, current_time)
        else:
            self.failed_attempts[client_ip] = (1, current_time)
            
        logger.warning(f"⚠️ Tentativa de autenticação falhada para IP: {client_ip}")
    
    def record_successful_attempt(self, client_ip: str):
        """Registra tentativa bem-sucedida e limpa falhas"""
        if client_ip in self.failed_attempts:
            del self.failed_attempts[client_ip]

# Instância global do serviço de autenticação
auth_service = AuthenticationService()

def verify_token(token: str, client_ip: str = "unknown") -> bool:
    """
    Verifica se o token de acesso é válido com proteções de segurança

    Args:
        token: Token de acesso fornecido
        client_ip: IP do cliente para rate limiting

    Returns:
        bool: True se o token for válido

    Raises:
        HTTPException: Se o token for inválido ou IP estiver em lockout
    """
    try:
        # Verificar lockout de IP
        if auth_service.is_ip_locked_out(client_ip):
            logger.warning(f"🚫 IP em lockout: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas de autenticação falhadas. Tente novamente em 5 minutos.",
                headers={"Retry-After": "300"}
            )

        # Obter token esperado do ambiente
        expected_token = os.getenv("API_TOKEN")

        if not expected_token:
            logger.error("❌ API_TOKEN não configurado no servidor")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Configuração de autenticação não encontrada"
            )

        if not token:
            logger.warning(f"⚠️ Token não fornecido na requisição (IP: {client_ip})")
            auth_service.record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acesso é obrigatório",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Validação básica do formato
        if len(token.strip()) < 8:
            logger.warning(f"⚠️ Token muito curto fornecido (IP: {client_ip})")
            auth_service.record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Formato de token inválido",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Comparação segura de tokens
        if not secure_token_compare(token.strip(), expected_token.strip()):
            logger.warning(f"⚠️ Token inválido fornecido (IP: {client_ip}, length: {len(token)})")
            auth_service.record_failed_attempt(client_ip)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acesso inválido",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Autenticação bem-sucedida
        auth_service.record_successful_attempt(client_ip)
        logger.info(f"✅ Token válido - Acesso autorizado (IP: {client_ip})")
        return True

    except HTTPException:
        # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"❌ Erro na verificação do token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno na autenticação"
        )

def secure_token_compare(token1: str, token2: str) -> bool:
    """
    Comparação segura de tokens usando hash para evitar timing attacks
    
    Args:
        token1: Primeiro token
        token2: Segundo token
        
    Returns:
        bool: True se os tokens são iguais
    """
    # Usar hash SHA-256 para comparação
    hash1 = hashlib.sha256(token1.encode('utf-8')).hexdigest()
    hash2 = hashlib.sha256(token2.encode('utf-8')).hexdigest()
    
    # Comparação de tempo constante
    return hash1 == hash2

def get_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """
    Extrai o token Bearer do cabeçalho Authorization

    Args:
        authorization_header: Valor do cabeçalho Authorization

    Returns:
        Optional[str]: Token extraído ou None
    """
    if not authorization_header:
        return None

    parts = authorization_header.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]

def generate_secure_token(length: int = 32) -> str:
    """
    Gera um token seguro para uso em desenvolvimento
    
    Args:
        length: Comprimento do token
        
    Returns:
        str: Token seguro gerado
    """
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits + "-_"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def validate_token_strength(token: str) -> dict:
    """
    Valida a força de um token
    
    Args:
        token: Token para validar
        
    Returns:
        dict: Análise da força do token
    """
    analysis = {
        "valid": True,
        "strength": "weak",
        "issues": [],
        "recommendations": []
    }
    
    if len(token) < 16:
        analysis["issues"].append("Token muito curto")
        analysis["recommendations"].append("Use pelo menos 16 caracteres")
        analysis["valid"] = False
    
    if len(token) < 8:
        analysis["strength"] = "very_weak"
    elif len(token) < 16:
        analysis["strength"] = "weak"
    elif len(token) < 32:
        analysis["strength"] = "medium"
    else:
        analysis["strength"] = "strong"
    
    if token.lower() in ["password", "123456", "admin", "token"]:
        analysis["issues"].append("Token comum/previsível")
        analysis["recommendations"].append("Use um token único e complexo")
        analysis["valid"] = False
    
    return analysis

def get_auth_stats() -> dict:
    """
    Retorna estatísticas de autenticação
    
    Returns:
        dict: Estatísticas do sistema de auth
    """
    return {
        "locked_ips": len([ip for ip, (count, _) in auth_service.failed_attempts.items() 
                          if count >= auth_service.max_attempts]),
        "total_failed_attempts": sum(count for count, _ in auth_service.failed_attempts.values()),
        "max_attempts_per_ip": auth_service.max_attempts,
        "lockout_duration_minutes": auth_service.lockout_duration / 60
    }
