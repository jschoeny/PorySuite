from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog

import mainwindow
from app_util import reveal_directory
from ui.ui_exporting import Ui_Exporting


class Exporting(QDialog):
    logSignal = Signal(str)

    def __init__(self, parent: mainwindow = None):
        super().__init__(parent)
        self.parent = parent
        self.ui = Ui_Exporting()
        self.ui.setupUi(self)
        self.logSignal.connect(self.log)
        self.progress = 0.0

    def log(self, message):
        if message.startswith("Exported ROM:"):
            rom_dir = message[len("Exported ROM:"):].strip()
            try:
                reveal_directory(rom_dir, is_file=True)
            except FileNotFoundError:
                self.parent.log(f"Could not find file: {rom_dir}")
            self.close()
        elif message.startswith("cd build"):
            self.progress = 80
            self.ui.progressBar.setValue(80)
        try:
            self.ui.progressBar.setValue(int(message))
            self.progress = int(message)
        except ValueError:
            self.progress += 0.002
            self.ui.progressBar.setValue(int(self.progress))
            self.parent.log(message)
