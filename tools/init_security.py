"""Создаёт security/pubkey.json из пароля администратора.
Пароль берётся из переменной ADMIN_PASSWORD (GitHub Secret) или спрашивается в консоли.
Сам пароль и приватный ключ НЕ сохраняются."""
import getpass, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from security.license import derive_private, public_b64  # noqa: E402

pw = os.environ.get("ADMIN_PASSWORD") or ""
if not pw and sys.stdin.isatty():
    pw = getpass.getpass("Пароль администратора (минимум 10 символов): ")
if len(pw) < 10:
    sys.exit("ОШИБКА: пароль администратора не задан или короче 10 символов "
             "(GitHub: Settings → Secrets and variables → Actions → ADMIN_PASSWORD).")
salt = os.environ.get("SIGNING_SALT", "")
pub = public_b64(derive_private(pw, salt))
(ROOT / "security" / "pubkey.json").write_text(json.dumps({"pub": pub, "salt": salt}), encoding="utf-8")
print("OK: security/pubkey.json создан")
