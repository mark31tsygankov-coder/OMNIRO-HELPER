from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
                               QScrollArea, QPushButton, QDialog, QTableWidget, QTableWidgetItem,
                               QHeaderView, QFrame, QTextEdit, QFileDialog, QMessageBox)
from database import db
from database.paths import user_data_dir
from .widgets import Card, CardGrid, make_pixmap, fade_in


def scrolled(inner):
    sc = QScrollArea()
    sc.setWidgetResizable(True)
    sc.setWidget(inner)
    return sc


class ItemDialog(QDialog):
    def __init__(self, parent, sid, sec, item):
        super().__init__(parent)
        self.setWindowTitle(item.get("name", ""))
        self.resize(620, 640)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(10)
        im = QLabel()
        im.setPixmap(make_pixmap(item, sec.get("icon"), 576, 220))
        lay.addWidget(im)
        t = QLabel(item.get("name", ""))
        t.setObjectName("h1")
        t.setWordWrap(True)
        lay.addWidget(t)
        meta = " · ".join(x for x in [sec.get("title"), item.get("category"), item.get("price")] if x)
        m = QLabel(meta)
        m.setObjectName("accent")
        m.setWordWrap(True)
        lay.addWidget(m)
        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(item.get("description", "Описание уточняется."))
        lay.addWidget(body, 2)
        stats = item.get("stats") or {}
        if stats:
            tb = QTableWidget(len(stats), 2)
            tb.setHorizontalHeaderLabels(["Параметр", "Значение"])
            tb.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tb.verticalHeader().hide()
            tb.setEditTriggers(QTableWidget.NoEditTriggers)
            for r, (k, v) in enumerate(stats.items()):
                tb.setItem(r, 0, QTableWidgetItem(str(k)))
                tb.setItem(r, 1, QTableWidgetItem(str(v)))
            lay.addWidget(tb, 1)
        extra = [x for x in [item.get("note"), ("Источник: " + item["source"]) if item.get("source") else None] if x]
        if extra:
            n = QLabel("\n".join(extra))
            n.setObjectName("muted")
            n.setWordWrap(True)
            lay.addWidget(n)
        b = QPushButton("Закрыть")
        b.clicked.connect(self.accept)
        lay.addWidget(b)


class HomePage(QWidget):
    open_section = Signal(str)
    open_item = Signal(str, str)

    def __init__(self, catalog):
        super().__init__()
        self.catalog = catalog
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        h = QLabel("Справочник RADMIR CRMP")
        h.setObjectName("h1")
        lay.addWidget(h)
        self.grid = CardGrid(cell=266)
        lay.addWidget(self.grid)
        self.hist_title = QLabel("Вы смотрели")
        self.hist_title.setObjectName("h2")
        lay.addWidget(self.hist_title)
        self.hist = CardGrid(cell=246)
        lay.addWidget(self.hist)
        lay.addStretch()

    def refresh(self):
        cards = []
        for i, (sid, sec) in enumerate(self.catalog.ordered()):
            c = Card(f"{sec.get('icon', '')}  {sec.get('title', sid)}",
                     f"{len(sec['items'])} карточек", make_pixmap({"id": sid}, sec.get("icon"), 246, 110, i),
                     w=266, h=206)
            c.clicked.connect(lambda s=sid: self.open_section.emit(s))
            cards.append(c)
        self.grid.set_cards(cards)
        hc = []
        for sid, iid in db.recent_history():
            it = self.catalog.get_item(sid, iid)
            if it:
                sec = self.catalog.sections[sid]
                c = Card(it.get("name", ""), sec.get("title", ""), make_pixmap(it, sec.get("icon"), 210, 96))
                c.clicked.connect(lambda s=sid, i=iid: self.open_item.emit(s, i))
                hc.append(c)
        self.hist.set_cards(hc)
        self.hist_title.setVisible(bool(hc))
        self.hist.setVisible(bool(hc))


class SectionPage(QWidget):
    open_item = Signal(str, str)

    def __init__(self, catalog):
        super().__init__()
        self.catalog, self.sid = catalog, None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.desc = QLabel()
        self.desc.setObjectName("muted")
        self.desc.setWordWrap(True)
        self.meta = QLabel()
        self.meta.setObjectName("muted")
        row = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Фильтр в разделе…")
        self.cat = QComboBox()
        row.addWidget(self.filter, 1)
        row.addWidget(self.cat)
        self.grid = CardGrid()
        self.faq_box = QVBoxLayout()
        self.faq_box.setSpacing(8)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.grid)
        hl.addLayout(self.faq_box)
        hl.addStretch()
        for w in (self.title, self.desc, self.meta):
            lay.addWidget(w)
        lay.addLayout(row)
        lay.addWidget(scrolled(holder), 1)
        self.filter.textChanged.connect(self.render)
        self.cat.currentIndexChanged.connect(self.render)

    def show_section(self, sid):
        self.sid = sid
        sec = self.catalog.sections[sid]
        self.title.setText(f"{sec.get('icon', '')}  {sec.get('title', sid)}")
        self.desc.setText(sec.get("description", ""))
        self.meta.setText(f"Обновлено: {sec.get('updated', 'неизвестно')} · Источник: {sec.get('source', 'не указан')}")
        self.cat.blockSignals(True)
        self.cat.clear()
        self.cat.addItem("Все категории")
        cats = sorted({i.get("category") for i in sec["items"] if i.get("category")})
        self.cat.addItems(cats)
        self.cat.blockSignals(False)
        self.filter.blockSignals(True)
        self.filter.clear()
        self.filter.blockSignals(False)
        self.render()

    def render(self):
        sec = self.catalog.sections[self.sid]
        q = self.filter.text().lower().split()
        cat = self.cat.currentText() if self.cat.currentIndex() > 0 else None
        items = [i for i in sec["items"]
                 if (not cat or i.get("category") == cat)
                 and all(t in (str(i.get("name", "")) + str(i.get("description", "")) + " ".join(i.get("tags", []))).lower() for t in q)]
        while self.faq_box.count():
            w = self.faq_box.takeAt(0).widget()
            if w:
                w.deleteLater()
        if sec.get("layout") == "faq":
            self.grid.set_cards([])
            for it in items:
                self.faq_box.addWidget(FaqItem(it))
            return
        cards = []
        for n, it in enumerate(items):
            c = Card(it.get("name", ""), " · ".join(x for x in [it.get("category"), it.get("price")] if x),
                     make_pixmap(it, sec.get("icon"), 210, 120, n))
            c.clicked.connect(lambda i=it.get("id"): self.open_item.emit(self.sid, i))
            cards.append(c)
        self.grid.set_cards(cards)


class FaqItem(QFrame):
    def __init__(self, it):
        super().__init__()
        self.setObjectName("panel")
        lay = QVBoxLayout(self)
        self.btn = QPushButton("＋  " + it.get("name", ""))
        self.btn.setStyleSheet("text-align:left;border:none;font-size:14px;")
        self.ans = QLabel(it.get("description", ""))
        self.ans.setWordWrap(True)
        self.ans.setObjectName("muted")
        self.ans.hide()
        lay.addWidget(self.btn)
        lay.addWidget(self.ans)
        self.btn.clicked.connect(self.toggle)
        self.q = it.get("name", "")

    def toggle(self):
        v = not self.ans.isVisible()
        self.ans.setVisible(v)
        self.btn.setText(("－  " if v else "＋  ") + self.q)
        if v:
            fade_in(self.ans, 220)


class SearchPage(QWidget):
    open_item = Signal(str, str)

    def __init__(self, catalog):
        super().__init__()
        self.catalog = catalog
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        self.title = QLabel("Поиск")
        self.title.setObjectName("h1")
        self.info = QLabel()
        self.info.setObjectName("muted")
        self.grid = CardGrid()
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.grid)
        hl.addStretch()
        lay.addWidget(self.title)
        lay.addWidget(self.info)
        lay.addWidget(scrolled(holder), 1)

    def run(self, q):
        res = self.catalog.search(q)
        self.info.setText(f"Найдено: {len(res)} по запросу «{q}»" if res else f"По запросу «{q}» ничего не найдено. Попробуйте другое слово.")
        cards = []
        for n, (sid, it) in enumerate(res):
            sec = self.catalog.sections[sid]
            c = Card(it.get("name", ""), f"{sec.get('title', '')} · {it.get('category', '')}",
                     make_pixmap(it, sec.get("icon"), 210, 120, n))
            c.clicked.connect(lambda s=sid, i=it.get("id"): self.open_item.emit(s, i))
            cards.append(c)
        self.grid.set_cards(cards)


class SettingsPage(QWidget):
    reloaded = Signal()

    def __init__(self, catalog, license_info):
        super().__init__()
        self.catalog = catalog
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        h = QLabel("Настройки")
        h.setObjectName("h1")
        lay.addWidget(h)
        self.lic = QLabel(license_info)
        self.lic.setObjectName("muted")
        lay.addWidget(self.lic)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("muted")
        for text, fn in (("Импорт JSON в базу…", self.import_json),
                         ("Открыть папку данных", self.open_folder),
                         ("Обновить базу", self.reload)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            lay.addWidget(b)
        lay.addWidget(self.status)
        lay.addStretch()

    def import_json(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите JSON", "", "JSON (*.json)")
        ok, bad = [], []
        for f in files:
            try:
                ok.append(self.catalog.import_file(f))
            except Exception as e:
                bad.append(f"{f.split('/')[-1]}: {e}")
        msg = (f"Импортировано разделов: {len(ok)}. " if ok else "") + ("Ошибки:\n" + "\n".join(bad) if bad else "")
        self.status.setText(msg or "Файлы не выбраны.")
        if ok:
            self.reloaded.emit()

    def open_folder(self):
        import os
        p = str(user_data_dir())
        try:
            os.startfile(p)  # Windows
        except Exception:
            self.status.setText("Папка данных: " + p)

    def reload(self):
        self.catalog.load()
        self.status.setText("База обновлена." + (("\nПропущены файлы с ошибками:\n" + "\n".join(self.catalog.errors)) if self.catalog.errors else ""))
        self.reloaded.emit()
