"""Simulador local de geração/consumo residencial e servidor Modbus TCP."""
import argparse
import math
import random
import socket
import struct
import time

REGS = {0x0001: 0, 0x0003: 0, 0x0006: 0, 0x003B: 21500}


class CurveModel:
    WEATHER_GAIN = {
        "ceu_claro": 1.0,
        "parcialmente_nublado": 0.74,
        "nublado": 0.5,
    }

    def __init__(self, weather="parcialmente_nublado", kwp=5.0):
        self.weather = weather
        self.kwp = kwp
        self.daily_kwh = 0.0
        self.total_kwh = 2150.0
        self.last = time.time()

    def _sun(self, hour_float):
        return max(0.0, math.sin((hour_float - 6) / 12 * math.pi))

    def _load(self, hour_float):
        base = 0.42
        if 6 <= hour_float <= 8:
            base += 0.45
        if 12 <= hour_float <= 13.5:
            base += 0.22
        if 18 <= hour_float <= 22.5:
            base += 1.15
        return max(0.2, base + random.uniform(-0.12, 0.18))

    def tick(self):
        now = time.time()
        delta_h = (now - self.last) / 3600.0
        self.last = now
        lt = time.localtime(now)
        hour_float = lt.tm_hour + lt.tm_min / 60.0
        sun = self._sun(hour_float)
        pv_kw = max(0.0, self.kwp * sun * (self.WEATHER_GAIN[self.weather] + random.uniform(-0.05, 0.05)))
        load_kw = self._load(hour_float)
        export_kw = max(0.0, pv_kw - load_kw)
        import_kw = max(0.0, load_kw - pv_kw)
        self.daily_kwh += pv_kw * max(delta_h, 0.0)
        self.total_kwh += pv_kw * max(delta_h, 0.0)
        REGS[0x0001] = int(pv_kw * 1000)
        REGS[0x0003] = int(180 + 220 * sun)
        REGS[0x0006] = int(self.daily_kwh * 10)
        REGS[0x003B] = int(self.total_kwh * 10)
        return {
            "pv_kw": round(pv_kw, 3),
            "load_kw": round(load_kw, 3),
            "import_kw": round(import_kw, 3),
            "export_kw": round(export_kw, 3),
            "weather": self.weather,
        }


def serve(host="0.0.0.0", port=1502, weather="parcialmente_nublado"):
    model = CurveModel(weather=weather)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(5)
    sock.settimeout(1)
    print("Simulador Growatt Modbus TCP em {}:{} ({})".format(host, port, weather))
    while True:
        snapshot = model.tick()
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
        print("[sim] pv={pv_kw}kW load={load_kw}kW import={import_kw}kW export={export_kw}kW clima={weather}".format(**snapshot))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=1502)
    parser.add_argument("--weather", default="parcialmente_nublado", choices=["ceu_claro", "parcialmente_nublado", "nublado"])
    args = parser.parse_args()
    serve(args.host, args.port, args.weather)
