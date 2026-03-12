# CleanSun

Sistema embarcado para interpretação simplificada de dados fotovoltaicos no módulo Wi-Fi de inversores Growatt.

## Arquitetura

- `main.py`: loop principal (`uasyncio`) e polling Modbus a cada 5s.
- `modbus_reader.py`: leitura dos registros Growatt via Modbus RTU.
- `data_processor.py`: cálculo de autoconsumo, excedente, economia, PR e status.
- `http_server.py`: servidor HTTP local (`/`, `/api/data` e SSE em `/api/events`).
- `dashboard.html`: SPA HTML/CSS/JS offline (sem CDN), totalmente autocontida (<50KB), com gráfico de barras e gauge em CSS puro.
- `simulate_growatt.py`: simulador Modbus TCP para testes em PC.

## Registros Growatt lidos

- `0x0001` potência instantânea (W)
- `0x0003` tensão DC (V)
- `0x0006` geração do dia (0.1 kWh)
- `0x003B` geração total (0.1 kWh)


## Leitura periódica em memória local

O módulo `modbus_reader.py` implementa `GrowattModbusReader.poll_and_store_forever(interval_seconds=5)`, que lê todos os registros a cada 5 segundos e mantém um buffer circular em RAM (`memory_buffer`), sem banco de dados externo.

## Histórico em CSV circular (flash)

`data_processor.py` mantém `history.csv` em formato horário com colunas `timestamp,geracao_kwh,consumo_kwh,exportado_kwh`, gravando no máximo 512KB (`history_max_bytes=524288`) com rotação circular em flash.

## API HTTP e atualização em tempo real

- `GET /` → retorna `dashboard.html`
- `GET /api/data` → JSON com dados atuais (`payload()` do processador)
- `GET /api/events` → stream SSE (`event: update`) para atualização em tempo real sem WebSocket
- `GET /api/history?days=7` → histórico horário dos últimos N dias

## Flash (ESP32/ESP8266 com MicroPython 1.21+)

1. Apague e grave firmware MicroPython no módulo Shine WiFi-X.
2. Copie os arquivos:
   - `main.py`
   - `modbus_reader.py`
   - `data_processor.py`
   - `http_server.py`
   - `dashboard.html`
   - `config.json`
   - `history.csv`
3. Reinicie o módulo.
4. Conecte no mesmo Wi-Fi local e acesse `http://cleansun.local` ou IP do módulo.

Exemplo com `mpremote`:

```bash
mpremote connect /dev/ttyUSB0 fs cp main.py :main.py
mpremote connect /dev/ttyUSB0 fs cp modbus_reader.py :modbus_reader.py
mpremote connect /dev/ttyUSB0 fs cp data_processor.py :data_processor.py
mpremote connect /dev/ttyUSB0 fs cp http_server.py :http_server.py
mpremote connect /dev/ttyUSB0 fs cp dashboard.html :dashboard.html
mpremote connect /dev/ttyUSB0 fs cp config.json :config.json
mpremote connect /dev/ttyUSB0 fs cp history.csv :history.csv
mpremote connect /dev/ttyUSB0 reset
```

## Simulação sem hardware

```bash
python3 simulate_growatt.py --weather ensolarado --port 1502
```

O simulador responde função Modbus `0x03` com curva solar diária (pico ao meio-dia), variação de clima e carga residencial típica.

## Restrições de projeto

- Operação totalmente offline (LAN local).
- Sem app móvel e sem nuvem.
- Dashboard autocontido e leve (<50KB).


- Dashboard otimizado para carregamento alvo <1s em rede local e legibilidade mobile (fonte base 16px).
