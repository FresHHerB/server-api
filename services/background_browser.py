import asyncio
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, BrowserContext, Page, Browser
from typing import Optional

logger = logging.getLogger(__name__)

class BackgroundBrowser:
    """
    Navegador que roda em background independente da API
    - Mantém sessão YouTube sempre ativa
    - Refresh a cada 10 segundos  
    - Atualiza cookies.txt automaticamente
    - Não interfere na API
    """

    def __init__(self, cookie_filepath: str = "cookies.txt"):
        self.cookie_filepath = cookie_filepath
        self.debug_port = 9222
        self.refresh_interval = 10  # segundos
        
        # Lock para evitar conflito de arquivo
        self.cookie_lock = threading.Lock()
        
        # Componentes do navegador
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Status
        self.is_running = False
        self.refresh_count = 0
        self.start_time = None
        
        logger.info("🤖 BackgroundBrowser inicializado")
        logger.info(f"🍪 Cookies: {self.cookie_filepath}")
        logger.info(f"🔄 Refresh interval: {self.refresh_interval}s")

    async def start(self):
        """Inicializar navegador e começar loop de refresh"""
        if self.is_running:
            logger.info("✅ BackgroundBrowser já está rodando")
            return True
            
        try:
            logger.info("🚀 Iniciando BackgroundBrowser...")
            
            # Conectar ao Chrome existente
            logger.info("📦 Iniciando Playwright...")
            self.playwright = await async_playwright().start()
            
            logger.info(f"🔗 Conectando ao Chrome na porta {self.debug_port}...")
            self.browser = await self.playwright.chromium.connect_over_cdp(
                f"http://localhost:{self.debug_port}"
            )
            
            # Obter contexto existente
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
                logger.info("✅ Usando contexto existente")
            else:
                self.context = await self.browser.new_context()
                logger.info("✅ Novo contexto criado")
            
            # Obter página existente
            pages = self.context.pages
            if pages:
                self.page = pages[0]
                logger.info("✅ Usando página existente")
            else:
                self.page = await self.context.new_page()
                logger.info("✅ Nova página criada")
            
            # Carregar cookies iniciais se existirem
            await self._load_initial_cookies()
            
            # Navegar para YouTube
            logger.info("🌐 Navegando para YouTube...")
            await self.page.goto("https://www.youtube.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # Salvar cookies iniciais
            await self._save_cookies_safe()
            
            self.is_running = True
            self.start_time = datetime.now()
            
            logger.info("✅ BackgroundBrowser ativo!")
            logger.info("🔄 Iniciando loop de refresh a cada 10s...")
            
            # Iniciar loop de refresh em background
            asyncio.create_task(self._refresh_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao iniciar BackgroundBrowser: {e}")
            await self._cleanup()
            return False

    async def _refresh_loop(self):
        """Loop infinito que faz refresh a cada 10 segundos"""
        while self.is_running:
            try:
                await asyncio.sleep(self.refresh_interval)
                
                if not self.is_running:
                    break
                
                logger.info(f"🔄 Refresh #{self.refresh_count + 1} - F5 natural...")
                
                # F5 simples na página
                await self.page.reload(wait_until="domcontentloaded")
                await asyncio.sleep(2)
                
                # Coleta cookies naturais após refresh
                success = await self._save_cookies_safe()
                
                if success:
                    self.refresh_count += 1
                    logger.info(f"✅ Refresh #{self.refresh_count} completo - cookies atualizados")
                else:
                    logger.warning(f"⚠️ Falha no refresh #{self.refresh_count + 1}")
                
            except Exception as e:
                logger.error(f"❌ Erro no refresh loop: {e}")
                await asyncio.sleep(5)  # Espera mais tempo se houver erro

    async def _load_initial_cookies(self):
        """Carregar cookies iniciais apenas na primeira vez"""
        if not os.path.exists(self.cookie_filepath):
            logger.info("📝 Nenhum cookie inicial para carregar")
            return
            
        try:
            with self.cookie_lock:
                cookies = []
                with open(self.cookie_filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip().startswith('#') or not line.strip():
                            continue
                        
                        parts = line.strip().split('\t')
                        if len(parts) == 7:
                            domain, include_subdomains, path, secure, expires, name, value = parts
                            
                            cookies.append({
                                "name": name,
                                "value": value,
                                "domain": domain,
                                "path": path,
                                "expires": int(expires) if expires != '0' else -1,
                                "secure": secure.lower() == 'true'
                            })
                
                if cookies:
                    await self.context.add_cookies(cookies)
                    logger.info(f"🍪 {len(cookies)} cookies iniciais carregados")
                    
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar cookies iniciais: {e}")

    async def _save_cookies_safe(self):
        """Salvar cookies com lock para evitar conflitos"""
        try:
            cookies = await self.context.cookies()
            
            # Filtrar apenas cookies do YouTube/Google
            youtube_cookies = [
                c for c in cookies 
                if any(domain in c.get('domain', '') for domain in ['youtube.com', 'google.com'])
            ]
            
            if not youtube_cookies:
                logger.warning("⚠️ Nenhum cookie do YouTube encontrado")
                return False
            
            # Salvar com lock
            with self.cookie_lock:
                with open(self.cookie_filepath, 'w', encoding='utf-8') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# http://curl.haxx.se/rfc/cookie_spec.html\n")
                    f.write("# This is a generated file!  Do not edit.\n\n")
                    
                    for cookie in youtube_cookies:
                        domain = cookie.get('domain', '')
                        include_subdomains = "TRUE" if domain.startswith('.') else "FALSE"
                        secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                        expires = int(cookie.get('expires', 0)) if cookie.get('expires', -1) != -1 else 0
                        
                        f.write(f"{domain}\t{include_subdomains}\t{cookie.get('path', '/')}\t{secure}\t{expires}\t{cookie.get('name', '')}\t{cookie.get('value', '')}\n")
            
            logger.debug(f"💾 {len(youtube_cookies)} cookies salvos")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar cookies: {e}")
            return False

    def get_status(self):
        """Status do navegador em background"""
        return {
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "refresh_count": self.refresh_count,
            "refresh_interval": self.refresh_interval,
            "uptime_minutes": (
                (datetime.now() - self.start_time).total_seconds() / 60
                if self.start_time else 0
            )
        }

    async def stop(self):
        """Parar o navegador background"""
        logger.info("🛑 Parando BackgroundBrowser...")
        self.is_running = False
        # Não fazer cleanup - deixar navegador rodando
        logger.info("🔒 BackgroundBrowser parado (navegador permanece aberto)")

    async def _cleanup(self):
        """Cleanup apenas se necessário"""
        try:
            self.is_running = False
            
            if self.page:
                await self.page.close()
                self.page = None
                
            if self.context:
                await self.context.close()
                self.context = None
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            logger.info("🧹 BackgroundBrowser cleanup concluído")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro no cleanup: {e}")