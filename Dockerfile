# Ubuntu 20.04 LTS para melhor compatibilidade com Playwright
FROM ubuntu:20.04

# Evitar prompts interativos
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Playwright configurações
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PLAYWRIGHT_DOWNLOAD_TIMEOUT=300000

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    # Ferramentas básicas
    software-properties-common \
    curl \
    wget \
    ca-certificates \
    gnupg \
    git \
    # FFmpeg para processamento de áudio
    ffmpeg \
    # Dependências COMPLETAS do Chromium para Ubuntu 20.04
    libnss3 \
    libnspr4 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libxtst6 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0 \
    # Dependências críticas que estavam faltando
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcb-dri3-0 \
    libxcb-shm0 \
    libxext6 \
    libxi6 \
    libxrender1 \
    libxfixes3 \
    libxcursor1 \
    libxdamage1 \
    libfontconfig1 \
    libfreetype6 \
    libdbus-1-3 \
    libexpat1 \
    libuuid1 \
    # Libs adicionais para Chrome
    libappindicator3-1 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libgconf-2-4 \
    libgdk-pixbuf2.0-0 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxi6 \
    libxrandr2 \
    libxrender1 \
    libxss1 \
    libxtst6 \
    # Fontes
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    # Xvfb para ambiente headless
    xvfb \
    # Dependências adicionais
    libu2f-udev \
    libvulkan1 \
    # Lib essencial que pode estar faltando
    libgcc-s1 \
    libc6-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Adicionar repositório Python 3.11
RUN add-apt-repository ppa:deadsnakes/ppa -y && \
    apt-get update && \
    apt-get install -y \
        python3.11 \
        python3.11-dev \
        python3.11-venv \
        python3.11-distutils \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Criar links simbólicos para Python
RUN ln -sf /usr/bin/python3.11 /usr/bin/python3 && \
    ln -sf /usr/bin/python3.11 /usr/bin/python

# Instalar pip para Python 3.11
RUN curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

# Atualizar pip
RUN python3.11 -m pip install --upgrade pip setuptools wheel

# Criar usuário não-root
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Definir diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

# Instalar Playwright com stealth otimizado
RUN python3.11 -m playwright install-deps && \
    python3.11 -m playwright install chromium --with-deps && \
    python3.11 -m playwright install firefox --with-deps

# Criar diretórios necessários com permissões corretas
RUN mkdir -p /app/logs \
             /app/temp \
             /app/browser_profile \
             /app/crashpad \
             /tmp/chrome-crashpad \
             /ms-playwright && \
    chmod 777 /tmp/chrome-crashpad && \
    chown -R appuser:appuser /app /ms-playwright

# Copiar código da aplicação
COPY --chown=appuser:appuser . .

# Criar arquivo cookies.txt se não existir
RUN if [ ! -f cookies.txt ]; then \
    echo "# Netscape HTTP Cookie File" > cookies.txt && \
    echo "# Este arquivo será automaticamente preenchido pela sessão persistente" >> cookies.txt && \
    chown appuser:appuser cookies.txt; \
    fi

# Mudar para usuário não-root
USER appuser

# Configurar variáveis de ambiente para Chromium
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    DISPLAY=:99 \
    # Variáveis críticas para evitar crash do Chrome
    CHROME_DEVEL_SANDBOX=false \
    CHROME_NO_FIRST_RUN=true \
    GOOGLE_API_KEY="no" \
    GOOGLE_DEFAULT_CLIENT_ID="no" \
    GOOGLE_DEFAULT_CLIENT_SECRET="no" \
    # Evitar crash relacionado a libs
    LD_LIBRARY_PATH=/ms-playwright/chromium-*/chrome-linux \
    # Configurações de memória
    MALLOC_CHECK_=0 \
    MALLOC_PERTURB_=0 \
    # Disable crash reports
    CHROME_CRASHPAD_PIPE_NAME="" \
    BREAKPAD_DUMP_LOCATION="" \
    # Force single process
    CHROMIUM_FLAGS="--single-process --no-zygote"

# Expor porta
EXPOSE 8000

# Copiar script de Chrome
COPY --chown=appuser:appuser start_chrome.sh /app/start_chrome.sh
RUN chmod +x /app/start_chrome.sh

# Script de inicialização com Xvfb e Chrome
RUN echo '#!/bin/bash\n\
# Iniciar Xvfb em background\n\
Xvfb :99 -screen 0 1920x1080x24 > /dev/null 2>&1 &\n\
# Aguardar Xvfb inicializar\n\
sleep 2\n\
# Iniciar Chrome persistente\n\
/app/start_chrome.sh\n\
# Aguardar Chrome estar pronto\n\
sleep 3\n\
# Executar aplicação\n\
exec python3.11 -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1\n\
' > /app/start.sh && chmod +x /app/start.sh

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando padrão
CMD ["/app/start.sh"]
