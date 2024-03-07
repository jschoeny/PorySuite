from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QApplication

from ui.ui_loadingproject import Ui_LoadingProject


class LoadingProject(QDialog):
    progress = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_LoadingProject()
        self.ui.setupUi(self)
        self.progress.connect(self.update_progress)

    def update_progress(self, progress: int):
        self.ui.progressBar.setValue(progress)
        self.ui.progressBar.update()
        QApplication.processEvents()
