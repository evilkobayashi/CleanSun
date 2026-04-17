"""Entrypoint para simular um cenário off-grid com detecção automática."""
from app_runner import run_app


if __name__ == "__main__":
    run_app(inverter_type="off-grid")
