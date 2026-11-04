ACCENT = "#ff3d6e"
QSS = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; color: #f2f2f4; }
QMainWindow, QDialog, QWidget#root { background: #0b0b0d; }
QWidget { background: transparent; }
QFrame#card { background: #17171a; border: 1px solid #26262b; border-radius: 16px; }
QFrame#card:hover { border: 1px solid #ff3d6e; background: #1c1c20; }
QFrame#panel { background: #131316; border: 1px solid #26262b; border-radius: 14px; }
QLabel#h1 { font-size: 26px; font-weight: 800; }
QLabel#h2 { font-size: 18px; font-weight: 700; }
QLabel#muted { color: #8b8b94; }
QLabel#accent { color: #ff3d6e; font-weight: 700; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDateTimeEdit {
  background: #131316; border: 1px solid #2a2a30; border-radius: 12px; padding: 9px 12px;
  selection-background-color: #ff3d6e; }
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #ff3d6e; }
QComboBox QAbstractItemView { background: #17171a; selection-background-color: #ff3d6e; border: 1px solid #2a2a30; }
QPushButton { background: #1c1c20; border: 1px solid #2a2a30; border-radius: 12px; padding: 9px 16px; font-weight: 600; }
QPushButton:hover { border: 1px solid #ff3d6e; }
QPushButton#primary { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #ff3d6e, stop:1 #ff6a4d); border: none; }
QPushButton#primary:hover { background: #ff5580; }
QPushButton#danger { background: #3a1018; border: 1px solid #7a1f33; }
QPushButton#nav { text-align: left; background: transparent; border: none; padding: 11px 14px; font-size: 14px; }
QPushButton#nav:hover { background: #1c1c20; }
QPushButton#nav:checked { background: #2a1119; color: #ff3d6e; }
QScrollArea { border: none; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #2e2e35; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QTableWidget { background: #131316; border: 1px solid #26262b; border-radius: 12px; gridline-color: #232328; }
QHeaderView::section { background: #1a1a1e; border: none; padding: 8px; color: #8b8b94; }
QTableWidget::item:selected { background: #3a1522; }
QToolTip { background: #17171a; border: 1px solid #ff3d6e; }
"""
