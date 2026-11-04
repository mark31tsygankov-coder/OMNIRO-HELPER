from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QIcon, QGuiApplication
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFrame
from database.paths import asset
from security import license as L
from security.device import get_device_id
from .widgets import ClickLabel, ClickCounter, fade_in


class ActivationWindow(QWidget):
    activated = Signal(dict)

    def __init__(self, open_admin):
        super().__init__()
        self.open_admin = open_admin
        self.setWindowTitle("OMNIRO HELPER — активация")
        self.setWindowIcon(QIcon(str(asset("icon.png"))))
        self.setObjectName("root")
        self.setFixedSize(520, 640)
        self.counter = ClickCounter(7, 5.0)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 30, 36, 30)
        lay.setSpacing(12)
        logo = QLabel()
        logo.setPixmap(QPixmap(str(asset("icon.png"))).scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        lay.addWidget(logo, alignment=Qt.AlignHCenter)
        self.title = ClickLabel("OMNIRO HELPER")
        self.title.setObjectName("h1")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.clicked.connect(lambda: self.open_admin(self) if self.counter.hit() else None)
        lay.addWidget(self.title)
        sub = QLabel("Премиальный справочник RADMIR CRMP\nВведите лицензионный ключ для активации")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        lay.addSpacing(8)
        lay.addWidget(self._lbl("ID вашего устройства"))
        row = QHBoxLayout()
        self.dev = QLineEdit(get_device_id())
        self.dev.setReadOnly(True)
        cp = QPushButton("Копировать")
        cp.clicked.connect(lambda: (QGuiApplication.clipboard().setText(self.dev.text()), self.msg("ID устройства скопирован.", ok=True)))
        row.addWidget(self.dev, 1)
        row.addWidget(cp)
        lay.addLayout(row)
        lay.addWidget(self._lbl("Лицензионный ключ"))
        self.key = QLineEdit()
        self.key.setPlaceholderText("OH1-…")
        self.key.returnPressed.connect(self.activate)
        lay.addWidget(self.key)
        btn = QPushButton("Активировать")
        btn.setObjectName("primary")
        btn.setMinimumHeight(44)
        btn.clicked.connect(self.activate)
        lay.addWidget(btn)
        self.out = QLabel("")
        self.out.setWordWrap(True)
        self.out.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.out)
        lay.addStretch()
        hint = QLabel("Отправьте ID устройства владельцу, чтобы получить ключ.")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignCenter)
        lay.addWidget(hint)
        fade_in(self, 450)

    @staticmethod
    def _lbl(t):
        l = QLabel(t)
        l.setObjectName("muted")
        return l

    def msg(self, text, ok=False):
        self.out.setStyleSheet(f"color:{'#3ddc97' if ok else '#ff6b86'};font-weight:600;")
        self.out.setText(text)

    def activate(self):
        k = self.key.text().strip()
        if not k:
            return self.msg("Введите ключ.")
        try:
            p = L.verify_key(k)
        except L.LicenseError as e:
            return self.msg(str(e))
        except Exception as e:
            return self.msg(f"Непредвиденная ошибка: {e}")
        L.save_activation(k)
        self.activated.emit(p)
