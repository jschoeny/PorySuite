from PySide6.QtWidgets import QDialog
from ui.ui_plugininfo import Ui_PluginInfoDialog


class PluginInfoDialog(QDialog):
    def __init__(self, plugin_info: dict, parent=None):
        super().__init__(parent)

        self.ui = Ui_PluginInfoDialog()
        self.ui.setupUi(self)

        self.setWindowTitle(f"About {plugin_info["name"]}")
        self.__plugin_info = plugin_info

        self.__load_readme()

    def __load_readme(self):
        self.ui.readme.setMarkdown(self.__plugin_info["readme"])
