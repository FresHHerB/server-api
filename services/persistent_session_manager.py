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
            
            # Playwright simples com timeout agressivo
            logger.info("📦 Iniciando Playwright...")
            try:
                self.playwright = await asyncio.wait_for(
                    async_playwright().start(), 
                    timeout=15
                )
                logger.info("✅ Playwright iniciado")
            except asyncio.TimeoutError:
                logger.error("❌ Timeout ao iniciar Playwright")
                return False
            
            # Argumentos ULTRA mínimos para evitar travamento
            args = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--headless=new',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-crash-reporter',
                '--disable-breakpad',
                '--mute-audio',
                f'--remote-debugging-port={self.debug_port}'
            ]
            
            logger.info("🌐 Lançando navegador Chrome...")
            logger.info(f"🔧 Args: {len(args)} argumentos")
            
            # Tentar lançar navegador com timeout muito agressivo
            try:
                self.browser = await asyncio.wait_for(
                    self.playwright.chromium.launch(
                        headless=True,
                        args=args,
                        timeout=30000,  # 30 segundos apenas
                        slow_mo=None,
                        devtools=False
                    ),
                    timeout=45  # 45 segundos max
                )
                logger.info("✅ Navegador Chrome lançado")
            except asyncio.TimeoutError:
                logger.error("❌ Timeout ao lançar Chrome - tentando com argumentos mínimos")
                # Fallback com argumentos ainda mais mínimos
                minimal_args = ['--no-sandbox', '--disable-dev-shm-usage', '--headless=new']
                try:
                    self.browser = await asyncio.wait_for(
                        self.playwright.chromium.launch(
                            headless=True,
                            args=minimal_args,
                            timeout=20000
                        ),
                        timeout=30
                    )
                    logger.info("✅ Navegador lançado com argumentos mínimos")
                except:
                    logger.error("❌ Falha total no lançamento do navegador")
                    return False
            
            logger.info("🔗 Criando contexto do navegador...")
            try:
                self.context = await asyncio.wait_for(
                    self.browser.new_context(
                        user_agent="Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36",
                        viewport={'width': 1280, 'height': 720}
                    ),
                    timeout=20
                )
                logger.info("✅ Contexto criado")
            except asyncio.TimeoutError:
                logger.error("❌ Timeout ao criar contexto")
                return False
            
            logger.info("📄 Criando página...")
            try:
                self.page = await asyncio.wait_for(
                    self.context.new_page(),
                    timeout=15
                )
                logger.info("✅ Página criada")
            except asyncio.TimeoutError:
                logger.error("❌ Timeout ao criar página")
                return False
            
            logger.info("🍪 Carregando cookies existentes...")
            await self._load_cookies()
            
            logger.info("🌐 Navegando para YouTube...")
            try:
                await asyncio.wait_for(
                    self.page.goto("https://www.youtube.com", wait_until="networkidle"),
                    timeout=60
                )
                logger.info("✅ YouTube carregado")
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout no YouTube, tentando com domcontentloaded...")
                try:
                    await asyncio.wait_for(
                        self.page.goto("https://www.youtube.com", wait_until="domcontentloaded"),
                        timeout=30
                    )
                    logger.info("✅ YouTube carregado (domcontentloaded)")
                except:
                    logger.error("❌ Falha total ao carregar YouTube")
                    return False
            
            await asyncio.sleep(2)
            
            logger.info("💾 Salvando cookies...")
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
            logger.error(f"❌ Tipo do erro: {type(e).__name__}")
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