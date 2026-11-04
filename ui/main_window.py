from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap, QShortcut, QKeySequence, QIcon
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit,
                               QPushButton, QStackedWidget, QButtonGroup, QMessageBox)
from database import db
from database.paths import asset
from .pages import HomePage, SectionPage, SearchPage, SettingsPage, ItemDialog
from .widgets import ClickLabel, ClickCounter, fade_in


class MainWindow(QMainWindow):
    def __init__(self, catalog, payload, open_admin):
        super().__init__()
        self.catalog, self.open_admin = catalog, open_admin
        self.setWindowTitle("OMNIRO HELPER")
        self.setWindowIcon(QIcon(str(asset("icon.png"))))
        w, h = db.get_setting("win_size", [1280, 800])
        self.resize(w, h)
        self.setMinimumSize(900, 600)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QHBoxLayout()
        top.setContentsMargins(18, 12, 18, 12)
        self.logo = ClickLabel()
        self.logo.setPixmap(QPixmap(str(asset("icon.png"))).scaled(34, 34, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo.setToolTip("OMNIRO HELPER")
        name = QLabel("OMNIRO HELPER")
        name.setObjectName("h2")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по всем разделам: предмет, машина… (Ctrl+K)")
        self.bolt = ClickLabel("⚡")
        self.bolt.setStyleSheet("font-size:22px;color:#ff3d6e;padding:0 8px;")
        self.bolt.setCursor(Qt.PointingHandCursor)
        self.counter = ClickCounter(7, 5.0)
        self.bolt.clicked.connect(lambda: self.open_admin(self) if self.counter.hit() else None)
        top.addWidget(self.logo)
        top.addWidget(name)
        top.addSpacing(16)
        top.addWidget(self.search, 1)
        top.addWidget(self.bolt)
        outer.addLayout(top)

        body = QHBoxLayout()
        body.setSpacing(0)
        side = QWidget()
        side.setFixedWidth(210)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 6, 12, 12)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.nav = {}
        self._add_nav(sl, "home", "🏁  Главная")
        self.nav_box = QVBoxLayout()
        sl.addLayout(self.nav_box)
        sl.addStretch()
        self._add_nav(sl, "settings", "⚙  Настройки")
        body.addWidget(side)

        self.stack = QStackedWidget()
        self.home = HomePage(catalog)
        self.section = SectionPage(catalog)
        self.results = SearchPage(catalog)
        self.settings = SettingsPage(catalog, f"Лицензия: «{payload['n']}», действует до {self._fmt(payload['e'])}")
        for p in (self.home, self.section, self.results, self.settings):
            self.stack.addWidget(p)
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        self.home.open_section.connect(self.go_section)
        self.home.open_item.connect(self.show_item)
        self.section.open_item.connect(self.show_item)
        self.results.open_item.connect(self.show_item)
        self.settings.reloaded.connect(self.rebuild)
        self.search.returnPressed.connect(self.do_search)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.do_search)
        self.search.textChanged.connect(lambda: self._timer.start(350))
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self.search.setFocus)
        self.rebuild()
        self.go("home")
        if catalog.errors:
            QMessageBox.warning(self, "Файлы с ошибками", "Пропущены:\n" + "\n".join(catalog.errors))

    @staticmethod
    def _fmt(ts):
        import time
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(ts))

    def _add_nav(self, layout, key, text):
        b = QPushButton(text)
        b.setObjectName("nav")
        b.setCheckable(True)
        b.setCursor(Qt.PointingHandCursor)
        self.group.addButton(b)
        self.nav[key] = b
        b.clicked.connect(lambda: self.go(key) if key in ("home", "settings") else self.go_section(key))
        layout.addWidget(b)

    def rebuild(self):
        while self.nav_box.count():
            w = self.nav_box.takeAt(0).widget()
            if w:
                self.group.removeButton(w)
                w.deleteLater()
        for k in [k for k in self.nav if k not in ("home", "settings")]:
            self.nav.pop(k)
        for sid, sec in self.catalog.ordered():
            self._add_nav(self.nav_box, sid, f"{sec.get('icon', '')}  {sec.get('title', sid)}")
        self.home.refresh()
        if self.stack.currentWidget() is self.section and self.section.sid in self.catalog.sections:
            self.section.show_section(self.section.sid)

    def go(self, key):
        page = {"home": self.home, "settings": self.settings}[key]
        if key == "home":
            self.home.refresh()
        self.nav[key].setChecked(True)
        self.stack.setCurrentWidget(page)
        fade_in(page)

    def go_section(self, sid):
        if sid not in self.catalog.sections:
            return
        self.section.show_section(sid)
        if sid in self.nav:
            self.nav[sid].setChecked(True)
        self.stack.setCurrentWidget(self.section)
        fade_in(self.section)

    def do_search(self):
        q = self.search.text().strip()
        if not q:
            return
        self.group.setExclusive(False)
        for b in self.group.buttons():
            b.setChecked(False)
        self.group.setExclusive(True)
        self.results.run(q)
        if self.stack.currentWidget() is not self.results:
            self.stack.setCurrentWidget(self.results)
            fade_in(self.results)

    def show_item(self, sid, iid):
        it = self.catalog.get_item(sid, iid)
        if not it:
            return
        db.add_history(sid, iid)
        ItemDialog(self, sid, self.catalog.sections[sid], it).exec()

    def closeEvent(self, e):
        db.set_setting("win_size", [self.width(), self.height()])
        super().closeEvent(e)
