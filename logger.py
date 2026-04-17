"""Logging estruturado para o CleanSun com níveis configuráveis."""
import json
import sys
import time
from enum import IntEnum


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class CleanSunLogger:
    """Logger estruturado com saída JSON e níveis."""
    
    def __init__(self, name="cleansun", min_level=LogLevel.INFO, output=None):
        self.name = name
        self.min_level = LogLevel[min_level.upper()] if isinstance(min_level, str) else min_level
        self.output = output or (sys.stdout.write if sys.implementation.name != "micropython" else print)
        self._stats = {
            "messages_logged": 0,
            "by_level": {"debug": 0, "info": 0, "warning": 0, "error": 0, "critical": 0},
            "errors": [],
        }
    
    def _format(self, level_name, message, **kwargs):
        return {
            "timestamp": int(time.time()),
            "level": level_name.lower(),
            "logger": self.name,
            "message": message,
            **kwargs,
        }
    
    def _emit(self, level_enum, level_name, message, **kwargs):
        if level_enum < self.min_level:
            return
        self._stats["messages_logged"] += 1
        self._stats["by_level"][level_name.lower()] += 1
        
        log_entry = self._format(level_name, message, **kwargs)
        self.output(json.dumps(log_entry, ensure_ascii=False) + "\n")
        
        if level_enum >= LogLevel.ERROR and len(self._stats["errors"]) < 100:
            self._stats["errors"].append({"message": message, "timestamp": int(time.time())})
    
    def debug(self, message, **kwargs):
        self._emit(LogLevel.DEBUG, "DEBUG", message, **kwargs)
    
    def info(self, message, **kwargs):
        self._emit(LogLevel.INFO, "INFO", message, **kwargs)
    
    def warning(self, message, **kwargs):
        self._emit(LogLevel.WARNING, "WARNING", message, **kwargs)
    
    def error(self, message, **kwargs):
        self._emit(LogLevel.ERROR, "ERROR", message, **kwargs)
    
    def critical(self, message, **kwargs):
        self._emit(LogLevel.CRITICAL, "CRITICAL", message, **kwargs)
    
    def stats(self):
        return dict(self._stats)


DEFAULT_LOGGER = CleanSunLogger()