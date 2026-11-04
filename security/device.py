import hashlib, platform, sys, uuid


def get_device_id() -> str:
    raw = ""
    if sys.platform == "win32":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                               winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            raw = winreg.QueryValueEx(k, "MachineGuid")[0]
        except Exception:
            raw = ""
    if not raw:
        raw = f"{uuid.getnode()}-{platform.node()}"
    h = hashlib.sha256(("OMNIRO-HELPER|" + raw).encode()).hexdigest().upper()[:16]
    return "OH-" + "-".join(h[i:i + 4] for i in range(0, 16, 4))


def normalize(dev: str) -> str:
    return "".join(ch for ch in dev.upper() if ch.isalnum())
