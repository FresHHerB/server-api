import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from .persistent_session_service import PersistentSessionService

logger = logging.getLogger(__name__)

class CookieServicePersistent:
    """CookieService que usa sessão persistente para atualização contínua de cookies"""

    def __init__(self, cookie_filepath: str = "cookies.txt"):
        self.cookie_filepath = cookie_filepath
        self.session_service = PersistentSessionService(cookie_filepath)
        
        # Configurações de refresh
        self.auto_refresh_interval = timedelta(minutes=15)  # Refresh a cada 15 min
        self.last_refresh = None
        self._refresh_lock = asyncio.Lock()
        
        # Task para refresh automático
        self._refresh_task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()

    async def initialize(self) -> bool:
        """Inicializa o serviço e a sessão persistente"""
        try:
            logger.info("🚀 Inicializando CookieService com sessão persistente...")
            
            # Inicializar sessão persistente
            success = await self.session_service.initialize_session()
            if not success:
                logger.error("❌ Falha ao inicializar sessão persistente")
                return False
            
            # Iniciar task de refresh automático
            self._refresh_task = asyncio.create_task(self._auto_refresh_loop())
            
            logger.info("✅ CookieService com sessão persistente inicializado!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar CookieService: {e}")
            return False

    async def ensure_fresh_cookies(self) -> bool:
        """Garante que os cookies estão frescos usando a sessão persistente"""
        async with self._refresh_lock:
            try:
                # Verificar saúde da sessão primeiro
                if not await self.session_service.health_check():
                    logger.warning("⚠️ Sessão não está saudável, tentando renovar...")
                    if not await self.session_service.renew_session():
                        logger.error("❌ Falha ao renovar sessão")
                        return False
                
                # Verificar se precisa refresh baseado no tempo
                needs_refresh = False
                if self.last_refresh is None:
                    needs_refresh = True
                    logger.info("🔄 Primeiro refresh da sessão")
                elif datetime.now() - self.last_refresh > self.auto_refresh_interval:
                    needs_refresh = True
                    logger.info("🔄 Refresh periódico necessário")
                
                if needs_refresh:
                    success = await self.session_service.refresh_session_cookies()
                    if success:
                        self.last_refresh = datetime.now()
                        logger.info("✅ Cookies atualizados via sessão persistente")
                        return True
                    else:
                        logger.warning("⚠️ Falha no refresh, mas sessão ainda ativa")
                        return False
                else:
                    logger.info("✅ Cookies ainda são válidos (sessão ativa)")
                    return True
                    
            except Exception as e:
                logger.error(f"❌ Erro ao garantir cookies frescos: {e}")
                return False

    async def force_refresh(self) -> bool:
        """Força refresh imediato dos cookies"""
        async with self._refresh_lock:
            try:
                logger.info("🔄 Forçando refresh de cookies...")
                
                success = await self.session_service.refresh_session_cookies()
                if success:
                    self.last_refresh = datetime.now()
                    logger.info("✅ Refresh forçado bem-sucedido")
                    return True
                else:
                    logger.warning("❌ Falha no refresh forçado")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erro no refresh forçado: {e}")
                return False

    async def _auto_refresh_loop(self):
        """Loop automático para refresh periódico de cookies"""
        logger.info("🔄 Iniciando loop de refresh automático...")
        
        while not self._shutdown_event.is_set():
            try:
                # Aguardar próximo ciclo ou shutdown
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(), 
                        timeout=self.auto_refresh_interval.total_seconds()
                    )
                    # Se chegou aqui, é porque o shutdown foi sinalizado
                    break
                except asyncio.TimeoutError:
                    # Timeout normal, continuar com refresh
                    pass
                
                # Verificar se a sessão está ativa antes de tentar refresh
                if self.session_service.is_active:
                    logger.info("🔄 Auto-refresh de cookies...")
                    
                    try:
                        await self.ensure_fresh_cookies()
                    except Exception as e:
                        logger.warning(f"⚠️ Erro no auto-refresh: {e}")
                        
                        # Tentar renovar sessão se falhar
                        logger.info("🔄 Tentando renovar sessão após falha...")
                        await self.session_service.renew_session()
                else:
                    logger.warning("⚠️ Sessão inativa no auto-refresh")
                    
            except Exception as e:
                logger.error(f"❌ Erro no loop de auto-refresh: {e}")
                # Aguardar um pouco antes de tentar novamente
                await asyncio.sleep(60)
        
        logger.info("🛑 Loop de auto-refresh encerrado")

    def get_cookie_status(self) -> Dict:
        """Retorna status completo dos cookies e sessão"""
        cookie_exists = os.path.exists(self.cookie_filepath)
        cookie_count = 0
        
        if cookie_exists:
            try:
                with open(self.cookie_filepath, 'r') as f:
                    lines = [line for line in f if not line.strip().startswith('#') and line.strip()]
                    cookie_count = len(lines)
            except Exception:
                cookie_count = 0
        
        session_status = self.session_service.get_session_status()
        
        return {
            "cookie_file_exists": cookie_exists,
            "cookie_count": cookie_count,
            "last_refresh": self.last_refresh.isoformat() if self.last_refresh else None,
            "auto_refresh_interval_minutes": self.auto_refresh_interval.total_seconds() / 60,
            "cookie_file_path": self.cookie_filepath,
            "session_status": session_status,
            "mode": "persistent_session"
        }

    async def get_detailed_status(self) -> Dict:
        """Status detalhado incluindo health check da sessão"""
        basic_status = self.get_cookie_status()
        
        # Adicionar health check em tempo real
        session_healthy = await self.session_service.health_check()
        
        basic_status.update({
            "session_healthy": session_healthy,
            "refresh_task_running": self._refresh_task and not self._refresh_task.done(),
            "minutes_since_last_refresh": (
                (datetime.now() - self.last_refresh).total_seconds() / 60
                if self.last_refresh else None
            )
        })
        
        return basic_status

    async def shutdown(self):
        """Encerra o serviço e a sessão persistente"""
        logger.info("🛑 Encerrando CookieService persistente...")
        
        # Sinalizar shutdown para o auto-refresh loop
        self._shutdown_event.set()
        
        # Aguardar o task de refresh terminar
        if self._refresh_task and not self._refresh_task.done():
            try:
                await asyncio.wait_for(self._refresh_task, timeout=10)
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout ao aguardar task de refresh")
                self._refresh_task.cancel()
        
        # Encerrar sessão persistente
        await self.session_service.shutdown()
        
        logger.info("✅ CookieService persistente encerrado")


# Função para detectar qual CookieService usar
def create_cookie_service(persistent_mode: bool = True) -> 'CookieServiceBase':
    """Factory para criar o CookieService apropriado"""
    
    if persistent_mode:
        try:
            # Verificar se Playwright está disponível
            import playwright
            return CookieServicePersistent()
        except ImportError:
            logger.warning("⚠️ Playwright não disponível, usando modo fallback")
            from .cookie_service_fallback import CookieServiceFallback
            return CookieServiceFallback()
    else:
        # Modo não-persistente (original)
        try:
            from .cookie_service import CookieService
            return CookieService()
        except ImportError:
            from .cookie_service_fallback import CookieServiceFallback
            return CookieServiceFallback()
