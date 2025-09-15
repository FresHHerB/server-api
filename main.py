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
from services.persistent_session_manager import PersistentSessionManager
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
session_manager = None
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
    global session_manager, youtube_service, whisper_service
    
    logger.info("🛑 Iniciando shutdown gracioso...")
    
    try:
        # Encerrar sessão persistente
        if session_manager:
            logger.info("🍪 Encerrando sessão persistente...")
            await session_manager.shutdown()
        
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
    """Inicialização da aplicação com sessão persistente"""
    global session_manager, youtube_service, whisper_service
    
    logger.info("🚀 Iniciando YouTube Transcription API v3.0 (Sessão Persistente)...")

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
        # Inicializar WhisperService primeiro
        logger.info("🎤 Inicializando WhisperService...")
        whisper_service = WhisperService()
        
        # Inicializar Gerenciador de Sessão Persistente
        if PERSISTENT_SESSION_ENABLED:
            logger.info("🎭 Inicializando sessão persistente do navegador...")
            session_manager = PersistentSessionManager()
            
            # Inicializar e aguardar sessão estar pronta
            session_ready = await session_manager.initialize()
            
            if session_ready:
                logger.info("✅ Sessão persistente inicializada com sucesso!")
            else:
                logger.warning("⚠️ Falha na sessão persistente, usando modo fallback...")
                session_manager = None
        else:
            logger.info("🔄 Modo sessão persistente desabilitado")
            session_manager = None
        
        # Inicializar YouTubeService
        youtube_service = YouTubeService(session_manager=session_manager)
        
        # Log de status final
        if session_manager:
            session_status = await session_manager.get_session_status()
            logger.info(f"📊 Status da sessão: {session_status}")
        
        logger.info("✅ API inicializada com sucesso!")

    except Exception as e:
        logger.error(f"❌ Erro crítico na inicialização: {e}")
        if session_manager:
            await session_manager.shutdown()
        raise RuntimeError(f"Falha na inicialização: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Limpeza ao encerrar a aplicação"""
    await graceful_shutdown()

@app.get("/")
async def root():
    """Endpoint raiz - Health check"""
    session_info = {}
    if session_manager:
        try:
            session_info = await session_manager.get_session_status()
        except Exception:
            session_info = {"error": "Status não disponível"}
    
    return {
        "message": "YouTube Video Transcription API - Persistent Session",
        "status": "running",
        "version": "3.0.0",
        "persistent_session_enabled": PERSISTENT_SESSION_ENABLED,
        "session_info": session_info
    }

@app.get("/health")
async def health_check():
    """Health check detalhado"""
    try:
        health_status = {
            "status": "healthy",
            "version": "3.0.0",
            "persistent_session": {
                "enabled": PERSISTENT_SESSION_ENABLED,
                "active": False,
                "details": {}
            },
            "services": {
                "whisper": whisper_service is not None,
                "youtube": youtube_service is not None
            }
        }
        
        # Verificar status da sessão persistente
        if session_manager:
            try:
                session_status = await session_manager.get_session_status()
                health_status["persistent_session"]["active"] = session_status.get("is_active", False)
                health_status["persistent_session"]["details"] = session_status
            except Exception as e:
                health_status["persistent_session"]["error"] = str(e)
        
        return health_status
        
    except Exception as e:
        logger.warning(f"⚠️ Erro no health check: {e}")
        return {"status": "degraded", "error": str(e)}

@app.get("/session/status")
async def get_session_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Status detalhado da sessão persistente"""
    try:
        verify_token(credentials.credentials)
        
        if not session_manager:
            return {
                "success": False,
                "message": "Sessão persistente não está ativa",
                "persistent_session_enabled": PERSISTENT_SESSION_ENABLED
            }
        
        session_status = await session_manager.get_session_status()
        detailed_status = await session_manager.get_detailed_status()
        
        return {
            "success": True,
            "session_status": session_status,
            "detailed_status": detailed_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao obter status da sessão: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao obter status da sessão: {str(e)}"
        )

@app.post("/session/refresh")
async def refresh_session(
    force: bool = False,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Força refresh da sessão persistente"""
    try:
        verify_token(credentials.credentials)
        
        if not session_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sessão persistente não está ativa"
            )
        
        logger.info(f"🔄 Refresh da sessão solicitado (force={force})")
        
        if force:
            success = await session_manager.force_refresh()
        else:
            success = await session_manager.refresh_cookies()
        
        session_status = await session_manager.get_session_status()
        
        return {
            "success": success,
            "message": "Sessão atualizada com sucesso" if success else "Falha na atualização",
            "session_status": session_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao refresh sessão: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao refresh sessão: {str(e)}"
        )

@app.post("/cookies/update")
async def update_cookies(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Endpoint específico para atualizar cookies"""
    try:
        verify_token(credentials.credentials)
        
        if not session_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Sessão persistente não está ativa"
            )
        
        logger.info("🍪 Atualização de cookies solicitada...")
        
        # Força uma nova navegação e extração de cookies
        success = await session_manager.force_refresh()
        
        if success:
            session_status = await session_manager.get_session_status()
            logger.info("✅ Cookies atualizados com sucesso!")
            
            return {
                "success": True,
                "message": "Cookies atualizados com sucesso",
                "refresh_count": session_status.get("refresh_count", 0),
                "last_cookie_update": session_status.get("last_cookie_update"),
                "session_active": session_status.get("is_active", False)
            }
        else:
            logger.warning("⚠️ Falha na atualização dos cookies")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha na atualização dos cookies"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar cookies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar cookies: {str(e)}"
        )

@app.post("/video/getData", response_model=VideoResponse)
async def get_video_data(
    request: VideoRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Endpoint principal para transcrever vídeos com sessão persistente ativa

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

        logger.info("📝 Processando %d vídeo(s) com sessão persistente...", len(request.video_urls))

        # Refresh da sessão antes do processamento
        if session_manager:
            logger.info("🔄 Atualizando sessão antes do processamento...")
            refresh_success = await session_manager.refresh_cookies()
            if not refresh_success:
                logger.warning("⚠️ Falha no refresh da sessão, tentando continuar...")

        video_data_list: List[VideoData] = []

        # Processamento sequencial com refresh entre vídeos
        for i, video_url in enumerate(request.video_urls, 1):
            try:
                logger.info("🎬 Processando vídeo %d/%d: %s", i, len(request.video_urls), video_url)

                # Refresh da sessão a cada vídeo (para manter ativa)
                if session_manager and i > 1:
                    await session_manager.light_refresh()

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
