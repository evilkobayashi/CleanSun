# CleanSun

Sistema embarcado para interpretação simplificada de dados fotovoltaicos no módulo Wi-Fi de inversores Growatt.

## Arquitetura

- `main.py`: loop principal (`uasyncio`) e polling Modbus a cada 5s.
- `modbus_reader.py`: leitura dos registros Growatt via Modbus RTU.
- `data_processor.py`: cálculo de autoconsumo, excedente, economia, PR e status.
- `http_server.py`: servidor HTTP local (`/` + `/api/state`).
- `dashboard.html`: SPA HTML/CSS/JS offline (sem CDN).
- `simulate_growatt.py`: simulador Modbus TCP para testes em PC.

## Registros Growatt lidos

- `0x0001` status do sistema
- `0x0003` tensão DC (V)
- `0x0005` corrente DC (A)
- `0x0006` potência saída AC (W)
- `0x003C` geração diária (0.1 kWh)
- `0x0055` geração total (0.1 kWh)
- `0x007D` temperatura interna (0.1 °C)
- `0x0100` potência instantânea total (W)

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
