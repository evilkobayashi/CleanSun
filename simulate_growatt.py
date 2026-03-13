"""Growatt Modbus TCP simulator for CleanSun tests.

Implements a minimal subset of Modbus function 0x03.
"""
import math
import random
import socket
import struct
import time

REGS = {
    0x0001: 0,   # potencia instantanea AC (W)  -- BUG CORRIGIDO: era 1, nunca atualizado
    0x0003: 0,   # tensao DC (V)
    0x0005: 0,   # corrente DC (A)
    0x0006: 0,   # geracao do dia em 0.1 kWh    -- BUG CORRIGIDO: era consumo proprio
    0x003C: 0,   # geracao do dia em 0.1 kWh (alias, mesmo valor)
    0x0055: 25000,
    0x007D: 250,
    0x0100: 0,
}


class CurveModel:
    WEATHER_GAIN = {"ensolarado": 1.0, "nublado": 0.58, "chuvoso": 0.25}

    def __init__(self, weather="ensolarado", kwp=5.0):
        self.weather = weather
        self.kwp = kwp
        self.daily_kwh = 0.0

    def tick(self):
        now = time.localtime()
        h = now.tm_hour + now.tm_min / 60.0
        sunlight = max(0.0, math.sin((h - 6) / 12 * math.pi))
        gain = self.WEATHER_GAIN.get(self.weather, 1.0)
        cloud_noise = random.uniform(-0.06, 0.06)
        pv_kw = max(0.0, self.kwp * sunlight * (gain + cloud_noise))

        home_load_kw = 0.7 + (0.8 if 18 <= now.tm_hour <= 22 else 0.2)
        home_load_kw += random.uniform(-0.15, 0.15)
        home_load_kw = max(0.2, home_load_kw)

        export_kw = max(0.0, pv_kw - home_load_kw)
        self.daily_kwh += pv_kw * (5 / 3600)

        dc_v = 160 + 240 * sunlight
        dc_a = (pv_kw * 1000 / max(dc_v, 10))
        temp_c = 24 + 18 * sunlight + random.uniform(-1.5, 1.5)

        # BUG CORRIGIDO: 0x0001 agora recebe potencia instantanea AC (W)
        REGS[0x0001] = int(pv_kw * 1000)
        REGS[0x0003] = int(dc_v)
        REGS[0x0005] = int(dc_a)
        # BUG CORRIGIDO: 0x0006 agora recebe geracao do dia (0.1 kWh), igual 0x003C
        REGS[0x0006] = int(self.daily_kwh * 10)
        REGS[0x003C] = int(self.daily_kwh * 10)
        REGS[0x0055] += int(max(pv_kw, 0) * 10 / 3600)
        REGS[0x007D] = int(temp_c * 10)
        REGS[0x0100] = int(pv_kw * 1000)


def serve(host="0.0.0.0", port=1502, weather="ensolarado"):
    model = CurveModel(weather=weather)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    sock.settimeout(1)
    print("Simulador Growatt Modbus TCP em {}:{} ({})".format(host, port, weather))

    last_tick = 0
    while True:
        now = time.time()
        if now - last_tick >= 5:
            model.tick()
            last_tick = now
        try:
            conn, _addr = sock.accept()
        except socket.timeout:
            continue
        with conn:
            req = conn.recv(260)
            if len(req) < 12:
                continue
            tx_id, proto_id, _length, unit_id, func, start, qty = struct.unpack(">HHHBBHH", req[:12])
            if proto_id != 0 or func != 3:
                continue
            words = [REGS.get(start + i, 0) & 0xFFFF for i in range(qty)]
            data = b"".join(struct.pack(">H", w) for w in words)
            pdu = struct.pack(">BBB", unit_id, func, len(data)) + data
            mbap = struct.pack(">HHH", tx_id, 0, len(pdu))
            conn.sendall(mbap + pdu)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=1502)
    parser.add_argument("--weather", default="ensolarado", choices=["ensolarado", "nublado", "chuvoso"])
    args = parser.parse_args()
    serve(args.host, args.port, args.weather)
