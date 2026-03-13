# CleanSun ☀️

**Inteligência embarcada no inversor solar Growatt**

Sistema de interpretação simplificada de dados fotovoltaicos que roda diretamente no módulo Wi-Fi do inversor — sem aplicativo externo, sem nuvem, sem internet. O usuário acessa o dashboard pelo navegador do celular na própria rede local da residência.

> Desenvolvido como Trabalho de Conclusão de Curso (TCC) em Engenharia.

---

## O problema que o CleanSun resolve

Inversores solares expõem dados técnicos como potência instantânea, tensão DC e energia exportada — mas o usuário residencial não sabe o que fazer com esses números. O CleanSun cruza esses dados e traduz tudo em linguagem simples:

| Dado técnico do inversor | CleanSun exibe |
|---|---|
| `instant_total_w: 2300` | Sua casa está usando 68% da energia gerada agora |
| `daily_gen_kwh: 8.4` | Você gerou 8.40 kWh hoje |
| `excedente_exportado: 2.69` | R$ 7,73 economizados (autoconsumo + créditos) |
| `performance_ratio: 0.29` | Atenção: geração abaixo do esperado para este horário |

---

## Arquitetura

```
┌─────────────────────────────────────────────┐
│            Inversor Growatt                  │
│                                             │
│  ┌──────────────┐    Modbus RTU    ┌──────┐ │
│  │  Processador │ ←─────────────── │ UART │ │
│  │  (geração,   │                  └──────┘ │
│  │  tensão, etc)│                           │
│  └──────┬───────┘                           │
│         │ dados brutos                       │
│  ┌──────▼───────────────────────────────┐   │
│  │        Módulo Wi-Fi (ESP32)          │   │
│  │                                      │   │
│  │  modbus_reader.py  →  data_processor │   │
│  │         ↓                            │   │
│  │    http_server.py  →  dashboard.html │   │
│  │    porta 80 (HTTP local)             │   │
│  └──────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
                    │ Wi-Fi local
              ┌─────▼─────┐
              │  Celular   │
              │ (navegador)│
              └───────────┘
```

**Sem nuvem. Sem app. Sem conta.** O inversor serve o dashboard diretamente.

---

## Estrutura de arquivos

```
CleanSun/
├── main.py               # Entry point — inicia servidor e loop de leitura
├── modbus_reader.py      # Leitura dos registros Modbus do Growatt
├── data_processor.py     # Cálculo de KPIs e geração de frases simplificadas
├── http_server.py        # Servidor HTTP assíncrono (uasyncio / asyncio)
├── dashboard.html        # Interface do usuário (arquivo único, ~20KB)
├── simulate_growatt.py   # Simulador Modbus TCP para testes sem hardware
├── config.json           # Configurações da instalação
├── history.csv           # Histórico horário circular (máx. 512KB em flash)
└── README.md
```

---

## Como testar no PC (sem inversor físico)

Você precisa de dois terminais abertos na pasta do projeto.

### Terminal 1 — Simulador Growatt

```bash
python simulate_growatt.py --weather ensolarado
```

O simulador gera uma curva realista de irradiância solar ao longo do dia e expõe os registros Modbus via TCP na porta `1502`. Opções de clima:

| Flag | Comportamento |
|---|---|
| `--weather ensolarado` | Geração normal, pico ao meio-dia |
| `--weather nublado` | Geração reduzida a ~58% |
| `--weather chuvoso` | Geração reduzida a ~25% |

Porta padrão: `1502`. Para alterar: `--port 502`

### Terminal 2 — Servidor CleanSun

```bash
python main.py
```

O servidor HTTP sobe na porta `80`. Acesse no navegador:

```
http://localhost
```

> **Nota:** no ESP32 embarcado, o dashboard fica acessível em `http://cleansun.local` ou pelo IP da rede local.

---

## Dashboard

O dashboard é uma página única (`dashboard.html`) servida diretamente pelo inversor. Não depende de CDN externo para o layout — apenas o Chart.js é carregado via CDN quando há internet disponível.

### Seções

| Seção | O que exibe |
|---|---|
| **Status** | Indicador visual (verde / amarelo / vermelho) com texto em linguagem simples |
| **KPIs** | Gerado hoje (kWh) · Economizado hoje (R$) · Enviado à rede (kWh) |
| **Fluxo de energia** | Diagrama Painéis → Casa → Rede com valores em tempo real |
| **Geração hora a hora** | Gráfico de linhas com geração e consumo estimado |
| **Autoconsumo** | Gauge circular com percentual de energia própria consumida |
| **Performance ratio** | Barra de progresso comparando geração real vs esperada |
| **Histórico semanal** | Gráfico de barras com geração, consumo e exportado dos últimos 7 dias |
| **Frases automáticas** | Resumo em linguagem simples gerado pelos dados calculados |

### Atualização em tempo real

O dashboard usa **SSE (Server-Sent Events)** como método principal de atualização, com fallback automático para polling a cada 5 segundos caso o cliente não suporte SSE.

---

## API local

O servidor expõe três rotas:

| Rota | Método | Descrição |
|---|---|---|
| `GET /` | GET | Retorna o `dashboard.html` |
| `GET /api/data` | GET | JSON com snapshot, métricas e config atuais |
| `GET /api/history?days=N` | GET | JSON com histórico dos últimos N dias (padrão: 7) |
| `GET /api/events` | GET | Stream SSE com atualizações a cada 5 segundos |

### Exemplo de resposta — `/api/data`

```json
{
  "snapshot": {
    "instant_total_w": 2300,
    "daily_gen_kwh": 8.4,
    "total_gen_kwh": 1543.2
  },
  "metrics": {
    "autoconsumo_pct": 68.0,
    "excedente_exportado_kwh": 2.69,
    "economia_diaria_rs": 7.73,
    "performance_ratio": 0.29,
    "status": "ALERTA",
    "status_text": "Geração muito abaixo do esperado",
    "phrases": [
      "Sua casa usou 68% da energia gerada hoje (5.71 kWh).",
      "Economia estimada hoje: R$ 7,73 (autoconsumo + créditos).",
      "2.69 kWh foram enviados à rede como crédito."
    ],
    "hourly": { "0": 0, "1": 0, "12": 2300, "13": 2300 }
  },
  "fault": null
}
```

---

## Configuração (`config.json`)

| Campo | Descrição | Padrão |
|---|---|---|
| `tarifa_kwh` | Tarifa da concessionária em R$/kWh | `0.92` |
| `potencia_sistema_kwp` | Potência total instalada em kWp | `5.0` |
| `nome_instalacao` | Nome exibido no topo do dashboard | `"Residencia"` |
| `expected_irradiance` | Tabela de irradiância esperada por hora (0.0–1.0) | Ver arquivo |
| `history_max_bytes` | Tamanho máximo do histórico em flash | `524288` (512KB) |

Para ajustar a tarifa após instalar:

```json
{
  "tarifa_kwh": 0.85,
  "potencia_sistema_kwp": 6.0,
  "nome_instalacao": "Casa da Praia"
}
```

---

## Registros Modbus lidos do Growatt

| Endereço | Nome | Escala | Unidade |
|---|---|---|---|
| `0x0001` | Potência instantânea AC | ×1 | W |
| `0x0003` | Tensão entrada DC | ×1 | V |
| `0x0006` | Geração do dia | ÷10 | kWh |
| `0x003B` | Geração total acumulada | ÷10 | kWh |

---

## Indicadores calculados

| Indicador | Fórmula |
|---|---|
| Autoconsumo (%) | `energia_própria_consumida / geração_total × 100` |
| Excedente exportado (kWh) | `geração_total − autoconsumo` |
| Economia diária (R$) | `(autoconsumo + excedente) × tarifa_kwh` |
| Performance ratio | `potência_real_kW / (potência_kwp × irradiância_esperada_hora)` |
| Status do sistema | NORMAL se PR ≥ 0.85 · ATENÇÃO se PR ≥ 0.55 · ALERTA se PR < 0.55 |

---

## Compatibilidade

| Ambiente | Suporte |
|---|---|
| MicroPython 1.21+ (ESP32 / ESP8266) | ✅ Produção |
| CPython 3.9+ (PC — testes) | ✅ Desenvolvimento |
| Inversores Growatt série SPH / MIN / MID | ✅ Testado |
| Outros inversores com Modbus RTU | ⚠️ Requer ajuste no `modbus_reader.py` |

---

## Histórico de versões

### v1.1 — Dashboard redesenhado
- Interface completamente reescrita com tipografia DM Sans / DM Mono
- Diagrama de fluxo de energia (Painéis → Casa → Rede) em tempo real
- Gauge SVG animado com cor dinâmica por faixa de desempenho
- Gráfico de linha hora a hora com geração e consumo estimado
- Gráfico semanal com três séries (geração, consumo, exportado)
- Performance ratio com barra de progresso e marcação de faixa normal

### v1.0 — Correção de bugs críticos
1. `simulate_growatt.py` — Potência instantânea (`0x0001`) nunca era atualizada (sempre 1W)
2. `simulate_growatt.py` — Registro `0x0006` recebia consumo próprio, não geração do dia
3. `data_processor.py` — Consumo hardcoded em 65%, ignorando dados reais
4. `data_processor.py` — Economia não incluía créditos do excedente exportado
5. `data_processor.py` — Horas noturnas geravam falso status ALERTA
6. `http_server.py` — `writer.wait_closed()` não existe no MicroPython (crash no hardware)
7. `http_server.py` — `asyncio.start_server` com API diferente no MicroPython 1.21
8. `http_server.py` — CORS ausente em `/api/data` e `/api/history`
9. `main.py` — `asyncio.create_task()` necessário no MicroPython para paralelismo
10. `dashboard.html` — Gauge CSS com ângulo incorreto (`conic-gradient from 180deg`)
