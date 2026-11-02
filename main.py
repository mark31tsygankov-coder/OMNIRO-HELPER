"""OMNIRO ONLANE - юридическая база (оверлей)."""
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QScrollArea, QSlider,
    QVBoxLayout, QWidget,
)

APP_NAME = "OMNIRO ONLANE"
HOTKEYS = ["home", "end", "insert", "delete", "page_up", "page_down"] + [f"f{i}" for i in range(1, 13)]

DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / APP_NAME
SETTINGS_FILE = DATA_DIR / "settings.json"
DB_FILE = DATA_DIR / "laws.json"
BACKUP_FILE = DATA_DIR / "laws.backup.json"
DEFAULTS = {"hotkey": "home", "opacity": 95, "on_top": True, "update_url": ""}


def res(rel):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / rel


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
    else:
        # если вышла новая версия программы с более свежей базой - обновляем
        if ver_tuple(load_json(bundled, {}).get("version")) > ver_tuple(load_json(DB_FILE, {}).get("version")):
            shutil.copy(DB_FILE, BACKUP_FILE)
            shutil.copy(bundled, DB_FILE)
    settings = dict(DEFAULTS)
    settings.update(load_json(SETTINGS_FILE, {}))
    return settings


def save_settings(s):
    SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def validate_db(d):
    if not isinstance(d, dict) or "version" not in d or not isinstance(d.get("sections"), list) or not d["sections"]:
        return False
    for s in d["sections"]:
        if not isinstance(s, dict) or "id" not in s or "title" not in s or not isinstance(s.get("items"), list):
            return False
        for it in s["items"]:
            if not isinstance(it, dict) or "id" not in it or "text" not in it:
                return False
    return True


def update_from_url(url):
    req = urllib.request.Request(url, headers={"User-Agent": APP_NAME})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    if not validate_db(data):
        raise ValueError("Файл базы имеет неверный формат")
    if DB_FILE.exists():
        shutil.copy(DB_FILE, BACKUP_FILE)
    DB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


STYLE = """
* { font-family: 'Segoe UI', Arial; color: #f2f2f2; }
QWidget#root, QDialog { background: #080808; }
QLabel#title { font-size: 20px; font-weight: 700; }
QLabel#sub { color: #8a8a8a; font-size: 12px; }
QLineEdit { background: #171717; border: 1px solid #262626; border-radius: 12px; padding: 10px 14px; font-size: 14px; }
QLineEdit:focus { border: 1px solid #ff7a00; }
QListWidget { background: #0f0f0f; border: none; border-radius: 12px; padding: 6px; font-size: 13px; outline: 0; }
QListWidget::item { padding: 10px 12px; border-radius: 8px; }
QListWidget::item:selected { background: #ff7a00; color: #080808; }
QListWidget::item:hover:!selected { background: #1d1d1d; }
QPushButton { background: #f2f2f2; color: #080808; border: none; border-radius: 12px; padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: #ffffff; }
QPushButton#orange { background: #ff7a00; }
QPushButton#orange:hover { background: #ff8f26; }
QFrame#card { background: #171717; border: 1px solid #222; border-radius: 14px; }
QLabel#badge { background: #ff7a00; color: #080808; border-radius: 8px; padding: 3px 10px; font-weight: 700; }
QLabel#ctext { font-size: 14px; }
QLabel#pun { background: #241505; border-left: 3px solid #ff7a00; border-radius: 6px; padding: 8px 10px; color: #ffb066; font-weight: 600; }
QLabel#note { color: #9a9a9a; font-size: 12px; }
QLabel#head { color: #ff7a00; font-size: 15px; font-weight: 700; padding: 8px 2px 0 2px; }
QLabel#empty { color: #777; font-size: 14px; padding: 30px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; }
QScrollBar::handle:vertical { background: #333; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QComboBox { background: #171717; border: 1px solid #262626; border-radius: 10px; padding: 6px 10px; }
QComboBox QAbstractItemView { background: #171717; selection-background-color: #ff7a00; }
QSlider::groove:horizontal { background: #262626; height: 6px; border-radius: 3px; }
QSlider::handle:horizontal { background: #ff7a00; width: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #ff7a00; border-radius: 3px; }
"""


class Card(QFrame):
    def __init__(self, item):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)
        top = QHBoxLayout()
        badge = QLabel(f"Ст. {item['id']}")
        badge.setObjectName("badge")
        top.addWidget(badge)
        top.addStretch()
        lay.addLayout(top)
        text = QLabel(item["text"])
        text.setObjectName("ctext")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(text)
        if item.get("punishment"):
            pun = QLabel(item["punishment"])
            pun.setObjectName("pun")
            pun.setWordWrap(True)
            pun.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(pun)
        for n in item.get("notes", []):
            note = QLabel(n)
            note.setObjectName("note")
            note.setWordWrap(True)
            note.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(note)


class SettingsDialog(QDialog):
    def __init__(self, parent, settings, on_update, on_rollback):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(420)
        self.s = settings
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        lay.addWidget(QLabel("Клавиша открытия/скрытия:"))
        self.hk = QComboBox()
        self.hk.addItems([h.upper() for h in HOTKEYS])
        self.hk.setCurrentText(settings["hotkey"].upper())
        lay.addWidget(self.hk)

        lay.addWidget(QLabel("Прозрачность окна:"))
        self.op = QSlider(Qt.Horizontal)
        self.op.setRange(40, 100)
        self.op.setValue(settings["opacity"])
        lay.addWidget(self.op)

        self.top = QCheckBox("Поверх всех окон")
        self.top.setChecked(settings["on_top"])
        lay.addWidget(self.top)

        lay.addWidget(QLabel("Ссылка на JSON с базой (для обновления):"))
        self.url = QLineEdit(settings["update_url"])
        self.url.setPlaceholderText("https://example.com/laws.json")
        lay.addWidget(self.url)

        row = QHBoxLayout()
        b_up = QPushButton("Обновить базу")
        b_up.setObjectName("orange")
        b_up.clicked.connect(lambda: (self.apply(), on_update()))
        b_rb = QPushButton("Откатить базу")
        b_rb.clicked.connect(on_rollback)
        row.addWidget(b_up)
        row.addWidget(b_rb)
        lay.addLayout(row)

        b_ok = QPushButton("Сохранить")
        b_ok.setObjectName("orange")
        b_ok.clicked.connect(lambda: (self.apply(), self.accept()))
        lay.addWidget(b_ok)

    def apply(self):
        self.s["hotkey"] = self.hk.currentText().lower()
        self.s["opacity"] = self.op.value()
        self.s["on_top"] = self.top.isChecked()
        self.s["update_url"] = self.url.text().strip()
        save_settings(self.s)
        self.parent().apply_window_settings()


class Bridge(QObject):
    toggle = Signal()


class MainWindow(QWidget):
    def __init__(self, settings, bridge):
        super().__init__()
        self.setObjectName("root")
        self.settings = settings
        self.db = load_json(DB_FILE, {"version": "?", "sections": []})
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(res("icon.png"))))
        self.resize(1000, 700)
        bridge.toggle.connect(self.toggle_visible)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(str(res("icon.png"))).pixmap(40, 40))
        head.addWidget(logo)
        col = QVBoxLayout()
        col.setSpacing(0)
        t = QLabel(APP_NAME)
        t.setObjectName("title")
        self.sub = QLabel()
        self.sub.setObjectName("sub")
        col.addWidget(t)
        col.addWidget(self.sub)
        head.addLayout(col)
        head.addStretch()
        b_set = QPushButton("Настройки")
        b_set.clicked.connect(self.open_settings)
        head.addWidget(b_set)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(14)
        self.secs = QListWidget()
        self.secs.setFixedWidth(250)
        body.addWidget(self.secs)

        right = QVBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск: номер статьи, слово, наказание (например: DM, 4.1, деморган)")
        self.search.textChanged.connect(self.refresh)
        right.addWidget(self.search)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.holder = QWidget()
        self.holder.setStyleSheet("background: transparent;")
        self.vbox = QVBoxLayout(self.holder)
        self.vbox.setSpacing(10)
        self.vbox.setContentsMargins(0, 0, 8, 0)
        self.scroll.setWidget(self.holder)
        right.addWidget(self.scroll)
        body.addLayout(right)
        root.addLayout(body)

        self.fill_sections()
        self.secs.currentRowChanged.connect(self.refresh)
        self.apply_window_settings()

    def fill_sections(self):
        self.secs.blockSignals(True)
        self.secs.clear()
        self.secs.addItem("Все разделы")
        for s in self.db["sections"]:
            self.secs.addItem(f"{s['id']}. {s['title']}")
        self.secs.setCurrentRow(0)
        self.secs.blockSignals(False)
        total = sum(len(s["items"]) for s in self.db["sections"])
        self.sub.setText(f"Юридическая база  ·  версия {self.db.get('version', '?')}  ·  статей: {total}")
        self.refresh()

    def refresh(self):
        while self.vbox.count():
            w = self.vbox.takeAt(0).widget()
            if w:
                w.deleteLater()
        q = self.search.text().lower().strip()
        row = self.secs.currentRow()
        found = 0
        for i, s in enumerate(self.db["sections"], start=1):
            if row > 0 and i != row:
                continue
            cards = []
            for it in s["items"]:
                hay = " ".join([it["id"], it["text"], it.get("punishment", ""), *it.get("notes", [])]).lower()
                if q in hay:
                    cards.append(it)
            if not cards:
                continue
            if row <= 0:
                h = QLabel(f"{s['id']}. {s['title']}")
                h.setObjectName("head")
                self.vbox.addWidget(h)
            for it in cards:
                self.vbox.addWidget(Card(it))
                found += 1
        if not found:
            e = QLabel("Ничего не найдено")
            e.setObjectName("empty")
            e.setAlignment(Qt.AlignCenter)
            self.vbox.addWidget(e)
        self.vbox.addStretch()

    def apply_window_settings(self):
        vis = self.isVisible()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(self.settings["on_top"]))
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

    def open_settings(self):
        SettingsDialog(self, self.settings, self.do_update, self.do_rollback).exec()

    def do_update(self):
        url = self.settings["update_url"]
        if not url:
            QMessageBox.information(self, APP_NAME, "Сначала укажите ссылку на JSON с базой.")
            return
        try:
            self.db = update_from_url(url)
            self.fill_sections()
            QMessageBox.information(self, APP_NAME, f"База обновлена до версии {self.db['version']}.")
        except Exception as e:
            QMessageBox.warning(self, APP_NAME, f"Не удалось обновить базу:\n{e}\n\nСтарая база сохранена.")

    def do_rollback(self):
        if not BACKUP_FILE.exists():
            QMessageBox.information(self, APP_NAME, "Резервной копии пока нет.")
            return
        shutil.copy(BACKUP_FILE, DB_FILE)
        self.db = load_json(DB_FILE, self.db)
        self.fill_sections()
        QMessageBox.information(self, APP_NAME, "База откачена к предыдущей версии.")


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
    app.setStyleSheet(STYLE)
    app.setWindowIcon(QIcon(str(res("icon.png"))))
    bridge = Bridge()
    win = MainWindow(settings, bridge)
    win.show()
    start_hotkey_listener(settings, bridge)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
