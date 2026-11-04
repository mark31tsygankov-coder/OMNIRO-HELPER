import time
from datetime import datetime
from PySide6.QtCore import Qt, QDateTime
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSpinBox, QCheckBox, QDateTimeEdit, QTableWidget, QTableWidgetItem,
                               QHeaderView, QTextEdit, QMessageBox, QFileDialog, QApplication)
import json
from database import db
from security import license as L
from security.device import get_device_id


class AdminLogin(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Вход администратора")
        self.setFixedSize(380, 290)
        self.priv = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 24, 26, 24)
        t = QLabel("Админ-панель")
        t.setObjectName("h1")
        lay.addWidget(t)
        self.login = QLineEdit(L.ADMIN_LOGIN)
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.Password)
        self.pw.setPlaceholderText("Пароль")
        self.pw.returnPressed.connect(self.go)
        lay.addWidget(self.login)
        lay.addWidget(self.pw)
        self.err = QLabel("")
        self.err.setStyleSheet("color:#ff6b86;")
        self.err.setWordWrap(True)
        lay.addWidget(self.err)
        b = QPushButton("Войти")
        b.setObjectName("primary")
        b.clicked.connect(self.go)
        lay.addWidget(b)
        self.pw.setFocus()

    def go(self):
        self.err.setText("Проверка…")
        QApplication.processEvents()
        try:
            self.priv = L.admin_login(self.login.text(), self.pw.text())
            self.accept()
        except L.LicenseError as e:
            self.err.setText(str(e))
            self.pw.clear()


class AdminPanel(QDialog):
    def __init__(self, priv, parent=None):
        super().__init__(parent)
        self.priv = priv
        self.setWindowTitle("OMNIRO HELPER — админ-панель")
        self.resize(900, 700)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(10)
        h = QLabel("Лицензионные ключи")
        h.setObjectName("h1")
        lay.addWidget(h)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Название ключа (например: Иван, друг)")
        lay.addWidget(self.name)
        r = QHBoxLayout()
        self.dev = QLineEdit()
        self.dev.setPlaceholderText("ID устройства (пусто = любой ПК)")
        me = QPushButton("Этот ПК")
        me.clicked.connect(lambda: self.dev.setText(get_device_id()))
        r.addWidget(self.dev, 1)
        r.addWidget(me)
        lay.addLayout(r)
        r2 = QHBoxLayout()
        self.days = QSpinBox()
        self.days.setRange(1, 365)
        self.days.setValue(30)
        self.days.setSuffix(" дн.")
        self.custom = QCheckBox("Произвольный срок:")
        self.until = QDateTimeEdit(QDateTime.currentDateTime().addDays(400))
        self.until.setCalendarPopup(True)
        self.until.setEnabled(False)
        self.custom.toggled.connect(self.until.setEnabled)
        self.custom.toggled.connect(lambda v: self.days.setEnabled(not v))
        r2.addWidget(QLabel("Срок:"))
        r2.addWidget(self.days)
        r2.addSpacing(12)
        r2.addWidget(self.custom)
        r2.addWidget(self.until)
        r2.addStretch()
        lay.addLayout(r2)
        mk = QPushButton("Создать ключ")
        mk.setObjectName("primary")
        mk.clicked.connect(self.create)
        lay.addWidget(mk)
        self.out = QTextEdit()
        self.out.setReadOnly(True)
        self.out.setFixedHeight(80)
        self.out.setPlaceholderText("Здесь появится созданный ключ")
        lay.addWidget(self.out)
        cp = QPushButton("Копировать созданный ключ")
        cp.clicked.connect(lambda: QGuiApplication.clipboard().setText(self.out.toPlainText()))
        lay.addWidget(cp)

        self.tb = QTableWidget(0, 5)
        self.tb.setHorizontalHeaderLabels(["Название", "Устройство", "Действует до", "Статус", "ID"])
        self.tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tb.verticalHeader().hide()
        self.tb.setSelectionBehavior(QTableWidget.SelectRows)
        self.tb.setEditTriggers(QTableWidget.NoEditTriggers)
        lay.addWidget(self.tb, 1)
        r3 = QHBoxLayout()
        for text, fn, obj in (("Копировать ключ", self.copy_sel, ""), ("Отозвать", self.revoke, "danger"),
                              ("Удалить", self.delete, "danger"), ("Экспорт revoked.json", self.export_revoked, "")):
            b = QPushButton(text)
            if obj:
                b.setObjectName(obj)
            b.clicked.connect(fn)
            r3.addWidget(b)
        lay.addLayout(r3)
        note = QLabel("Отзыв действует на ПК пользователей после того, как файл revoked.json попадёт в их папку данных "
                      "(или в сборку). Без сервера мгновенный отзыв невозможен.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        lay.addWidget(note)
        self.records = []
        self.refresh()

    def refresh(self):
        self.records = db.list_issued()
        self.tb.setRowCount(len(self.records))
        for r, rec in enumerate(self.records):
            vals = [rec["name"], rec["device"], datetime.fromtimestamp(rec["expires"]).strftime("%d.%m.%Y %H:%M"),
                    L.status_of(rec), rec["id"]]
            for c, v in enumerate(vals):
                self.tb.setItem(r, c, QTableWidgetItem(v if v != "*" else "любой ПК"))

    def selected(self):
        r = self.tb.currentRow()
        return self.records[r] if 0 <= r < len(self.records) else None

    def create(self):
        try:
            dev = self.dev.text().strip()
            if dev and len(dev) < 10:
                raise L.LicenseError("ID устройства выглядит неполным.")
            exp = self.until.dateTime().toSecsSinceEpoch() if self.custom.isChecked() else None
            key, p = L.create_key(self.priv, self.name.text(), dev, days=self.days.value(), expires_ts=exp)
        except L.LicenseError as e:
            return QMessageBox.warning(self, "Ошибка", str(e))
        db.add_issued({"id": p["id"], "name": p["n"], "device": p["d"], "created": p["c"], "expires": p["e"], "key": key})
        self.out.setPlainText(key)
        QGuiApplication.clipboard().setText(key)
        self.refresh()

    def copy_sel(self):
        s = self.selected()
        if s:
            QGuiApplication.clipboard().setText(s["key"])

    def revoke(self):
        s = self.selected()
        if s:
            db.set_revoked(s["id"], True)
            self.refresh()

    def delete(self):
        s = self.selected()
        if s and QMessageBox.question(self, "Удалить", f"Удалить ключ «{s['name']}» из списка?") == QMessageBox.Yes:
            db.delete_issued(s["id"])
            self.refresh()

    def export_revoked(self):
        ids = [r["id"] for r in db.list_issued() if r["revoked"]]
        f, _ = QFileDialog.getSaveFileName(self, "Сохранить", "revoked.json", "JSON (*.json)")
        if f:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump({"revoked": ids}, fh)
            # сразу применяем и на этом ПК
            from database.paths import user_data_dir
            (user_data_dir() / "revoked.json").write_text(json.dumps({"revoked": ids}), encoding="utf-8")


def open_admin(parent=None):
    dlg = AdminLogin(parent)
    if dlg.exec() == QDialog.Accepted and dlg.priv:
        AdminPanel(dlg.priv, parent).exec()
