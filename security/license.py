"""Лицензии OMNIRO HELPER: подпись Ed25519, привязка к устройству, срок, отзыв.

Приватный ключ нигде не хранится: он выводится из пароля администратора (scrypt)
только в момент входа в админ-панель. В программе лежит лишь ПУБЛИЧНЫЙ ключ
(security/pubkey.json), создаваемый при сборке (tools/init_security.py).
"""
import base64, hashlib, hmac, json, os, time, uuid
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from database.paths import bundle_dir, appdata_dir, data_sources
from .device import get_device_id, normalize

PREFIX = "OH1"
ADMIN_LOGIN = "omniro_boss"
_SALT = b"OMNIRO-HELPER-ED25519-v1"


class LicenseError(Exception):
    pass


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def derive_private(password: str, extra_salt: str = "") -> Ed25519PrivateKey:
    seed = hashlib.scrypt(password.encode("utf-8"), salt=_SALT + extra_salt.encode(),
                          n=2 ** 15, r=8, p=1, maxmem=128 * 1024 * 1024, dklen=32)
    return Ed25519PrivateKey.from_private_bytes(seed)


def public_b64(priv: Ed25519PrivateKey) -> str:
    return b64e(priv.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))


def load_pub():
    p = bundle_dir() / "security" / "pubkey.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def admin_login(login: str, password: str) -> Ed25519PrivateKey:
    cfg = load_pub()
    if not cfg:
        raise LicenseError("Админ-панель не настроена: при сборке не задан пароль администратора.")
    ok_login = hmac.compare_digest(login.strip().encode(), ADMIN_LOGIN.encode())
    priv = derive_private(password, cfg.get("salt", ""))
    ok_pass = hmac.compare_digest(public_b64(priv).encode(), cfg["pub"].encode())
    if not (ok_login and ok_pass):
        time.sleep(1.0)
        raise LicenseError("Неверный логин или пароль.")
    return priv


def create_key(priv, name, device, days=None, expires_ts=None):
    now = time.time()
    exp = expires_ts if expires_ts else now + float(days) * 86400
    if exp <= now:
        raise LicenseError("Срок действия должен быть в будущем.")
    dev = "*" if not device.strip() else device.strip().upper()
    payload = {"v": 1, "id": uuid.uuid4().hex[:10], "n": name.strip() or "Без названия",
               "d": dev, "c": int(now), "e": int(exp)}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    key = f"{PREFIX}-{b64e(raw)}.{b64e(priv.sign(raw))}"
    return key, payload


def revoked_ids():
    ids = set()
    for folder in data_sources():
        f = Path(folder) / "revoked.json"
        if f.exists():
            try:
                ids.update(json.loads(f.read_text(encoding="utf-8")).get("revoked", []))
            except Exception:
                pass
    return ids


def verify_key(key: str, device_id: str = None, now: float = None) -> dict:
    cfg = load_pub()
    if not cfg:
        raise LicenseError("Приложение собрано без ключа проверки лицензий.")
    key = "".join(key.split())
    if not key.startswith(PREFIX + "-") or "." not in key:
        raise LicenseError("Неверный формат ключа.")
    try:
        body, sig = key[len(PREFIX) + 1:].split(".", 1)
        raw, sigb = b64d(body), b64d(sig)
        Ed25519PublicKey.from_public_bytes(b64d(cfg["pub"])).verify(sigb, raw)
        p = json.loads(raw)
    except InvalidSignature:
        raise LicenseError("Ключ поддельный или повреждён (подпись не прошла).")
    except Exception:
        raise LicenseError("Ключ повреждён: проверьте, что скопировали его целиком.")
    dev = device_id or get_device_id()
    if p["d"] != "*" and normalize(p["d"]) != normalize(dev):
        raise LicenseError("Ключ привязан к другому компьютеру.")
    now = now or time.time()
    if p["e"] < now:
        raise LicenseError("Срок действия ключа истёк.")
    if p["id"] in revoked_ids():
        raise LicenseError("Ключ отозван администратором.")
    return p


# ---- сохранённая активация ----
def _file() -> Path:
    return appdata_dir() / "activation.json"


def save_activation(key: str):
    _file().write_text(json.dumps({"key": key, "last_seen": time.time()}), encoding="utf-8")


def clear_activation():
    try:
        _file().unlink()
    except FileNotFoundError:
        pass


def check_saved():
    f = _file()
    if not f.exists():
        raise LicenseError("Приложение не активировано.")
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        raise LicenseError("Файл активации повреждён. Введите ключ заново.")
    now = time.time()
    if now < d.get("last_seen", 0) - 600:
        raise LicenseError("Обнаружен сдвиг системных часов назад. Верните правильное время.")
    p = verify_key(d["key"], now=now)
    d["last_seen"] = max(now, d.get("last_seen", 0))
    f.write_text(json.dumps(d), encoding="utf-8")
    return p


def status_of(rec: dict) -> str:
    if rec.get("revoked"):
        return "отозван"
    return "истёк" if rec["expires"] < time.time() else "активен"
