#!/bin/bash

# Script para manter Chromium do Playwright rodando em background
echo "🚀 Iniciando Chromium persistente em background..."

# Encontrar binário do Chromium do Playwright
CHROMIUM_BIN=""
if [ -d "/ms-playwright" ]; then
    # Procurar pelo chrome do Playwright
    CHROMIUM_BIN=$(find /ms-playwright -name "chrome" -type f -path "*/chromium-*/chrome-linux/chrome" 2>/dev/null | head -1)
fi

# Fallback se não encontrar
if [ -z "$CHROMIUM_BIN" ] || [ ! -f "$CHROMIUM_BIN" ]; then
    echo "❌ Chromium do Playwright não encontrado, listando diretório..."
    ls -la /ms-playwright/ 2>/dev/null || echo "Diretório /ms-playwright não existe"
    find /ms-playwright -name "*chrome*" -type f 2>/dev/null | head -5
    exit 1
fi

echo "🔍 Chromium binary: $CHROMIUM_BIN"
echo "🔧 Debug port: 9222"
echo "📁 Data dir: /app/browser_profile"

# Argumentos mínimos para Chromium em container
CHROMIUM_ARGS="
--no-sandbox
--disable-dev-shm-usage
--headless=new
--disable-gpu
--no-first-run
--disable-crash-reporter
--disable-breakpad
--remote-debugging-port=9222
--remote-allow-origins=*
--user-data-dir=/app/browser_profile
--disable-web-security
--disable-features=VizDisplayCompositor
--disable-software-rasterizer
--disable-background-timer-throttling
"

# Teste se binário é executável
if [ ! -x "$CHROMIUM_BIN" ]; then
    echo "❌ Binário não é executável: $CHROMIUM_BIN"
    ls -la "$CHROMIUM_BIN"
    exit 1
fi

# Iniciar Chromium em background
echo "▶️ Executando: $CHROMIUM_BIN $CHROMIUM_ARGS"
nohup "$CHROMIUM_BIN" $CHROMIUM_ARGS > /app/logs/chrome.log 2>&1 &
CHROME_PID=$!

echo "✅ Chromium iniciado com PID: $CHROME_PID"
echo $CHROME_PID > /tmp/chrome.pid

# Aguardar Chromium estar pronto
echo "⏳ Aguardando Chromium estar pronto..."
for i in {1..15}; do
    if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
        echo "✅ Chromium está respondendo na porta 9222"
        break
    fi
    echo "⏳ Tentativa $i/15..."
    sleep 3
done

# Verificar se Chromium está rodando
if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "🎉 Chromium persistente está ativo!"
    curl -s http://localhost:9222/json/version
else
    echo "❌ Chromium não está respondendo"
    echo "📋 Log do Chromium:"
    tail -20 /app/logs/chrome.log 2>/dev/null || echo "Sem logs disponíveis"
    echo "🔍 Processos do Chrome:"
    ps aux | grep -i chrome || echo "Nenhum processo Chrome encontrado"
    exit 1
fi