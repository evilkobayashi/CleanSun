from __future__ import annotations
import json
from dataclasses import dataclass, field


@dataclass
class LANConfig:
    datalogger_ip: str
    datalogger_serial: int
    port: int = 8899
    poll_seconds: float = 5.0
    fail_threshold: int = 3
    battery_kwh: float = 9.6


@dataclass
class CloudConfig:
    enabled: bool = False
    app_id: str = ""
    app_secret: str = ""
    email: str = ""
    password: str = ""
    device_sn: str = ""


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8080
    db_path: str = "history.db"


@dataclass
class Settings:
    lan: LANConfig
    cloud: CloudConfig = field(default_factory=CloudConfig)
    server: ServerConfig = field(default_factory=ServerConfig)

    @classmethod
    def from_file(cls, path: str = "config.json") -> "Settings":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        lan = LANConfig(**data["lan"])
        cloud_data = data.get("cloud", {})
        cloud = CloudConfig(**{k: v for k, v in cloud_data.items()
                               if k in CloudConfig.__dataclass_fields__})
        server_data = data.get("server", {})
        server = ServerConfig(**{k: v for k, v in server_data.items()
                                 if k in ServerConfig.__dataclass_fields__})
        return cls(lan=lan, cloud=cloud, server=server)
