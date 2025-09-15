import os
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CookieServiceFallback:
    """
    Versão de fallback do CookieService que funciona sem Playwright
    Para casos onde o Playwright não pode ser instalado no container
    """

    def __init__(self, cookie_filepath: str = "cookies.txt"):
        self.cookie_filepath = cookie_filepath
        self.last_update = None
        self.update_interval = timedelta(hours=12)  # Mais conservador sem auto-update
        self._lock = asyncio.Lock()
        
        logger.warning("🔄 Usando CookieService em modo FALLBACK (sem Playwright)")

    def parse_netscape_cookies(self, file_path: str) -> List[Dict]:
        """Lê cookies do formato Netscape"""
        if not os.path.exists(file_path):
            logger.warning(f"Arquivo de cookies não encontrado em '{file_path}'")
            return []

        cookies = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('#') or not line.strip():
                        continue

                    try:
                        parts = line.strip().split('\t')
                        if len(parts) != 7:
                            continue

                        domain, include_subdomains, path, secure, expires, name, value = parts

                        cookies.append({
                            "name": name,
                            "value": value,
                            "domain": domain,
                            "path": path,
                            "expires": int(expires) if expires != '0' else -1,
                            "httpOnly": False,
                            "secure": secure.lower() == 'true',
                            "sameSite": "Lax"
                        })
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Linha mal formatada ignorada: {line.strip()} - {e}")
                        continue

        except Exception as e:
            logger.error(f"Erro ao ler arquivo de cookies: {e}")
            return []

        logger.info(f"✅ {len(cookies)} cookies carregados de '{file_path}'")
        return cookies

    async def needs_update(self) -> bool:
        """Verifica se cookies precisam ser atualizados"""
        if self.last_update is None:
            return True
        return datetime.now() - self.last_update > self.update_interval

    async def update_cookies(self, force: bool = False) -> bool:
        """
        Versão fallback - não atualiza cookies automaticamente
        Apenas retorna False e log de aviso
        """
        async with self._lock:
            logger.warning("⚠️ Atualização automática de cookies não disponível (Playwright não instalado)")
            logger.info("💡 Para atualizar cookies, faça isso manualmente e substitua o arquivo cookies.txt")
            
            # Marcar como "atualizado" para evitar tentativas constantes
            if force:
                self.last_update = datetime.now()
                return False
            
            return False

    async def ensure_fresh_cookies(self) -> bool:
        """Sempre retorna True (assumindo que cookies estão OK)"""
        logger.info("✅ Usando cookies existentes (modo fallback)")
        return True

    def get_cookie_status(self) -> Dict:
        """Retorna status dos cookies"""
        cookie_exists = os.path.exists(self.cookie_filepath)
        cookie_count = 0
        
        if cookie_exists:
            cookies = self.parse_netscape_cookies(self.cookie_filepath)
            cookie_count = len(cookies)
        
        return {
            "cookie_file_exists": cookie_exists,
            "cookie_count": cookie_count,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "needs_update": False,  # Sempre False no modo fallback
            "cookie_file_path": self.cookie_filepath,
            "fallback_mode": True,
            "playwright_available": False
        }
