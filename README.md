# P.U.R.A. — Purificação Unificada e Reativa do Ar (versão local, sem Docker)

Sistema autônomo de monitoramento e purificação de microclimas internos para habitações muito vedadas. Nós **ESP32** medem CO₂, PM2.5 e VOC; um servidor **Python** prevê a evolução dos poluentes, escolhe o acionamento de **exaustor e purificador** (fuzzy, algoritmo genético ou simulated annealing) e envia comandos assinados de volta, sem intervenção manual.

Esta versão mantém **a mesma lógica do projeto original** (modelo físico, otimizadores, guardas de segurança, assinatura HMAC, painel), mas **não precisa de Docker nem de broker MQTT**: o servidor e os ESP32 virtuais rodam no mesmo processo Python, ligados por um barramento em memória (`LocalBus`). O modo MQTT continua disponível para ESP32 reais.

> **Status: MVP.** Cenários sintéticos e física simplificada; validar com hardware é o objetivo dos testes de bancada.

## Início rápido

Requisito: **Python 3.10 ou superior** ([python.org/downloads](https://www.python.org/downloads/) — no Windows, marque **"Add python.exe to PATH"** no instalador).

### Windows

Dê duplo clique em **`iniciar.bat`**. Na primeira vez ele cria o ambiente virtual, instala as dependências (1–2 min), cria o `.env` e abre o painel no navegador.

Ou, manualmente, no PowerShell dentro da pasta do projeto:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e .
Copy-Item .env.example .env
.venv\Scripts\python -m pura --open
```

> Se o PowerShell bloquear scripts, não ative o venv: chame `.venv\Scripts\python` direto, como acima.

### Linux / macOS

```bash
./iniciar.sh
```

ou

```bash
python3 -m venv .venv && .venv/bin/python -m pip install -e .
cp .env.example .env
.venv/bin/python -m pura --open
```

Painel em **http://localhost:8000**. Para parar: `Ctrl+C` (ou feche a janela).

## O que você vê

Dois cômodos simulados (sala e quarto) ao vivo: CO₂, PM2.5, previsão de 15 minutos, nível do exaustor e do purificador, eventos (leituras aceitas/rejeitadas, limites excedidos, modo seguro) e um seletor de estratégia (`fuzzy`, `hysteresis`, `timer`, `ga`, `sa`). O tempo simulado roda 30× mais rápido, então em um minuto você já vê o PM2.5 subir, o purificador reagir e o ar voltar ao normal.

## Opções de linha de comando

```
python -m pura [--mqtt] [--open] [--host H] [--port P] [--speed X] [--period S] [--seed N]
```

| Opção | Efeito |
|---|---|
| `--open` | abre o painel no navegador |
| `--port 8001` | muda a porta (padrão 8000) |
| `--host 0.0.0.0` | libera o painel para a rede local (padrão: só esta máquina) |
| `--speed 1` | tempo simulado em tempo real (padrão 30×) |
| `--seed 3` | outro cenário simulado |
| `--mqtt` | usa um broker MQTT externo (ESP32 reais), sem simulador local |

## Configuração (`.env`)

Todas as variáveis são opcionais no modo local. O programa lê o `.env` sozinho (não precisa de `source`). Variáveis já definidas no ambiente têm prioridade. Principais:

| Variável | Para quê |
|---|---|
| `PURA_ROOMS` | cômodos: `nome:volume_m3[:bedroom]`, separados por vírgula (`bedroom` ativa a janela de sono 22h–7h) |
| `PURA_OPTIMIZER` | estratégia inicial (`fuzzy`, `hysteresis`, `timer`, `ga`, `sa`) |
| `PURA_CYCLE_S` / `PURA_MIN_RUN_S` / `PURA_STALE_S` | ciclo de decisão, tempo mínimo ligado, tempo até "sem dados". Produção: 900 / 600 / 180 |
| `PURA_KEYS` | chaves HMAC por cômodo. Em branco no modo local (geradas a cada execução); **obrigatório** com ESP32 real |
| `PURA_API_PORT` / `PURA_API_TOKEN` | porta do painel e token do `POST /api/optimizer` |

## Testes com ESP32 real

Use o modo `--mqtt` com um broker Mosquitto instalado direto no computador. Passo a passo para Windows: **[`docs/esp32-real.md`](docs/esp32-real.md)**. Ligações, firmware e checklist de validação: [`docs/hardware-testing.md`](docs/hardware-testing.md).

## Testes e experimentos

```bash
pip install -e ".[dev]"
pytest --cov=pura      # função objetivo, restrições, segurança, guardas, fluxo ponta a ponta sem broker, API
ruff check .

python experiments/run_benchmark.py --runs 30                      # otimizador × baselines (CSV e gráfico em results/)
python experiments/validate_predictor.py data/AirQualityUCI.csv    # previsor vs. persistência (dataset UCI)
```

## Arquitetura

```
  Modo local (padrão)                              Modo MQTT (--mqtt, ESP32 reais)
  ┌───────────────────────────────────────┐        ┌────────────┐  MQTT  ┌───────────────────────┐
  │ um único processo Python              │        │ ESP32      │◄──────►│ Mosquitto ◄► servidor │
  │  nós virtuais ◄─ LocalBus ─► servidor │        │ (firmware) │        │ (mesmo núcleo)        │
  └───────────────────────────────────────┘        └────────────┘        └───────────────────────┘

  servidor:  security (HMAC · janela de tempo · nonce) → pipeline (calibração → previsão Holt)
             → optimizers (Strategy: fuzzy|GA|SA|baselines) → guards (Chain: Safe→Teto CO₂→Ruído→Min-run)
             → events (Observer) → API FastAPI + WebSocket + painel
```

| Padrão | Onde |
|---|---|
| Strategy | `optimizers/` — troque a estratégia pelo painel ou por `PURA_OPTIMIZER` |
| Chain of Responsibility | `guards.py` — cadeia de segurança antes de qualquer comando |
| Observer | `events.py` — painel, logs e alertas assinam eventos |
| Ports & Adapters | `adapters/` — o núcleo não conhece MQTT; `LocalBus` e `MqttBus` são intercambiáveis |
| Pipeline | `pipeline.py` + `service.py` — validação → calibração → previsão → decisão → guardas |

Decisões em [`docs/adr/`](docs/adr), modelagem em [`docs/modelagem.md`](docs/modelagem.md), protocolo e ameaças em [`docs/protocolo.md`](docs/protocolo.md).

## O que mudou em relação ao projeto original

| Original | Esta versão |
|---|---|
| `docker compose up` (broker + servidor + simulador) | `python -m pura` (tudo em um processo) |
| Mosquitto em container | `LocalBus` em memória; Mosquitto nativo só para ESP32 reais |
| `cp .env.example .env` + `source .env` | `.env` lido pelo próprio programa (funciona no Windows) |
| `paho-mqtt` sempre instalado | só com `pip install -e ".[mqtt]"` (modo `--mqtt`) |
| Painel em `0.0.0.0` | painel em `127.0.0.1` por padrão |
| Modo seguro TLS + ACL via Docker | **não incluído** (veja Segurança) |

Não mudaram: modelo físico, otimizadores, guardas, assinatura das mensagens, API, painel e firmware.

## Estrutura

```
src/pura/     model/ · optimizers/ · adapters/ (local_bus, mqtt_bus) · api/ (+ painel)
              security · guards · pipeline · events · service · simulator
              envfile (leitor de .env) · local_run (nós virtuais no mesmo processo) · __main__ (CLI)
firmware/     esp32/pura_node/ (sketch Arduino)
infra/        configuração do Mosquitto para o modo MQTT
experiments/  benchmark e validação do previsor
docs/         modelagem · protocolo · esp32-real · hardware-testing · adr/
tests/
iniciar.bat · iniciar.sh
```

## Segurança

- O painel escuta só em `127.0.0.1`. Use `--host 0.0.0.0` apenas em rede confiável e defina `PURA_API_TOKEN`.
- Leituras e comandos são assinados com HMAC-SHA256, com janela de tempo e nonce, em ambos os modos.
- O modo MQTT usa o Mosquitto **sem TLS e sem senha** (`infra/mosquitto/mosquitto.dev.conf`): só em rede de laboratório isolada. TLS, usuário por nó e ACL por tópico existiam no projeto original via Docker e não foram portados; dá para configurá-los no Mosquitto nativo (`password_file`, `acl_file`, `cafile`/`certfile`/`keyfile`).
- Nunca faça commit de `.env`, `config.h`, certificados ou senhas. Veja [`SECURITY.md`](SECURITY.md).

## Contribuindo e licença

[`CONTRIBUTING.md`](CONTRIBUTING.md) · [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) · [MIT](LICENSE).
