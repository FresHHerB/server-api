import os
import logging
import httpx
import aiofiles
import asyncio
import random
import math
from typing import Optional, List, Tuple
from pydub import AudioSegment
from pydub.utils import make_chunks

logger = logging.getLogger(__name__)

class WhisperService:
    """Serviço para transcrição de áudio usando a API da OpenAI"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.error("❌ OPENAI_API_KEY não configurada")
            raise ValueError("OPENAI_API_KEY é obrigatória para transcrição")

        self.api_url = "https://api.openai.com/v1/audio/transcriptions"
        self.model = os.getenv("WHISPER_API_MODEL", "whisper-1")

        # Configurações de timeout e chunking
        self.request_timeout = float(os.getenv("WHISPER_TIMEOUT", "600.0"))  # 10 minutos
        self.max_duration_seconds = float(os.getenv("WHISPER_CHUNK_DURATION_SECONDS", "1500.0"))  # 25 minutos (1500s)

        self.client = httpx.AsyncClient(
            timeout=self.request_timeout,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

        self.max_retries = int(os.getenv("WHISPER_MAX_RETRIES", "3"))
        self.base_delay = float(os.getenv("WHISPER_RETRY_DELAY", "2.0"))

        logger.info(f"🎤 WhisperService inicializado (modelo: {self.model}, max_retries: {self.max_retries}, timeout: {self.request_timeout}s, chunk_duration: {self.max_duration_seconds}s)")

    def _get_audio_duration(self, audio_path: str) -> float:
        """
        Obtém a duração do áudio em segundos

        Returns:
            float: Duração em segundos
        """
        try:
            audio = AudioSegment.from_file(audio_path)
            duration_seconds = len(audio) / 1000.0  # pydub retorna em ms
            logger.info(f"🕒 Duração do áudio: {duration_seconds:.2f} segundos ({duration_seconds/60:.2f} minutos)")
            return duration_seconds
        except Exception as e:
            logger.warning(f"⚠️ Erro ao detectar duração do áudio: {e}")
            return 0.0

    def _split_audio_by_duration(self, audio_path: str, max_duration_seconds: float) -> List[str]:
        """
        Divide o áudio em chunks baseado na duração

        Args:
            audio_path: Caminho do arquivo de áudio
            max_duration_seconds: Duração máxima por chunk em segundos

        Returns:
            List[str]: Lista de caminhos dos arquivos de chunk
        """
        try:
            audio = AudioSegment.from_file(audio_path)
            total_duration_ms = len(audio)
            max_duration_ms = int(max_duration_seconds * 1000)  # Converter para ms

            chunk_paths = []
            base_name = os.path.splitext(audio_path)[0]

            # Se o áudio é menor que o limite, retorna o arquivo original
            if total_duration_ms <= max_duration_ms:
                logger.info(f"🔊 Áudio não precisa ser dividido ({total_duration_ms/1000:.2f}s / {total_duration_ms/60000:.2f}min)")
                return [audio_path]

            # Calcular número de chunks necessários
            num_chunks = math.ceil(total_duration_ms / max_duration_ms)
            logger.info(f"✂️ Dividindo áudio em {num_chunks} chunks de ~{max_duration_seconds}s ({max_duration_seconds/60:.2f}min)")

            for i in range(num_chunks):
                start_time = i * max_duration_ms
                end_time = min((i + 1) * max_duration_ms, total_duration_ms)

                chunk = audio[start_time:end_time]
                chunk_path = f"{base_name}_chunk_{i+1:02d}.ogg"

                # Exportar chunk
                chunk.export(chunk_path, format="ogg", codec="libvorbis")
                chunk_paths.append(chunk_path)

                chunk_duration_s = (end_time - start_time) / 1000  # Converter para segundos
                chunk_duration_min = chunk_duration_s / 60  # Converter para minutos
                logger.info(f"📄 Chunk {i+1}/{num_chunks} criado: {chunk_duration_s:.2f}s ({chunk_duration_min:.2f}min)")

            return chunk_paths

        except Exception as e:
            logger.error(f"❌ Erro ao dividir áudio: {e}")
            return [audio_path]  # Fallback para arquivo original

    def _validate_audio_file(self, audio_path: str) -> tuple[bool, str]:
        """
        Valida arquivo de áudio antes do envio

        Returns:
            tuple: (is_valid, error_message)
        """
        if not os.path.exists(audio_path):
            return False, f"Arquivo não encontrado: {audio_path}"

        try:
            file_size = os.path.getsize(audio_path)
            if file_size == 0:
                return False, "Arquivo de áudio está vazio"

            # OpenAI limite: 25MB (mas vamos permitir pois faremos chunking)
            max_size = 25 * 1024 * 1024  # 25MB
            if file_size > max_size:
                logger.warning(f"⚠️ Arquivo grande ({file_size / (1024*1024):.2f}MB), mas será dividido em chunks")

            # Verificar se é um arquivo de áudio válido (básico)
            with open(audio_path, 'rb') as f:
                header = f.read(12)
                if len(header) < 12:
                    return False, "Arquivo corrompido ou muito pequeno"

                # Verificar alguns headers comuns de áudio
                if not (header.startswith(b'ID3') or  # MP3
                       header[8:12] == b'WAVE' or    # WAV
                       header[4:8] == b'ftyp'):      # M4A/AAC
                    logger.warning(f"⚠️ Formato de áudio não reconhecido, tentando envio mesmo assim")

            return True, ""

        except Exception as e:
            return False, f"Erro ao validar arquivo: {str(e)}"

    async def _make_transcription_request(self, audio_path: str, headers: dict, data: dict, files: dict) -> httpx.Response:
        """
        Faz requisição para API da OpenAI com retry em caso de erro 500
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    delay = self.base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    logger.info(f"🔄 Tentativa {attempt + 1}/{self.max_retries + 1} após {delay:.1f}s...")
                    await asyncio.sleep(delay)

                response = await self.client.post(
                    self.api_url,
                    headers=headers,
                    data=data,
                    files=files
                )

                # Se sucesso ou erro não-retriável, retorna
                if response.status_code == 200 or response.status_code in [400, 401, 413, 429]:
                    return response

                # Erro 500+ são retriáveis
                if response.status_code >= 500:
                    logger.warning(f"⚠️ Erro {response.status_code} da OpenAI (tentativa {attempt + 1})")
                    if attempt < self.max_retries:
                        continue

                return response

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exception = e
                logger.warning(f"⚠️ Erro de conexão (tentativa {attempt + 1}): {str(e)}")
                if attempt < self.max_retries:
                    continue
                raise e
            except Exception as e:
                logger.error(f"❌ Erro inesperado na requisição: {str(e)}")
                raise e

        if last_exception:
            raise last_exception

        return response

    async def _transcribe_single_file(self, audio_path: str) -> str:
        """
        Transcreve um único arquivo de áudio via API OpenAI

        Args:
            audio_path: Caminho para o arquivo de áudio

        Returns:
            str: Texto transcrito

        Raises:
            Exception: Se houver erro na transcrição
        """
        file_size = os.path.getsize(audio_path) / (1024 * 1024)  # MB
        logger.info(f"📤 Enviando arquivo para OpenAI ({file_size:.2f}MB)...")

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            # Ler arquivo de forma assíncrona
            async with aiofiles.open(audio_path, 'rb') as audio_file:
                audio_content = await audio_file.read()
                
                files = {
                    'file': (os.path.basename(audio_path), audio_content, 'audio/mpeg')
                }
                data = {
                    'model': self.model,
                    # Remover 'language' para detecção automática do idioma original
                    'response_format': 'text'
                }
                
                # Fazer requisição à API com retry
                logger.info("🔄 Processando transcrição via OpenAI (detecção automática de idioma)...")
                response = await self._make_transcription_request(audio_path, headers, data, files)
                
                # Verificar se a resposta foi bem-sucedida
                response.raise_for_status()
                
                # Debug: verificar conteúdo da resposta
                logger.debug(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"Response content: {response.text[:200]}...")
                
                # Para response_format='text', a resposta é diretamente o texto
                logger.debug(f"Model: '{self.model}', Response format: '{data.get('response_format')}'")
                
                if data.get('response_format') == 'text':
                    # Resposta é texto puro
                    transcription = response.text.strip()
                    logger.info(f"📝 Recebido texto da OpenAI: {len(transcription)} caracteres")
                    if not transcription:
                        logger.warning("⚠️ OpenAI retornou texto vazio")
                        return ""
                else:
                    # Fallback para formato JSON
                    try:
                        result = response.json()
                        transcription = result.get('text', '').strip()
                    except ValueError as json_error:
                        logger.error(f"❌ Erro ao parsear JSON da OpenAI: {json_error}")
                        logger.error(f"Response content: {response.text[:200]}...")
                        return ""

                char_count = len(transcription)
                logger.info(f"✅ Transcrição concluída ({char_count} caracteres)")
                
                return transcription

        except httpx.HTTPStatusError as e:
            error_details = ""
            error_message = ""
            try:
                error_details = e.response.text
                # Tentar extrair mensagem de erro do JSON
                if error_details:
                    try:
                        error_json = e.response.json()
                        if "error" in error_json and "message" in error_json["error"]:
                            error_message = error_json["error"]["message"]
                    except:
                        pass
            except Exception:
                pass

            logger.error(f"❌ Erro HTTP da OpenAI: {e.response.status_code}")
            logger.error(f"📄 Detalhes: {error_details}")

            # Tratamento específico por código de erro
            if e.response.status_code == 400:
                if "something went wrong reading your request" in error_message.lower():
                    raise Exception("Arquivo de áudio corrompido ou formato inválido. Tente converter o arquivo para MP3.")
                elif "invalid_request_error" in error_details:
                    raise Exception(f"Parâmetros inválidos na requisição: {error_message or 'Verifique o formato do arquivo'}")
                else:
                    raise Exception(f"Requisição inválida para OpenAI: {error_message or error_details}")

            elif e.response.status_code == 401:
                raise Exception("API key da OpenAI inválida ou expirada.")

            elif e.response.status_code == 413:
                raise Exception("Arquivo de áudio muito grande para a API da OpenAI (limite: 25MB).")

            elif e.response.status_code == 429:
                raise Exception("Rate limit atingido na API da OpenAI. Tente novamente em alguns minutos.")

            elif e.response.status_code >= 500:
                raise Exception(f"Erro interno da OpenAI (servidor indisponível): {e.response.status_code}")

            else:
                raise Exception(f"Erro na API da OpenAI: {e.response.status_code} - {error_message or error_details}")
                
            
        except httpx.TimeoutException:
            logger.error("❌ Timeout na requisição para OpenAI")
            raise Exception("Timeout na transcrição - arquivo muito grande ou API lenta.")

        except Exception as e:
            logger.error(f"❌ Erro inesperado na transcrição: {str(e)}")
            raise Exception(f"Falha na transcrição: {str(e)}")

    async def transcribe(self, audio_path: str) -> str:
        """
        Transcreve arquivo de áudio via API OpenAI com suporte a chunking para arquivos longos

        Args:
            audio_path: Caminho para o arquivo de áudio

        Returns:
            str: Texto transcrito

        Raises:
            Exception: Se houver erro na transcrição
        """
        chunk_files = []
        try:
            # Validar arquivo antes do envio
            is_valid, error_msg = self._validate_audio_file(audio_path)
            if not is_valid:
                logger.error(f"❌ Validação falhou: {error_msg}")
                raise ValueError(f"Arquivo inválido: {error_msg}")

            # Verificar duração do áudio
            duration_seconds = self._get_audio_duration(audio_path)

            # Se a duração é maior que o limite, dividir em chunks
            if duration_seconds > self.max_duration_seconds:
                logger.info(f"🔴 Áudio longo detectado ({duration_seconds:.2f}s ({duration_seconds/60:.2f}min) > {self.max_duration_seconds}s ({self.max_duration_seconds/60:.2f}min))")
                logger.info(f"✂️ Dividindo em chunks de {self.max_duration_seconds}s ({self.max_duration_seconds/60:.2f}min)...")

                chunk_files = self._split_audio_by_duration(audio_path, self.max_duration_seconds)

                if len(chunk_files) == 1:
                    # Não foi dividido, usar arquivo original
                    logger.info("🔊 Usando arquivo original (chunk único)")
                    transcription = await self._transcribe_single_file(audio_path)
                else:
                    # Transcrever cada chunk e concatenar
                    logger.info(f"📋 Transcrevendo {len(chunk_files)} chunks...")
                    transcriptions = []

                    for i, chunk_path in enumerate(chunk_files, 1):
                        logger.info(f"🎤 Transcrevendo chunk {i}/{len(chunk_files)}...")
                        chunk_transcription = await self._transcribe_single_file(chunk_path)

                        if chunk_transcription.strip():
                            transcriptions.append(chunk_transcription.strip())
                            logger.info(f"✅ Chunk {i} transcrito ({len(chunk_transcription)} caracteres)")
                        else:
                            logger.warning(f"⚠️ Chunk {i} retornou transcrição vazia")

                    # Concatenar todas as transcrições
                    transcription = " ".join(transcriptions)
                    logger.info(f"🔗 Transcrições concatenadas ({len(transcription)} caracteres total)")
            else:
                # Áudio dentro do limite, transcrever diretamente
                logger.info(f"🔊 Áudio dentro do limite ({duration_seconds:.2f}s / {duration_seconds/60:.2f}min)")
                transcription = await self._transcribe_single_file(audio_path)

            return transcription

        finally:
            # Limpar arquivo original
            self._cleanup_audio_file(audio_path)

            # Limpar arquivos de chunk
            for chunk_file in chunk_files:
                if chunk_file != audio_path:  # Não remover o arquivo original duas vezes
                    self._cleanup_audio_file(chunk_file)

    def _cleanup_audio_file(self, audio_path: str):
        """Remove arquivo de áudio após processamento"""
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"🗑️ Arquivo removido: {os.path.basename(audio_path)}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao remover arquivo: {str(e)}")

    async def health_check(self) -> bool:
        """Verifica se a API está acessível"""
        try:
            # Teste simples sem fazer transcrição real
            headers = {"Authorization": f"Bearer {self.api_key}"}
            response = await self.client.get(
                "https://api.openai.com/v1/models", 
                headers=headers,
                timeout=10.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"⚠️ Health check falhou: {e}")
            return False

    def get_service_info(self) -> dict:
        """Retorna informações do serviço"""
        return {
            "service": "OpenAI Whisper API",
            "model": self.model,
            "api_url": self.api_url,
            "api_key_configured": bool(self.api_key),
            "client_configured": self.client is not None,
            "timeout_seconds": self.request_timeout,
            "chunk_duration_seconds": self.max_duration_seconds,
            "chunking_enabled": True,
            "max_file_size_mb": 25
        }

    async def cleanup(self):
        """Fecha cliente HTTP"""
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            logger.info("✅ Cliente HTTP do WhisperService fechado")
