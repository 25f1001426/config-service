import os
from pathlib import Path

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

BASE = Path(__file__).parent
APP_ENV = os.environ.get("APP_ENV", "development")

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DEFAULTS = {
    "port": 8000,
    "workers": 1,
    "debug": False,
    "log_level": "info",
    "api_key": "default-secret-000",
}

ALIASES = {"num_workers": "workers"}


def clean_key(raw: str) -> str:
    key = raw.lower()
    if key.startswith("app_"):
        key = key[4:]
    return ALIASES.get(key, key)


def to_bool(value) -> bool:
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def coerce(key: str, value):
    if key in ("port", "workers"):
        return int(value)
    if key == "debug":
        return to_bool(value)
    return str(value)


def load_yaml() -> dict:
    path = BASE / f"config.{APP_ENV}.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    return {clean_key(k): v for k, v in data.items()}


def load_dotenv() -> dict:
    path = BASE / ".env"
    result = {}
    if not path.exists():
        return result
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[clean_key(k.strip())] = v.strip().strip('"').strip("'")
    return result


def load_os_env() -> dict:
    return {clean_key(k): v for k, v in os.environ.items() if k.startswith("APP_") and k != "APP_ENV"}


@app.get("/effective-config")
def effective_config(set_params: list[str] = Query(default=[], alias="set")):
    merged = dict(DEFAULTS)
    for layer in (load_yaml(), load_dotenv(), load_os_env()):  # low -> high
        merged.update(layer)

    for item in set_params:
        if "=" not in item:
            raise HTTPException(status_code=400, detail=f"Bad override: {item}")
        k, v = item.split("=", 1)
        merged[clean_key(k.strip())] = v

    try:
        result = {k: coerce(k, v) for k, v in merged.items()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    result["api_key"] = "****"
    order = ["port", "workers", "debug", "log_level", "api_key"]
    return {**{k: result[k] for k in order}, **{k: v for k, v in result.items() if k not in order}}