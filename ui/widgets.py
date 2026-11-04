import time
from collections import deque
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QSize, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QFont, QBrush
from PySide6.QtWidgets import (QFrame, QLabel, QVBoxLayout, QWidget, QGridLayout,
                               QGraphicsOpacityEffect)
from database.paths import data_sources

PALETTE = [("#ff3d6e", "#6a1030"), ("#ff8a3d", "#5a2a10"), ("#8a5cff", "#2a1a5a"),
           ("#2dd4bf", "#0f3a35"), ("#3d8bff", "#10285a"), ("#e0c341", "#4a3f10")]


def fade_in(w, ms=280):
    eff = QGraphicsOpacityEffect(w)
    w.setGraphicsEffect(eff)
    a = QPropertyAnimation(eff, b"opacity", w)
    a.setDuration(ms)
    a.setStartValue(0.0)
    a.setEndValue(1.0)
    a.setEasingCurve(QEasingCurve.OutCubic)
    a.finished.connect(lambda: w.setGraphicsEffect(None))
    a.start()
    w._fade = a


class ClickCounter:
    """N быстрых кликов за T секунд."""
    def __init__(self, n=7, seconds=5.0):
        self.n, self.seconds, self.t = n, seconds, deque(maxlen=n)

    def hit(self) -> bool:
        now = time.monotonic()
        self.t.append(now)
        if len(self.t) == self.n and now - self.t[0] <= self.seconds:
            self.t.clear()
            return True
        return False


class ClickLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, e):
        self.clicked.emit()
        super().mousePressEvent(e)


def find_image(name):
    if not name:
        return None
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    for folder in data_sources():
        for cand in (Path(folder) / name, Path(folder) / "images" / name):
            if cand.exists():
                return cand
    return None


def make_pixmap(item, icon, w, h, idx=0):
    """Картинка из файла либо градиентная обложка с эмодзи раздела."""
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    src = find_image(item.get("image"))
    if src:
        img = QPixmap(str(src))
        if not img.isNull():
            p.fillRect(0, 0, w, h, QColor("#101013"))
            img = img.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.drawPixmap((w - img.width()) // 2, (h - img.height()) // 2, img)
            p.end()
            return pm
    c1, c2 = PALETTE[(hash(item.get("id", "")) + idx) % len(PALETTE)]
    g = QLinearGradient(0, 0, w, h)
    g.setColorAt(0, QColor(c2))
    g.setColorAt(1, QColor("#0e0e11"))
    p.fillRect(0, 0, w, h, QBrush(g))
    p.setPen(QColor(c1))
    f = QFont("Segoe UI Emoji")
    f.setPixelSize(int(h * 0.5))
    p.setFont(f)
    p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, icon or "📦")
    p.end()
    return pm


class Card(QFrame):
    clicked = Signal()

    def __init__(self, title, subtitle, pixmap, w=230, h=232):
        super().__init__()
        self.setObjectName("card")
        self.setFixedSize(w, h)
        self.setCursor(Qt.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 10, 10, 12)
        lay.setSpacing(6)
        im = QLabel()
        im.setPixmap(pixmap)
        im.setFixedSize(pixmap.size())
        lay.addWidget(im, alignment=Qt.AlignHCenter)
        t = QLabel(title)
        t.setWordWrap(True)
        t.setStyleSheet("font-weight:700;font-size:14px;")
        s = QLabel(subtitle)
        s.setObjectName("muted")
        s.setWordWrap(True)
        lay.addWidget(t)
        lay.addWidget(s)
        lay.addStretch()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class CardGrid(QWidget):
    """Сетка, которая сама перестраивается под ширину окна."""
    def __init__(self, cell=246):
        super().__init__()
        self.cell, self.cards = cell, []
        self.grid = QGridLayout(self)
        self.grid.setSpacing(14)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self._cols = 0

    def set_cards(self, cards):
        for c in self.cards:
            c.setParent(None)
            c.deleteLater()
        self.cards = cards
        self._cols = 0
        self._layout()

    def _layout(self):
        cols = max(1, self.width() // self.cell)
        if cols == self._cols and self.grid.count() == len(self.cards):
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        for i, c in enumerate(self.cards):
            self.grid.addWidget(c, i // cols, i % cols, Qt.AlignTop | Qt.AlignLeft)
        self.grid.setColumnStretch(cols, 1)

    def resizeEvent(self, e):
        self._layout()
        super().resizeEvent(e)
