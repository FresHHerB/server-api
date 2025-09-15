import os
import asyncio
import logging
import random
from pathlib import Path
from typing import Optional, Dict, List
from playwright.async_api import async_playwright, BrowserContext, Page, Browser
from playwright_stealth import stealth_async
from fake_useragent import UserAgent
import time
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class PersistentSessionManager:
    """Gerenciador de sessão persistente otimizado para playwright-stealth"""

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
        
        # Status da sessão
        self.is_active = False
        self.is_healthy = False
        self.session_start_time = None
        self.last_activity = None
        self.last_cookie_update = None
        self.refresh_count = 0
        
        # User agent rotator
        self.ua = UserAgent()
        self.current_user_agent = self.ua.chrome
        
        # Lock para operações concorrentes
        self._lock = asyncio.Lock()
        self._shutdown_requested = False
        
        # Criar diretório de perfil
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"🎭 PersistentSessionManager inicializado (stealth otimizado)")
        logger.info(f"📁 Perfil do navegador: {self.profile_dir}")
        logger.info(f"🍪 Arquivo de cookies: {self.cookie_filepath}")

    async def initialize(self) -> bool:
        """Inicializa a sessão persistente com playwright-stealth"""
        async with self._lock:
            if self.is_active:
                logger.info("✅ Sessão já está ativa")
                return True
                
            try:
                logger.info("🚀 Inicializando sessão stealth persistente...")
                
                # Inicializar Playwright
                self.playwright = await async_playwright().start()
                
                # User agent dinâmico
                self.current_user_agent = self.ua.chrome
                logger.info(f"🎭 User-Agent: {self.current_user_agent}")
                
                # Argumentos otimizados para stealth
                stealth_args = self._get_stealth_args()
                
                # Usar browser normal (não persistent context para melhor controle)
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=stealth_args,
                    slow_mo=random.randint(50, 150),  # Humanizar timing
                    chromium_sandbox=False
                )
                
                # Criar contexto com stealth settings
                self.context = await self.browser.new_context(
                    user_agent=self.current_user_agent,
                    viewport={'width': 1920, 'height': 1080},
                    locale='pt-BR',
                    timezone_id='America/Sao_Paulo',
                    permissions=['geolocation'],
                    geolocation={'latitude': -23.5505, 'longitude': -46.6333},  # São Paulo
                    color_scheme='light',
                    reduced_motion='reduce',
                    forced_colors='none',
                    extra_http_headers={
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8,en-US;q=0.7',
                        'Accept-Encoding': 'gzip, deflate, br',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-User': '?1',
                        'sec-ch-ua': '"Google Chrome";v="120", "Chromium";v="120", "Not_A Brand";v="99"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"'
                    }
                )
                
                # Criar página principal
                self.page = await self.context.new_page()
                
                # Aplicar stealth avançado
                await self._apply_advanced_stealth()
                
                # Carregar cookies existentes
                await self._load_initial_cookies()
                
                # Estabelecer sessão no YouTube
                await self._establish_youtube_session()
                
                # Marcar como ativa
                self.is_active = True
                self.is_healthy = True
                self.session_start_time = datetime.now()
                self.last_activity = datetime.now()
                
                logger.info("✅ Sessão persistente stealth inicializada com sucesso!")
                logger.info("🔒 Navegador configurado para NUNCA fechar")
                return True
                
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar sessão stealth: {e}")
                await self._cleanup_session()
                return False

    def _get_stealth_args(self) -> List[str]:
        """Argumentos otimizados para stealth máximo"""
        return [
            # Segurança
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            
            # Anti-detecção core
            '--disable-blink-features=AutomationControlled',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--disable-ipc-flooding-protection',
            
            # GPU e renderização
            '--disable-gpu',
            '--disable-software-rasterizer', 
            '--disable-gpu-sandbox',
            '--use-gl=swiftshader',
            
            # Stealth específico
            '--disable-extensions',
            '--disable-extensions-file-access-check',
            '--disable-extensions-http-throttling',
            '--disable-component-extensions-with-background-pages',
            '--disable-default-apps',
            '--disable-sync',
            '--disable-translate',
            '--disable-background-networking',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows',
            '--disable-client-side-phishing-detection',
            '--disable-component-update',
            '--disable-domain-reliability',
            '--disable-features=TranslateUI,BlinkGenPropertyTrees',
            
            # Performance e recursos
            '--memory-pressure-off',
            '--max_old_space_size=4096',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-hang-monitor',
            '--disable-prompt-on-repost',
            '--disable-popup-blocking',
            
            # Audio/Video
            '--mute-audio',
            '--disable-audio-output',
            
            # Logging e crash (SOLUÇÃO DEFINITIVA)
            '--disable-logging',
            '--disable-crashpad',
            '--disable-crash-reporter',
            '--disable-breakpad',
            '--no-crash-upload',
            '--log-level=3',
            '--silent',
            
            # Flags adicionais de stealth
            '--disable-infobars',
            '--disable-dev-tools',
            '--disable-remote-fonts',
            '--disable-shared-workers',
            '--disable-speech-api',
            '--disable-file-system',
            '--disable-presentation-api',
            '--disable-permissions-api',
            '--disable-new-zip-unpacker',
            '--disable-media-session-api',
            '--disable-notifications',
            '--autoplay-policy=no-user-gesture-required'
        ]

    async def _apply_advanced_stealth(self):
        """Aplicar stealth avançado e personalizado"""
        try:
            # Aplicar playwright-stealth básico
            await stealth_async(self.page)
            
            # Scripts avançados de stealth
            await self.page.add_init_script("""
                // Override navigator properties
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer'},
                        {name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
                        {name: 'Native Client', description: '', filename: 'internal-nacl-plugin'}
                    ],
                    configurable: true
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['pt-BR', 'pt', 'en-US', 'en'],
                    configurable: true
                });
                
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => Math.max(2, Math.floor(Math.random() * 8) + 1),
                    configurable: true
                });
                
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => Math.pow(2, Math.floor(Math.random() * 3) + 2),
                    configurable: true
                });
                
                // Chrome runtime object
                window.chrome = {
                    runtime: {
                        onConnect: undefined,
                        onMessage: undefined
                    },
                    csi: () => ({}),
                    loadTimes: () => ({
                        commitLoadTime: Date.now() / 1000 - Math.random() * 100,
                        connectionInfo: 'h2',
                        finishDocumentLoadTime: Date.now() / 1000 - Math.random() * 50,
                        finishLoadTime: Date.now() / 1000 - Math.random() * 30,
                        firstPaintAfterLoadTime: 0,
                        firstPaintTime: Date.now() / 1000 - Math.random() * 80,
                        navigationType: 'Other',
                        npnNegotiatedProtocol: 'h2',
                        requestTime: Date.now() / 1000 - Math.random() * 120,
                        startLoadTime: Date.now() / 1000 - Math.random() * 110,
                        wasAlternateProtocolAvailable: false,
                        wasFetchedViaSpdy: true,
                        wasNpnNegotiated: true
                    })
                };
                
                // Permissions API mock
                Object.defineProperty(navigator, 'permissions', {
                    get: () => ({
                        query: (params) => Promise.resolve({
                            state: Math.random() > 0.5 ? 'granted' : 'prompt',
                            name: params.name
                        })
                    }),
                    configurable: true
                });
                
                // Battery API mock
                Object.defineProperty(navigator, 'getBattery', {
                    get: () => () => Promise.resolve({
                        charging: Math.random() > 0.5,
                        chargingTime: Math.random() * 10000,
                        dischargingTime: Math.random() * 20000,
                        level: Math.random()
                    }),
                    configurable: true
                });
                
                // WebGL fingerprint protection
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Intel Inc.';
                    if (parameter === 37446) return 'Intel(R) Iris(TM) Graphics 6100';
                    return getParameter.call(this, parameter);
                };
                
                // Canvas fingerprint protection
                const toDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function() {
                    const noise = Math.random() * 0.0001;
                    const context = this.getContext('2d');
                    const originalData = context.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < originalData.data.length; i += 4) {
                        originalData.data[i] += noise;
                    }
                    context.putImageData(originalData, 0, 0);
                    return toDataURL.call(this);
                };
                
                // Remove automation indicators
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Proxy;
            """)
            
            logger.info("🥷 Stealth avançado aplicado com sucesso")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao aplicar stealth avançado: {e}")

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
        """Estabelece sessão stealth no YouTube"""
        try:
            logger.info("🌐 Estabelecendo sessão stealth no YouTube...")
            
            # Navegação com timing humanizado
            await self.page.goto("https://www.youtube.com", 
                                 timeout=60000, 
                                 wait_until="domcontentloaded")
            
            # Aguardar carregamento natural
            await asyncio.sleep(random.uniform(2, 4))
            
            # Simular comportamento humano
            await self._simulate_human_behavior()
            
            # Extrair e salvar cookies
            await self._extract_and_save_cookies()
            
            logger.info("✅ Sessão stealth no YouTube estabelecida")
            
        except Exception as e:
            logger.error(f"❌ Erro ao estabelecer sessão stealth no YouTube: {e}")
            raise

    async def _simulate_human_behavior(self):
        """Simula comportamento humano avançado"""
        try:
            # Movimento natural do mouse
            for _ in range(random.randint(2, 4)):
                x = random.randint(100, 1820)
                y = random.randint(100, 980)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            # Scroll natural
            scroll_amount = random.randint(200, 600)
            await self.page.evaluate(f"window.scrollTo({{top: {scroll_amount}, behavior: 'smooth'}})")
            await asyncio.sleep(random.uniform(1, 2))
            
            # Voltar ao topo
            await self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            await asyncio.sleep(random.uniform(0.5, 1))
            
            # Hover em elementos se existirem
            try:
                await self.page.hover('ytd-masthead', timeout=5000)
                await asyncio.sleep(random.uniform(0.3, 0.8))
            except:
                pass
                
            # Movimento final aleatório
            final_x = random.randint(400, 1520)
            final_y = random.randint(300, 780)
            await self.page.mouse.move(final_x, final_y)
            
            logger.debug("🎭 Comportamento humano simulado")
            
        except Exception as e:
            logger.debug(f"Erro na simulação humana: {e}")

    async def refresh_cookies(self) -> bool:
        """Refresh inteligente de cookies com stealth"""
        if not self.is_active or not self.page:
            logger.warning("⚠️ Sessão não está ativa para refresh")
            return False
            
        try:
            logger.info("🔄 Refresh stealth de cookies...")
            
            # User agent rotation ocasional
            if random.random() < 0.3:  # 30% chance
                await self._rotate_user_agent()
            
            # Navegação para YouTube
            await self.page.goto("https://www.youtube.com", 
                                 timeout=45000, 
                                 wait_until="domcontentloaded")
            
            # Timing humanizado
            await asyncio.sleep(random.uniform(1.5, 3))
            
            # Comportamento humano leve
            await self._simulate_human_behavior()
            
            # Extrair cookies
            success = await self._extract_and_save_cookies()
            
            if success:
                self.last_activity = datetime.now()
                self.last_cookie_update = datetime.now()
                self.refresh_count += 1
                logger.info(f"✅ Cookies stealth atualizados (#{self.refresh_count})")
                return True
            else:
                logger.warning("⚠️ Falha ao extrair cookies")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro no refresh stealth: {e}")
            return False

    async def _rotate_user_agent(self):
        """Rotaciona user agent ocasionalmente"""
        try:
            new_ua = self.ua.chrome
            if new_ua != self.current_user_agent:
                self.current_user_agent = new_ua
                await self.page.set_extra_http_headers({'User-Agent': new_ua})
                logger.debug(f"🔄 User-Agent rotacionado: {new_ua[:50]}...")
        except Exception as e:
            logger.debug(f"Erro na rotação de UA: {e}")

    async def force_refresh(self) -> bool:
        """Refresh forçado com stealth avançado"""
        if not self.is_active or not self.page:
            return False
            
        try:
            logger.info("🔄 Refresh forçado stealth...")
            
            # Limpar cache e cookies antigos
            await self.context.clear_cookies()
            
            # Recarregar cookies do arquivo
            await self._load_initial_cookies()
            
            # Navegação com stealth
            await self.page.goto("https://www.youtube.com", 
                                 timeout=60000, 
                                 wait_until="domcontentloaded")
            
            await asyncio.sleep(random.uniform(2, 4))
            
            # Comportamento humano mais elaborado
            await self._simulate_human_behavior()
            
            # Nova extração
            success = await self._extract_and_save_cookies()
            
            if success:
                self.last_activity = datetime.now()
                self.last_cookie_update = datetime.now()
                self.refresh_count += 1
                logger.info(f"✅ Refresh forçado stealth #{self.refresh_count}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Erro no refresh forçado stealth: {e}")
            
        return False

    async def light_refresh(self) -> bool:
        """Refresh leve apenas para manter atividade"""
        if not self.is_active or not self.page:
            return False
            
        try:
            # Movimento leve do mouse
            x = random.randint(200, 1720)
            y = random.randint(200, 880)
            await self.page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
            self.last_activity = datetime.now()
            return True
            
        except Exception as e:
            logger.debug(f"Erro no light refresh: {e}")
            return False

    async def _extract_and_save_cookies(self) -> bool:
        """Extrai e salva cookies com preservação inteligente"""
        try:
            cookies = await self.context.cookies()
            
            if not cookies:
                logger.warning("⚠️ Nenhum cookie extraído")
                return False
            
            # Filtrar cookies relevantes
            relevant_cookies = [
                cookie for cookie in cookies 
                if any(domain in cookie.get('domain', '') 
                       for domain in ['youtube.com', 'google.com', 'googlevideo.com', 'googleusercontent.com'])
            ]
            
            if not relevant_cookies:
                logger.warning("⚠️ Nenhum cookie relevante encontrado")
                return False
            
            # Salvar no formato Netscape otimizado
            self._write_netscape_cookies(relevant_cookies)
            
            logger.info(f"💾 {len(relevant_cookies)} cookies stealth salvos")
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
        """Escreve cookies no formato Netscape com preservação inteligente"""
        try:
            # Preservar cookies importantes existentes
            important_cookies = {}
            if os.path.exists(self.cookie_filepath):
                try:
                    with open(self.cookie_filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip().startswith('#') or not line.strip():
                                continue
                            parts = line.strip().split('\t')
                            if len(parts) == 7:
                                domain, _, _, _, _, name, value = parts
                                if name in ['LOGIN_INFO', 'SID', '__Secure-1PSID', '__Secure-3PSID', 
                                          'SAPISID', '__Secure-1PAPISID', '__Secure-3PAPISID', 'HSID', 'SSID', 'APISID']:
                                    important_cookies[f"{domain}:{name}"] = line.strip()
                except Exception as e:
                    logger.debug(f"Erro ao ler cookies existentes: {e}")
            
            with open(self.cookie_filepath, 'w', encoding='utf-8') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# http://curl.haxx.se/rfc/cookie_spec.html\n") 
                f.write("# This is a generated file!  Do not edit.\n\n")
                
                # Cookies processados
                written_cookies = set()
                
                # Primeiro: cookies importantes preservados
                for cookie_line in important_cookies.values():
                    f.write(cookie_line + "\n")
                    parts = cookie_line.split('\t')
                    if len(parts) >= 6:
                        written_cookies.add(f"{parts[0]}:{parts[5]}")
                
                # Segundo: cookies novos (evitar duplicatas)
                for cookie in cookies:
                    domain = cookie.get('domain', '')
                    name = cookie.get('name', '')
                    cookie_key = f"{domain}:{name}"
                    
                    if cookie_key not in written_cookies:
                        include_subdomains = "TRUE" if domain.startswith('.') else "FALSE"
                        secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                        expires = cookie.get('expires', 0)
                        if expires == -1 or expires is None:
                            expires = 0
                        else:
                            expires = int(expires)
                        
                        cookie_line = (
                            f"{domain}\t"
                            f"{include_subdomains}\t"
                            f"{cookie.get('path', '/')}\t"
                            f"{secure}\t"
                            f"{expires}\t"
                            f"{name}\t"
                            f"{cookie.get('value', '')}"
                        )
                        
                        f.write(cookie_line + "\n")
                        written_cookies.add(cookie_key)
                
                logger.info(f"💾 {len(written_cookies)} cookies únicos salvos")
                    
        except Exception as e:
            logger.error(f"Erro ao escrever cookies: {e}")

    async def get_session_status(self) -> Dict:
        """Retorna status da sessão stealth"""
        return {
            "is_active": self.is_active,
            "is_healthy": self.is_healthy,
            "session_start_time": self.session_start_time.isoformat() if self.session_start_time else None,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "last_cookie_update": self.last_cookie_update.isoformat() if self.last_cookie_update else None,
            "refresh_count": self.refresh_count,
            "current_user_agent": self.current_user_agent,
            "session_age_minutes": (
                (datetime.now() - self.session_start_time).total_seconds() / 60
                if self.session_start_time else 0
            ),
            "stealth_mode": "advanced"
        }

    async def get_detailed_status(self) -> Dict:
        """Status detalhado da sessão stealth"""
        basic_status = await self.get_session_status()
        
        try:
            basic_status.update({
                "page_info": {
                    "url": await self.page.url() if self.page else None,
                    "title": await self.page.title() if self.page else None
                } if self.page else {},
                "stealth_features": {
                    "user_agent_rotation": True,
                    "fingerprint_protection": True,
                    "automation_detection_bypass": True,
                    "human_behavior_simulation": True
                }
            })
        except Exception as e:
            logger.debug(f"Erro ao obter status detalhado: {e}")
        
        return basic_status

    async def _cleanup_session(self):
        """Limpa recursos da sessão"""
        self._shutdown_requested = True
        
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
            self.is_healthy = False
            logger.info("🧹 Sessão stealth limpa")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro na limpeza da sessão: {e}")

    async def shutdown(self):
        """Shutdown - mantém navegador até fim do container"""
        logger.info("🛑 Shutdown solicitado - navegador stealth permanece ativo")
        # Não chama cleanup para manter navegador aberto