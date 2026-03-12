"""Growatt Modbus RTU reader abstraction.

Designed to run with a MicroPython-friendly minimalmodbus-like adapter.
"""
try:
    from machine import UART
except ImportError:
    UART = None


REGISTERS = {
    "status": 0x0001,
    "dc_voltage_v": 0x0003,
    "dc_current_a": 0x0005,
    "ac_output_w": 0x0006,
    "daily_gen_kwh_x10": 0x003C,
    "total_gen_kwh_x10": 0x0055,
    "temperature_c_x10": 0x007D,
    "instant_total_w": 0x0100,
}


class _FallbackInstrument:
    """Tiny fallback interface for development without hardware."""

    def read_register(self, register, _decimals=0, _signed=False):
        return 0


class GrowattModbusReader:
    def __init__(self, slave_id=1, port=1, baudrate=9600, instrument=None):
        self.slave_id = slave_id
        if instrument is not None:
            self.instrument = instrument
            return

        self.instrument = _FallbackInstrument()
        if UART is None:
            return

        # Placeholder for integration with adapted minimalmodbus implementation.
        # Example:
        # uart = UART(port, baudrate=baudrate, bits=8, parity=None, stop=1)
        # self.instrument = MinimalModbusInstrument(uart, slave_id)

    @staticmethod
    def _scale(raw_name, raw_value):
        if raw_name in ("daily_gen_kwh_x10", "total_gen_kwh_x10"):
            return raw_value / 10.0
        if raw_name == "temperature_c_x10":
            return raw_value / 10.0
        return float(raw_value)

    def read_all(self):
        payload = {}
        for key, register in REGISTERS.items():
            raw = self.instrument.read_register(register, 0, False)
            payload[key.replace("_x10", "")] = self._scale(key, raw)
        return payload
