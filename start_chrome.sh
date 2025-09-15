#!/bin/bash

# Script para manter Chrome rodando em background no container
echo "🚀 Iniciando Chrome persistente em background..."

# Argumentos mínimos para Chrome em container
CHROME_ARGS="
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
"

# Encontrar binário do Chrome
if [ -f "/ms-playwright/chromium-*/chrome-linux/chrome" ]; then
    CHROME_BIN=$(find /ms-playwright -name "chrome" -type f | head -1)
else
    CHROME_BIN="chromium-browser"
fi

echo "🔍 Chrome binary: $CHROME_BIN"
echo "🔧 Debug port: 9222"
echo "📁 Data dir: /app/browser_profile"

# Iniciar Chrome em background
nohup $CHROME_BIN $CHROME_ARGS > /app/logs/chrome.log 2>&1 &
CHROME_PID=$!

echo "✅ Chrome iniciado com PID: $CHROME_PID"
echo $CHROME_PID > /tmp/chrome.pid

# Aguardar Chrome estar pronto
echo "⏳ Aguardando Chrome estar pronto..."
for i in {1..10}; do
    if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
        echo "✅ Chrome está respondendo na porta 9222"
        break
    fi
    echo "⏳ Tentativa $i/10..."
    sleep 2
done

# Verificar se Chrome está rodando
if curl -s http://localhost:9222/json/version > /dev/null 2>&1; then
    echo "🎉 Chrome persistente está ativo!"
    curl -s http://localhost:9222/json/version | head -1
else
    echo "❌ Chrome não está respondendo"
    exit 1
fi