"""Entry point."""
import uvicorn
from backend.config import Settings

if __name__ == "__main__":
    cfg = Settings.from_file()
    uvicorn.run(
        "backend.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        reload=False,
    )
