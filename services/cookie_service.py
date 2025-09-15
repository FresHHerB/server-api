import os
import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CookieService:
    """Serviço para gerenciar e atualizar cookies do YouTube usando Playwright"""

    def __init__(self, cookie_filepath: str = "cookies.txt"):
        self.cookie_filepath = cookie_filepath
        self.last_update = None
        self.update_interval = timedelta(minutes=30)  # Atualizar a cada 30 minutos
        self._lock = asyncio.Lock()  # Para evitar múltiplas atualizações simultâneas
        
        # Cookies críticos que DEVEM ser preservados
        self.critical_cookies = {
            'SID', 'HSID', 'SSID', 'APISID', 'SAPISID', 
            '__Secure-1PAPISID', '__Secure-3PAPISID',
            '__Secure-1PSID', '__Secure-3PSID', 'LOGIN_INFO',
            '__Secure-1PSIDTS', '__Secure-3PSIDTS',
            '__Secure-1PSIDCC', '__Secure-3PSIDCC'
        }

    def parse_netscape_cookies(self, file_path: str) -> List[Dict]:
        """
        Lê um arquivo de cookies no formato Netscape e o converte para o formato que o Playwright espera.
        """
        if not os.path.exists(file_path):
            logger.warning(f"Arquivo de cookies não encontrado em '{file_path}'")
            return []

        cookies = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Ignora linhas de comentário e linhas vazias
                    if line.strip().startswith('#') or not line.strip():
                        continue

                    try:
                        # O formato Netscape tem 7 colunas separadas por tabulação
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
                            "httpOnly": False,  # O formato Netscape não especifica httpOnly
                            "secure": secure.lower() == 'true',
                            "sameSite": "Lax"  # Valor padrão seguro
                        })
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Linha mal formatada ignorada: {line.strip()} - {e}")
                        continue

        except Exception as e:
            logger.error(f"Erro ao ler arquivo de cookies: {e}")
            return []

        logger.info(f"✅ {len(cookies)} cookies carregados de '{file_path}'")
        return cookies

    def merge_cookies(self, original_cookies: List[Dict], new_cookies: List[Dict]) -> List[Dict]:
        """
        Mescla cookies antigos e novos, preservando cookies críticos.
        """
        # Criar mapa de cookies existentes por nome+domínio
        original_map = {(c['name'], c['domain']): c for c in original_cookies}
        new_map = {(c['name'], c['domain']): c for c in new_cookies}
        
        # Começar com todos os cookies novos
        merged = {}
        for key, cookie in new_map.items():
            merged[key] = cookie
        
        # Preservar cookies críticos que podem ter sido perdidos
        critical_preserved = 0
        for key, cookie in original_map.items():
            cookie_name = cookie['name']
            
            # Se é um cookie crítico e não está nos novos cookies, preservar
            if cookie_name in self.critical_cookies and key not in new_map:
                # Verificar se o cookie não expirou
                expires = cookie.get('expires', -1)
                if expires == -1 or expires > time.time():
                    merged[key] = cookie
                    critical_preserved += 1
                    logger.info(f"🔒 Cookie crítico preservado: {cookie_name}")
        
        if critical_preserved > 0:
            logger.info(f"🛡️ {critical_preserved} cookies críticos preservados da sessão anterior")
        
        return list(merged.values())

    def write_netscape_cookies(self, file_path: str, cookies_from_playwright: List[Dict]):
        """
        Converte os cookies do formato Playwright de volta para o formato Netscape e os salva em um arquivo.
        """
        try:
            # Ler cookies originais para mesclagem
            original_cookies = self.parse_netscape_cookies(file_path)
            
            # Mesclar cookies preservando os críticos
            merged_cookies = self.merge_cookies(original_cookies, cookies_from_playwright)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# Gerado automaticamente pela API de Transcrição\n")
                f.write(f"# Atualizado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                for cookie in merged_cookies:
                    # Filtrar apenas cookies do YouTube/Google
                    domain = cookie.get('domain', '')
                    if not any(target in domain for target in ['youtube.com', 'google.com', 'googlevideo.com']):
                        continue

                    # Converte os valores booleanos de volta para string
                    include_subdomains = "TRUE" if domain.startswith('.') else "FALSE"
                    secure = "TRUE" if cookie.get('secure', False) else "FALSE"

                    # O timestamp de expiração. Se for -1 (sessão), usar 0
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

            logger.info(f"💾 Cookies atualizados salvos em '{file_path}' ({len(merged_cookies)} total)")
            
        except Exception as e:
            logger.error(f"Erro ao salvar cookies: {e}")
            raise Exception(f"Falha ao salvar cookies: {e}")

    async def needs_update(self) -> bool:
        """
        Verifica se os cookies precisam ser atualizados baseado no tempo desde a última atualização.
        """
        if self.last_update is None:
            return True
        
        return datetime.now() - self.last_update > self.update_interval

    async def update_cookies(self, force: bool = False) -> bool:
        """
        Atualiza os cookies do YouTube usando Playwright com melhor stealth.
        
        Args:
            force: Se True, força a atualização mesmo se ainda não passou o intervalo
            
        Returns:
            bool: True se os cookies foram atualizados, False caso contrário
        """
        async with self._lock:
            # Verifica se precisa atualizar (a menos que seja forçado)
            if not force and not await self.needs_update():
                logger.info("⏭️ Cookies ainda são recentes, pulando atualização")
                return False

            logger.info("🔄 Iniciando atualização de cookies do YouTube...")

            # Ler cookies existentes
            initial_cookies = self.parse_netscape_cookies(self.cookie_filepath)
            if not initial_cookies:
                logger.warning("⚠️ Nenhum cookie inicial encontrado. Tentando sem cookies...")

            try:
                async with async_playwright() as p:
                    # Configurações mais stealth para o navegador
                    browser = await p.chromium.launch(
                        headless=True,
                        args=[
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
                            '--disable-backgrounding-occluded-windows'
                        ]
                    )
                    
                    # Context com configurações mais realistas
                    context = await browser.new_context(
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

                    # Adicionar cookies existentes ao contexto
                    if initial_cookies:
                        try:
                            await context.add_cookies(initial_cookies)
                            logger.info("🍪 Cookies existentes injetados no navegador")
                        except Exception as e:
                            logger.warning(f"⚠️ Erro ao injetar cookies: {e}")

                    page = await context.new_page()

                    # Remover webdriver property para ser mais stealth
                    await page.evaluate("""
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined,
                        });
                    """)

                    # Acessar YouTube de forma mais natural
                    logger.info("➡️ Acessando https://www.youtube.com...")
                    try:
                        await page.goto("https://www.youtube.com", timeout=60000, wait_until="domcontentloaded")
                        
                        # Aguardar a página carregar e fazer interações mais naturais
                        logger.info("⏳ Aguardando a página carregar e simulando atividade...")
                        await page.wait_for_timeout(3000)  # 3 segundos
                        
                        # Interações mais naturais para parecer humano
                        try:
                            # Scroll suave
                            await page.evaluate("window.scrollTo(0, 200)")
                            await page.wait_for_timeout(1000)
                            await page.evaluate("window.scrollTo(0, 0)")
                            await page.wait_for_timeout(2000)
                            
                            # Movimento do mouse mais natural
                            await page.mouse.move(300, 300)
                            await page.wait_for_timeout(500)
                            await page.mouse.move(600, 400)
                            await page.wait_for_timeout(2000)
                            
                        except Exception as e:
                            logger.debug(f"Interações opcionais falharam: {e}")

                        # Aguardar mais tempo para sessão se estabilizar
                        await page.wait_for_timeout(5000)

                    except Exception as e:
                        logger.error(f"❌ Erro ao acessar o YouTube: {e}")
                        await browser.close()
                        return False

                    # Coletar cookies atualizados
                    updated_cookies = await context.cookies()
                    logger.info(f"🔄 {len(updated_cookies)} cookies coletados do navegador")

                    # Fechar navegador
                    await browser.close()

                    # Salvar novos cookies (com mesclagem inteligente)
                    if updated_cookies:
                        self.write_netscape_cookies(self.cookie_filepath, updated_cookies)
                        self.last_update = datetime.now()
                        logger.info("✅ Cookies atualizados com sucesso!")
                        return True
                    else:
                        logger.warning("⚠️ Nenhum cookie foi coletado")
                        return False

            except Exception as e:
                logger.error(f"❌ Erro durante atualização de cookies: {e}")
                return False

    async def ensure_fresh_cookies(self) -> bool:
        """
        Garante que os cookies estão frescos, atualizando se necessário.
        
        Returns:
            bool: True se os cookies estão frescos (atualizados ou ainda válidos)
        """
        try:
            if await self.needs_update():
                logger.info("🔄 Cookies precisam ser atualizados")
                return await self.update_cookies()
            else:
                logger.info("✅ Cookies ainda são válidos")
                return True
        except Exception as e:
            logger.error(f"❌ Erro ao verificar/atualizar cookies: {e}")
            return False

    def get_cookie_status(self) -> Dict:
        """
        Retorna informações sobre o status dos cookies.
        
        Returns:
            Dict: Informações sobre os cookies
        """
        cookie_exists = os.path.exists(self.cookie_filepath)
        cookie_count = 0
        critical_count = 0
        
        if cookie_exists:
            cookies = self.parse_netscape_cookies(self.cookie_filepath)
            cookie_count = len(cookies)
            
            # Contar cookies críticos
            for cookie in cookies:
                if cookie['name'] in self.critical_cookies:
                    critical_count += 1
        
        # Verificação síncrona se precisa atualizar
        needs_update = True
        if self.last_update is not None:
            needs_update = datetime.now() - self.last_update > self.update_interval
        
        return {
            "cookie_file_exists": cookie_exists,
            "cookie_count": cookie_count,
            "critical_cookies_count": critical_count,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "needs_update": needs_update,
            "cookie_file_path": self.cookie_filepath
        }
