import os
import platformdirs

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QMovie
from PySide6.QtWidgets import QLabel, QMainWindow, QApplication

from app_info import APP_NAME, AUTHOR
from app_util import reveal_directory, condense_path
from newproject import NewProject
from ui.ui_projectselector import Ui_ProjectSelector


class ProjectSelector(QMainWindow):
    close_signal = Signal()

    def __init__(self, parent=None, projects=None):
        super().__init__(parent)
        self.ui = Ui_ProjectSelector()
        self.ui.setupUi(self)
        self.setWindowFlags(Qt.Window |
                            Qt.CustomizeWindowHint |
                            Qt.WindowTitleHint)
        self.projects = projects
        self.selected_index = -1
        movie = QMovie(":/images/PorySuite.gif")
        self.ui.label_icon.setMovie(movie)
        movie.start()
        # Sort projects by last opened
        if projects is not None:
            self.projects.sort(key=lambda x: x["last_opened"], reverse=True)
        for i, project in enumerate(projects):
            self.add_project(project["name"], project["dir"], i)

    def add_project(self, name: str, path: str, p_info_index: int):
        label = QLabel(self)
        label.setTextFormat(Qt.MarkdownText)
        label.setMargin(10)
        label.setCursor(QCursor(Qt.PointingHandCursor))
        label.setText(f"**[\u273b {name}](#)**    {condense_path(path)}")
        label.mousePressEvent = lambda _: self.select_project(p_info_index)
        self.ui.verticalLayout_projects.addWidget(label)

    def select_project(self, index: int):
        self.selected_index = index
        self.close()

    def new_project(self):
        self.selected_index = -2
        new_ui = NewProject(parent=self)
        new_ui.exec()
        if new_ui.project_info is not None:
            self.close()
        else:
            self.selected_index = -1

    @staticmethod
    def open_plugins_folder():
        data_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
        reveal_directory(os.path.join(data_dir, "plugins"))

    def close(self):
        self.close_signal.emit()
        if self.selected_index == -1:
            self.hide()
            super().close()
            self.destroy()
            QApplication.quit()
        else:
            super().close()
            self.destroy()

    def quit(self):
        self.selected_index = -1
        self.close()
