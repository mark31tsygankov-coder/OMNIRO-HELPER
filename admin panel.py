"""Секретная админ-панель: вход по логину и паролю, создание и учёт ключей."""
import json
import time
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
)

import licensing

PRESETS = [("1 день", 1), ("3 дня", 3), ("7 дней", 7), ("30 дней", 30), ("90 дней", 90), ("365 дней", 365)]


class SecretLabel(QLabel):
    """Надпись/иконка: 7 быстрых нажатий подряд (за 5 секунд) открывают вход администратора."""
    triggered = Signal()

    def __init__(self, text="", clicks=7, window=5.0):
        super().__init__(text)
        self._need, self._window, self._times = clicks, window, []

    def mousePressEvent(self, e):
        now = time.monotonic()
        self._times = [t for t in self._times if now - t < self._window] + [now]
        if len(self._times) >= self._need:
            self._times.clear()
            self.triggered.emit()
        super().mousePressEvent(e)


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.priv = None
        self.setWindowTitle("Вход")
        self.setFixedWidth(320)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)
        lay.addWidget(QLabel("Вход администратора"))
        self.login = QLineEdit()
        self.login.setPlaceholderText("Логин")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.returnPressed.connect(self.submit)
        self.err = QLabel("")
        self.err.setStyleSheet("color: #ff5555;")
        self.btn = QPushButton("Войти")
        self.btn.clicked.connect(self.submit)
        for w in (self.login, self.password, self.err, self.btn):
            lay.addWidget(w)

    def submit(self):
        self.btn.setEnabled(False)
        self.btn.setText("Проверяю…")
        QApplication.processEvents()
        priv = licensing.unlock_admin(self.login.text(), self.password.text())
        self.btn.setEnabled(True)
        self.btn.setText("Войти")
        if priv is None:
            self.err.setText("Неверный логин или пароль")
            self.password.clear()
            return
        self.priv = priv
        self.accept()


class AdminPanel(QDialog):
    def __init__(self, priv, data_dir, parent=None):
        super().__init__(parent)
        self.priv = priv
        self.path = Path(data_dir) / "issued_keys.json"
        self.own_key = None
        self.setWindowTitle("Админ-панель")
        self.resize(520, 600)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(8)

        t = QLabel("🔑 Создать ключ")
        t.setStyleSheet("font-size: 17px; font-weight: bold; color: #ff7a00;")
        lay.addWidget(t)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Название (ник игрока / кому)")
        lay.addWidget(self.name)

        row = QHBoxLayout()
        self.hwid = QLineEdit()
        self.hwid.setPlaceholderText("ID устройства XXXX-XXXX-XXXX")
        b_own = QPushButton("Этот ПК")
        b_own.clicked.connect(lambda: self.hwid.setText(licensing.get_hwid()))
        row.addWidget(self.hwid, 1)
        row.addWidget(b_own)
        lay.addLayout(row)

        row = QHBoxLayout()
        self.days = QSpinBox()
        self.days.setRange(1, 3650)
        self.days.setValue(30)
        self.days.setSuffix(" дн.")
        self.preset = QComboBox()
        for label, _ in PRESETS:
            self.preset.addItem(label)
        self.preset.setCurrentIndex(3)
        self.preset.currentIndexChanged.connect(lambda i: self.days.setValue(PRESETS[i][1]))
        row.addWidget(self.days, 1)
        row.addWidget(self.preset, 1)
        lay.addLayout(row)

        b_make = QPushButton("Создать ключ и скопировать")
        b_make.clicked.connect(self.create)
        lay.addWidget(b_make)
        self.out = QLineEdit()
        self.out.setReadOnly(True)
        self.out.setPlaceholderText("Здесь появится ключ")
        lay.addWidget(self.out)

        lay.addWidget(QLabel("Выданные ключи"))
        self.listw = QListWidget()
        lay.addWidget(self.listw, 1)
        row = QHBoxLayout()
        b_copy = QPushButton("Копировать ключ")
        b_copy.clicked.connect(self.copy_selected)
        b_del = QPushButton("Удалить из списка")
        b_del.clicked.connect(self.delete_selected)
        row.addWidget(b_copy)
        row.addWidget(b_del)
        lay.addLayout(row)
        note = QLabel("Срок ключа считается от момента создания. Ключ работает только на устройстве "
                      "с указанным ID. Досрочно отозвать ключ нельзя — выдавайте разумные сроки.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-size: 11px;")
        lay.addWidget(note)
        b_close = QPushButton("Закрыть")
        b_close.clicked.connect(self.accept)
        lay.addWidget(b_close)
        self.refresh()

    # ----- список -----
    def load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save(self, items):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    def refresh(self):
        self.listw.clear()
        now = time.time()
        for it in self.load():
            state = "активен" if it["expires"] > now else "истёк"
            date = time.strftime("%d.%m.%Y", time.localtime(it["expires"]))
            self.listw.addItem(f"{it['name']} · {it['hwid']} · до {date} · {state}")

    def create(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Админ-панель", "Впишите название.")
            return
        try:
            key, expires = licensing.make_key(self.priv, name, self.days.value(), self.hwid.text())
        except ValueError as e:
            QMessageBox.warning(self, "Админ-панель", str(e))
            return
        dev = licensing.norm_hwid(self.hwid.text())
        pretty = "-".join(dev[i:i + 4] for i in (0, 4, 8))
        items = self.load()
        items.append({"name": name, "hwid": pretty, "days": self.days.value(), "expires": expires, "key": key})
        self.save(items)
        self.out.setText(key)
        QApplication.clipboard().setText(key)
        if pretty == licensing.get_hwid():
            self.own_key = key
        self.refresh()

    def selected_index(self):
        i = self.listw.currentRow()
        return i if i >= 0 else None

    def copy_selected(self):
        i = self.selected_index()
        if i is not None:
            QApplication.clipboard().setText(self.load()[i]["key"])

    def delete_selected(self):
        i = self.selected_index()
        if i is None:
            return
        if QMessageBox.question(self, "Админ-панель", "Удалить запись? Сам ключ продолжит работать до конца срока.") \
                == QMessageBox.Yes:
            items = self.load()
            del items[i]
            self.save(items)
            self.refresh()
