import os
import asyncio
import logging
import tempfile
import uuid
from typing import Tuple, Optional, Dict
import yt_dlp
from pathlib import Path
import time
import random

logger = logging.getLogger(__name__)

class YouTubeService:
    """Serviço para baixar áudios de vídeos do YouTube com sessão persistente"""

    def __init__(self, session_manager=None, cookies_path: str = "cookies.txt"):
        """
        Inicializa o serviço.

        Args:
            session_manager: Instância do PersistentSessionManager
            cookies_path: Caminho para o arquivo de cookies
        """
        self.temp_dir = tempfile.mkdtemp()
        self.cookies_path = cookies_path
        self.session_manager = session_manager
        self.last_download_time = 0
        self.min_delay_between_downloads = 2
        self.download_count = 0
        
        # Verificar se o arquivo de cookies existe
        if os.path.exists(self.cookies_path):
            logger.info(f"🍪 Arquivo de cookies encontrado: {self.cookies_path}")
        else:
            logger.warning("⚠️ Arquivo de cookies não encontrado")
            
        if self.session_manager:
            logger.info("🎭 YouTubeService integrado com sessão persistente")
        else:
            logger.info("📁 YouTubeService usando modo tradicional")
            
        logger.info(f"📁 Diretório temporário: {self.temp_dir}")

    async def _respect_rate_limit(self):
        """Rate limiting entre downloads"""
        current_time = time.time()
        time_since_last = current_time - self.last_download_time
        
        if time_since_last < self.min_delay_between_downloads:
            sleep_time = self.min_delay_between_downloads - time_since_last
            logger.info(f"⏳ Rate limiting: aguardando {sleep_time:.1f}s...")
            await asyncio.sleep(sleep_time)
        
        self.last_download_time = time.time()

    async def _ensure_session_fresh(self):
        """Garante que a sessão persistente está fresca"""
        if not self.session_manager:
            return True
            
        try:
            # Verificar se sessão está saudável
            session_status = await self.session_manager.get_session_status()
            
            if not session_status.get('is_healthy', False):
                logger.warning("⚠️ Sessão não está saudável, tentando refresh...")
                return await self.session_manager.force_refresh()
            
            # Fazer light refresh para manter ativa
            await self.session_manager.light_refresh()
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao verificar sessão: {e}")
            return False

    def _get_yt_dlp_options(self, unique_id: str, strategy: str = "default", enable_compression: bool = False, speed_up: bool = False) -> dict:
        """
        Retorna opções do yt-dlp otimizadas
        
        Args:
            unique_id: ID único para o arquivo
            strategy: Estratégia (default, mobile, aggressive, stealth)
            enable_compression: Ativa compressão agressiva para reduzir tamanho
            speed_up: Acelera áudio em 2x para reduzir duração
        """
        output_template = os.path.join(self.temp_dir, f'{unique_id}.%(ext)s')
        
        # Definir codec e qualidade baseado na compressão
        if enable_compression:
            # Usar Opus com compressão agressiva para máxima eficiência
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '32',  # Muito baixo para máxima compressão
            }]
            # Argumentos FFmpeg para compressão máxima
            postprocessor_args = [
                '-ar', '16000',  # 16kHz sample rate
                '-ac', '1',      # Mono
                '-c:a', 'libopus',
                '-b:a', '12k',   # Bitrate muito baixo (12kbps)
                '-application', 'voip',  # Otimizado para voz
                '-compression_level', '10',  # Máxima compressão
                '-vbr', 'on',    # Variable bitrate
                '-cutoff', '8000'  # Cortar frequências acima de 8kHz
            ]
            if speed_up:
                # Acelerar áudio em 2x
                postprocessor_args.extend(['-af', 'atempo=2.0'])

        else:
            # Configuração padrão melhorada
            postprocessors = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',  # Reduzido de 192 para 128
            }]
            postprocessor_args = ['-ar', '22050', '-ac', '1']  # Increased from 16kHz
            if speed_up:
                postprocessor_args.extend(['-af', 'atempo=2.0'])

        base_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'postprocessors': postprocessors,
            'postprocessor_args': postprocessor_args,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'retries': 3,
            'retry_sleep': 2,
            'fragment_retries': 5,
            'skip_unavailable_fragments': True,
        }

        if strategy == "mobile":
            # Estratégia mobile otimizada
            base_opts.update({
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'mweb'],
                        'player_skip': ['webpage']
                    }
                },
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            })
        elif strategy == "aggressive":
            # Estratégia agressiva com múltiplos clientes
            base_opts.update({
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web', 'mweb', 'tv_embedded'],
                        'player_skip': ['configs'],
                        'skip': ['hls', 'dash']
                    }
                },
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none'
                }
            })
        elif strategy == "stealth":
            # Estratégia stealth para casos difíceis
            base_opts.update({
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage', 'configs'],
                        'skip': ['hls']
                    }
                },
                'http_headers': {
                    'Accept': '*/*',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'same-origin'
                },
                'sleep_interval': 1,
                'max_sleep_interval': 3
            })
        else:
            # Estratégia padrão otimizada
            base_opts.update({
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage']
                    }
                },
                'http_headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            })

        # Adicionar cookies se disponível
        if os.path.exists(self.cookies_path):
            base_opts['cookiefile'] = self.cookies_path

        return base_opts

    async def _estimate_file_size_and_choose_compression(self, video_url: str) -> tuple[bool, bool]:
        """
        Estima duração do vídeo e decide se usar compressão/aceleração

        Returns:
            tuple: (enable_compression, speed_up)
        """
        try:
            # Extrair info sem baixar
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'skip_download': True
            }

            loop = asyncio.get_event_loop()
            info_dict = await loop.run_in_executor(
                None,
                lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(video_url, download=False)
            )

            duration = info_dict.get('duration', 0)  # em segundos
            if duration == 0:
                logger.warning("⚠️ Duração não detectada, usando compressão padrão")
                return True, False

            # Estimativas aproximadas de tamanho do arquivo:
            # MP3 128kbps mono: ~1MB por minuto
            # Opus 12kbps: ~0.09MB por minuto

            duration_minutes = duration / 60
            estimated_size_mb = duration_minutes * 1.0  # MP3 128kbps mono

            logger.info(f"📊 Duração estimada: {duration_minutes:.1f}min, tamanho estimado: {estimated_size_mb:.1f}MB")

            # Decisão baseada no tamanho estimado
            if estimated_size_mb > 20:  # Muito próximo do limite de 25MB
                logger.info("🔥 Vídeo longo detectado - usando compressão máxima + aceleração 2x")
                return True, True  # Compressão + velocidade 2x
            elif estimated_size_mb > 10:
                logger.info("⚡ Vídeo médio detectado - usando compressão")
                return True, False  # Apenas compressão
            else:
                logger.info("✅ Vídeo curto detectado - configuração padrão")
                return False, False  # Configuração padrão

        except Exception as e:
            logger.warning(f"⚠️ Erro ao estimar tamanho: {e}, usando compressão por segurança")
            return True, False

    async def download_audio(self, video_url: str) -> Tuple[str, str]:
        """
        Baixa áudio com sessão persistente ativa

        Args:
            video_url: URL do vídeo do YouTube

        Returns:
            Tuple[str, str]: (caminho_do_audio, titulo_do_video)

        Raises:
            Exception: Se houver erro no download
        """
        try:
            self.download_count += 1
            logger.info(f"🎬 Iniciando download #{self.download_count}: {video_url}")
            
            # Rate limiting
            await self._respect_rate_limit()

            # Garantir sessão fresca se disponível
            if self.session_manager:
                session_fresh = await self._ensure_session_fresh()
                if session_fresh:
                    logger.info("✅ Sessão persistente verificada/atualizada")
                else:
                    logger.warning("⚠️ Problema com sessão persistente, continuando...")

            # Estimar tamanho e escolher configuração de compressão
            enable_compression, speed_up = await self._estimate_file_size_and_choose_compression(video_url)

            # Estratégias de download em ordem de prioridade
            strategies = ["default", "mobile", "aggressive", "stealth"]
            
            for strategy_index, strategy in enumerate(strategies):
                try:
                    logger.info(f"🎯 Tentativa {strategy_index + 1}/{len(strategies)} - Estratégia: {strategy}")
                    
                    unique_id = str(uuid.uuid4())[:8]
                    # Extensão do arquivo baseada na compressão
                    file_extension = "opus" if enable_compression else "mp3"
                    final_audio_path = os.path.join(self.temp_dir, f"{unique_id}.{file_extension}")
                    ydl_opts = self._get_yt_dlp_options(unique_id, strategy, enable_compression, speed_up)

                    logger.info(f"🔽 Baixando áudio com estratégia '{strategy}'...")

                    # Executar download de forma assíncrona
                    loop = asyncio.get_event_loop()
                    info_dict = await loop.run_in_executor(
                        None, 
                        self._download_with_ytdlp, 
                        video_url, 
                        ydl_opts
                    )

                    video_title = info_dict.get('title', 'Título não encontrado')

                    # Verificar se arquivo foi criado
                    if not os.path.exists(final_audio_path):
                        # Procurar arquivo com extensão diferente
                        for file in os.listdir(self.temp_dir):
                            if file.startswith(unique_id):
                                final_audio_path = os.path.join(self.temp_dir, file)
                                break
                        
                        if not os.path.exists(final_audio_path):
                            raise Exception(f"Arquivo de áudio não foi criado: {final_audio_path}")

                    file_size = os.path.getsize(final_audio_path) / (1024 * 1024)

                    logger.info(f"✅ Download #{self.download_count} bem-sucedido!")
                    logger.info(f"📄 Título: {video_title}")
                    logger.info(f"📊 Tamanho: {file_size:.2f}MB")
                    logger.info(f"🎯 Estratégia: {strategy}")
                    logger.info(f"🗜️ Compressão: {'Ativa' if enable_compression else 'Padrão'}")
                    logger.info(f"⚡ Velocidade: {'2x' if speed_up else '1x'}")

                    # Verificar se ainda está muito grande e aplicar compressão de emergência
                    if file_size > 24:  # Muito próximo do limite
                        logger.warning(f"⚠️ Arquivo ainda muito grande ({file_size:.2f}MB), aplicando compressão de emergência...")
                        final_audio_path = await self._emergency_compression(final_audio_path, unique_id)
                        file_size = os.path.getsize(final_audio_path) / (1024 * 1024)
                        logger.info(f"🗜️ Após compressão de emergência: {file_size:.2f}MB")

                    return final_audio_path, video_title

                except yt_dlp.utils.DownloadError as e:
                    error_msg = str(e).lower()
                    logger.warning(f"❌ Estratégia '{strategy}' falhou: {e}")
                    
                    # Se não é a última estratégia, continuar tentando
                    if strategy_index < len(strategies) - 1:
                        # Delay progressivo entre tentativas
                        delay = random.uniform(2, 5) * (strategy_index + 1)
                        logger.info(f"⏳ Aguardando {delay:.1f}s antes da próxima tentativa...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Última tentativa - verificar se é problema de autenticação
                        if any(keyword in error_msg for keyword in 
                               ['sign in', 'login', 'cookies', 'blocked', 'bot', 'unavailable']):
                            
                            if self.session_manager:
                                logger.info("🔄 Problema de autenticação detectado, forçando refresh da sessão...")
                                try:
                                    refresh_success = await self.session_manager.force_refresh()
                                    if refresh_success:
                                        logger.info("✅ Sessão renovada! Tentando download final...")
                                        return await self._final_retry_download(video_url)
                                    else:
                                        logger.error("❌ Falha ao renovar sessão")
                                except Exception as refresh_error:
                                    logger.error(f"❌ Erro ao renovar sessão: {refresh_error}")
                        
                        # Se chegou aqui, todas as estratégias falharam
                        raise Exception(f"Todas as estratégias falharam. Último erro: {e}")

                except Exception as e:
                    logger.warning(f"❌ Erro inesperado na estratégia '{strategy}': {e}")
                    if strategy_index < len(strategies) - 1:
                        continue
                    else:
                        raise Exception(f"Download falhou com erro: {e}")

            # Não deveria chegar aqui
            raise Exception("Erro inesperado no loop de estratégias")

        except Exception as e:
            if "Todas as estratégias" not in str(e) and "Download falhou" not in str(e):
                logger.error(f"❌ Erro crítico no download #{self.download_count}: {e}")
                raise Exception(f"Falha crítica no download: {e}")
            else:
                raise

    async def _emergency_compression(self, audio_path: str, unique_id: str) -> str:
        """
        Aplica compressão extrema para arquivos que ainda estão muito grandes
        """
        try:
            import subprocess

            # Novo arquivo com compressão máxima
            compressed_path = os.path.join(self.temp_dir, f"{unique_id}_compressed.opus")

            # Comando ffmpeg para compressão extrema
            cmd = [
                'ffmpeg', '-y',  # Forçar overwrite
                '-i', audio_path,
                '-vn',  # Sem vídeo
                '-map_metadata', '-1',  # Remover metadados
                '-ac', '1',  # Mono
                '-ar', '12000',  # Sample rate muito baixo (12kHz)
                '-c:a', 'libopus',
                '-b:a', '8k',  # Bitrate extremamente baixo (8kbps)
                '-application', 'voip',
                '-compression_level', '10',
                '-af', 'atempo=2.5',  # Acelerar ainda mais (2.5x)
                compressed_path
            ]

            logger.info("🚨 Executando compressão de emergência...")
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                logger.error(f"❌ Erro na compressão de emergência: {stderr.decode()}")
                return audio_path  # Retorna o original

            # Remover arquivo original
            if os.path.exists(audio_path):
                os.remove(audio_path)

            return compressed_path

        except Exception as e:
            logger.error(f"❌ Falha na compressão de emergência: {e}")
            return audio_path  # Retorna o original em caso de erro

    async def _final_retry_download(self, video_url: str) -> Tuple[str, str]:
        """
        Tentativa final após refresh da sessão
        """
        try:
            # Usar compressão máxima na tentativa final
            enable_compression, speed_up = True, True
            unique_id = str(uuid.uuid4())[:8]
            final_audio_path = os.path.join(self.temp_dir, f"{unique_id}.opus")
            ydl_opts = self._get_yt_dlp_options(unique_id, "stealth", enable_compression, speed_up)
            
            logger.info(f"🔄 Tentativa final de download: {video_url}")
            
            loop = asyncio.get_event_loop()
            info_dict = await loop.run_in_executor(
                None, 
                self._download_with_ytdlp, 
                video_url, 
                ydl_opts
            )
            
            video_title = info_dict.get('title', 'Título não encontrado')
            
            if not os.path.exists(final_audio_path):
                for file in os.listdir(self.temp_dir):
                    if file.startswith(unique_id):
                        final_audio_path = os.path.join(self.temp_dir, file)
                        break
                        
                if not os.path.exists(final_audio_path):
                    raise Exception(f"Arquivo não criado na tentativa final: {final_audio_path}")
            
            file_size = os.path.getsize(final_audio_path) / (1024 * 1024)
            logger.info(f"✅ Tentativa final bem-sucedida: '{video_title}' ({file_size:.2f}MB)")
            
            return final_audio_path, video_title
            
        except Exception as e:
            logger.error(f"❌ Falha na tentativa final: {e}")
            raise Exception(f"Falha na tentativa final: {e}")

    def _download_with_ytdlp(self, video_url: str, ydl_opts: dict) -> dict:
        """
        Execução síncrona do download
        """
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(video_url, download=True)
        except Exception as e:
            # Log adicional para debug
            logger.debug(f"yt-dlp error details: {e}")
            raise

    def get_download_stats(self) -> Dict:
        """Retorna estatísticas de download"""
        return {
            "total_downloads": self.download_count,
            "temp_directory": self.temp_dir,
            "cookies_available": os.path.exists(self.cookies_path),
            "session_manager_active": self.session_manager is not None,
            "last_download_time": self.last_download_time
        }

    def cleanup_temp_directory(self):
        """Remove diretório temporário"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"🗑️ Diretório temporário removido: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao limpar diretório temporário: {e}")

    def __del__(self):
        """Cleanup automático"""
        self.cleanup_temp_directory()
