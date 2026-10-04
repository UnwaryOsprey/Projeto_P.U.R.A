# Modelagem do problema de otimização

## Problema
Decidir, para cada cômodo `c` e cada slot de 15 min `t` (24 h = 96 slots), o nível do exaustor `u[c,t]` e do purificador `f[c,t]`, ambos em {0,1,2,3}, minimizando a exposição dos moradores a CO₂ e PM2.5 com o menor custo energético, térmico e sonoro.

## Dinâmica (balanço de massa, solução exata por slot)
```
dC/dt = G + ke·C_ext − (ke + kf)·C      →   C(t+Δt) = Ceq + (C − Ceq)·exp(−(ke+kf)·Δt),  Ceq = (G + ke·C_ext)/(ke+kf)
ke = k_inf + vazão_exaustor[u]/V         kf = CADR_purificador[f]/V   (kf = 0 para CO₂)
```
Tabelas (em `src/pura/model/dynamics.py`, calibráveis com o hardware real):

| Nível | Vazão exaustor (m³/h) | Potência (W) | Ruído (dB) | CADR purificador (m³/h) | Potência (W) | Ruído (dB) |
|---|---|---|---|---|---|---|
| 0 | 0 | 0 | — | 0 | 0 | — |
| 1 | 40 | 8 | 30 | 60 | 5 | 26 |
| 2 | 80 | 18 | 36 | 120 | 12 | 32 |
| 3 | 140 | 35 | 42 | 200 | 25 | 39 |

Ruído combinado: soma em potência das fontes ligadas + ruído de fundo de 25 dB.
CO₂ gerado: 0,018 m³/h por pessoa (repouso). `k_inf` = 0,12 /h (casa muito vedada).

## Função objetivo
```
J = Σ_{c,t} (ocup[c,t] + 0,05)·Δt·[ max(0, CO₂−1000)/1000 + max(0, PM−15)/15 ]     (exposição)
  + α·kWh + β·kWh_térmicos + γ·ruído_acordado + penalidades
```
`α=2, β=1,5, γ=0,5` (em `Weights`). Perda térmica: `0,34 Wh/(m³·K) · vazão · |T_int − T_ext| · Δt`.

## Restrições (penalidade = 5 por unidade; cada uma é reportada separadamente)
1. Teto rígido de CO₂ (1500 ppm) com cômodo ocupado.
2. Ruído ≤ 35 dB no horário de sono.
3. Orçamento de energia (1,2 kWh/dia, proporcional ao horizonte).
4. Potência simultânea total ≤ 60 W.
5. Anti short-cycling: dois chaveamentos do motor em menos de 30 min contam como violação.

*Fora do MVP:* vida útil do filtro, fronteira de Pareto (NSGA-II).

## Dados
- **Sintéticos documentados** (`src/pura/model/scenarios.py`): sala (ocupada 7–9 h, 12–13:30, 18–22 h; refeições às ~7:30, 12:15 e 19:00 geram 150–400 µg/m³/h de PM2.5 por 30–60 min) e quarto de casal (2 pessoas, 22–7 h, limite de ruído). PM2.5 externo 12 µg/m³, com pico de fumaça de +30 a +60 entre 14 e 17 h. T_ext senoidal (11–25 °C). Estado inicial: 450 ppm, 10 µg/m³.
- **Real:** UCI Air Quality (`experiments/validate_predictor.py`) para validar o previsor Holt contra a persistência.
- **Hardware:** leituras reais dos ESP32 com SCD4x, PMS5003 e SGP30.

## Algoritmos e baselines
| Nome | Tipo |
|---|---|
| `timer` | baseline: nível 1 constante |
| `hysteresis` | baseline: liga >1000 ppm/25 µg, desliga <800 ppm/15 µg (ignora ruído noturno) |
| `hysteresis_sleep` | baseline justo: histerese respeitando o limite noturno |
| `fuzzy` | Takagi-Sugeno ordem zero (CO₂, PM2.5, VOC, presença) |
| `ga`, `ga_seeded` | Algoritmo Genético (população 80, 120 gerações); `ga_seeded` parte dos planos dos baselines e do fuzzy |
| `sa` | Simulated Annealing, 16 cadeias paralelas × 600 iterações (orçamento de avaliações equivalente ao do GA) |

Reprodução: `python experiments/run_benchmark.py --runs 30`.
