"""Módulo de leitura Modbus para inversores Growatt.

Implementação principal com `minimalmodbus` (Python) e fallback para ambiente sem
hardware, mantendo interface simples para uso no firmware/app.
"""
import time

try:
    import minimalmodbus  # type: ignore
except ImportError:
    minimalmodbus = None


# Mapa solicitado pelo usuário
# 0x0001 = potência instantânea (W)
# 0x0003 = tensão DC (V)
# 0x0006 = geração do dia (kWh)
# 0x003B = geração total (kWh)
REGISTER_MAP = {
    "potencia_instantanea_w": 0x0001,
    "tensao_dc_v": 0x0003,
    "geracao_dia_kwh": 0x0006,
    "geracao_total_kwh": 0x003B,
}


class _FallbackInstrument:
    """Instrumento mínimo para desenvolvimento sem serial/inversor."""

    def read_register(self, register, number_of_decimals=0, signed=False):
        _ = (number_of_decimals, signed)
        mock = {
            0x0001: 1250,
            0x0003: 380,
            0x0006: 84,    # 8.4 kWh (escala x10)
            0x003B: 15432, # 1543.2 kWh (escala x10)
        }
        return mock.get(register, 0)


class GrowattModbusReader:
    """Leitor Modbus com polling periódico e armazenamento em memória local."""

    def __init__(
        self,
        port="/dev/ttyUSB0",
        slave_id=1,
        baudrate=9600,
        bytesize=8,
        parity="N",
        stopbits=1,
        timeout=0.4,
        instrument=None,
        memory_size=1024,
    ):
        self.memory_size = memory_size
        self.memory_buffer = []  # histórico em memória RAM local
        self.last_payload = {}

        if instrument is not None:
            self.instrument = instrument
            return

        if minimalmodbus is None:
            self.instrument = _FallbackInstrument()
            return

        inst = minimalmodbus.Instrument(port, slave_id)
        inst.serial.baudrate = baudrate
        inst.serial.bytesize = bytesize
        inst.serial.parity = parity
        inst.serial.stopbits = stopbits
        inst.serial.timeout = timeout
        inst.mode = minimalmodbus.MODE_RTU
        self.instrument = inst

    @staticmethod
    def _scale(register, raw_value):
        # Registros de energia geralmente vêm em décimos de kWh
        if register in (0x0006, 0x003B):
            return raw_value / 10.0
        return float(raw_value)

    def read_all(self):
        data = {}
        for name, register in REGISTER_MAP.items():
            raw = self.instrument.read_register(register, 0, False)
            data[name] = self._scale(register, raw)

        # aliases para compatibilidade com módulos já existentes
        data["instant_total_w"] = data["potencia_instantanea_w"]
        data["daily_gen_kwh"] = data["geracao_dia_kwh"]
        data["total_gen_kwh"] = data["geracao_total_kwh"]

        self.last_payload = data
        return data

    def poll_and_store_forever(self, interval_seconds=5, on_update=None):
        """Lê registros a cada 5s e salva em memória local (sem BD externo)."""
        while True:
            payload = self.read_all()
            payload["timestamp"] = int(time.time())
            self.memory_buffer.append(payload)
            if len(self.memory_buffer) > self.memory_size:
                self.memory_buffer.pop(0)

            if on_update is not None:
                on_update(payload)

            time.sleep(interval_seconds)

    def get_memory_snapshot(self):
        return list(self.memory_buffer)
