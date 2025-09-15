#!/usr/bin/env python3
"""
Gerador Automático do Projeto YouTube Transcription API

Execute este script para gerar todos os arquivos do projeto automaticamente.
python generate_project.py
"""

import os
from pathlib import Path


def create_directory_structure():
    """Cria a estrutura de diretórios do projeto"""
    directories = [
        "models",
        "services",
        "middleware",
        "utils",
        "logs",
        "temp"
    ]

    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"📁 Criado diretório: {directory}/")


def write_file(filepath, content):
    """Escreve conteúdo em arquivo, criando diretórios se necessário"""
    file_path = Path(filepath)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Criado arquivo: {filepath}")


def generate_all_files():
    """Gera todos os arquivos do projeto"""

    # main.py
    main_py_content = '''from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from typing import List
import os
from dotenv import load_dotenv

from models.schemas import VideoRequest, VideoResponse, VideoData
from services.youtube_service import YouTubeService
from services.whisper_service import WhisperService
from middleware.auth import verify_token

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="YouTube Video Transcription API",
    description="API para transcrever vídeos do YouTube usando Whisper",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure conforme necessário
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar serviços
youtube_service = YouTubeService()
whisper_service = WhisperService()

# Esquema de segurança
security = HTTPBearer()

@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação"""
    logger.info("🚀 Iniciando YouTube Transcription API...")

    # Verificar se o token está configurado
    if not os.getenv("API_TOKEN"):
        logger.error("❌ API_TOKEN não configurado no arquivo .env")
        raise Exception("API_TOKEN é obrigatório")

    # Inicializar modelo Whisper
    await whisper_service.load_model()
    logger.info("✅ API inicializada com sucesso!")

@app.on_event("shutdown")
async def shutdown_event():
    """Limpeza ao encerrar a aplicação"""
    logger.info("🛑 Encerrando YouTube Transcription API...")
    await whisper_service.cleanup()

@app.get("/")
async def root():
    """Endpoint raiz - Health check"""
    return {
        "message": "YouTube Video Transcription API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.post("/video/getData", response_model=VideoResponse)
async def get_video_data(
    request: VideoRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Endpoint principal para transcrever vídeos do YouTube

    Args:
        request: Lista de URLs de vídeos do YouTube
        credentials: Token de autenticação

    Returns:
        VideoResponse: Lista com dados dos vídeos (título, transcrição, num_char)
    """
    try:
        # Verificar autenticação
        verify_token(credentials.credentials)

        logger.info(f"📝 Processando {len(request.video_urls)} vídeo(s)...")

        video_data_list = []

        for i, video_url in enumerate(request.video_urls, 1):
            try:
                logger.info(f"🎬 Processando vídeo {i}/{len(request.video_urls)}: {video_url}")

                # Baixar áudio do vídeo
                audio_path, video_title = await youtube_service.download_audio(video_url)

                # Transcrever áudio
                transcription = await whisper_service.transcribe(audio_path)

                # Criar objeto de dados do vídeo
                video_data = VideoData(
                    titulo=video_title,
                    transcricao=transcription.strip(),
                    num_char=len(transcription.strip())
                )

                video_data_list.append(video_data)

                logger.info(f"✅ Vídeo {i} processado: {video_title} ({video_data.num_char} chars)")

            except Exception as e:
                logger.error(f"❌ Erro ao processar vídeo {video_url}: {str(e)}")
                # Adicionar entrada com erro
                video_data_list.append(VideoData(
                    titulo=f"Erro ao processar: {video_url}",
                    transcricao=f"Erro: {str(e)}",
                    num_char=0
                ))

        logger.info(f"🎉 Processamento concluído! {len(video_data_list)} vídeo(s) processado(s)")

        return VideoResponse(
            success=True,
            message=f"Processados {len(video_data_list)} vídeo(s) com sucesso",
            data=video_data_list
        )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"❌ Erro interno: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)'''

    write_file("main.py", main_py_content)

    # models/schemas.py
    schemas_py_content = '''from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional

class VideoRequest(BaseModel):
    """Modelo para requisição de transcrição de vídeos"""
    video_urls: List[str] = Field(
        ...,
        description="Lista de URLs de vídeos do YouTube",
        example=[
            "https://www.youtube.com/watch?v=OqsvA8xcb80",
            "https://www.youtube.com/watch?v=Xno_qxQ9G7g"
        ]
    )

class VideoData(BaseModel):
    """Modelo para dados de um vídeo processado"""
    titulo: str = Field(
        ...,
        description="Título do vídeo",
        example="Como programar em Python"
    )
    transcricao: str = Field(
        ...,
        description="Transcrição do áudio do vídeo",
        example="Bem-vindos ao curso de Python. Hoje vamos aprender..."
    )
    num_char: int = Field(
        ...,
        description="Número de caracteres na transcrição",
        example=1234
    )

class VideoResponse(BaseModel):
    """Modelo para resposta da API"""
    success: bool = Field(
        ...,
        description="Indica se a operação foi bem-sucedida",
        example=True
    )
    message: str = Field(
        ...,
        description="Mensagem explicativa",
        example="Processados 2 vídeo(s) com sucesso"
    )
    data: List[VideoData] = Field(
        ...,
        description="Lista com dados dos vídeos processados"
    )

class ErrorResponse(BaseModel):
    """Modelo para resposta de erro"""
    success: bool = Field(
        default=False,
        description="Indica que houve erro"
    )
    message: str = Field(
        ...,
        description="Mensagem de erro",
        example="Token de acesso inválido"
    )
    error_code: Optional[str] = Field(
        None,
        description="Código do erro",
        example="AUTH_001"
    )'''

    write_file("models/schemas.py", schemas_py_content)

    # services/youtube_service.py
    youtube_service_py_content = '''import os
import asyncio
import logging
import tempfile
import uuid
from typing import Tuple
import yt_dlp
from pathlib import Path

logger = logging.getLogger(__name__)

class YouTubeService:
    """Serviço para baixar áudios de vídeos do YouTube"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"📁 Diretório temporário criado: {self.temp_dir}")

    async def download_audio(self, video_url: str) -> Tuple[str, str]:
        """
        Baixa o áudio de um vídeo do YouTube

        Args:
            video_url: URL do vídeo do YouTube

        Returns:
            Tuple[str, str]: (caminho_do_audio, titulo_do_video)

        Raises:
            Exception: Se houver erro no download
        """
        try:
            # Gerar nome único para o arquivo
            unique_id = str(uuid.uuid4())[:8]
            audio_filename = f"{unique_id}.mp3"
            audio_path = os.path.join(self.temp_dir, audio_filename)

            # Configurações do yt-dlp
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.join(self.temp_dir, f'{unique_id}.%(ext)s'),
                'noplaylist': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'quiet': True,  # Reduzir logs do yt-dlp
                'no_warnings': True,
            }

            logger.info(f"🔽 Baixando áudio de: {video_url}")

            # Executar download de forma assíncrona
            loop = asyncio.get_event_loop()
            info_dict = await loop.run_in_executor(
                None, 
                self._download_with_ytdlp, 
                video_url, 
                ydl_opts
            )

            video_title = info_dict.get('title', 'Título não encontrado')

            # Verificar se o arquivo foi criado
            if not os.path.exists(audio_path):
                raise Exception(f"Arquivo de áudio não foi criado: {audio_path}")

            file_size = os.path.getsize(audio_path) / (1024 * 1024)  # MB
            logger.info(f"✅ Áudio baixado: {video_title} ({file_size:.1f}MB)")

            return audio_path, video_title

        except Exception as e:
            logger.error(f"❌ Erro ao baixar áudio de {video_url}: {str(e)}")
            raise Exception(f"Falha no download do vídeo: {str(e)}")

    def _download_with_ytdlp(self, video_url: str, ydl_opts: dict) -> dict:
        """
        Função auxiliar para executar o download de forma síncrona

        Args:
            video_url: URL do vídeo
            ydl_opts: Opções do yt-dlp

        Returns:
            dict: Informações do vídeo
        """
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            return info_dict

    def cleanup_file(self, file_path: str):
        """
        Remove um arquivo específico

        Args:
            file_path: Caminho do arquivo a ser removido
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"🗑️ Arquivo removido: {file_path}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao remover arquivo {file_path}: {str(e)}")

    def cleanup_temp_directory(self):
        """Remove todos os arquivos temporários"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"🗑️ Diretório temporário removido: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao limpar diretório temporário: {str(e)}")

    def __del__(self):
        """Cleanup ao destruir o objeto"""
        self.cleanup_temp_directory()'''

    write_file("services/youtube_service.py", youtube_service_py_content)

    # services/whisper_service.py
    whisper_service_py_content = '''import asyncio
import logging
import os
import torch
import whisper
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class WhisperService:
    """Serviço para transcrição de áudio usando Whisper"""

    def __init__(self, model_name: str = "medium"):
        self.model_name = model_name
        self.model: Optional[whisper.Whisper] = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # Configurar diretório de cache do Whisper
        self.cache_dir = self._setup_cache_directory()

        logger.info(f"🖥️ Dispositivo selecionado: {self.device.upper()}")
        logger.info(f"📁 Cache do Whisper: {self.cache_dir}")

    def _setup_cache_directory(self) -> str:
        """
        Configura o diretório de cache do Whisper de forma segura

        Returns:
            str: Caminho para o diretório de cache
        """
        # Tentar usar variável de ambiente primeiro
        cache_dir = os.getenv("WHISPER_CACHE")

        if not cache_dir:
            # Usar XDG_CACHE_HOME se definido
            xdg_cache = os.getenv("XDG_CACHE_HOME")
            if xdg_cache:
                cache_dir = os.path.join(xdg_cache, "whisper")
            else:
                # Fallback para diretório da aplicação
                cache_dir = os.path.join(os.getcwd(), ".cache", "whisper")

        # Criar diretório se não existir
        try:
            os.makedirs(cache_dir, exist_ok=True)
            # Testar se pode escrever no diretório
            test_file = os.path.join(cache_dir, ".test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logger.info(f"✅ Diretório de cache configurado: {cache_dir}")
        except Exception as e:
            logger.warning(f"⚠️ Problema com cache {cache_dir}: {e}")
            # Usar temp como último recurso
            import tempfile
            cache_dir = os.path.join(tempfile.gettempdir(), "whisper_cache")
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"📁 Usando cache temporário: {cache_dir}")

        return cache_dir

    async def load_model(self):
        """Carrega o modelo Whisper de forma assíncrona"""
        if self.model is None:
            try:
                logger.info(f"📥 Carregando modelo Whisper '{self.model_name}'...")
                logger.info(f"📂 Diretório de cache: {self.cache_dir}")

                # Carregar modelo de forma assíncrona com diretório específico
                loop = asyncio.get_event_loop()
                self.model = await loop.run_in_executor(
                    None,
                    self._load_model_sync
                )

                logger.info(f"✅ Modelo '{self.model_name}' carregado com sucesso!")

            except Exception as e:
                logger.error(f"❌ Erro ao carregar modelo Whisper: {str(e)}")
                raise Exception(f"Falha ao carregar modelo Whisper: {str(e)}")

    def _load_model_sync(self):
        """
        Carrega o modelo de forma síncrona com diretório de cache personalizado

        Returns:
            whisper.Whisper: Modelo carregado
        """
        return whisper.load_model(
            name=self.model_name,
            device=self.device,
            download_root=self.cache_dir
        )

    async def transcribe(self, audio_path: str) -> str:
        """
        Transcreve um arquivo de áudio

        Args:
            audio_path: Caminho para o arquivo de áudio

        Returns:
            str: Texto transcrito

        Raises:
            Exception: Se houver erro na transcrição
        """
        try:
            # Garantir que o modelo está carregado
            if self.model is None:
                await self.load_model()

            # Verificar se o arquivo existe
            if not os.path.exists(audio_path):
                raise Exception(f"Arquivo de áudio não encontrado: {audio_path}")

            file_size = os.path.getsize(audio_path) / (1024 * 1024)  # MB
            logger.info(f"🎤 Iniciando transcrição do arquivo ({file_size:.1f}MB)...")

            # Executar transcrição de forma assíncrona
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio_path
            )

            transcription = result['text']
            char_count = len(transcription.strip())

            logger.info(f"✅ Transcrição concluída! ({char_count} caracteres)")

            # Limpar arquivo após transcrição
            self._cleanup_audio_file(audio_path)

            return transcription

        except Exception as e:
            logger.error(f"❌ Erro na transcrição: {str(e)}")
            # Tentar limpar arquivo mesmo em caso de erro
            self._cleanup_audio_file(audio_path)
            raise Exception(f"Falha na transcrição: {str(e)}")

    def _transcribe_sync(self, audio_path: str) -> dict:
        """
        Função auxiliar para executar transcrição de forma síncrona

        Args:
            audio_path: Caminho do arquivo de áudio

        Returns:
            dict: Resultado da transcrição
        """
        return self.model.transcribe(
            audio_path,
            language='pt',  # Forçar português (pode ser removido para detecção automática)
            fp16=False,     # Usar FP32 para melhor compatibilidade
            verbose=False   # Reduzir logs
        )

    def _cleanup_audio_file(self, audio_path: str):
        """
        Remove arquivo de áudio após processamento

        Args:
            audio_path: Caminho do arquivo a ser removido
        """
        try:
            if os.path.exists(audio_path):
                os.remove(audio_path)
                logger.info(f"🗑️ Arquivo de áudio removido: {os.path.basename(audio_path)}")
        except Exception as e:
            logger.warning(f"⚠️ Erro ao remover arquivo de áudio: {str(e)}")

    async def cleanup(self):
        """Limpeza ao encerrar o serviço"""
        logger.info("🧹 Limpando recursos do Whisper...")

        if self.model is not None:
            # Liberar memória da GPU se estiver sendo usada
            if self.device == "cuda":
                try:
                    torch.cuda.empty_cache()
                    logger.info("🖥️ Cache da GPU limpo")
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao limpar cache da GPU: {str(e)}")

            self.model = None
            logger.info("✅ Recursos do Whisper liberados")

    def get_model_info(self) -> dict:
        """
        Retorna informações sobre o modelo atual

        Returns:
            dict: Informações do modelo
        """
        return {
            "model_name": self.model_name,
            "device": self.device,
            "is_loaded": self.model is not None,
            "cuda_available": torch.cuda.is_available(),
            "cache_directory": self.cache_dir
        }

    def preload_model(self):
        """
        Pré-carrega o modelo de forma síncrona (útil para testes)
        """
        try:
            if self.model is None:
                logger.info(f"🔄 Pré-carregando modelo {self.model_name}...")
                self.model = self._load_model_sync()
                logger.info("✅ Modelo pré-carregado com sucesso!")
        except Exception as e:
            logger.error(f"❌ Erro no pré-carregamento: {str(e)}")
            raise'''

    write_file("services/whisper_service.py", whisper_service_py_content)

    # middleware/auth.py
    auth_py_content = '''import os
import logging
from fastapi import HTTPException, status
from typing import Optional

logger = logging.getLogger(__name__)

def verify_token(token: str) -> bool:
    """
    Verifica se o token de acesso é válido

    Args:
        token: Token de acesso fornecido

    Returns:
        bool: True se o token for válido

    Raises:
        HTTPException: Se o token for inválido ou não fornecido
    """
    try:
        # Obter token esperado do ambiente
        expected_token = os.getenv("API_TOKEN")

        if not expected_token:
            logger.error("❌ API_TOKEN não configurado no servidor")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Configuração de autenticação não encontrada"
            )

        if not token:
            logger.warning("⚠️ Token não fornecido na requisição")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acesso é obrigatório",
                headers={"WWW-Authenticate": "Bearer"}
            )

        # Comparar tokens
        if token.strip() != expected_token.strip():
            logger.warning(f"⚠️ Token inválido fornecido: {token[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de acesso inválido",
                headers={"WWW-Authenticate": "Bearer"}
            )

        logger.info("✅ Token válido - Acesso autorizado")
        return True

    except HTTPException:
        # Re-raise HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"❌ Erro na verificação do token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno na autenticação"
        )

def get_bearer_token(authorization_header: Optional[str]) -> Optional[str]:
    """
    Extrai o token Bearer do cabeçalho Authorization

    Args:
        authorization_header: Valor do cabeçalho Authorization

    Returns:
        Optional[str]: Token extraído ou None
    """
    if not authorization_header:
        return None

    parts = authorization_header.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]

class AuthenticationError(Exception):
    """Exceção personalizada para erros de autenticação"""

    def __init__(self, message: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)'''

    write_file("middleware/auth.py", auth_py_content)

    # Arquivos __init__.py
    init_files = {
        "models/__init__.py": '''"""
Modelos de dados da aplicação

Contém os schemas Pydantic para validação de entrada e saída da API.
"""

from .schemas import VideoRequest, VideoResponse, VideoData, ErrorResponse

__all__ = ["VideoRequest", "VideoResponse", "VideoData", "ErrorResponse"]''',

        "services/__init__.py": '''"""
Serviços da aplicação

Contém a lógica de negócio para download de vídeos e transcrição.
"""

from .youtube_service import YouTubeService
from .whisper_service import WhisperService

__all__ = ["YouTubeService", "WhisperService"]''',

        "middleware/__init__.py": '''"""
Middleware da aplicação

Contém middleware personalizado, incluindo autenticação.
"""

from .auth import verify_token, get_bearer_token, AuthenticationError

__all__ = ["verify_token", "get_bearer_token", "AuthenticationError"]''',

        "utils/__init__.py": '''"""
Utilitários da aplicação

Funções auxiliares e helpers utilizados em toda a aplicação.
"""'''
    }

    for filepath, content in init_files.items():
        write_file(filepath, content)

    # requirements.txt
    requirements_content = '''# FastAPI e servidor
fastapi==0.104.1
uvicorn[standard]==0.24.0
python-multipart==0.0.6

# Processamento de áudio/vídeo
openai-whisper==20231117
yt-dlp==2023.11.16
torch==2.1.0
torchaudio==2.1.0

# Utilitários
python-dotenv==1.0.0
pydantic==2.4.2
httpx==0.25.2
aiofiles==23.2.0

# Monitoramento e logs
psutil==5.9.6

# Processamento de dados
numpy==1.24.4
pandas==2.1.3

# Desenvolvimento (opcional - pode remover em produção)
pytest==7.4.3
pytest-asyncio==0.21.1
black==23.10.1
flake8==6.1.0

# Segurança
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4'''

    write_file("requirements.txt", requirements_content)

    # Dockerfile
    dockerfile_content = '''# Use uma imagem Python oficial com suporte a CUDA (opcional)
# Para CPU apenas, use: FROM python:3.11-slim
FROM python:3.11-slim

# Definir variáveis de ambiente
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    DEBIAN_FRONTEND=noninteractive \\
    PIP_NO_CACHE_DIR=1 \\
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Criar usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \\
    ffmpeg \\
    wget \\
    curl \\
    && rm -rf /var/lib/apt/lists/* \\
    && apt-get clean

# Definir diretório de trabalho
WORKDIR /app

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Criar diretórios necessários
RUN mkdir -p /app/logs /app/temp && \\
    chown -R appuser:appuser /app

# Copiar código da aplicação
COPY --chown=appuser:appuser . .

# Mudar para usuário não-root
USER appuser

# Expor porta
EXPOSE 8000

# Verificação de saúde
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8000/health || exit 1

# Comando padrão
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]'''

    write_file("Dockerfile", dockerfile_content)

    # docker-compose.yml
    docker_compose_content = '''version: '3.8'

services:
  youtube-transcription-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: youtube_transcription_api
    ports:
      - "${PORT:-8000}:8000"
    environment:
      - API_TOKEN=${API_TOKEN}
      - PORT=${PORT:-8000}
      - PYTHONPATH=/app
    env_file:
      - .env
    volumes:
      # Volume para logs (opcional)
      - ./logs:/app/logs
      # Volume para arquivos temporários (opcional)
      - /tmp/youtube_transcription:/app/temp
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    # Recursos limitados (ajuste conforme necessário)
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
        reservations:
          memory: 2G
          cpus: '1.0'
    # Configurações de logging
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

# Volumes nomeados (opcional)
volumes:
  app_logs:
  app_temp:

# Rede personalizada (opcional)
networks:
  default:
    name: youtube_transcription_network'''

    write_file("docker-compose.yml", docker_compose_content)

    # .env.example
    env_example_content = '''# =============================================================================
# YouTube Video Transcription API - Configuração de Ambiente
# =============================================================================

# Token de autenticação da API (OBRIGATÓRIO)
# Gere um token seguro e complexo para proteger sua API
API_TOKEN=your_secure_api_token_here_change_me

# Porta do servidor (opcional, padrão: 8000)
PORT=8000

# Configurações do Whisper
WHISPER_MODEL=medium
WHISPER_DEVICE=auto  # auto, cpu, cuda

# Configurações de logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR

# Configurações de recursos (opcional)
MAX_CONCURRENT_DOWNLOADS=2
MAX_CONCURRENT_TRANSCRIPTIONS=1

# Configurações de limpeza automática
AUTO_CLEANUP_TEMP_FILES=true
TEMP_FILE_MAX_AGE_HOURS=24

# Configurações de limites (opcional)
MAX_VIDEO_DURATION_MINUTES=120
MAX_VIDEOS_PER_REQUEST=10

# =============================================================================
# INSTRUÇÕES:
# 1. Copie este arquivo para .env
# 2. Altere API_TOKEN para um valor seguro e único
# 3. Ajuste outras configurações conforme necessário
# 4. NÃO compartilhe o arquivo .env - ele contém informações sensíveis
# ============================================================================='''

    write_file(".env.example", env_example_content)

    # .gitignore
    gitignore_content = '''# Arquivos de ambiente (IMPORTANTE!)
.env
.env.local
.env.production

# Arquivos Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# Arquivos temporários e downloads
temp/
tmp/
downloads/
*.mp3
*.mp4
*.wav
*.m4a
*.webm

# Logs
logs/
*.log
*.log.*

# Jupyter Notebook
.ipynb_checkpoints

# pyenv
.python-version

# pipenv
Pipfile.lock

# poetry
poetry.lock

# celery beat schedule file
celerybeat-schedule

# SageMath parsed files
*.sage.py

# Ambientes virtuais
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# IDEs
.idea/
.vscode/
*.swp
*.swo
*~

# Sistema operacional
.DS_Store
.DS_Store?
._*
.Spotlight-V100
.Trashes
ehthumbs.db
Thumbs.db

# Docker
.dockerignore

# Pytest
.pytest_cache/
.coverage
htmlcov/

# Arquivos de backup
*.bak
*.backup
*.old

# Modelos Whisper (podem ser grandes)
# Descomente se quiser baixar sempre
# ~/.cache/whisper/'''

    write_file(".gitignore", gitignore_content)

    # README.md
    readme_content = '''# 🎤 YouTube Video Transcription API

Uma API REST moderna e robusta para transcrever vídeos do YouTube usando OpenAI Whisper. Desenvolvida com FastAPI e pronta para produção.

## 🚀 Características

- ⚡ **FastAPI**: Framework moderno e performático
- 🎯 **Whisper AI**: Transcrição precisa de áudios
- 🔐 **Autenticação**: Sistema de tokens seguros
- 🐳 **Docker**: Containerizado e pronto para deploy
- 📊 **Logging**: Sistema completo de logs
- 🔄 **Assíncrono**: Processamento não-bloqueante
- 🧹 **Auto-limpeza**: Remove arquivos temporários automaticamente

## 📋 Pré-requisitos

- Python 3.11+ ou Docker
- FFmpeg (para processamento de áudio)
- GPU NVIDIA (opcional, para melhor performance)

## 🛠️ Instalação

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/youtube-transcription-api.git
cd youtube-transcription-api
```

### 2. Configuração de Ambiente

```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Edite com suas configurações
nano .env
```

**Configure pelo menos:**
```bash
API_TOKEN=seu_token_super_secreto_aqui
```

### 3. Opção A: Docker (Recomendado)

```bash
# Build e execução
docker-compose up --build -d

# Ver logs
docker-compose logs -f
```

### 3. Opção B: Instalação Local

```bash
# Criar ambiente virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\\Scripts\\activate     # Windows

# Instalar dependências
pip install -r requirements.txt

# Executar servidor
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 📖 Uso da API

### Endpoint Principal

**POST** `/video/getData`

### Headers Obrigatórios

```http
Authorization: Bearer SEU_TOKEN_AQUI
Content-Type: application/json
```

### Exemplo de Requisição

```json
{
  "video_urls": [
    "https://www.youtube.com/watch?v=OqsvA8xcb80",
    "https://www.youtube.com/watch?v=Xno_qxQ9G7g"
  ]
}
```

### Exemplo de Resposta

```json
{
  "success": true,
  "message": "Processados 2 vídeo(s) com sucesso",
  "data": [
    {
      "titulo": "Como Programar em Python - Aula 1",
      "transcricao": "Bem-vindos ao curso de Python. Hoje vamos aprender os fundamentos...",
      "num_char": 1234
    },
    {
      "titulo": "Estruturas de Dados em Python",
      "transcricao": "Nesta aula vamos estudar listas, dicionários e tuplas...",
      "num_char": 987
    }
  ]
}
```

## 🧪 Testando a API

### 1. Health Check

```bash
curl http://localhost:8000/health
```

### 2. Teste com cURL

```bash
curl -X POST "http://localhost:8000/video/getData" \\
  -H "Authorization: Bearer SEU_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{
    "video_urls": ["https://www.youtube.com/watch?v=OqsvA8xcb80"]
  }'
```

### 3. Teste com Python

```python
import requests

url = "http://localhost:8000/video/getData"
headers = {
    "Authorization": "Bearer SEU_TOKEN",
    "Content-Type": "application/json"
}
data = {
    "video_urls": [
        "https://www.youtube.com/watch?v=OqsvA8xcb80"
    ]
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

## 🌐 Deploy no EasyPanel

### 1. Preparar Repositório

Certifique-se de que todos os arquivos estão no GitHub:
- `Dockerfile`
- `requirements.txt`
- Código da aplicação
- `.env.example`

### 2. Configurar no EasyPanel

1. **Criar novo serviço**
2. **Conectar ao GitHub**: Selecione o repositório
3. **Configurar variáveis de ambiente**:
   ```
   API_TOKEN=seu_token_super_secreto
   PORT=8000
   ```
4. **Deploy automático**: EasyPanel irá usar o Dockerfile

### 3. Configurações Recomendadas

- **CPU**: 2+ cores
- **RAM**: 4GB+ (modelo Whisper é pesado)
- **Storage**: 10GB+ para arquivos temporários
- **Health Check**: `/health`

## 📁 Estrutura do Projeto

```
youtube-transcription-api/
├── main.py                     # Aplicação principal FastAPI
├── requirements.txt            # Dependências Python
├── Dockerfile                 # Container da aplicação
├── docker-compose.yml         # Orquestração Docker
├── .env.example              # Exemplo de configuração
├── .gitignore                # Arquivos ignorados
├── README.md                 # Esta documentação
├── models/
│   ├── __init__.py           
│   └── schemas.py            # Modelos Pydantic
├── services/
│   ├── __init__.py           
│   ├── youtube_service.py    # Download de vídeos
│   └── whisper_service.py    # Transcrição
├── middleware/
│   ├── __init__.py           
│   └── auth.py               # Autenticação
└── utils/
    ├── __init__.py           
    └── helpers.py            # Funções auxiliares
```

## ⚙️ Configurações Avançadas

### Variáveis de Ambiente Disponíveis

| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `API_TOKEN` | Token de autenticação (obrigatório) | - |
| `PORT` | Porta do servidor | 8000 |
| `WHISPER_MODEL` | Modelo Whisper (tiny, small, medium, large) | medium |
| `LOG_LEVEL` | Nível de log (DEBUG, INFO, WARNING, ERROR) | INFO |
| `MAX_VIDEOS_PER_REQUEST` | Máximo de vídeos por requisição | 10 |

### Modelos Whisper Disponíveis

| Modelo | Tamanho | Precisão | Velocidade |
|--------|---------|----------|------------|
| tiny | ~39 MB | Baixa | Muito rápida |
| small | ~244 MB | Média | Rápida |
| medium | ~769 MB | Boa | Moderada |
| large | ~1550 MB | Excelente | Lenta |

## 🚀 Deploy Rápido

```bash
# 1. Clone e configure
git clone https://github.com/seu-usuario/youtube-transcription-api.git
cd youtube-transcription-api
cp .env.example .env
# Edite .env com seu token

# 2. Execute com Docker
docker-compose up -d

# 3. Teste
curl -X POST "http://localhost:8000/video/getData" \\
  -H "Authorization: Bearer SEU_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"video_urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]}'
```

✨ **API pronta para uso!**'''

    write_file("README.md", readme_content)


def main():
    """Função principal do gerador"""
    print("🎤 YouTube Transcription API - Gerador de Projeto")
    print("=" * 60)

    # Criar estrutura de diretórios
    print("\n📁 Criando estrutura de diretórios...")
    create_directory_structure()

    # Gerar todos os arquivos
    print("\n📝 Gerando arquivos do projeto...")
    generate_all_files()

    print("\n" + "=" * 60)
    print("🎉 PROJETO GERADO COM SUCESSO!")
    print("\n📋 Próximos passos:")
    print("   1. cp .env.example .env")
    print("   2. Edite .env com seu API_TOKEN")
    print("   3. pip install -r requirements.txt")
    print("   4. uvicorn main:app --reload")
    print("   5. Acesse http://localhost:8000/docs")

    print("\n🐳 Com Docker:")
    print("   1. cp .env.example .env")
    print("   2. Edite .env com seu API_TOKEN")
    print("   3. docker-compose up --build")

    print("\n🚀 Para EasyPanel:")
    print("   1. Suba tudo para o GitHub")
    print("   2. Configure API_TOKEN nas variáveis de ambiente")
    print("   3. EasyPanel usará o Dockerfile automaticamente")

    print("\n✨ Estrutura criada em:")
    import os
    print(f"   {os.path.abspath('.')}")

    # Listar arquivos criados
    import os
    files_created = []
    for root, dirs, files in os.walk('.'):
        for file in files:
            if not file.startswith('.') and file != 'generate_project.py':
                files_created.append(os.path.join(root, file))

    print(f"\n📊 Total de arquivos criados: {len(files_created)}")


if __name__ == "__main__":
    main()