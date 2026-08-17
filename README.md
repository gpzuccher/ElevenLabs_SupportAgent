# ElevenLabs SupportAgent

Estudo prático de integração da Conversational AI da ElevenLabs com um
sistema de terceiros real. Caso de uso simulado: suporte ao cliente para uma
holding com múltiplas marcas de e-commerce (Aurora Cosméticos, Nordic Home),
onde o agente de voz consulta um sistema real (Monday.com, usado aqui como
substituto de um sistema interno de pedidos) via tool-calling para responder
"cadê meu pedido" e "posso trocar".

O objetivo é entender na prática como funciona toda a cadeia: tool-calling do
agente → backend próprio → sistema externo real, e como provisionar múltiplos
agentes de forma programática em vez de configurar um por um no dashboard.

## Estrutura

- `monday_client.py` — cliente GraphQL do board "Orders" no Monday.com
  (board 18424777126). Documenta o mapeamento coluna → ID no topo do
  arquivo.
- `ecommerce_api.py` — API FastAPI que o agente ElevenLabs chama via
  tool-calling. Consulta o Monday.com em vez de dados hardcoded.
- `provision_agents.py` — lê `brands.csv` e cria um agente ElevenLabs por
  marca, já com as tools apontando para a API acima. Suporta `--dry-run`.
- `brands.csv` — marcas de exemplo (Aurora Cosméticos, Nordic Home).

## Setup

**Requer Python 3.10+** (o código usa a sintaxe `str | None` / `dict | None`,
introduzida no Python 3.10 — em versões anteriores a importação falha com
`TypeError`).

### Windows

**Importante:** crie o ambiente virtual fora do OneDrive (ex: `C:\venvs\supportagent`),
não dentro da pasta do repositório — um caminho muito aninhado dentro do
OneDrive quebra a instalação do SDK `elevenlabs` no Windows (erro de long
path).

```bash
python -m venv /c/venvs/supportagent
/c/venvs/supportagent/Scripts/pip install -r requirements.txt
cp .env.example .env
# editar .env e preencher MONDAY_API_TOKEN, MONDAY_BOARD_ID,
# ELEVENLABS_API_KEY e MOCK_API_BASE_URL
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# editar .env e preencher MONDAY_API_TOKEN, MONDAY_BOARD_ID,
# ELEVENLABS_API_KEY e MOCK_API_BASE_URL
```

## Rodar a API

```bash
# Windows
/c/venvs/supportagent/Scripts/python -m uvicorn ecommerce_api:app --reload --port 8000

# macOS / Linux
.venv/bin/uvicorn ecommerce_api:app --reload --port 8000
```

Docs interativas (Swagger): http://localhost:8000/docs

## Expor a API publicamente (ngrok)

Necessário para o agente ElevenLabs (rodando na nuvem) conseguir chamar as
tools da sua API local.

```bash
ngrok http 8000
```

Copie a URL pública gerada (ex: `https://xxxx.ngrok-free.app`) e atualize:
- `MOCK_API_BASE_URL` no `.env` (usado por `provision_agents.py`);
- a URL das tools `lookup_order_status` e `check_return_eligibility` no
  agente já criado no dashboard da ElevenLabs (se o agente já existir e
  você não for reprovisionar).

Se o túnel do ngrok estiver configurado na porta **80** em vez da 8000
(ex: domínio reservado que só libera 80/443), suba a API nessa porta —
requer privilégio de root:

```bash
sudo .venv/bin/uvicorn ecommerce_api:app --port 80
```

## Provisionar agentes (CSV → N agentes ElevenLabs)

```bash
# só mostra o payload, não chama a API
.venv/bin/python provision_agents.py --csv brands.csv --dry-run

# cria de verdade — precisa de ELEVENLABS_API_KEY no .env e de
# MOCK_API_BASE_URL apontando para uma URL pública (ex: túnel do ngrok),
# já que o webhook tool precisa alcançar a API pela internet
.venv/bin/python provision_agents.py --csv brands.csv
```



