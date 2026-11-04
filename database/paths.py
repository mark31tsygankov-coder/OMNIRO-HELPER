import os, sys
from pathlib import Path

APP_NAME = "OmniroHelper"


def bundle_dir() -> Path:
    """Папка с ресурсами (внутри EXE или корень проекта)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def appdata_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    p = Path(base) / APP_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_data_dir() -> Path:
    p = appdata_dir() / "user_data"
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_sources():
    """Папки с JSON-каталогами. Следующие переопределяют предыдущие."""
    out = [bundle_dir() / "data"]
    side = exe_dir() / "data"
    if side.exists() and side.resolve() != out[0].resolve():
        out.append(side)
    out.append(user_data_dir())
    return out


def asset(name: str) -> Path:
    return bundle_dir() / "assets" / name
