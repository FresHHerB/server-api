from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from typing import List
import os
import asyncio
from dotenv import load_dotenv
import signal
import sys

from models.schemas import VideoRequest, VideoResponse, VideoData
from services.youtube_service import YouTubeService
from services.whisper_service import WhisperService
from services.background_browser import BackgroundBrowser
from middleware.auth import verify_token

# Carregar variáveis de ambiente
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/app/logs/app.log") if os.path.exists("/app/logs") else logging.NullHandler()
    ]
)
logger = logging.getLogger("yt-transcription-persistent")

# Inicializar FastAPI
app = FastAPI(
    title="YouTube Video Transcription API - Persistent Session",
    description="API para transcrever vídeos do YouTube com sessão persistente do navegador",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configurar CORS
allow_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "*")
allow_origins = [o.strip() for o in allow_origins_env.split(",")] if allow_origins_env else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Variáveis globais para serviços
background_browser = None
youtube_service = None
whisper_service = None

# Esquema de segurança
security = HTTPBearer()

# Configurações
MAX_VIDEOS_PER_REQUEST = int(os.getenv("MAX_VIDEOS_PER_REQUEST", "10"))
AUTO_CLEANUP_TEMP_FILES = os.getenv("AUTO_CLEANUP_TEMP_FILES", "true").strip().lower() == "true"
PERSISTENT_SESSION_ENABLED = os.getenv("PERSISTENT_SESSION_ENABLED", "true").strip().lower() == "true"

# Variável global para controle de shutdown
_shutdown_event = asyncio.Event()

async def graceful_shutdown():
    """Shutdown gracioso da aplicação"""
    global background_browser, youtube_service, whisper_service
    
    logger.info("🛑 Iniciando shutdown gracioso...")
    
    try:
        # Parar navegador em background
        if background_browser:
            logger.info("🤖 Parando navegador em background...")
            await background_browser.stop()
        
        # Encerrar WhisperService
        if whisper_service:
            await whisper_service.cleanup()
        
        # Limpeza de arquivos temporários
        if AUTO_CLEANUP_TEMP_FILES and youtube_service:
            youtube_service.cleanup_temp_directory()
            
        logger.info("✅ Shutdown gracioso concluído")
        
    except Exception as e:
        logger.warning(f"⚠️ Erro durante shutdown: {e}")

def signal_handler(sig, frame):
    """Handler para sinais do sistema"""
    logger.info(f"🔄 Recebido sinal {sig}, iniciando shutdown...")
    _shutdown_event.set()
    loop = asyncio.get_event_loop()
    loop.create_task(graceful_shutdown())

# Registrar handlers de sinal
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

@app.on_event("startup")
async def startup_event():
    """Inicialização da aplicação com navegador em background"""
    global background_browser, youtube_service, whisper_service
    
    logger.info("🚀 Iniciando YouTube Transcription API v4.0 (Background Browser)...")

    # Verificar variáveis obrigatórias
    api_token = os.getenv("API_TOKEN")
    if not api_token:
        logger.error("❌ API_TOKEN não configurado no arquivo .env")
        raise RuntimeError("API_TOKEN é obrigatório")

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        logger.error("❌ OPENAI_API_KEY não configurado no arquivo .env")
        raise RuntimeError("OPENAI_API_KEY é obrigatório")

    try:
        # Inicializar WhisperService
        logger.info("🎤 Inicializando WhisperService...")
        whisper_service = WhisperService()
        
        # Inicializar Navegador em Background
        if PERSISTENT_SESSION_ENABLED:
            logger.info("🤖 Inicializando navegador em background...")
            background_browser = BackgroundBrowser()
            
            # Inicializar navegador background
            browser_ready = await background_browser.start()
            
            if browser_ready:
                logger.info("✅ Navegador em background ativo!")
                logger.info("🔄 Refresh automático a cada 10s iniciado")
            else:
                logger.warning("⚠️ Falha no navegador background, usando modo tradicional...")
                background_browser = None
        else:
            logger.info("🔄 Modo navegador em background desabilitado")
            background_browser = None
        
        # Inicializar YouTubeService sem session_manager
        youtube_service = YouTubeService(session_manager=None)
        
        # Log de status final
        if background_browser:
            browser_status = background_browser.get_status()
            logger.info(f"🤖 Status do navegador background: {browser_status}")
        
        logger.info("✅ API inicializada com sucesso!")

    except Exception as e:
        logger.error(f"❌ Erro crítico na inicialização: {e}")
        if background_browser:
            await background_browser.stop()
        raise RuntimeError(f"Falha na inicialização: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Limpeza ao encerrar a aplicação"""
    await graceful_shutdown()

@app.get("/")
async def root():
    """Endpoint raiz - Health check"""
    browser_info = {}
    if background_browser:
        try:
            browser_info = background_browser.get_status()
        except Exception:
            browser_info = {"error": "Status não disponível"}
    
    return {
        "message": "YouTube Video Transcription API - Background Browser",
        "status": "running",
        "version": "4.0.0",
        "background_browser_enabled": PERSISTENT_SESSION_ENABLED,
        "browser_info": browser_info
    }

@app.get("/health")
async def health_check():
    """Health check detalhado"""
    try:
        health_status = {
            "status": "healthy",
            "version": "4.0.0",
            "background_browser": {
                "enabled": PERSISTENT_SESSION_ENABLED,
                "active": False,
                "details": {}
            },
            "services": {
                "whisper": whisper_service is not None,
                "youtube": youtube_service is not None
            }
        }
        
        # Verificar status do navegador em background
        if background_browser:
            try:
                browser_status = background_browser.get_status()
                health_status["background_browser"]["active"] = browser_status.get("is_running", False)
                health_status["background_browser"]["details"] = browser_status
            except Exception as e:
                health_status["background_browser"]["error"] = str(e)
        
        return health_status
        
    except Exception as e:
        logger.warning(f"⚠️ Erro no health check: {e}")
        return {"status": "degraded", "error": str(e)}

@app.get("/browser/status")
async def get_browser_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Status detalhado do navegador em background"""
    try:
        verify_token(credentials.credentials)
        
        if not background_browser:
            return {
                "success": False,
                "message": "Navegador em background não está ativo",
                "background_browser_enabled": PERSISTENT_SESSION_ENABLED
            }
        
        browser_status = background_browser.get_status()
        
        return {
            "success": True,
            "browser_status": browser_status,
            "message": "Navegador rodando em background com refresh automático"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao obter status do navegador: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter status do navegador: {str(e)}"
        )

# Endpoints de refresh removidos - navegador em background faz refresh automático

@app.post("/video/getData", response_model=VideoResponse)
async def get_video_data(
    request: VideoRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Endpoint principal para transcrever vídeos com navegador em background

    Args:
        request: Lista de URLs de vídeos do YouTube
        credentials: Token de autenticação

    Returns:
        VideoResponse: Lista com dados dos vídeos (título, transcrição, num_char)
    """
    try:
        verify_token(credentials.credentials)

        if not request.video_urls:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A lista 'video_urls' não pode ser vazia.",
            )

        if len(request.video_urls) > MAX_VIDEOS_PER_REQUEST:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Máximo de {MAX_VIDEOS_PER_REQUEST} vídeos por requisição.",
            )

        logger.info("📝 Processando %d vídeo(s) com cookies sempre atualizados...", len(request.video_urls))

        video_data_list: List[VideoData] = []

        # Processamento sequencial simples - cookies sempre frescos do background browser
        for i, video_url in enumerate(request.video_urls, 1):
            try:
                logger.info("🎬 Processando vídeo %d/%d: %s", i, len(request.video_urls), video_url)

                # Download do áudio
                audio_path, video_title = await youtube_service.download_audio(video_url)

                # Transcrição
                transcription = await whisper_service.transcribe(audio_path)
                transcription = (transcription or "").strip()

                # Criar objeto de dados do vídeo
                video_data = VideoData(
                    titulo=video_title,
                    transcricao=transcription,
                    num_char=len(transcription),
                )

                video_data_list.append(video_data)
                logger.info("✅ Vídeo %d processado: %s (%d chars)", i, video_title, video_data.num_char)

            except Exception as e:
                logger.error("❌ Erro ao processar vídeo %s: %s", video_url, str(e))
                video_data_list.append(
                    VideoData(
                        titulo=f"Erro ao processar: {video_url}",
                        transcricao=f"Erro: {str(e)}",
                        num_char=0,
                    )
                )

        logger.info("🎉 Processamento concluído! %d vídeo(s) processado(s)", len(video_data_list))

        return VideoResponse(
            success=True,
            message=f"Processados {len(video_data_list)} vídeo(s) com sucesso",
            data=video_data_list,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("❌ Erro interno: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno do servidor: {str(e)}",
        )

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
