"""Input validation helpers."""
import collections


def validate_config(config):
    """Validate that config is a mapping type with required keys."""
    if not isinstance(config, collections.Mapping):  # BUG: removed in Python 3.10
        raise TypeError(f"Expected a mapping, got {type(config).__name__}")
    required = {"host", "port", "db_name"}
    missing = required - set(config.keys())
    if missing:
        raise ValueError(f"Missing required config keys: {missing}")
    return config


def validate_port(port):
    if not isinstance(port, int) or not (1 <= port <= 65535):
        raise ValueError(f"Invalid port: {port}")
    return port
