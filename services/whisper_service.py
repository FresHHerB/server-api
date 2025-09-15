import os
import logging
import httpx
import aiofiles
from typing import Optional

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
        self.client = httpx.AsyncClient(
            timeout=300.0,  # 5 minutos
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

        logger.info(f"🎤 WhisperService inicializado (modelo: {self.model})")

    async def transcribe(self, audio_path: str) -> str:
        """
        Transcreve arquivo de áudio via API OpenAI

        Args:
            audio_path: Caminho para o arquivo de áudio

        Returns:
            str: Texto transcrito

        Raises:
            Exception: Se houver erro na transcrição
        """
        if not os.path.exists(audio_path):
            logger.error(f"Arquivo de áudio não encontrado: {audio_path}")
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")

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
                    'language': 'pt',  # Português
                    'response_format': 'text'
                }
                
                # Fazer requisição à API
                logger.info("🔄 Processando transcrição via OpenAI...")
                response = await self.client.post(
                    self.api_url, 
                    headers=headers, 
                    data=data, 
                    files=files
                )
                
                # Verificar se a resposta foi bem-sucedida
                response.raise_for_status()
                
                # Para response_format='text', a resposta é diretamente o texto
                if self.model == "whisper-1" and data.get('response_format') == 'text':
                    transcription = response.text.strip()
                else:
                    # Fallback para formato JSON
                    result = response.json()
                    transcription = result.get('text', '').strip()

                char_count = len(transcription)
                logger.info(f"✅ Transcrição concluída ({char_count} caracteres)")
                
                return transcription

        except httpx.HTTPStatusError as e:
            error_details = ""
            try:
                error_details = e.response.text
            except Exception:
                pass
                
            logger.error(f"❌ Erro HTTP da OpenAI: {e.response.status_code}")
            logger.error(f"📄 Detalhes: {error_details}")
            
            if e.response.status_code == 429:
                raise Exception("Rate limit atingido na API da OpenAI. Tente novamente em alguns minutos.")
            elif e.response.status_code == 401:
                raise Exception("API key da OpenAI inválida ou expirada.")
            elif e.response.status_code == 413:
                raise Exception("Arquivo de áudio muito grande para a API da OpenAI.")
            else:
                raise Exception(f"Erro na API da OpenAI: {e.response.status_code} - {error_details}")
                
        except httpx.TimeoutException:
            logger.error("❌ Timeout na requisição para OpenAI")
            raise Exception("Timeout na transcrição - arquivo muito grande ou API lenta.")
            
        except Exception as e:
            logger.error(f"❌ Erro inesperado na transcrição: {str(e)}")
            raise Exception(f"Falha na transcrição: {str(e)}")
            
        finally:
            # Limpar arquivo após transcrição
            self._cleanup_audio_file(audio_path)

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
            "client_configured": self.client is not None
        }

    async def cleanup(self):
        """Fecha cliente HTTP"""
        if self.client and not self.client.is_closed:
            await self.client.aclose()
            logger.info("✅ Cliente HTTP do WhisperService fechado")
