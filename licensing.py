"""Лицензии OMNIRO ONLANE: ключи подписаны (Ed25519), проверяются без интернета.

Ключ привязан к одному устройству (ID устройства) и имеет дату окончания.
Подделать ключ нельзя: для подписи нужен секретный ключ, он есть только в админ-панели
и зашифрован логином и паролем администратора.
"""
import base64
import hashlib
import json
import time
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# ===== Эти значения создаются один раз вместе с админ-доступом. НЕ МЕНЯТЬ. =====
PUBLIC_KEY = "98vWDZuYUWC4qu9Pw/kU+fnugIoxkFEKk2Ylzztntsw="
ADMIN_BLOB = {
    "salt": "4EaWWzJAhHZIFEncobkhLg==",
    "nonce": "ZyAp13d43eFqZ4Vn",
    "ct": "dECjSQO8tsugTUV4yzri5zLhcgsYgPBDsz2OUyK6HOkwcsOZzxH/4XZN1gX5gMuU",
}
# ==============================================================================

PREFIX = "OMNI-"
VERSION = 1


def _b64(s):
    return base64.b64decode(s)


# ---------- устройство ----------
def get_hwid():
    """ID устройства вида XXXX-XXXX-XXXX (не меняется между запусками)."""
    raw = ""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as k:
            raw = winreg.QueryValueEx(k, "MachineGuid")[0]
    except Exception:
        raw = str(uuid.getnode())
    h = hashlib.sha256(("omniro-" + raw).encode()).hexdigest()[:12].upper()
    return "-".join(h[i:i + 4] for i in (0, 4, 8))


def norm_hwid(text):
    h = "".join(c for c in str(text).upper() if c in "0123456789ABCDEF")
    return h if len(h) == 12 else None


# ---------- проверка ключа ----------
def verify(key, hwid=None):
    """-> dict(ok, error, name, expires)."""
    hwid = norm_hwid(hwid or get_hwid())
    token = "".join(str(key).split())
    if not token.upper().startswith(PREFIX):
        return {"ok": False, "error": "Неверный формат ключа"}
    try:
        blob = base64.urlsafe_b64decode(token[len(PREFIX):] + "=" * (-len(token[len(PREFIX):]) % 4))
        payload, sig = blob[:-64], blob[-64:]
        Ed25519PublicKey.from_public_bytes(_b64(PUBLIC_KEY)).verify(sig, payload)
        ver, expires, dev, nlen = payload[0], int.from_bytes(payload[1:5], "big"), payload[5:11], payload[11]
        name = payload[12:12 + nlen].decode("utf-8")
    except (InvalidSignature, ValueError, IndexError, UnicodeDecodeError):
        return {"ok": False, "error": "Ключ недействителен"}
    if ver != VERSION:
        return {"ok": False, "error": "Ключ от другой версии программы"}
    if dev.hex().upper() != hwid:
        return {"ok": False, "error": "Этот ключ выдан для другого устройства"}
    if expires < time.time():
        return {"ok": False, "error": "Срок действия ключа истёк"}
    return {"ok": True, "name": name, "expires": expires}


class Store:
    """Сохранённый ключ + защита от перевода часов назад."""

    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def clock_ok(self):
        return time.time() >= self.load().get("max_seen", 0) - 3600

    def touch(self, key=None):
        d = self.load()
        d["max_seen"] = max(d.get("max_seen", 0), int(time.time()))
        if key:
            d["key"] = key
        self._write(d)

    def clear(self):
        d = self.load()
        d.pop("key", None)
        self._write(d)


def check_saved(store):
    """Проверка сохранённого ключа при запуске и по таймеру -> dict как у verify()."""
    if not store.clock_ok():
        return {"ok": False, "error": "Системное время изменено. Верните правильное время."}
    key = store.load().get("key")
    if not key:
        return {"ok": False, "error": ""}
    r = verify(key)
    if r["ok"]:
        store.touch()
    return r


# ---------- админ ----------
def unlock_admin(login, password):
    """Расшифровывает секретный ключ по логину и паролю. Неверно -> None."""
    try:
        k = Scrypt(salt=_b64(ADMIN_BLOB["salt"]), length=32, n=2**15, r=8, p=1).derive(
            f"{login.strip()}\n{password}".encode())
        raw = AESGCM(k).decrypt(_b64(ADMIN_BLOB["nonce"]), _b64(ADMIN_BLOB["ct"]), b"omniro-admin")
        return Ed25519PrivateKey.from_private_bytes(raw)
    except (InvalidTag, ValueError):
        return None


def make_key(priv, name, days, hwid):
    """Создаёт ключ для устройства hwid на days дней. -> (key, expires)."""
    dev = norm_hwid(hwid)
    if not dev:
        raise ValueError("ID устройства должен быть вида XXXX-XXXX-XXXX")
    nb = name.strip().encode("utf-8")[:32]
    nb = nb.decode("utf-8", "ignore").encode("utf-8")
    expires = int(time.time()) + int(days) * 86400
    payload = bytes([VERSION]) + expires.to_bytes(4, "big") + bytes.fromhex(dev) + bytes([len(nb)]) + nb
    token = base64.urlsafe_b64encode(payload + priv.sign(payload)).decode().rstrip("=")
    return PREFIX + token, expires
