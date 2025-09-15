import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, BrowserContext, Page
from playwright_stealth import stealth_async
import time
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class PersistentSessionManager:
    """Gerenciador de sessão persistente do navegador para YouTube"""

    def __init__(self, 
                 cookie_filepath: str = "cookies.txt", 
                 profile_dir: str = "/app/browser_profile"):
        self.cookie_filepath = cookie_filepath
        self.profile_dir = Path(profile_dir)
        
        # Componentes da sessão
        self.playwright = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Status da sessão
        self.is_active = False
        self.is_healthy = False
        self.session_start_time = None
        self.last_activity = None
        self.last_cookie_update = None
        self.refresh_count = 0
        
        # Configurações
        self.max_session_duration = timedelta(hours=8)
        self.cookie_refresh_interval = timedelta(minutes=5)
        self.health_check_interval = timedelta(minutes=2)
        
        # Lock para operações concorrentes
        self._lock = asyncio.Lock()
        self._shutdown_requested = False
        
        # Tasks em background
        self._health_check_task = None
        self._auto_refresh_task = None
        
        # Criar diretório de perfil
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎭 PersistentSessionManager inicializado")
        logger.info(f"📁 Perfil do navegador: {self.profile_dir}")
        logger.info(f"🍪 Arquivo de cookies: {self.cookie_filepath}")

    async def initialize(self) -> bool:
        """Inicializa a sessão persistente"""
        async with self._lock:
            if self.is_active:
                logger.info("✅ Sessão já está ativa")
                return True
                
            try:
                logger.info("🚀 Inicializando sessão persistente...")
                
                # Inicializar Playwright
                self.playwright = await async_playwright().start()
                
                # Configurações do navegador com stealth
                browser_args = [
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps',
                    '--disable-background-timer-throttling',
                    '--disable-renderer-backgrounding',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-client-side-phishing-detection',
                    '--disable-sync',
                    '--disable-translate',
                    '--hide-scrollbars',
                    '--mute-audio',
                    '--no-zygote',
                    '--disable-ipc-flooding-protection',
                    '--disable-component-update',
                    '--disable-default-apps',
                    '--disable-domain-reliability',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--no-default-browser-check',
                    '--no-first-run',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI,BlinkGenPropertyTrees',
                    '--disable-features=VizDisplayCompositor'
                ]
                
                # Usar contexto persistente
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),
                    headless=True,
                    args=browser_args,
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR',
                    timezone_id='America/Sao_Paulo',
                    extra_http_headers={
                        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Cache-Control': 'no-cache'
                    },
                    ignore_https_errors=True,
                    java_script_enabled=True,
                    bypass_csp=True
                )
                
                # Criar página principal
                if self.context.pages:
                    self.page = self.context.pages[0]
                else:
                    self.page = await self.context.new_page()
                
                # Aplicar stealth com configurações avançadas
                await stealth_async(self.page)
                
                # Configurações adicionais de stealth
                await self.page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined,
                    });
                    
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5],
                    });
                    
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['pt-BR', 'pt', 'en-US', 'en'],
                    });
                    
                    window.chrome = {
                        runtime: {},
                    };
                    
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: () => Promise.resolve({ state: 'granted' }),
                        }),
                    });
                """)
                
                # Carregar cookies existentes
                await self._load_initial_cookies()
                
                # Estabelecer sessão no YouTube
                await self._establish_youtube_session()
                
                # Marcar como ativa
                self.is_active = True
                self.is_healthy = True
                self.session_start_time = datetime.now()
                self.last_activity = datetime.now()
                
                # Iniciar tasks em background
                self._start_background_tasks()
                
                logger.info("✅ Sessão persistente inicializada com sucesso!")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar sessão: {e}")
                await self._cleanup_session()
                return False

    async def _load_initial_cookies(self):
        """Carrega cookies iniciais se existirem"""
        if not os.path.exists(self.cookie_filepath):
            logger.info("📝 Nenhum cookie inicial encontrado")
            return
            
        try:
            cookies = self._parse_netscape_cookies()
            if cookies:
                await self.context.add_cookies(cookies)
                logger.info(f"🍪 {len(cookies)} cookies iniciais carregados")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar cookies iniciais: {e}")

    async def _establish_youtube_session(self):
        """Estabelece e mantém sessão ativa no YouTube"""
        try:
            logger.info("🌐 Estabelecendo sessão no YouTube...")
            
            # Navegar para YouTube
            await self.page.goto("https://www.youtube.com", 
                                 timeout=60000, 
                                 wait_until="domcontentloaded")
            
            # Aguardar carregamento
            await self.page.wait_for_timeout(3000)
            
            # Interações naturais
            await self._simulate_natural_activity()
            
            # Extrair e salvar cookies
            await self._extract_and_save_cookies()
            
            logger.info("✅ Sessão no YouTube estabelecida")
            
        except Exception as e:
            logger.error(f"❌ Erro ao estabelecer sessão no YouTube: {e}")
            raise

    async def _simulate_natural_activity(self):
        """Simula atividade humana natural"""
        try:
            # Scroll suave para baixo
            await self.page.evaluate("window.scrollTo({top: 300, behavior: 'smooth'})")
            await self.page.wait_for_timeout(1500)
            
            # Movimento do mouse
            await self.page.mouse.move(400, 300)
            await self.page.wait_for_timeout(800)
            await self.page.mouse.move(600, 450)
            await self.page.wait_for_timeout(1200)
            
            # Scroll para cima
            await self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            await self.page.wait_for_timeout(1000)
            
            # Hover em elementos
            try:
                # Tentar hover no logo do YouTube
                await self.page.hover('a[href="/"]', timeout=5000)
                await self.page.wait_for_timeout(500)
            except Exception:
                pass
            
            # Movimento final do mouse
            await self.page.mouse.move(500, 350)
            await self.page.wait_for_timeout(1000)
            
        except Exception as e:
            logger.debug(f"Erro em atividade simulada: {e}")

    async def refresh_cookies(self) -> bool:
        """Refresh manual de cookies"""
        async with self._lock:
            if not self.is_active or not self.page:
                logger.warning("⚠️ Sessão não está ativa para refresh")
                return False
                
            try:
                logger.info("🔄 Fazendo refresh de cookies...")
                
                # Reload da página
                await self.page.reload(wait_until="domcontentloaded")
                await self.page.wait_for_timeout(2000)
                
                # Atividade leve
                await self.page.mouse.move(300, 300)
                await self.page.wait_for_timeout(1000)
                
                # Extrair cookies atualizados
                success = await self._extract_and_save_cookies()
                
                if success:
                    self.last_activity = datetime.now()
                    self.last_cookie_update = datetime.now()
                    self.refresh_count += 1
                    logger.info(f"✅ Cookies atualizados (refresh #{self.refresh_count})")
                    return True
                else:
                    logger.warning("⚠️ Falha ao atualizar cookies")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erro no refresh de cookies: {e}")
                return False

    async def light_refresh(self) -> bool:
        """Refresh leve apenas com movimento do mouse"""
        if not self.is_active or not self.page:
            return False
            
        try:
            # Movimento leve do mouse para manter sessão ativa
            await self.page.mouse.move(400, 400)
            await self.page.wait_for_timeout(200)
            await self.page.mouse.move(500, 500)
            
            self.last_activity = datetime.now()
            return True
            
        except Exception as e:
            logger.debug(f"Erro no light refresh: {e}")
            return False

    async def force_refresh(self) -> bool:
        """Refresh forçado com nova navegação"""
        async with self._lock:
            if not self.is_active or not self.page:
                return False
                
            try:
                logger.info("🔄 Fazendo refresh forçado...")
                
                # Nova navegação
                await self.page.goto("https://www.youtube.com", 
                                     timeout=60000, 
                                     wait_until="domcontentloaded")
                
                # Atividade simulada
                await self._simulate_natural_activity()
                
                # Extrair cookies
                success = await self._extract_and_save_cookies()
                
                if success:
                    self.last_activity = datetime.now()
                    self.last_cookie_update = datetime.now()
                    self.refresh_count += 1
                    logger.info("✅ Refresh forçado bem-sucedido")
                    return True
                    
            except Exception as e:
                logger.error(f"❌ Erro no refresh forçado: {e}")
                
            return False

    async def _extract_and_save_cookies(self) -> bool:
        """Extrai e salva cookies da sessão"""
        try:
            # Extrair cookies do contexto
            cookies = await self.context.cookies()
            
            if not cookies:
                logger.warning("⚠️ Nenhum cookie extraído")
                return False
            
            # Filtrar cookies relevantes
            relevant_cookies = [
                cookie for cookie in cookies 
                if any(domain in cookie.get('domain', '') 
                       for domain in ['youtube.com', 'google.com', 'googlevideo.com'])
            ]
            
            if not relevant_cookies:
                logger.warning("⚠️ Nenhum cookie relevante encontrado")
                return False
            
            # Salvar no formato Netscape
            self._write_netscape_cookies(relevant_cookies)
            
            logger.info(f"💾 {len(relevant_cookies)} cookies salvos")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao extrair/salvar cookies: {e}")
            return False

    def _parse_netscape_cookies(self) -> List[Dict]:
        """Parse cookies do formato Netscape"""
        cookies = []
        try:
            with open(self.cookie_filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip().startswith('#') or not line.strip():
                        continue
                    
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
                    
        except Exception as e:
            logger.warning(f"Erro ao fazer parse de cookies: {e}")
            
        return cookies

    def _write_netscape_cookies(self, cookies: List[Dict]):
        """Escreve cookies no formato Netscape"""
        try:
            with open(self.cookie_filepath, 'w', encoding='utf-8') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Gerado por sessão persistente\n")
                f.write(f"# Atualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# Refresh count: {self.refresh_count}\n\n")
                
                for cookie in cookies:
                    domain = cookie.get('domain', '')
                    include_subdomains = "TRUE" if domain.startswith('.') else "FALSE"
                    secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                    expires = int(cookie.get('expires', 0)) if cookie.get('expires', -1) != -1 else 0
                    
                    f.write(
                        f"{domain}\t"
                        f"{include_subdomains}\t"
                        f"{cookie.get('path', '/')}\t"
                        f"{secure}\t"
                        f"{expires}\t"
                        f"{cookie.get('name', '')}\t"
                        f"{cookie.get('value', '')}\n"
                    )
                    
        except Exception as e:
            logger.error(f"Erro ao escrever cookies: {e}")

    def _start_background_tasks(self):
        """Inicia tasks em background"""
        if not self._shutdown_requested:
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._auto_refresh_task = asyncio.create_task(self._auto_refresh_loop())

    async def _health_check_loop(self):
        """Loop de health check em background"""
        logger.info("🔍 Iniciando health check loop...")
        
        while not self._shutdown_requested and self.is_active:
            try:
                await asyncio.sleep(self.health_check_interval.total_seconds())
                
                if self._shutdown_requested:
                    break
                    
                # Verificar saúde da página
                try:
                    await self.page.evaluate("document.title")
                    self.is_healthy = True
                except Exception:
                    logger.warning("⚠️ Página não responde, marcando como não saudável")
                    self.is_healthy = False
                    
                # Verificar se sessão não expirou
                if self.session_start_time:
                    session_age = datetime.now() - self.session_start_time
                    if session_age > self.max_session_duration:
                        logger.warning("⏰ Sessão atingiu idade máxima")
                        await self._renew_session()
                        
            except Exception as e:
                logger.warning(f"⚠️ Erro no health check: {e}")
                await asyncio.sleep(30)  # Aguardar mais em caso de erro

    async def _auto_refresh_loop(self):
        """Loop de refresh automático de cookies"""
        logger.info("🔄 Iniciando auto-refresh loop...")
        
        while not self._shutdown_requested and self.is_active:
            try:
                await asyncio.sleep(self.cookie_refresh_interval.total_seconds())
                
                if self._shutdown_requested:
                    break
                    
                # Refresh automático de cookies
                if self.is_healthy:
                    await self.refresh_cookies()
                else:
                    logger.warning("⚠️ Pulando refresh automático - sessão não saudável")
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro no auto-refresh: {e}")
                await asyncio.sleep(60)

    async def _renew_session(self) -> bool:
        """Renova completamente a sessão"""
        logger.info("🔄 Renovando sessão...")
        
        await self._cleanup_session()
        await asyncio.sleep(2)
        
        return await self.initialize()

    async def get_session_status(self) -> Dict:
        """Retorna status da sessão"""
        return {
            "is_active": self.is_active,
            "is_healthy": self.is_healthy,
            "session_start_time": self.session_start_time.isoformat() if self.session_start_time else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "last_cookie_update": self.last_cookie_update.isoformat() if self.last_cookie_update else None,
            "refresh_count": self.refresh_count,
            "profile_dir": str(self.profile_dir),
            "session_age_minutes": (
                (datetime.now() - self.session_start_time).total_seconds() / 60
                if self.session_start_time else 0
            )
        }

    async def get_detailed_status(self) -> Dict:
        """Status detalhado com informações extras"""
        basic_status = await self.get_session_status()
        
        # Adicionar informações extras
        basic_status.update({
            "background_tasks": {
                "health_check": self._health_check_task and not self._health_check_task.done(),
                "auto_refresh": self._auto_refresh_task and not self._auto_refresh_task.done()
            },
            "configuration": {
                "max_session_duration_hours": self.max_session_duration.total_seconds() / 3600,
                "cookie_refresh_interval_minutes": self.cookie_refresh_interval.total_seconds() / 60,
                "health_check_interval_minutes": self.health_check_interval.total_seconds() / 60
            },
            "page_info": {
                "url": await self.page.url() if self.page else None,
                "title": await self.page.title() if self.page else None
            } if self.page else {}
        })
        
        return basic_status

    async def _cleanup_session(self):
        """Limpa recursos da sessão"""
        self._shutdown_requested = True
        
        try:
            # Cancelar tasks em background
            if self._health_check_task and not self._health_check_task.done():
                self._health_check_task.cancel()
                
            if self._auto_refresh_task and not self._auto_refresh_task.done():
                self._auto_refresh_task.cancel()
            
            # Fechar página
            if self.page:
                await self.page.close()
                self.page = None
                
            # Fechar contexto
            if self.context:
                await self.context.close()
                self.context = None
                
            # Parar Playwright
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            self.is_active = False
            self.is_healthy = False
            logger.info("🧹 Sessão limpa")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na limpeza da sessão: {e}")

    async def shutdown(self):
        """Shutdown completo do gerenciador"""
        logger.info("🛑 Encerrando gerenciador de sessão persistente...")
        await self._cleanup_session()
