"""Entrypoint para simular um cenário on-grid com detecção automática."""
from app_runner import run_app


if __name__ == "__main__":
    run_app(inverter_type="on-grid")
