# 🎤 YouTube Video Transcription API

Uma API REST moderna e robusta para transcrever vídeos do YouTube usando OpenAI Whisper. Desenvolvida com FastAPI e pronta para produção.

## 🚀 Características

- ⚡ **FastAPI**: Framework moderno e performático
- 🎯 **Whisper AI**: Transcrição precisa de áudios
- 🔐 **Autenticação**: Sistema de tokens seguros
- 🐳 **Docker**: Containerizado e pronto para deploy
- 📊 **Logging**: Sistema completo de logs
- 🔄 **Assíncrono**: Processamento não-bloqueante
- 🧹 **Auto-limpeza**: Remove arquivos temporários automaticamente
- ✂️ **Chunking Inteligente**: Divide áudios longos automaticamente
- 🍪 **Cookies Dinâmicos**: Refresh automático para sessões estáveis

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
venv\Scripts\activate     # Windows

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
curl -X POST "http://localhost:8000/video/getData" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
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

#### 🔐 **Autenticação**
| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `API_TOKEN` | Token de autenticação (obrigatório) | - |

#### 🎤 **OpenAI Whisper**
| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `OPENAI_API_KEY` | Chave da API OpenAI (obrigatória) | - |
| `WHISPER_API_MODEL` | Modelo Whisper API | whisper-1 |
| `WHISPER_TIMEOUT` | Timeout para transcrições (segundos) | 600.0 |
| `WHISPER_MAX_RETRIES` | Máximo de tentativas | 3 |
| `WHISPER_RETRY_DELAY` | Delay entre tentativas (segundos) | 2.0 |
| `WHISPER_CHUNK_DURATION_SECONDS` | Duração máxima por chunk (segundos) | 1500.0 |

> **💡 Chunking de Áudio**: Áudios maiores que o limite configurado são automaticamente divididos em chunks menores, transcritos separadamente e depois concatenados, resolvendo problemas de timeout com vídeos longos.

#### 🌐 **Navegador e Cookies**
| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `BROWSER_REFRESH_INTERVAL` | Intervalo de refresh dos cookies (segundos) | 10 |

> **🍪 Cookies Dinâmicos**: O navegador em background atualiza automaticamente os cookies do YouTube no intervalo configurado, mantendo sessões ativas e evitando bloqueios.

#### ⚙️ **Servidor**
| Variável | Descrição | Padrão |
|----------|-----------|---------|
| `PORT` | Porta do servidor | 8000 |
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
curl -X POST "http://localhost:8000/video/getData" \
  -H "Authorization: Bearer SEU_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"video_urls": ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]}'
```

✨ **API pronta para uso!**