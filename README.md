P.U.R.A. — Purificação Unificada e Reativa do Ar (versão local, sem Docker)
Sistema autônomo de monitoramento e purificação de microclimas internos para habitações muito vedadas. Nós ESP32 medem CO₂, PM2.5 e VOC; um servidor Python prevê a evolução dos poluentes, escolhe o acionamento de exaustor e purificador (fuzzy, algoritmo genético ou simulated annealing) e envia comandos assinados de volta, sem intervenção manual.

## O problema (resumo)
- **Variáveis**: caminho de cada fluxo (e, opcionalmente, taxa de banda).
- **Objetivo (min)**: `J = Σ peso·(latência sob carga + 30·risco do enlace) + penalidades` (ver `pura/model.py`).
- **Restrições**: capacidade dos enlaces · zonas proibidas para fluxos de controle · rota válida.
- **Dinâmica**: 7 eventos por execução (2 falhas de enlace, pico de tráfego, pico de latência, recuperações).

## Como rodar
```bash
python -m unittest discover -s tests -t .          # 39 testes
ruff check .                                       # lint (CI exige)
python -m pura.experiments --seeds 30              # resultados em results/ (~1 min)
$env:PURA_SECRET="um-segredo-com-16-ou-mais"
python -m pura.server   # http://localhost:8000 (dashboard)
PYTHONPATH=. python tools/security_demo.py         # demonstração de ataques e mitigações (somente 127.0.0.1)
```
Somente biblioteca padrão (Python 3.10+); `matplotlib` é opcional (gráficos PNG).
ESP32: ver `docs/HARDWARE.md` e `firmware/esp32_node/`.

## Estrutura
| Pasta | Conteúdo |
|---|---|
| `pura/model.py` | problema: rede, fluxos, restrições, função objetivo |
| `pura/routers/` | Strategy: `static`, `dijkstra`, `dijkstra_residual`, `aco`, `memetic` |
| `pura/events.py` | Observer: eventos de rede + `EventBus` |
| `pura/bandwidth.py` | PSO × alocação proporcional |
| `pura/simulator.py` | simulador + guarda de rotas inválidas |
| `pura/security.py`, `server.py` | HMAC, anti-replay, gateway, API |
| `pura/monitor.py` | monitoramento de tráfego, alertas e bloqueio automático |
| `Dockerfile`, `render.yaml`, `.github/workflows/ci.yml` | nuvem (camada gratuita) e CI/CD com lint e testes |
| `firmware/esp32_node/` | firmware do nó físico |
| `tools/` | `security_demo.py`, `minilint.py`, `github_setup.sh` (protege a main), `preparar_entrega.py` (pendências antes da tag) |
| `web/index.html` | dashboard (resultados + telemetria ao vivo) |
| `docs/adr/` | 8 ADRs · `docs/MVP1.md` · `docs/HARDWARE.md` |
| `docs/VULNERABILIDADES.md` | 7 vulnerabilidades reais, mitigadas e testadas |
| `docs/DEPLOY.md`, `docs/TESTES.md`, `docs/REQUISITOS_NEXUS.md` | deploy, roteiro de testes e matriz de requisitos |

## Resultado em uma frase (30 sementes, pico ×2.0)
ACO e Memético reduzem a latência p95 de ~128 ms (Dijkstra) para ~85 ms e elevam o goodput de 0,90 para ~0,99, mas
**contra um Dijkstra com capacidade residual o ganho é pequeno** (≈9 ms em p95; goodput praticamente igual) e custa ~70–120× mais
tempo de decisão (35–56 ms vs 0,5 ms). Detalhes, protocolo e limitações no relatório técnico.

## Segurança e nuvem
O gateway monitora o tráfego (assinaturas inválidas, replay, inundação, silêncio de nó), bloqueia IPs abusivos e roda em
contêiner na camada gratuita do Render com TLS. A revisão do próprio sistema encontrou e corrigiu 7 vulnerabilidades
(ver `docs/VULNERABILIDADES.md`).

## Licença e contribuição
MIT (`LICENSE`) · `CONTRIBUTING.md` · `GOVERNANCE.md` · `CODE_OF_CONDUCT.md` · `SECURITY.md`.
