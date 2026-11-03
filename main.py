"""OMNIRO ONLANE - юридическая база (оверлей)."""
import html
import json
import os
import re
import shutil
import sys
import threading
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QSizeGrip, QSlider,
    QVBoxLayout, QWidget,
)

import licensing
from admin_panel import AdminPanel, LoginDialog, SecretLabel

APP_NAME = "OMNIRO ONLANE"

# ===== НАСТРОЙКИ ВЛАДЕЛЬЦА (меняйте перед сборкой) =====
UPDATE_URL = ""                # ссылка на ваш laws.json на хостинге (https://...)
# =======================================================

HOTKEYS = ["home", "end", "insert", "delete", "page_up", "page_down"] + [f"f{i}" for i in range(1, 13)]
SCALES = [0.9, 1.0, 1.15]

DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
SETTINGS_FILE = DATA_DIR / "settings.json"
DB_FILE = DATA_DIR / "laws.json"
BACKUP_FILE = DATA_DIR / "laws.backup.json"
LICENSE_FILE = DATA_DIR / "license.json"
DEFAULTS = {"hotkey": "home", "opacity": 96, "on_top": True, "update_url": "", "scale": 1, "fav": []}

STOP = set("что чем мне мой моя меня будет быть за на в во и или а как по при с со у к от до для не это то ли же бы если можно нельзя".split())


def res(rel):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / rel


def load_json(path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return fallback


def ver_tuple(v):
    try:
        return tuple(int(x) for x in str(v).split("."))
    except ValueError:
        return (0,)


def prepare_data():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    bundled = res("laws.json")
    if not DB_FILE.exists():
        shutil.copy(bundled, DB_FILE)
    elif ver_tuple(load_json(bundled, {}).get("version")) > ver_tuple(load_json(DB_FILE, {}).get("version")):
        shutil.copy(DB_FILE, BACKUP_FILE)
        shutil.copy(bundled, DB_FILE)
    settings = dict(DEFAULTS)
    settings.update(load_json(SETTINGS_FILE, {}))
    return settings


def save_settings(s):
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def write_db(db):
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=1), encoding="utf-8")


def validate_db(d):
    if not isinstance(d, dict) or "version" not in d or not isinstance(d.get("sections"), list) or not d["sections"]:
        return False
    for key in ("sections", "laws"):
        for s in d.get(key, []):
            if not isinstance(s, dict) or "id" not in s or "title" not in s or not isinstance(s.get("items"), list):
                return False
            for it in s["items"]:
                if not isinstance(it, dict) or "id" not in it or "text" not in it:
                    return False
    return True


def fetch_remote(url):
    req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not validate_db(data):
        raise ValueError("Файл базы имеет неверный формат")
    return data


# ---------- поиск ----------
def stem(w):
    return w if len(w) <= 3 else w[: max(3, len(w) - 2)]


def has(text, tok):
    return re.search(r"(?<![\wё])" + re.escape(tok), text) is not None


def tokens(q):
    return [stem(w) for w in re.findall(r"[\wё]+", q.lower()) if w not in STOP and len(w) > 1]


def flat_items(sections):
    return [(s, it) for s in sections for it in s["items"]]


def search(sections, query):
    items = flat_items(sections)
    q = query.strip()
    if not q:
        return items
    if re.fullmatch(r"\d+(\.\d+)*", q):
        return [(s, it) for s, it in items if it["id"] == q or it["id"].startswith(q + ".")]
    toks = tokens(q)
    if not toks:
        return []
    need = len(toks) if len(toks) <= 2 else len(toks) - 1
    scored = []
    for s, it in items:
        text = it["text"].lower()
        rest = " ".join([it.get("punishment", ""), *it.get("notes", [])]).lower()
        in_text = sum(1 for t in toks if has(text, t))
        in_rest = sum(1 for t in toks if has(rest, t) and not has(text, t))
        if in_text + in_rest >= need:
            scored.append((in_text * 2 + in_rest, s, it))
    scored.sort(key=lambda x: -x[0])
    return [(s, it) for _, s, it in scored]


def highlight(text, toks):
    safe = html.escape(text)
    if not toks:
        return safe
    pat = re.compile("(" + "|".join(re.escape(html.escape(t)) + r"[\wё]*" for t in toks) + ")", re.I)
    return pat.sub(r'<span style="color:#ff8a1f;">\1</span>', safe)


def punish_chips(pun):
    return [c.strip().rstrip(".") for c in re.split(r"\s+или\s+", pun or "") if c.strip()]


def chip_colors(t):
    tl = t.lower()
    if "навсегда" in tl or "аккаунт" in tl:
        return "#2a0d12", "#6b1f2b", "#ff8a9a"
    if "чат" in tl or "репорт" in tl or "голос" in tl:
        return "#1c1c1f", "#33333a", "#cfcfd6"
    return "#2a1606", "#6b3a0f", "#ffb066"


def split_notes(notes):
    exc, other = [], []
    for n in notes:
        m = re.match(r"^Исключени[ея]\s*:\s*(.*)$", n)
        if m:
            exc += [x.strip().rstrip(".") for x in m.group(1).split(";") if x.strip()]
        else:
            other.append(n)
    return exc, other


def chip_label(text, wrap=False):
    bg, br, fg = chip_colors(text)
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    lab.setStyleSheet(f"background:{bg}; border:1px solid {br}; color:{fg}; border-radius:8px; padding:4px 10px; font-size:12px; font-weight:600;")
    return lab


STYLE = """
* { font-family: 'Segoe UI', 'Segoe UI Symbol', 'Segoe UI Emoji', Arial; color: #f2f2f2; }
QFrame#panel { background: #0d0d0e; border: 1px solid #232325; border-radius: 20px; }
QFrame#line { background: #1f1f22; }
QLineEdit#search { background: transparent; border: none; font-size: 20px; font-weight: 600; padding: 4px 6px; selection-background-color: #ff7a00; }
QPushButton#icon { background: #171719; border: 1px solid #262629; border-radius: 12px; padding: 0; min-width: 38px; max-width: 38px; min-height: 38px; max-height: 38px; font-size: 17px; }
QPushButton#icon:hover { background: #222226; }
QPushButton#icon:checked { background: #2a1606; border: 1px solid #ff7a00; color: #ff8a1f; }
QFrame#seg { background: #151517; border: 1px solid #232325; border-radius: 16px; }
QPushButton#tab { background: transparent; border: none; color: #77777d; font-weight: 600; padding: 7px 16px; border-radius: 13px; }
QPushButton#tab:checked { background: #26262a; color: #ffffff; }
QPushButton#copy { background: #171719; border: 1px solid #262629; border-radius: 10px; padding: 6px 12px; font-size: 12px; }
QPushButton#copy:hover { background: #222226; }
QPushButton#star { background: transparent; border: none; font-size: 20px; padding: 0 6px; color: #ff8a1f; }
QPushButton#orange { background: #ff7a00; color: #080808; border: none; border-radius: 12px; padding: 9px 16px; font-weight: 600; }
QPushButton#orange:hover { background: #ff8f26; }
QPushButton#plain { background: #f2f2f2; color: #080808; border: none; border-radius: 12px; padding: 9px 16px; font-weight: 600; }
QPushButton#danger { background: #3a1016; color: #ff8a9a; border: 1px solid #6b1f2b; border-radius: 12px; padding: 9px 16px; font-weight: 600; }
QLabel#rid { color: #ff7a00; font-size: 12px; font-weight: 700; }
QLabel#tag { color: #666; font-size: 11px; }
QLabel#rtext { color: #cfcfd2; font-size: 13px; }
QLabel#did { color: #ff7a00; font-size: 22px; font-weight: 700; }
QLabel#dsec { color: #77777d; font-size: 13px; }
QLabel#dtext { font-size: 16px; }
QLabel#more { background: #1a1a1d; border-radius: 6px; padding: 3px 7px; color: #8a8a90; font-size: 11px; }
QFrame#block { background: #141416; border-radius: 14px; }
QLabel#bhead { color: #8a8a90; font-size: 13px; }
QLabel#ghead { color: #4cd37b; font-size: 13px; font-weight: 700; }
QLabel#bitem { color: #a6a6ac; font-size: 13px; }
QLabel#empty { color: #6c6c72; font-size: 14px; padding: 30px; }
QLabel#result { color: #ffb066; font-size: 20px; font-weight: 700; padding: 10px 0; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #2c2c30; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QDialog { background: #0d0d0e; }
QLineEdit { background: #171719; border: 1px solid #262629; border-radius: 10px; padding: 8px 12px; selection-background-color: #ff7a00; }
QComboBox { background: #171719; border: 1px solid #262629; border-radius: 10px; padding: 6px 10px; }
QComboBox QAbstractItemView { background: #171719; selection-background-color: #ff7a00; }
QListWidget { background: #141416; border: 1px solid #262629; border-radius: 10px; padding: 4px; outline: 0; }
QListWidget::item { padding: 7px 8px; border-radius: 6px; }
QListWidget::item:selected { background: #ff7a00; color: #080808; }
QTabWidget::pane { border: none; }
QTabBar::tab { background: #171719; padding: 8px 18px; border-radius: 10px; margin-right: 6px; }
QTabBar::tab:selected { background: #ff7a00; color: #080808; }
QSlider::groove:horizontal { background: #262629; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #ff7a00; width: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #ff7a00; border-radius: 3px; }
"""


def build_style(scale_idx):
    f = SCALES[scale_idx] if 0 <= scale_idx < len(SCALES) else 1.0
    return re.sub(r"font-size:\s*(\d+)px", lambda m: f"font-size: {round(int(m.group(1)) * f)}px", STYLE)


def fav_key(tab, art_id):
    return f"{tab}:{art_id}"


class DragBar(QWidget):
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()


class ResultRow(QFrame):
    def __init__(self, section, item, toks, fav, on_click):
        super().__init__()
        self.item, self.section, self.on_click = item, section, on_click
        self.setObjectName("row")
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(5)
        top = QHBoxLayout()
        rid = QLabel(item["id"])
        rid.setObjectName("rid")
        tag = QLabel(("★ " if fav else "") + section.get("short", section["title"]))
        tag.setObjectName("tag")
        top.addWidget(rid)
        top.addStretch()
        top.addWidget(tag)
        lay.addLayout(top)
        txt = item["text"]
        if len(txt) > 110:
            txt = txt[:110].rstrip() + "…"
        lab = QLabel(highlight(txt, toks))
        lab.setTextFormat(Qt.RichText)
        lab.setObjectName("rtext")
        lab.setWordWrap(True)
        lay.addWidget(lab)
        chips = punish_chips(item.get("punishment"))
        if chips:
            row = QHBoxLayout()
            first = chips[0] if len(chips[0]) <= 34 else chips[0][:33] + "…"
            c = chip_label(first)
            c.setStyleSheet(c.styleSheet().replace("padding:4px 10px", "padding:2px 8px").replace("font-size:12px", "font-size:11px"))
            row.addWidget(c)
            if len(chips) > 1:
                m = QLabel(f"+{len(chips) - 1}")
                m.setObjectName("more")
                row.addWidget(m)
            row.addStretch()
            lay.addLayout(row)
        self.set_selected(False)

    def set_selected(self, sel):
        self.setStyleSheet("QFrame#row { background: %s; border-radius: 12px; }" % ("#1a1a1d" if sel else "transparent"))

    def mousePressEvent(self, e):
        self.on_click(self)


class SettingsDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(380)
        self.s = settings
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(QLabel("Клавиша открытия и скрытия"))
        self.hk = QComboBox()
        self.hk.addItems([h.upper() for h in HOTKEYS])
        self.hk.setCurrentText(settings["hotkey"].upper())
        lay.addWidget(self.hk)
        lay.addWidget(QLabel("Прозрачность окна"))
        self.op = QSlider(Qt.Horizontal)
        self.op.setRange(40, 100)
        self.op.setValue(settings["opacity"])
        lay.addWidget(self.op)
        lay.addWidget(QLabel("Размер текста"))
        self.sc = QComboBox()
        self.sc.addItems(["Мелкий", "Обычный", "Крупный"])
        self.sc.setCurrentIndex(settings["scale"])
        lay.addWidget(self.sc)
        self.top = QCheckBox("Поверх всех окон")
        self.top.setChecked(settings["on_top"])
        lay.addWidget(self.top)
        b_ok = QPushButton("Сохранить")
        b_ok.setObjectName("orange")
        b_ok.clicked.connect(lambda: (self.apply(), self.accept()))
        lay.addWidget(b_ok)
        b_quit = QPushButton("Закрыть программу")
        b_quit.setObjectName("plain")
        b_quit.clicked.connect(QApplication.quit)
        lay.addWidget(b_quit)

    def apply(self):
        self.s["hotkey"] = self.hk.currentText().lower()
        self.s["opacity"] = self.op.value()
        self.s["on_top"] = self.top.isChecked()
        self.s["scale"] = self.sc.currentIndex()
        save_settings(self.s)
        QApplication.instance().setStyleSheet(build_style(self.s["scale"]))
        self.parent().apply_window_settings()


class ActivationDialog(QDialog):
    def __init__(self, store, message=""):
        super().__init__()
        self.store = store
        self.hwid = licensing.get_hwid()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(res("icon.png"))))
        self.setFixedWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)
        title = SecretLabel("⚡ " + APP_NAME)
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #ff7a00;")
        title.triggered.connect(self.open_admin_panel)
        lay.addWidget(title)
        lay.addWidget(QLabel("ID вашего устройства (отправьте его администратору):"))
        row = QHBoxLayout()
        idl = QLabel(self.hwid)
        idl.setStyleSheet("font-size: 16px; font-weight: bold;")
        idl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        b_copy = QPushButton("Копировать")
        b_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.hwid))
        row.addWidget(idl, 1)
        row.addWidget(b_copy)
        lay.addLayout(row)
        lay.addWidget(QLabel("Ключ активации"))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Вставьте ключ OMNI-…")
        self.edit.returnPressed.connect(self.activate)
        lay.addWidget(self.edit)
        self.msg = QLabel(message)
        self.msg.setWordWrap(True)
        self.msg.setStyleSheet("color: #ff5555;")
        lay.addWidget(self.msg)
        self.btn = QPushButton("Активировать")
        self.btn.clicked.connect(self.activate)
        lay.addWidget(self.btn)

    def open_admin_panel(self):
        key = open_admin(self)
        if key:  # админ создал ключ для этого ПК - сразу активируем
            self.edit.setText(key)
            self.activate()

    def activate(self):
        key = "".join(self.edit.text().split())
        if not key:
            return
        r = licensing.verify(key)
        if r["ok"] and not self.store.clock_ok():
            r = {"ok": False, "error": "Системное время изменено. Верните правильное время."}
        if r["ok"]:
            self.store.touch(key)
            self.accept()
        else:
            self.msg.setText(r["error"])


def open_admin(parent=None):
    """Секретный вход админа. Возвращает ключ для этого ПК, если админ его создал."""
    login = LoginDialog(parent)
    if login.exec() != QDialog.Accepted or login.priv is None:
        return None
    panel = AdminPanel(login.priv, DATA_DIR, parent)
    panel.exec()
    return panel.own_key


def ensure_license():
    """True, если можно запускать программу."""
    store = licensing.Store(LICENSE_FILE)
    r = licensing.check_saved(store)
    if r["ok"]:
        return True
    return ActivationDialog(store, r["error"]).exec() == QDialog.Accepted


def watch_license():
    """Раз в 5 минут проверяет срок ключа (истёк -> программа закрывается)."""
    store = licensing.Store(LICENSE_FILE)

    def tick():
        r = licensing.check_saved(store)
        if not r["ok"]:
            QMessageBox.warning(None, APP_NAME, f"Ключ больше не действует.\n{r['error']}")
            QApplication.quit()

    timer = QTimer()
    timer.timeout.connect(tick)
    timer.start(5 * 60 * 1000)
    return timer


class Bridge(QObject):
    toggle = Signal()
    updated = Signal(object)
    failed = Signal(str)


class MainWindow(QWidget):
    def __init__(self, settings, bridge):
        super().__init__()
        self.settings = settings
        self.bridge = bridge
        self.db = load_json(DB_FILE, {"version": "?", "sections": [], "laws": []})
        self.tab = "sections"
        self.rows = []
        self.fav_mode = False
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(res("icon.png"))))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(1080, 660)
        bridge.toggle.connect(self.toggle_visible)
        bridge.updated.connect(self.on_updated)
        bridge.failed.connect(lambda m: QMessageBox.warning(self, APP_NAME, f"Не удалось обновить базу:\n{m}"))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        panel = QFrame()
        panel.setObjectName("panel")
        outer.addWidget(panel)
        root = QVBoxLayout(panel)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = DragBar()
        head = QHBoxLayout(bar)
        head.setContentsMargins(18, 14, 18, 14)
        head.setSpacing(8)
        logo = SecretLabel()
        logo.setPixmap(QIcon(str(res("icon.png"))).pixmap(34, 34))
        logo.triggered.connect(lambda: open_admin(self))
        head.addWidget(logo)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Что мне будет за убийство игрока?")
        self.search.textChanged.connect(self.refresh)
        head.addWidget(self.search, 1)
        seg = QFrame()
        seg.setObjectName("seg")
        sl = QHBoxLayout(seg)
        sl.setContentsMargins(3, 3, 3, 3)
        sl.setSpacing(0)
        self.b_rules = QPushButton("Правила")
        self.b_laws = QPushButton("Законы")
        for b, key in ((self.b_rules, "sections"), (self.b_laws, "laws")):
            b.setObjectName("tab")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, k=key: self.set_tab(k))
            sl.addWidget(b)
        self.b_rules.setChecked(True)
        head.addWidget(seg)

        self.b_fav = self.icon_btn("★", "Избранное", head, checkable=True)
        self.b_fav.clicked.connect(self.toggle_fav_mode)
        self.icon_btn("↻", "Обновить базу", head).clicked.connect(lambda: self.do_update(False))
        self.icon_btn("⚙", "Настройки", head).clicked.connect(lambda: SettingsDialog(self, self.settings).exec())
        self.icon_btn("–", "Скрыть", head).clicked.connect(self.hide)
        root.addWidget(bar)

        line = QFrame()
        line.setObjectName("line")
        line.setFixedHeight(1)
        root.addWidget(line)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self.left = QScrollArea()
        self.left.setWidgetResizable(True)
        self.left.setFixedWidth(400)
        self.left_w = QWidget()
        self.left_w.setStyleSheet("background: transparent;")
        self.left_l = QVBoxLayout(self.left_w)
        self.left_l.setContentsMargins(10, 10, 6, 10)
        self.left_l.setSpacing(2)
        self.left.setWidget(self.left_w)
        body.addWidget(self.left)
        vline = QFrame()
        vline.setObjectName("line")
        vline.setFixedWidth(1)
        body.addWidget(vline)
        self.right = QScrollArea()
        self.right.setWidgetResizable(True)
        self.right_w = QWidget()
        self.right_w.setStyleSheet("background: transparent;")
        self.right_l = QVBoxLayout(self.right_w)
        self.right_l.setContentsMargins(26, 22, 26, 22)
        self.right_l.setSpacing(14)
        self.right.setWidget(self.right_w)
        body.addWidget(self.right, 1)
        root.addLayout(body, 1)

        foot = QHBoxLayout()
        foot.setContentsMargins(18, 0, 10, 6)
        self.status = QLabel()
        self.status.setObjectName("tag")
        foot.addWidget(self.status)
        foot.addStretch()
        foot.addWidget(QSizeGrip(self))
        root.addLayout(foot)

        self.apply_window_settings()
        self.refresh()
        if self.settings.get("update_url") or UPDATE_URL:
            QTimer.singleShot(1500, lambda: self.do_update(True))

    def icon_btn(self, glyph, tip, layout, checkable=False):
        b = QPushButton(glyph)
        b.setObjectName("icon")
        b.setToolTip(tip)
        b.setCheckable(checkable)
        layout.addWidget(b)
        return b

    # ----- данные -----
    def sections(self):
        return self.db.get(self.tab, [])

    def set_tab(self, key):
        self.tab = key
        self.fav_mode = False
        self.sync_buttons()
        self.refresh()

    def toggle_fav_mode(self):
        self.fav_mode = self.b_fav.isChecked()
        self.sync_buttons()
        self.refresh()

    def sync_buttons(self):
        self.b_fav.setChecked(self.fav_mode)
        self.b_rules.setChecked(not self.fav_mode and self.tab == "sections")
        self.b_laws.setChecked(not self.fav_mode and self.tab == "laws")

    def clear(self, layout):
        while layout.count():
            it = layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def update_status(self):
        if self.fav_mode:
            fav = self.settings.get("fav", [])
            self.status.setText(f"{APP_NAME}  ·  избранное: {len(fav)}")
            return
        total = sum(len(s["items"]) for s in self.sections())
        self.status.setText(f"{APP_NAME}  ·  версия базы {self.db.get('version', '?')}  ·  записей: {total}")

    def flash(self, msg):
        self.status.setText(msg)
        QTimer.singleShot(3000, self.update_status)

    def collect(self):
        q = self.search.text()
        if not self.fav_mode:
            return [(self.tab, s, it) for s, it in search(self.sections(), q)]
        fav = set(self.settings.get("fav", []))
        out = []
        for tab in ("sections", "laws"):
            for s, it in search(self.db.get(tab, []), q):
                if fav_key(tab, it["id"]) in fav:
                    out.append((tab, s, it))
        return out

    def refresh(self):
        self.clear(self.left_l)
        self.rows = []
        toks = tokens(self.search.text())
        results = self.collect()
        fav = set(self.settings.get("fav", []))
        self.update_status()
        if not results:
            if self.fav_mode:
                msg = "В избранном пока пусто. Откройте статью и нажмите ☆"
            elif self.sections():
                msg = "Ничего не найдено"
            else:
                msg = "Раздел пока пуст"
            e = QLabel(msg)
            e.setObjectName("empty")
            e.setAlignment(Qt.AlignCenter)
            e.setWordWrap(True)
            self.left_l.addWidget(e)
            self.show_detail(None, None, None)
        else:
            for tab, s, it in results:
                row = ResultRow(s, it, toks, fav_key(tab, it["id"]) in fav, self.select_row)
                row.tab = tab
                self.rows.append(row)
                self.left_l.addWidget(row)
            self.select_row(self.rows[0])
        self.left_l.addStretch()

    def select_row(self, row):
        for r in self.rows:
            r.set_selected(r is row)
        self.show_detail(row.tab, row.section, row.item)

    def toggle_fav(self, tab, art_id):
        fav = self.settings.setdefault("fav", [])
        k = fav_key(tab, art_id)
        if k in fav:
            fav.remove(k)
        else:
            fav.append(k)
        save_settings(self.settings)
        self.refresh()
        for r in self.rows:
            if r.item["id"] == art_id and r.tab == tab:
                self.select_row(r)
                break

    def show_detail(self, tab, section, item):
        self.clear(self.right_l)
        if item is None:
            return
        toks = tokens(self.search.text())
        head = QWidget()
        hl = QHBoxLayout(head)
        hl.setContentsMargins(0, 0, 0, 0)
        did = QLabel(item["id"])
        did.setObjectName("did")
        dsec = QLabel(section["title"])
        dsec.setObjectName("dsec")
        hl.addWidget(did)
        hl.addWidget(dsec)
        hl.addStretch()
        is_fav = fav_key(tab, item["id"]) in self.settings.get("fav", [])
        b_star = QPushButton("★" if is_fav else "☆")
        b_star.setObjectName("star")
        b_star.setToolTip("В избранное")
        b_star.clicked.connect(lambda: self.toggle_fav(tab, item["id"]))
        hl.addWidget(b_star)
        b_copy = QPushButton("Копировать")
        b_copy.setObjectName("copy")
        b_copy.clicked.connect(lambda: self.copy_item(b_copy, item))
        hl.addWidget(b_copy)
        self.right_l.addWidget(head)

        t = QLabel(highlight(item["text"], toks))
        t.setTextFormat(Qt.RichText)
        t.setObjectName("dtext")
        t.setWordWrap(True)
        t.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.right_l.addWidget(t)

        chips = punish_chips(item.get("punishment"))
        if chips:
            blk = QFrame()
            blk.setObjectName("block")
            bl = QVBoxLayout(blk)
            bl.setContentsMargins(16, 14, 16, 16)
            bl.setSpacing(10)
            h = QLabel("Наказание")
            h.setObjectName("bhead")
            bl.addWidget(h)
            for c in chips:
                row = QHBoxLayout()
                row.addWidget(chip_label(c, wrap=True))
                row.addStretch()
                bl.addLayout(row)
            self.right_l.addWidget(blk)

        exc, other = split_notes(item.get("notes", []))
        if exc:
            self.right_l.addWidget(self.list_block("Исключения", exc, "ghead", "•"))
        if other:
            self.right_l.addWidget(self.list_block("Примечания", other, "bhead", ""))
        self.right_l.addStretch()

    def list_block(self, title, lines, head_obj, bullet):
        blk = QFrame()
        blk.setObjectName("block")
        bl = QVBoxLayout(blk)
        bl.setContentsMargins(16, 14, 16, 14)
        bl.setSpacing(8)
        h = QLabel(title)
        h.setObjectName(head_obj)
        bl.addWidget(h)
        for ln in lines:
            lab = QLabel((bullet + "  " if bullet else "") + ln)
            lab.setObjectName("bitem")
            lab.setWordWrap(True)
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            bl.addWidget(lab)
        return blk

    def copy_item(self, btn, item):
        text = f"Ст. {item['id']}: {item['text']}"
        if item.get("punishment"):
            text += f"\nНаказание: {item['punishment']}"
        QApplication.clipboard().setText(text)
        btn.setText("Скопировано")
        QTimer.singleShot(1200, lambda: btn.setText("Копировать"))

    # ----- обновление и админка -----
    def do_update(self, silent):
        url = self.settings.get("update_url") or UPDATE_URL
        if not url:
            if not silent:
                QMessageBox.information(self, APP_NAME, "Администратор ещё не указал ссылку для обновления.")
            return
        if not silent:
            self.flash("Проверяю обновления…")

        def work():
            try:
                self.bridge.updated.emit((fetch_remote(url), silent))
            except Exception as e:
                if not silent:
                    self.bridge.failed.emit(str(e))

        threading.Thread(target=work, daemon=True).start()

    def on_updated(self, payload):
        data, silent = payload
        if ver_tuple(data["version"]) <= ver_tuple(self.db.get("version", "0")):
            if not silent:
                self.flash("База актуальна")
            return
        if DB_FILE.exists():
            shutil.copy(DB_FILE, BACKUP_FILE)
        write_db(data)
        self.db.clear()
        self.db.update(data)
        self.refresh()
        self.flash(f"База обновлена до версии {data['version']}")

    # ----- окно -----
    def apply_window_settings(self):
        vis = self.isVisible()
        flags = Qt.Window | Qt.FramelessWindowHint
        if self.settings["on_top"]:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setWindowOpacity(self.settings["opacity"] / 100)
        if vis:
            self.show()

    def toggle_visible(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            self.search.setFocus()
            self.search.selectAll()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)


def start_hotkey_listener(settings, bridge):
    try:
        from pynput import keyboard
    except Exception:
        return

    def on_press(key):
        name = getattr(key, "name", None)
        if name and name == settings["hotkey"]:
            bridge.toggle.emit()

    keyboard.Listener(on_press=on_press, daemon=True).start()


def main():
    settings = prepare_data()
    app = QApplication(sys.argv)
    app.setStyleSheet(build_style(settings["scale"]))
    app.setWindowIcon(QIcon(str(res("icon.png"))))
    if not ensure_license():
        sys.exit(0)
    license_timer = watch_license()  # noqa: F841 (держим ссылку)
    bridge = Bridge()
    win = MainWindow(settings, bridge)
    win.show()
    start_hotkey_listener(settings, bridge)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
