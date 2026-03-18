# CleanSun

Protótipo funcional de TCC para interpretação simplificada de dados fotovoltaicos de um inversor Growatt, com foco em usuário leigo, operação local e valor acadêmico.

## Visão geral da refatoração

A arquitetura original foi preservada:

- `modbus_reader.py` continua responsável pela coleta.
- `data_processor.py` centraliza todos os cálculos, alertas, relatórios e comparações.
- `http_server.py` expõe a API local e o dashboard.
- `main.py` orquestra a execução.
- `simulate_growatt.py` continua servindo dados simulados mais ricos.
- `dashboard.html` agora apresenta dois modos: técnico e simplificado.

## Árvore sugerida

```text
CleanSun/
├── main.py
├── modbus_reader.py
├── data_processor.py
├── http_server.py
├── simulate_growatt.py
├── dashboard.html
├── config.json
├── history.csv
└── README.md
```

## Melhorias implementadas

### Backend / processamento

- Indicadores energéticos completos:
  - autoconsumo
  - autossuficiência
  - energia importada/exportada
  - economia diária, semanal, mensal e anual
  - projeção financeira
  - pico de geração e pico de consumo
  - taxa de aproveitamento solar
- Comparação entre geração real e esperada.
- Alertas automáticos com severidade.
- Relatórios automáticos diário e semanal.
- Comparações entre hoje/ontem, semana atual/anterior e mês atual/anterior.
- Perfil de consumo residencial com recomendações.
- Endpoints adicionados:
  - `/api/dashboard`
  - `/api/history`
  - `/api/summary/daily`
  - `/api/summary/weekly`
  - `/api/indicators`
  - `/api/alerts`
  - `/api/profile`
  - `/api/compare`
  - `/api/data`
  - `/api/events`

### Dashboard / UX

- Modo simplificado para usuário leigo.
- Modo técnico para apresentação acadêmica e engenharia.
- Cartões focados em economia e compreensão.
- Alertas em destaque.
- Relatórios textuais em linguagem natural.
- Filtros de período (hoje, 7 dias, 30 dias).
- Visualização de comparação entre períodos.
- Histórico semanal e curva horária.

### Simulação

- Geração solar coerente com horário do dia.
- Consumo residencial variável.
- Importação/exportação estimadas.
- Cenários de clima:
  - `ceu_claro`
  - `parcialmente_nublado`
  - `nublado`

## Execução no PowerShell

### 1. Rodar o simulador

```powershell
python .\simulate_growatt.py --weather parcialmente_nublado --port 1502
```

### 2. Rodar o servidor/dashboard local

```powershell
python .\main.py
```

### 3. Abrir o dashboard

No navegador:

```text
http://127.0.0.1/
```

Se estiver rodando em desktop com porta alternativa num teste manual, abra a porta correspondente.

## Observações de uso

- O sistema degrada graciosamente quando não há dados suficientes.
- O fallback local do leitor Modbus gera dados coerentes mesmo sem hardware.
- O histórico segue em CSV rotativo, sem banco de dados externo.
- O dashboard foi mantido simples para rodar localmente como protótipo funcional de TCC.


## Simulador retroativo (`simulate_growatt.py`)

O simulador agora pode preencher automaticamente o `history.csv` com histórico retroativo realista usando resolução de 15 minutos, clima diário simplificado e continuidade opcional após a carga inicial.

### Exemplos no PowerShell

Gerar 7 dias e encerrar:

```powershell
python .\simulate_growatt.py --days 7 --overwrite
```

Gerar 30 dias e continuar em modo contínuo:

```powershell
python .\simulate_growatt.py --days 30 --continuous
```

Gerar 90 dias sobrescrevendo o histórico anterior:

```powershell
python .\simulate_growatt.py --days 90 --overwrite
```

Usar intervalo diferente e tarifa específica:

```powershell
python .\simulate_growatt.py --days 30 --interval-minutes 10 --tariff 0.95
```
