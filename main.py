import sys, traceback
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont
from ui.style import QSS


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setFont(QFont("Segoe UI", 10))
    from database import db
    from database.db import Catalog
    from security import license as L
    from admin.panel import open_admin
    from ui.activation import ActivationWindow
    from ui.main_window import MainWindow

    holder = {}

    def start_main(payload):
        holder["main"] = MainWindow(Catalog(), payload, open_admin)
        holder["main"].show()
        if "act" in holder:
            holder["act"].close()

    try:
        payload = L.check_saved()
    except L.LicenseError as e:
        payload = None
        reason = str(e)
    if payload:
        start_main(payload)
    else:
        win = ActivationWindow(open_admin)
        if reason and "не активировано" not in reason:
            win.msg(reason)
        win.activated.connect(start_main)
        holder["act"] = win
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        err = traceback.format_exc()
        try:
            from database.paths import appdata_dir
            (appdata_dir() / "error.log").write_text(err, encoding="utf-8")
        except Exception:
            pass
        raise
