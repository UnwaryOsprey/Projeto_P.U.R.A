# P.U.R.A. — Purificação Unificada e Reativa do Ar

Sistema autônomo de monitoramento e purificação de microclimas internos para habitações muito vedadas (2050). Nós **ESP32** medem CO₂, PM2.5 e VOC e publicam por **MQTT**; um servidor local em **Python** prevê a evolução dos poluentes, escolhe o acionamento de **exaustor e purificador** (fuzzy, algoritmo genético ou simulated annealing) e envia comandos assinados de volta, sem intervenção manual.

Projeto Tech Integrado (FECAF) — *Software Architecture & Design Patterns*, *Telecommunications & Network Security*, *Computational Intelligence & Algorithm Optimization* e *Open Source Contribution & Collaboration*. Proposta autoral derivada da Trilha C (sequenciamento temporal de esforço minimizando risco residual acumulado).

> **Status: MVP.** Os resultados do benchmark usam cenários sintéticos e uma física simplificada; validar com o hardware é justamente o objetivo dos testes de bancada.

## Arquitetura

```
 ESP32 (sensores + PWM)                         Servidor local (Python, monólito modular)
 ┌──────────────────┐   MQTT (TLS opcional)    ┌──────────────────────────────────────────────┐
 │ SCD4x PMS5003    │ ── pura/../sensor ─────► │ adapters  MqttBus | LocalBus                 │
 │ SGP30            │   (JSON + HMAC)          │ security  HMAC · janela de tempo · nonce     │
 │                  │ ◄─ pura/../atuador/cmd ─ │ pipeline  calibração → previsão (Holt)       │
 │ exaustor PWM     │   (JSON + HMAC)          │ optimizers  Strategy: fuzzy|GA|SA|baselines  │
 │ purificador PWM  │                          │ guards    Chain: Safe→Teto CO₂→Ruído→Min-run │
 │ fail-safe local  │                          │ events    Observer ──► API/WebSocket         │
 └──────────────────┘                          └───────────────┬──────────────────────────────┘
        ▲                                        Mosquitto     │  FastAPI + dashboard (:8000)
        └──────────── broker ──────────────────────────────────┘
```

| Padrão | Onde |
|---|---|
| Strategy | `optimizers/` — troque a estratégia sem tocar no resto (`PURA_OPTIMIZER` ou pelo painel) |
| Chain of Responsibility | `guards.py` — cadeia de segurança antes de qualquer comando |
| Observer | `events.py` — painel, logs e alertas assinam eventos |
| Ports & Adapters | `adapters/` — o núcleo não conhece MQTT; testes usam `LocalBus` |
| Pipeline | `pipeline.py` + `service.py` — validação → calibração → previsão → decisão → guardas |

Decisões em [`docs/adr/`](docs/adr), modelagem em [`docs/modelagem.md`](docs/modelagem.md), protocolo e ameaças em [`docs/protocolo.md`](docs/protocolo.md).

## Início rápido (sem hardware: ESP32 virtual)

Requisitos: Docker + Docker Compose.

```bash
git clone <url-do-repositorio> && cd pura
cp .env.example .env                       # troque as chaves de PURA_KEYS
docker compose --profile sim up --build    # broker + servidor + 2 ESP32 virtuais
```

Abra **http://localhost:8000**: dois cômodos ao vivo, previsão de 15 min, níveis dos atuadores, eventos e seletor de estratégia.

## Testes com ESP32 real

Passo a passo completo (ligações, firmware, checklist de validação e testes de segurança): **[`docs/hardware-testing.md`](docs/hardware-testing.md)**. Resumo:

1. Servidor: `docker compose up --build` (sem `--profile sim`).
2. Firmware: copie `firmware/esp32/pura_node/config.example.h` para `config.h`, preencha Wi-Fi, IP do servidor, `ROOM` e `HMAC_KEY`, e grave com o Arduino IDE (core ESP32 3.x).
3. Sem algum sensor? `HAS_x 0`. Sem nenhum? `SIMULATE_SENSORS 1` testa rede, assinatura e atuadores.

## Rodando sem Docker

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
mosquitto -c infra/mosquitto/mosquitto.dev.conf &       # ou outro broker na 1883
set -a; source .env; set +a; export PURA_MQTT_HOST=localhost
python -m pura &                # servidor + dashboard
python -m pura.simulator        # ESP32 virtual (opcional)
```

## Experimentos (otimizador × baselines)

```bash
python experiments/run_benchmark.py --runs 30    # média ± desvio-padrão, CSV e gráfico em results/
python experiments/validate_predictor.py data/AirQualityUCI.csv   # previsor vs. persistência (dataset UCI)
```

Resultado preliminar (cenário sintético `seed=0`, 30 execuções por algoritmo estocástico; menor custo é melhor):

| otimizador | custo (média ± dp) | min com CO₂>1000 | min com PM>15 | kWh | ruído noturno (min) |
|---|---|---|---|---|---|
| timer (baseline) | 29,46 | 660 | 240 | 0,62 | 0 |
| hysteresis (baseline) | 179,16 | 75 | 225 | 0,28 | 480 |
| hysteresis_sleep (baseline justo) | 21,49 | 555 | 225 | 0,20 | 0 |
| fuzzy | 16,59 | 480 | 150 | 0,21 | 0 |
| ga | 20,73 ± 1,63 | 572 | 178 | 0,77 | 0 |
| ga_seeded | **15,50 ± 0,52** | 512 | 148 | 0,32 | 0 |
| sa | 21,14 ± 4,12 | 565 | 180 | 0,67 | 4 |

Leitura honesta: o fuzzy (determinístico, 15 ms) já supera os baselines; GA e SA sem semente ficam perto da referência (vencem em 77 % e 67 % das execuções) e só o GA com semente chega ao melhor custo. A histerese comercial viola o limite de ruído noturno (por isso a variante `hysteresis_sleep` para comparação justa). Esses números dependem do modelo físico: refazer com dados reais é parte do relatório.

## Testes e qualidade

```bash
pytest --cov=pura     # função objetivo, cada restrição, segurança MQTT, guardas, fluxo ponta a ponta, API
ruff check .
```

O CI (GitHub Actions) roda ambos em Python 3.10 e 3.12.

## Estrutura

```
src/pura/        model/ (física, objetivo, cenários) · optimizers/ · adapters/ · api/ (+ dashboard)
                 security.py · guards.py · pipeline.py · events.py · service.py · simulator.py
firmware/        esp32/pura_node/ (sketch Arduino)
infra/           Mosquitto (dev e modo seguro), gerador de certificados e de usuários
experiments/     benchmark e validação do previsor
docs/            modelagem · protocolo/ameaças · hardware-testing · adr/
tests/
```

## Segurança

- **Modo dev** (padrão): sem TLS/senha; usar só em rede de laboratório isolada. O HMAC já impede forjar leituras e comandos.
- **Modo seguro:** TLS + usuário por nó + ACL por tópico (`docs/hardware-testing.md`, seção 6).
- Nunca faça commit de `.env`, `config.h`, certificados ou senhas (já estão no `.gitignore`). Testes de ataque só no broker do próprio grupo. Veja [`SECURITY.md`](SECURITY.md).

## Contribuindo

Leia o [`CONTRIBUTING.md`](CONTRIBUTING.md) e o [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md). Resumo: branch a partir de `main`, *conventional commits*, PR revisado por outra pessoa, testes passando.

## Equipe

| Frente | Responsável |
|---|---|
| IA / otimização (`optimizers/`, `model/`, `experiments/`) | _nome_ |
| Arquitetura e back-end (`service.py`, `guards.py`, `api/`) | _nome_ |
| Redes, segurança e hardware (`firmware/`, `infra/`, `security.py`) | _nome_ |
| Repositório, QA e front-end (`tests/`, CI, dashboard) | _nome_ |

## Licença

[MIT](LICENSE).
