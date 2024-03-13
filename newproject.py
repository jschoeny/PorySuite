import os
import json
import string
import datetime
import shutil
import threading
import platformdirs
from unidecode import unidecode

from PySide6.QtWidgets import QDialog, QFileDialog, QListWidgetItem, QApplication
from PySide6.QtCore import Signal, Qt

import pluginmanager
from app_info import APP_NAME, AUTHOR
from app_util import reveal_directory
from docker_integration import DockerUtil
from plugininfodialog import PluginInfoDialog
from ui.ui_newproject import Ui_NewProject

SETUP_LOG_FINISH = "*** SETUP COMPLETE ***"

SETUP_STEPS = [
    "Cloning into",
    "Installing agbcc",
    "cc",
    "arm-none-eabi-as",
    "/usr/lib/gcc/arm-none-eabi",
    "tools/mapjson/mapjson",
    "tools/aif2pcm/aif2pcm",
    "tools/mid2agb/mid2agb",
    "tools/gbafix/gbafix",
    "Processing game data",
    None
]


def format_project_name(name):
    keep_characters = (' ', '.', '_')
    name = "".join(c for c in name if c.isalnum() or c in keep_characters).strip().lower().replace(" ", "_")
    name = unidecode(name)
    return name


class NewProject(QDialog):
    logSignal = Signal(str)

    def __init__(self, parent=None, cancel_quits=False):
        super().__init__(parent)
        self.ui = Ui_NewProject()
        self.ui.setupUi(self)
        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).setEnabled(False)
        self.ui.projectDirFull.setText("")
        self.ui.errorLabel.setVisible(False)
        self.logSignal.connect(self.log)
        self.currStep = 0
        self.ui.progressBar.setMaximum(len(SETUP_STEPS) * 1000)
        self.project_info = None
        self.project_dir = None
        self.base_project_dir = None
        self.cancel_quits = cancel_quits
        self.plugins = None
        self.add_plugins()
        self.selected_plugin = None
        self.error_encountered = False

    def add_plugins(self):
        self.plugins = pluginmanager.get_plugins_info()
        self.ui.pluginsList.clear()
        if len(self.plugins) == 0:
            self.ui.pluginsList.addItem(QListWidgetItem("No plugins found."))
        else:
            self.ui.pluginsList.addItem(QListWidgetItem("Choose one..."))
            for plugin in self.plugins:
                item = QListWidgetItem(f"{plugin["name"]} | v{plugin["version"]}")
                item.setData(Qt.UserRole, (plugin["identifier"], plugin["version"]))
                self.ui.pluginsList.addItem(item)
        self.ui.pluginsList.setCurrentRow(0)

    def open(self):
        super().open()
        origin = self.sender()
        if origin == self.ui.locationButton:
            file_dialog = QFileDialog(self)
            file_dialog.setFileMode(QFileDialog.FileMode.Directory)
            file_dialog.setOption(QFileDialog.Option.ShowDirsOnly)
            file_dialog.exec()
            self.base_project_dir = os.path.normpath(file_dialog.selectedFiles()[0])
            project_dir = os.path.join(self.base_project_dir, format_project_name(self.ui.projectName.text()))
            self.ui.projectDir.setText(self.base_project_dir)
            self.ui.projectDirFull.setText(project_dir)
            if os.path.exists(project_dir) and self.ui.projectName.text() != "":
                self.ui.errorLabel.setText("A directory with this name already exists at this location")
                self.ui.errorLabel.setVisible(True)
                self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).setEnabled(False)
                return
            else:
                self.ui.errorLabel.setVisible(False)
                if self.ui.projectName.text() != "" and self.ui.projectDir.text() != "" and \
                        self.ui.pluginsList.currentRow() > 0:
                    self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).setEnabled(True)
        elif origin == self.ui.openExistingButton:
            file_dialog = QFileDialog(self)
            file_dialog.setFileMode(QFileDialog.FileMode.Directory)
            file_dialog.setOption(QFileDialog.Option.ShowDirsOnly)
            file_dialog.exec()
            project_dir = os.path.normpath(file_dialog.selectedFiles()[0])
            project_json_path = os.path.join(project_dir, "project.json")
            if not os.path.exists(project_json_path):
                self.ui.errorLabel.setText("This is not a valid project directory.")
                self.ui.errorLabel.setVisible(True)
                return
            with open(project_json_path, "r") as f:
                self.project_info = json.load(f)
            if "project_base" not in self.project_info or "name" not in self.project_info \
                    or "version" not in self.project_info or "project_name" not in self.project_info:
                self.ui.errorLabel.setText("This is not a valid project directory.")
                self.ui.errorLabel.setVisible(True)
                return

            data_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
            projects_file = os.path.join(data_dir, "projects.json")
            with open(projects_file, "r") as f:
                projects = json.load(f)
            data_dir_project_info = {
                "name": self.project_info["name"],
                "project_name": self.project_info["project_name"],
                "dir": project_dir,
                "last_opened": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            for p in projects["projects"]:
                if p["dir"] == project_dir:
                    projects["projects"].remove(p)
                    break
            projects["projects"].insert(0, data_dir_project_info)
            with open(projects_file, "w") as f:
                json.dump(projects, f)

            self.accept()

    def reject(self):
        super().reject()
        self.remove_project_info()
        if self.cancel_quits:
            QApplication.exit()

    def accept(self):
        if self.error_encountered:
            self.reject()
            return

        super().accept()

    def open_about(self):
        plugin = self.plugins[self.ui.pluginsList.currentRow()-1]
        about_dialog = PluginInfoDialog(plugin, self.parent())
        about_dialog.show()

    def update(self):
        origin = self.sender()
        if origin == self.ui.projectName or origin == self.ui.projectDir or origin == self.ui.pluginsList:
            if origin == self.ui.pluginsList:
                if self.ui.pluginsList.currentRow() == 0:
                    self.ui.aboutPluginButton.setEnabled(False)
                else:
                    plugin = self.plugins[self.ui.pluginsList.currentRow()-1]
                    if plugin["readme"] != "":
                        self.ui.aboutPluginButton.setEnabled(True)
                    else:
                        self.ui.aboutPluginButton.setEnabled(False)
            project_name = format_project_name(self.ui.projectName.text())
            if self.base_project_dir is not None:
                project_dir = os.path.join(self.base_project_dir, project_name)
                self.ui.projectDir.setText(self.base_project_dir)
                self.ui.projectDirFull.setText(project_dir)
                if os.path.exists(project_dir) and project_name != "":
                    self.ui.errorLabel.setText("A directory with this name already exists at this location")
                    self.ui.errorLabel.setVisible(True)
                    self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).setEnabled(False)
                    return
                else:
                    self.ui.errorLabel.setVisible(False)
                    if self.ui.projectName.text() != "" and self.ui.projectDir.text() != "" and \
                            self.ui.pluginsList.currentRow() > 0:
                        self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).setEnabled(True)
            if self.ui.projectName.text() != "" and self.ui.projectDir.text() != "" and \
                    self.ui.pluginsList.currentRow() > 0:
                self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).setEnabled(True)
            else:
                self.ui.buttonBox.button(self.ui.buttonBox.StandardButton.Save).setEnabled(False)
        elif origin == self.ui.openPluginsButton:
            # Opens the plugins directory
            plugins_dir = os.path.join(platformdirs.user_data_dir(APP_NAME, AUTHOR), "plugins")
            if not os.path.exists(plugins_dir):
                os.makedirs(plugins_dir)
            reveal_directory(plugins_dir)
        elif origin == self.ui.buttonBox:
            data_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
            projects_file = os.path.join(data_dir, "projects.json")
            with open(projects_file, "r") as f:
                projects = json.load(f)
            formatted_name = format_project_name(self.ui.projectName.text())
            self.project_dir = os.path.join(self.base_project_dir, formatted_name)
            if self.project_dir in projects["projects"] or os.path.exists(self.project_dir) \
                    or self.ui.projectDirFull.text() in projects["projects"]:
                self.ui.errorLabel.setText(f"The project {formatted_name} already exists at this location.")
                self.ui.errorLabel.setVisible(True)
                return
            self.save_project_info()

            plugin = self.plugins[self.ui.pluginsList.currentRow()-1]
            self.selected_plugin, _ = pluginmanager.get_plugin(plugin["identifier"], plugin["version"])

            if self.selected_plugin is not None:
                self.ui.stackedWidget.setCurrentIndex(1)
                thread = threading.Thread(target=self.initialize_project)
                thread.start()
            else:
                self.ui.errorLabel.setText("An error occurred while initializing the project.")
                self.ui.errorLabel.setVisible(True)
                self.ui.finishButton.setEnabled(False)

    def log(self, message):
        if message.startswith("fatal:"):
            if self.currStep == 0:
                self.ui.progress_label.setText(message)
            self.error_encountered = True
            self.ui.setup_label.setText("An error occurred.")
            self.ui.finishButton.setEnabled(True)
            return
        if message == SETUP_LOG_FINISH:
            self.ui.progress_label.setText("Setup Complete")
            self.ui.progressBar.setValue(self.ui.progressBar.maximum())
            self.ui.finishButton.setEnabled(True)
            return
        elif self.currStep + 1 < len(SETUP_STEPS) and message.startswith(SETUP_STEPS[self.currStep + 1]):
            self.currStep += 1
            self.ui.progressBar.setValue(self.currStep * 1000)
        if message.startswith(SETUP_STEPS[self.currStep]):
            if self.currStep == 0:
                self.ui.progress_label.setText("Cloning repository...")
                value = self.ui.progressBar.value() + 333
                self.ui.progressBar.setValue(value)
            elif self.currStep == 1:
                self.ui.progress_label.setText("Installing agbcc...")
            elif self.currStep == 2:
                self.ui.progress_label.setText("Compiling preprocessor files...")
            elif self.currStep == 3:
                self.ui.progress_label.setText("Parsing GBA assembly...")
            elif self.currStep == 4:
                self.ui.progress_label.setText("Compiling code and graphics...")
                src = message.split(" ")[-1].split("/")[-1]
                value = lerp(string_to_fraction_ord(src), 0.78, 1, 0, 1)
                self.ui.progressBar.setValue(int((value + self.currStep) * 1000))
            elif self.currStep == 5:
                self.ui.progress_label.setText("Compiling maps...")
                words = message.split(" ")
                if words[1] == "map":
                    src = words[-2].split("/")[2]
                    value = lerp(string_to_fraction_ord(src), 0.78, 1, 0, 1)
                    self.ui.progressBar.setValue(int((value + self.currStep) * 1000))
            elif self.currStep == 6:
                self.ui.progress_label.setText("Compiling audio...")
                src = message.split(" ")[1].replace("sound/direct_sound_samples/", "")
                value = lerp(string_to_fraction_ord(src),  0.80374, 1, 0, 1)
                self.ui.progressBar.setValue(int((value + self.currStep) * 1000))
            elif self.currStep == 7:
                self.ui.progress_label.setText("Compiling midi...")
                src = message.split(" ")[1].replace("sound/songs/midi/", "")
                value = lerp(string_to_fraction_ord(src), 0.89397, 1, 0, 1)
                self.ui.progressBar.setValue(int((value + self.currStep) * 1000))
            elif self.currStep == 8:
                self.ui.progress_label.setText("Compiling ROM...")
                if ".elf" in message.split(" ")[1]:
                    value = 0.33
                    self.ui.progressBar.setValue(int((value + self.currStep) * 1000))
                elif ".gba" in message.split(" ")[1]:
                    value = 0.67
                    self.ui.progressBar.setValue(int((value + self.currStep) * 1000))
            elif self.currStep == 9:
                self.ui.progress_label.setText("Processing game data...")
                value = 0.5
                self.ui.progressBar.setValue(int((value + self.currStep) * 1000))

    def initialize_project(self):
        log = self.logSignal.emit
        try:
            d = DockerUtil(self.project_info)

            project_name = self.project_info["project_name"]

            d.try_get_nproc_from_container()

            repo = self.selected_plugin.project_base_repo
            branch = self.selected_plugin.project_base_branch

            run_command = d.run_docker_container_command
            if branch is None:
                run_command(["git", "clone", "--progress", "--verbose", repo, f"./projects/{project_name}/source"],
                            logger=self.logSignal)
            else:
                run_command(["git", "clone", "--progress", "--verbose",
                             "--branch", branch, repo, f"./projects/{project_name}/source"],
                            logger=self.logSignal)
            if self.error_encountered:
                return

            run_command(["git", "switch", "-c", project_name],
                        wdir=f"/root/projects/{project_name}/source",
                        logger=self.logSignal)
            if self.error_encountered:
                return

            # Clone base game repo
            run_command(["git", "clone", "--progress", "--verbose", self.selected_plugin.rom_base["repo"],
                         f"./projects/{project_name}/base"],
                        logger=self.logSignal)
            if self.error_encountered:
                return

            log("Installing agbcc")
            run_command(wdir=f"/root/agbcc", args=["./install.sh", f"../projects/{project_name}/source"],
                        logger=self.logSignal)
            if self.error_encountered:
                return
            run_command(wdir=f"/root/agbcc",
                        args=["./install.sh", f"../projects/{project_name}/base"], logger=self.logSignal)
            if self.error_encountered:
                return

            nproc = d.try_get_nproc_from_container()
            run_command(wdir=f"/root/projects/{project_name}/source",
                        args=["make", f"-j{nproc}"] if nproc is not None else ["make"], logger=self.logSignal)
            if self.error_encountered:
                return

            log(SETUP_LOG_FINISH)
        except Exception as e:
            print(f"fatal: {e}")
            log("Fatal error occurred while setting up project.")
            self.error_encountered = True
            self.ui.setup_label.setText("An error occurred.")
            self.ui.finishButton.setEnabled(True)

    def save_project_info(self):
        data_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
        projects_file = os.path.join(data_dir, "projects.json")
        with open(projects_file, "r") as f:
            projects = json.load(f)
        formatted_name = format_project_name(self.ui.projectName.text())
        data_dir_project_info = {
            "name": self.ui.projectName.text(),
            "project_name": formatted_name,
            "dir": self.project_dir,
            "last_opened": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.project_info = {
            "name": self.ui.projectName.text(),
            "project_name": formatted_name,
            "version": {
                "major": 0,
                "minor": 0,
                "patch": 0,
            },
            "plugin_identifier": self.ui.pluginsList.currentItem().data(Qt.UserRole)[0],
            "plugin_version": self.ui.pluginsList.currentItem().data(Qt.UserRole)[1],
            "date_created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "date_modified": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        projects["projects"].insert(0, data_dir_project_info)
        with open(projects_file, "w") as f:
            json.dump(projects, f)
        os.makedirs(os.path.join(self.project_dir, "data"), exist_ok=True)
        with open(os.path.join(self.project_dir, "project.json"), "w") as f:
            json.dump(self.project_info, f)
        self.project_info = data_dir_project_info | self.project_info

    def remove_project_info(self):
        if self.project_info is not None:
            try:
                data_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
                projects_file = os.path.join(data_dir, "projects.json")
                with open(projects_file, "r") as f:
                    projects = json.load(f)
                for p in projects["projects"]:
                    if p["dir"] == self.project_dir:
                        projects["projects"].remove(p)
                        break
                with open(projects_file, "w") as f:
                    json.dump(projects, f)
                shutil.rmtree(self.project_dir)
            except Exception as e:
                print(e)
            finally:
                self.project_info = None


def string_to_fraction_ord(s):
    # Define the allowed characters and sort them
    chars = sorted(string.digits + string.ascii_letters + '._')
    # Get the maximum ord value amongst the characters, and add 1 to get the base
    max_ord_value = max(ord(char) for char in chars) + 1
    # Convert the string to a fractional value based on its position
    value = 0
    base_exp = 1
    for char in s:
        value += ord(char) / (max_ord_value ** base_exp)
        base_exp += 1
    return value


def lerp(x, x_min, x_max, y_min, y_max):
    return y_min + (x - x_min) / (x_max - x_min) * (y_max - y_min)
