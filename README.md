# 🍃 P.U.R.A. — Purificação e Monitoramento Autônomo de Microclimas

> **Projeto para Exposição Acadêmica** | *Conceito de Habitação 2050*

O **P.U.R.A.** é um sistema autônomo de IoT e análise preditiva projetado para garantir a qualidade do ar em ambientes internos de alta eficiência energética. Pensado para o cenário residencial de 2050 — onde o isolamento térmico avançado limita a troca passiva de ar —, o projeto combina sensoriamento de borda e atuadores automáticos para manter o microclima saudável sem depender de intervenção humana.

---

## 🎯 Destaques do Sistema

* 🤖 **Atuação Preditiva:** Servidor local em Python que analisa dados de poluentes e antecipa picos de contaminação antes que atinjam níveis críticos.
* ⚡ **Comunicação em Tempo Real:** Protocolo MQTT para troca de dados leve, de baixa latência e tolerante a falhas.
* 📟 **Sensoriamento de Borda:** Nó central baseado em ESP32 para leitura contínua de parâmetros ambientais.
* 🔄 **Ciclo Fechado de Filtragem:** Acionamento automático de exaustão e filtragem com base em tomadas de decisão baseadas em dados.

---

## 🛠️ Arquitetura do Projeto

| Camada | Tecnologia | Função |
| :--- | :--- | :--- |
| **Hardware Embarcado** | ESP32 + Sensores | Coleta contínua de poluentes e estado do microclima |
| **Protocolo de Rede** | MQTT | Transmissão de eventos entre nós e servidor |
| **Processamento Local** | Python | Análise preditiva e motor de regras de acionamento |
| **Atuação** | Módulos de Exaustão/Filtragem | Controle ativo da purificação do ar |

---

## 🔮 Contexto: O Desafio de 2050

As residências do futuro utilizam materiais de isolamento térmico ultraeficientes para reduzir o consumo de energia. Contudo, essa vedação hermética cria um efeito colateral: a estagnação de poluentes internos. O **P.U.R.A.** resolve essa equação ao introduzir uma camada inteligente de ventilação e filtragem sob demanda.

---

## 🔄 Fluxo de Funcionamento

1. **Leitura:** O ESP32 realiza a amostragem dos poluentes no ambiente interno.
2. **Publicação:** Os dados de telemetria são enviados via MQTT para o broker local.
3. **Análise:** O servidor Python aplica algoritmos preditivos para avaliar a tendência da qualidade do ar.
4. **Intervenção:** Caso os padrões indiquem degradação, os exaustores e purificadores são acionados automaticamente até a estabilização do microclima.
