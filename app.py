import os
import sys
import json
import datetime
import platformdirs

from PySide6.QtCore import QEventLoop
from PySide6.QtGui import QFontDatabase, QAction
from PySide6.QtWidgets import QApplication

import res.resources_rc as resources_rc
import docker_integration
from app_info import APP_NAME, AUTHOR
from loadingproject import LoadingProject
from mainwindow import MainWindow
from projectselector import ProjectSelector


class App:

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.__initialize_fonts()
        self.__initialize_resources()
        self.main = None
        self.project_selector = None
        self.loading_dialog = None

    @staticmethod
    def __initialize_fonts():
        QFontDatabase.addApplicationFont(":/fonts/SourceCodePro-Regular.ttf")

    @staticmethod
    def __initialize_resources():
        resources_rc.qInitResources()

    def start(self):
        """
        Starts the application by performing the necessary setup and loading the main window.

        This method performs the following:
        1. Makes necessary directories.
        2. Shows project selector window.
        3. If necessary, shows Docker not found alert.
        4. If necessary, shows window for initial container setup.
        5. Handles project selection.
        6. Loads project into main window.
        """

        # Set up plugins directory
        data_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
        os.makedirs(os.path.join(data_dir, "plugins"), exist_ok=True)

        # Get projects from projects.json
        projects = App.get_projects(data_dir)

        # Show project selector
        self.project_selector = ProjectSelector(projects=projects["projects"])
        self.project_selector.show()

        # Check if Docker integration is successful
        if not docker_integration.try_docker_alert(self.project_selector):
            sys.exit()  # Exit if the user presses cancel

        # Check if initial container setup is needed
        setup_ui = docker_integration.try_initial_container_setup(self.project_selector)
        if setup_ui is not None:
            setup_ui.exec()

        # Wait for project selector to close
        loop = QEventLoop()
        self.project_selector.close_signal.connect(loop.quit)
        loop.exec()

        # Handle project selection
        if self.project_selector.selected_index == -1:
            # Exit if the user presses cancel
            sys.exit()
        elif self.project_selector.selected_index == -2:
            # Open a new project
            projects = App.get_projects(data_dir)
            self.project_selector.selected_index = 0

        # Load main window and show loading dialog
        self.main = MainWindow()
        self.loading_dialog = LoadingProject(self.main)
        self.loading_dialog.show()

        # Update loading progress
        self.loading_dialog.update_progress(10)

        # Load project information
        p_info = projects["projects"][self.project_selector.selected_index]
        self.loading_dialog.update_progress(20)
        with open(os.path.join(p_info["dir"], "project.json"), "r") as f:
            local_p_info = json.load(f)
        self.loading_dialog.update_progress(30)

        # Update last opened timestamp
        p_info["last_opened"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.loading_dialog.update_progress(40)

        # Load data into main window
        self.main.load_data(p_info | local_p_info)
        self.loading_dialog.update_progress(70)

        # Set window file path
        self.main.setWindowFilePath(p_info["dir"])
        self.loading_dialog.update_progress(80)

        # Set current item in tree view
        self.main.ui.tree_pokemon.setCurrentItem(self.main.ui.tree_pokemon.topLevelItem(0))
        self.loading_dialog.update_progress(90)

        # Update projects.json with modified project information
        projects["projects"][self.project_selector.selected_index] = p_info
        with open(os.path.join(data_dir, "projects.json"), "w") as file_projects:
            json.dump(projects, file_projects)

        # Update loading progress
        self.loading_dialog.update_progress(100)

        # Add recent projects to the menu
        for i in range(1, min(len(projects["projects"]), 5)):
            recent_project = QAction(projects["projects"][i]["name"] + " | " + projects["projects"][i]["dir"])
            recent_project.triggered.connect(
                lambda _, p=projects["projects"][i]: self.main.loadAndSaveProjectSignal.emit(p)
            )
            self.main.ui.menuRecent_Projects.addAction(recent_project)

        # Handle case when there are no recent projects
        if len(projects["projects"]) == 1:
            no_recent_projects = QAction("No Recent Projects")
            no_recent_projects.setEnabled(False)
            self.main.ui.menuRecent_Projects.addAction(no_recent_projects)

        # Close loading dialog and show main window
        self.loading_dialog.close()
        self.main.show()
        self.main.activateWindow()
        self.main.setFocus()

    @staticmethod
    def get_projects(path: str) -> dict:
        """
        Retrieve the projects from the projects.json file and return them as a dictionary.

        Args:
            path (str): The path to the directory containing the projects.json file.

        Returns:
            dict: A dictionary containing the projects retrieved from the projects.json file.
        """
        # Define the path to the projects.json file
        projects_file = os.path.join(path, "projects.json")
        
        # If the projects.json file doesn't exist, create an empty projects dictionary and save it to the file
        if not os.path.exists(projects_file):
            projects = {"projects": []}
            with open(projects_file, "w") as file_projects:
                json.dump(projects, file_projects)
        
        # Load the projects from the projects.json file
        with open(projects_file, "r") as file_projects:
            projects = json.load(file_projects)

        # Sort the projects by last opened timestamp in descending order
        projects["projects"].sort(
            key=lambda x: datetime.datetime.strptime(x["last_opened"], "%Y-%m-%d %H:%M:%S"),
            reverse=True)
        
        return projects


if __name__ == "__main__":
    app = App()
    app.start()
    sys.exit(QApplication.exec())
