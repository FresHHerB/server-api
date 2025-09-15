import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PersistentSessionService:
    """Serviço para manter uma sessão persistente do YouTube com Playwright"""

    def __init__(self, cookie_filepath: str = "cookies.txt", profile_dir: str = "./browser_profile"):
        self.cookie_filepath = cookie_filepath
        self.profile_dir = Path(profile_dir)
        
        # Componentes da sessão persistente
        self.playwright = None
        self.context: Optional[BrowserContext] = None  # Agora o context é o principal
        self.page: Optional[Page] = None
        
        # Status da sessão
        self.is_active = False
        self.last_activity = None
        self.session_start_time = None
        self.cookie_refresh_count = 0
        
        # Configurações
        self.max_session_duration = timedelta(hours=12)  # Renovar sessão a cada 12h
        self.activity_timeout = timedelta(minutes=30)    # Timeout de inatividade
        
        # Lock para operações concorrentes
        self._lock = asyncio.Lock()
        
        # Criar diretório de perfil
        self.profile_dir.mkdir(exist_ok=True)
        
    async def initialize_session(self) -> bool:
        """Inicializa a sessão persistente do Playwright"""
        async with self._lock:
            if self.is_active:
                logger.info("✅ Sessão já está ativa")
                return True
                
            try:
                logger.info("🚀 Inicializando sessão persistente do Playwright...")
                
                # Inicializar Playwright
                self.playwright = await async_playwright().start()
                
                # Configurações do navegador (sem --user-data-dir nos args)
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
                    # Não incluir --user-data-dir aqui!
                ]
                
                # Usar launch_persistent_context em vez de launch + new_context
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.profile_dir),  # Aqui é o lugar correto
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
                        'Cache-Control': 'max-age=0'
                    }
                )
                
                # Carregar cookies existentes se houver
                await self._load_initial_cookies()
                
                # Criar página
                self.page = await self.context.new_page()
                
                # Aplicar scripts stealth
                await self._apply_stealth_scripts()
                
                # Navegar para YouTube e estabelecer sessão
                await self._establish_youtube_session()
                
                # Marcar como ativa
                self.is_active = True
                self.session_start_time = datetime.now()
                self.last_activity = datetime.now()
                
                logger.info("✅ Sessão persistente inicializada com sucesso!")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar sessão persistente: {e}")
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
    
    async def _apply_stealth_scripts(self):
        """Aplica scripts para tornar o navegador mais stealth"""
        stealth_scripts = [
            # Remover webdriver property
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            """,
            # Mock chrome property
            """
            window.chrome = {
                runtime: {},
                app: {
                    isInstalled: false,
                },
            };
            """,
            # Mock plugins
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            """,
            # Mock languages
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en'],
            });
            """,
        ]
        
        for script in stealth_scripts:
            try:
                await self.page.evaluate(script)
            except Exception as e:
                logger.debug(f"Erro ao aplicar script stealth: {e}")
    
    async def _establish_youtube_session(self):
        """Estabelece sessão inicial no YouTube"""
        try:
            logger.info("🌐 Estabelecendo sessão no YouTube...")
            
            # Navegar para YouTube
            await self.page.goto("https://www.youtube.com", timeout=60000, wait_until="domcontentloaded")
            
            # Aguardar carregamento
            await self.page.wait_for_timeout(3000)
            
            # Fazer interações naturais para estabelecer sessão
            await self._simulate_human_activity()
            
            # Extrair e salvar cookies iniciais da sessão
            await self._extract_and_save_cookies()
            
            logger.info("✅ Sessão no YouTube estabelecida")
            
        except Exception as e:
            logger.error(f"❌ Erro ao estabelecer sessão no YouTube: {e}")
            raise
    
    async def _simulate_human_activity(self):
        """Simula atividade humana natural"""
        try:
            # Scroll suave
            await self.page.evaluate("window.scrollTo({top: 300, behavior: 'smooth'})")
            await self.page.wait_for_timeout(1000)
            
            # Movimento do mouse
            await self.page.mouse.move(400, 300)
            await self.page.wait_for_timeout(500)
            await self.page.mouse.move(600, 400)
            await self.page.wait_for_timeout(1000)
            
            # Scroll de volta
            await self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            await self.page.wait_for_timeout(2000)
            
            # Pequeno movimento final
            await self.page.mouse.move(500, 350)
            await self.page.wait_for_timeout(1000)
            
        except Exception as e:
            logger.debug(f"Erro em atividade simulada: {e}")
    
    async def refresh_session_cookies(self) -> bool:
        """Atualiza os cookies da sessão ativa"""
        async with self._lock:
            if not self.is_active or not self.page:
                logger.warning("⚠️ Sessão não está ativa para refresh")
                return False
                
            try:
                logger.info("🔄 Atualizando cookies da sessão ativa...")
                
                # Navegar novamente (refresh da página)
                await self.page.reload(wait_until="domcontentloaded")
                await self.page.wait_for_timeout(2000)
                
                # Atividade humana leve
                await self.page.mouse.move(300, 300)
                await self.page.wait_for_timeout(1000)
                
                # Extrair cookies atualizados
                success = await self._extract_and_save_cookies()
                
                if success:
                    self.last_activity = datetime.now()
                    self.cookie_refresh_count += 1
                    logger.info(f"✅ Cookies atualizados (refresh #{self.cookie_refresh_count})")
                    return True
                else:
                    logger.warning("⚠️ Falha ao atualizar cookies")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Erro ao atualizar cookies da sessão: {e}")
                return False
    
    async def _extract_and_save_cookies(self) -> bool:
        """Extrai cookies da sessão ativa e salva no arquivo"""
        try:
            # Extrair cookies do contexto
            cookies = await self.context.cookies()
            
            if not cookies:
                logger.warning("⚠️ Nenhum cookie extraído da sessão")
                return False
            
            # Filtrar apenas cookies relevantes
            filtered_cookies = [
                cookie for cookie in cookies 
                if any(domain in cookie.get('domain', '') 
                       for domain in ['youtube.com', 'google.com', 'googlevideo.com'])
            ]
            
            if not filtered_cookies:
                logger.warning("⚠️ Nenhum cookie relevante encontrado")
                return False
            
            # Salvar no formato Netscape
            self._write_netscape_cookies(filtered_cookies)
            
            logger.info(f"💾 {len(filtered_cookies)} cookies salvos da sessão ativa")
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
                f.write(f"# Atualizado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
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
    
    async def health_check(self) -> bool:
        """Verifica se a sessão está saudável"""
        if not self.is_active or not self.page:
            return False
            
        try:
            # Verificar se a página responde
            await self.page.evaluate("document.title")
            
            # Verificar se não ultrapassou o tempo máximo de sessão
            if self.session_start_time:
                session_age = datetime.now() - self.session_start_time
                if session_age > self.max_session_duration:
                    logger.info("⏰ Sessão atingiu idade máxima, precisa renovar")
                    return False
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Health check falhou: {e}")
            return False
    
    async def renew_session(self) -> bool:
        """Renova a sessão completamente"""
        logger.info("🔄 Renovando sessão persistente...")
        
        await self._cleanup_session()
        await asyncio.sleep(2)  # Pequeno delay
        
        return await self.initialize_session()
    
    async def _cleanup_session(self):
        """Limpa recursos da sessão"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
                
            if self.context:
                await self.context.close()
                self.context = None
                
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
                
            self.is_active = False
            logger.info("🧹 Sessão limpa")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na limpeza da sessão: {e}")
    
    async def shutdown(self):
        """Encerra a sessão persistente"""
        logger.info("🛑 Encerrando sessão persistente...")
        await self._cleanup_session()
        
    def get_session_status(self) -> Dict:
        """Retorna status da sessão"""
        return {
            "is_active": self.is_active,
            "session_start_time": self.session_start_time.isoformat() if self.session_start_time else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "cookie_refresh_count": self.cookie_refresh_count,
            "profile_dir": str(self.profile_dir),
            "session_age_minutes": (
                (datetime.now() - self.session_start_time).total_seconds() / 60
                if self.session_start_time else 0
            )
        }
