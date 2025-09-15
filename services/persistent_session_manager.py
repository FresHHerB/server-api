import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, BrowserContext, Page, Browser
from datetime import datetime
import random

logger = logging.getLogger(__name__)

class PersistentSessionManager:
    """Gerenciador SIMPLES de sessão persistente - apenas Playwright puro"""

    def __init__(self, 
                 cookie_filepath: str = "cookies.txt", 
                 profile_dir: str = "/app/browser_profile"):
        self.cookie_filepath = cookie_filepath
        self.profile_dir = Path(profile_dir)
        
        # Componentes da sessão
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Status simples
        self.is_active = False
        self.session_start_time = None
        self.last_activity = None
        self.refresh_count = 0
        
        # Debug port para conexão externa
        self.debug_port = 9222
        
        # Criar diretório
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎭 PersistentSessionManager SIMPLES inicializado")
        logger.info(f"📁 Perfil: {self.profile_dir}")
        logger.info(f"🍪 Cookies: {self.cookie_filepath}")
        logger.info(f"🐛 Debug port: {self.debug_port}")

    async def initialize(self) -> bool:
        """Inicialização SIMPLES - apenas abrir navegador e deixar aberto"""
        if self.is_active:
            logger.info("✅ Sessão já ativa")
            return True
            
        try:
            logger.info("🚀 Inicializando navegador SIMPLES...")
            
            # Playwright simples
            self.playwright = await async_playwright().start()
            
            # Argumentos mínimos necessários
            args = [
                '--no-sandbox',
                '--disable-setuid-sandbox', 
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-sync',
                '--disable-translate',
                '--mute-audio',
                # CRASHPAD - SOLUÇÃO DEFINITIVA
                '--disable-crashpad',
                '--disable-crash-reporter',
                '--disable-breakpad',
                '--crash-dumps-dir=/tmp',
                # Debug port para conexão externa
                f'--remote-debugging-port={self.debug_port}',
                '--remote-allow-origins=*'
            ]
            
            # Lançar navegador com debug port
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=args,
                devtools=False
            )
            
            # Contexto simples
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            
            # Página simples
            self.page = await self.context.new_page()
            
            # Carregar cookies se existirem
            await self._load_cookies()
            
            # Ir para YouTube uma vez
            await self.page.goto("https://www.youtube.com", timeout=60000)
            await asyncio.sleep(3)
            
            # Extrair e salvar cookies
            await self._save_cookies()
            
            # Marcar como ativo
            self.is_active = True
            self.session_start_time = datetime.now()
            self.last_activity = datetime.now()
            
            logger.info("✅ Navegador SIMPLES ativo!")
            logger.info(f"🌐 YouTube carregado na página")
            logger.info(f"🐛 Debug disponível em: localhost:{self.debug_port}")
            logger.info("🔒 NAVEGADOR PERMANECE ABERTO")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na inicialização simples: {e}")
            await self._cleanup()
            return False

    async def _load_cookies(self):
        """Carregar cookies simples"""
        if not os.path.exists(self.cookie_filepath):
            logger.info("📝 Nenhum cookie para carregar")
            return
            
        try:
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
                logger.info(f"🍪 {len(cookies)} cookies carregados")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar cookies: {e}")

    async def _save_cookies(self):
        """Salvar cookies simples"""
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
            
            # Salvar no formato Netscape
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
            
            logger.info(f"💾 {len(youtube_cookies)} cookies salvos")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar cookies: {e}")
            return False

    async def refresh_cookies(self) -> bool:
        """Refresh SIMPLES - apenas recarregar página e salvar cookies"""
        if not self.is_active or not self.page:
            logger.warning("⚠️ Navegador não está ativo")
            return False
            
        try:
            logger.info("🔄 Refresh simples...")
            
            # Apenas recarregar o YouTube
            await self.page.goto("https://www.youtube.com", timeout=45000)
            await asyncio.sleep(2)
            
            # Movimento simples do mouse
            await self.page.mouse.move(500, 400)
            await asyncio.sleep(1)
            
            # Salvar cookies
            success = await self._save_cookies()
            
            if success:
                self.last_activity = datetime.now()
                self.refresh_count += 1
                logger.info(f"✅ Refresh #{self.refresh_count} completo")
                return True
            else:
                logger.warning("⚠️ Falha no refresh")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no refresh: {e}")
            # IMPORTANTE: NÃO fechar navegador em caso de erro
            return False

    async def force_refresh(self) -> bool:
        """Force refresh - limpar cookies e recarregar"""
        if not self.is_active or not self.page:
            return False
            
        try:
            logger.info("🔄 Force refresh...")
            
            # Limpar cookies do contexto
            await self.context.clear_cookies()
            
            # Recarregar cookies do arquivo
            await self._load_cookies()
            
            # Recarregar página
            await self.page.goto("https://www.youtube.com", timeout=60000)
            await asyncio.sleep(3)
            
            # Salvar novos cookies
            success = await self._save_cookies()
            
            if success:
                self.last_activity = datetime.now()
                self.refresh_count += 1
                logger.info(f"✅ Force refresh #{self.refresh_count} completo")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro no force refresh: {e}")
            
        return False

    async def light_refresh(self) -> bool:
        """Light refresh - apenas movimento do mouse"""
        if not self.is_active or not self.page:
            return False
            
        try:
            await self.page.mouse.move(random.randint(100, 1800), random.randint(100, 900))
            await asyncio.sleep(0.5)
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            logger.debug(f"Erro no light refresh: {e}")
            return False

    async def get_session_status(self) -> Dict:
        """Status da sessão"""
        return {
            "is_active": self.is_active,
            "session_start_time": self.session_start_time.isoformat() if self.session_start_time else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "refresh_count": self.refresh_count,
            "debug_port": self.debug_port,
            "session_age_minutes": (
                (datetime.now() - self.session_start_time).total_seconds() / 60
                if self.session_start_time else 0
            )
        }

    async def get_detailed_status(self) -> Dict:
        """Status detalhado"""
        basic_status = await self.get_session_status()
        
        try:
            if self.page:
                basic_status["page_info"] = {
                    "url": await self.page.url(),
                    "title": await self.page.title()
                }
        except Exception:
            pass
            
        return basic_status

    async def _cleanup(self):
        """Cleanup recursos"""
        try:
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
                
            self.is_active = False
            logger.info("🧹 Recursos limpos")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na limpeza: {e}")

    async def shutdown(self):
        """Shutdown - NÃO fazer cleanup para manter navegador aberto"""
        logger.info("🛑 Shutdown solicitado - NAVEGADOR PERMANECE ABERTO")
        # Intencionalmente NÃO chama _cleanup()