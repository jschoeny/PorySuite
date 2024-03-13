import os
import sys
import time
import threading
import shutil
import subprocess
import datetime
import tarfile
import io
from pathlib import PurePosixPath, PureWindowsPath

import platformdirs
import docker
from docker import errors

from PySide6 import QtCore
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QDialog, QApplication

from app_info import APP_NAME, AUTHOR
from ui.ui_docker_not_running import Ui_DockerNotRunning
from ui.ui_programsetup import Ui_ProgramSetup

SETUP_LOG_FINISH = "*** SETUP COMPLETE ***"


class DockerNotRunning(QDialog):
    """
    Dialog window displayed on startup when Docker is not running.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_DockerNotRunning()
        self.ui.setupUi(self)


class ProgramSetup(QDialog):
    logSignal = Signal(str)

    def __init__(self, client, parent=None):
        # Initialize the ProgramSetup class
        super().__init__(parent)
        self.ui = Ui_ProgramSetup()
        self.ui.setupUi(self)

        # Connect the logSignal to the log method
        self.logSignal.connect(self.log)

        # Initialize variables
        self.prevStep = 0
        self.client = client
        self.fatal_error = False

        # Set window flags to customize the window appearance
        self.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.CustomizeWindowHint |
            QtCore.Qt.WindowMinimizeButtonHint |
            QtCore.Qt.WindowMaximizeButtonHint
        )

    def accept(self):
        if self.fatal_error:
            QApplication.exit()
        super().accept()
        self.close()

    def reject(self):
        super().reject()
        QApplication.exit()

    def next_page(self):
        self.ui.stackedWidget.setCurrentIndex(1)
        self.log("Building Docker Image...\n")

        # Start a separate thread to build the Docker image
        thread = threading.Thread(target=build_docker_image, args=(self.client, self.logSignal,))
        thread.start()

    def log(self, message):
        """
        Logs the given message and performs specific actions based on the message content.

        Parameters:
        - message (str): The message to be logged.
        """
        self.ui.textBrowser.append(message)

        if message == SETUP_LOG_FINISH and not self.fatal_error:
            self.handle_setup_complete()  # Handle setup completion
        elif "fatal:" in message:
            self.handle_fatal_error(message)
        elif message.startswith("Step "):
            self.handle_step_progress(message)  # Handle step progress
        elif message.startswith("Successfully tagged"):
            self.ui.progressBar.setValue(self.ui.progressBar.maximum())
        else:
            self.handle_default_progress()  # Handle default progress

    def handle_fatal_error(self, message):
        self.ui.textBrowser.append(message)
        self.ui.textBrowser.append("\n\n** An error occurred while creating the Docker Image. "
                                   "Please try again later. **")
        self.fatal_error = True
        self.ui.finishButton.setText("Exit")
        self.ui.finishButton.setEnabled(True)

    def handle_setup_complete(self):
        self.ui.label.setText("Setup Complete")
        self.ui.progressBar.setValue(self.ui.progressBar.maximum())
        self.ui.finishButton.setEnabled(True)

    def handle_step_progress(self, message):
        progress = message.split(" ")[1]
        values = progress.split("/")
        if len(values) == 2:
            self.ui.progressBar.setMaximum((int(values[1]) + 1) * 1000)
            self.ui.progressBar.setValue(int(values[0]) * 1000)
            self.prevStep = int(values[0]) * 1000

    def handle_default_progress(self):
        if self.ui.progressBar.value() < self.prevStep - 90:
            self.ui.progressBar.setValue(self.ui.progressBar.value() + 1)


def is_docker_running():
    """
    Checks if Docker is running by pinging the Docker daemon.

    Returns:
        bool: True if Docker is running, False otherwise.
    """
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception as e:
        print(e)
        return False


def try_docker_alert(parent=None) -> bool:
    """
    Displays a QMessageBox if Docker is not running and waits for the user to start Docker.
    
    Args:
        parent: The parent widget for the QMessageBox.
    
    Returns:
        bool: True if Docker is running, False otherwise.
    """
    dnr = DockerNotRunning(parent)
    while is_docker_running() is False:
        dnr.show()
        dnr.exec()
        if dnr.result() == QDialog.Rejected:
            QApplication.exit()
            return False
    return True


def try_initial_container_setup(parent=None):
    # Create a Docker client connection
    client = docker.from_env()
    
    try:
        # Check if the Docker image "porysuiteimage" exists
        client.images.get("porysuiteimage")
    except errors.ImageNotFound:
        # If the image does not exist, prompt the user to set up the container
        dialog = ProgramSetup(client, parent=parent)
        return dialog
    except Exception as e:
        print(e)
        return None
    
    return None


def build_docker_image(client, logger: Signal):
    """
    Builds a Docker image using the specified Docker client and logger.

    Args:
        client: The Docker client connection.
        logger: The logger object used to emit log signals.

    Raises:
        Exception: If an error occurs during the build process.
    """
    try:
        generator = client.api.build(decode=True, path=".", tag="porysuiteimage", rm=True)
        while True:
            try:
                output = generator.__next__()
                if 'stream' in output:
                    output_str = output['stream'].strip('\r\n').strip('\n')
                    logger.emit(output_str)
            except StopIteration:
                time.sleep(1)
                logger.emit(SETUP_LOG_FINISH)
                break
    except Exception as e:
        print(e)
        logger.emit(str(e))


class DockerUtil:
    def __init__(self, project_info: dict):
        self.project_info = project_info
        self.project_dir = project_info["dir"]
        self.project_dir_name = project_info["project_name"]

    def run_docker_container_command(self, args, wdir=None, logger: Signal = None, destroy=True, stdin_open=False):
        """
        Runs a Docker container with the specified command and options.

        Args:
            args (list): The command and arguments to run inside the container.
            wdir (str, optional): The working directory inside the container. Defaults to None.
            logger (Signal, optional): The logger object to log container output. Defaults to None.

        Returns:
            Container object
        """
        client = docker.from_env()
        volumes = {
            self.project_dir: {
                'bind': f'/root/projects/{self.project_dir_name}', 'mode': 'rw'
            }
        }
        if sys.platform == "win32":
            volumes = [f'porysuite_{self.project_dir_name}:/root/projects/{self.project_dir_name}']

        try:
            container = client.containers.run("porysuiteimage",
                                              args,
                                              working_dir=wdir,
                                              detach=True,
                                              auto_remove=destroy,
                                              remove=destroy,
                                              stdin_open=stdin_open,
                                              network_mode="host",
                                              pid_mode="host",
                                              uts_mode="host",
                                              volumes=volumes)
            if stdin_open:
                return container
            if logger is not None:
                for line in container.logs(stream=True):
                    logger.emit(line.decode("utf-8").strip('\r\n').strip('\n'))
                    print(line.decode("utf-8").strip('\r\n').strip('\n'))
            container.wait()
            return container
        except Exception as e:
            print(e)

    def try_get_nproc_from_container(self) -> str | None:
        """
        Tries to get the number of processors from a Docker container and saves the output to a file.

        Returns:
            str | None: The number of processors as a string, or None if an error occurs.
        """
        try:
            d_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
            nproc_file_path = os.path.join(d_dir, ".misc", "nproc.txt")
            if os.path.exists(nproc_file_path):
                with open(nproc_file_path, "r") as f:
                    return f.read().strip()
            else:
                os.makedirs(os.path.join(d_dir, ".misc"), exist_ok=True)
                self.run_docker_container_command(
                    wdir=f"/root/projects/{self.project_dir_name}",
                    args=["sh", "-c", "nproc > nproc.txt"]
                )
                with open(os.path.join(self.project_dir, "nproc.txt"), "r") as f:
                    nproc = f.read().strip()
                    with open(nproc_file_path, "w") as f2:
                        f2.write(nproc)
                    return nproc
        except Exception as e:
            print(e)
            return None

    def preprocess_c_file(self, input_file: str, includes: list = None):
        """
        Preprocesses a C file using gcc and saves the output in the 'processed' directory of the project.

        Args:
            input_file (str): The path to the input C file.
            includes (list, optional): A list of additional include files to be used during preprocessing.
        """
        includes_args = []

        if includes is not None:
            for include in includes:
                includes_args.append("-include")
                includes_args.append(include)

        output_file = f"../processed/{input_file}"

        args = [
            "gcc",
            "-E",
            input_file,
            "-Iinclude",
            *includes_args,
            "-DTRUE",
            "-o", output_file
        ]

        try:
            self.makedirs(f"processed/{os.path.dirname(input_file)}")
            self.run_docker_container_command(
                wdir=f"/root/projects/{self.project_dir_name}/source",
                args=args,
                logger=None
            )
        except Exception as e:
            print(f"An error occurred while preprocessing: {e}")

    def copy_file_to_host(self, source: str, dest: str):
        if sys.platform == "win32":
            source_path = f"/root/projects/{self.project_dir_name}/{source}"
            temp_file = io.BytesIO()
            container = self.run_docker_container_command(["echo", "copying"], destroy=False)
            bits, stat = container.get_archive(source_path)
            for chunk in bits:
                temp_file.write(chunk)
            dest_path = os.path.dirname(os.path.join(self.project_dir, dest))
            temp_file.seek(0)
            with tarfile.open(fileobj=temp_file) as f:
                f.extractall(dest_path)
            container.remove(force=True)
        else:
            source_path = os.path.join(self.project_dir, source)
            dest_path = os.path.join(self.project_dir, dest)
            shutil.copyfile(source_path, dest_path)

    def write_file_to_volume(self, fileobj: io.StringIO, dest: str):
        if sys.platform == "win32":
            dest_path = os.path.dirname(dest)
            dest_file = os.path.basename(dest)
            fileobj.seek(0)

            tar_stream = io.BytesIO()
            tar = tarfile.TarFile(fileobj=tar_stream, mode='w')
            tar_info = tarfile.TarInfo(dest_file.lstrip("/"))
            bytes_fileobj = io.BytesIO(fileobj.read().encode("utf-8"))
            tar_info.size = len(bytes_fileobj.getbuffer())
            tar_info.mtime = time.time()
            tar.addfile(tar_info, bytes_fileobj)

            # Write the tar file to a temporary location
            temp_path = os.path.join(self.project_dir, "temp")
            os.makedirs(temp_path, exist_ok=True)
            os.system(f'attrib +h "{temp_path}"')
            temp_file = os.path.join(temp_path, f"{dest_file}.tar")
            with open(temp_file, "wb") as f:
                f.write(tar_stream.getvalue())
            tar_stream.seek(0)
            container = self.run_docker_container_command(None, destroy=False, stdin_open=True)
            success = container.put_archive(dest_path, tar_stream)
            container.remove(force=True)
        else:
            shutil.copyfile(source, dest)

    def makedirs(self, path):
        if sys.platform == "win32":
            self.run_docker_container_command(
                ["mkdir", "-p", path],
                wdir=f"/root/projects/{self.project_dir_name}",
            )
        else:
            os.makedirs(os.path.join(self.project_dir, path), exist_ok=True)

    def copyfile(self, source, dest):
        if sys.platform == "win32":
            self.run_docker_container_command(
                ["cp", source, dest],
                wdir=f"/root/projects/{self.project_dir_name}",
            )
        else:
            shutil.copyfile(os.path.join(self.project_dir, source), os.path.join(self.project_dir, dest))

    def removefile(self, path):
        if sys.platform == "win32":
            self.run_docker_container_command(
                ["rm", path],
                wdir=f"/root/projects/{self.project_dir_name}",
            )
        else:
            os.remove(os.path.join(self.project_dir, path))

    def file_exists(self, path):
        if sys.platform == "win32":
            container = self.run_docker_container_command(
                ["test", "-e", f"/root/projects/{self.project_dir_name}/{path}"],
                destroy=False
            )
            response = container.wait()
            exists = (response['StatusCode'] == 0)
            container.remove(force=True)
            return exists
        else:
            return os.path.exists(os.path.join(self.project_dir, path))
        
    def getmtime(self, path):
        if sys.platform == "win32":
            container = self.run_docker_container_command(None, destroy=False, stdin_open=True)
            exit_code, output = container.exec_run(f"stat -c %Y /root/projects/{self.project_dir_name}/{path}")
            if exit_code != 0:
                print(f"An error occurred while getting the modification time of {path}.")
                print(output.decode("utf-8"))
                container.remove(force=True)
                return None
            mtime = output.decode("utf-8").strip()
            container.remove(force=True)
            return int(mtime)
        else:
            if not os.path.exists(os.path.join(self.project_dir, path)):
                return None
            return os.path.getmtime(os.path.join(self.project_dir, path))

    def export_rom(self, logger: Signal = None):
        """
        Export the ROM for the given project.

        Args:
            logger (Signal, optional): Logger object for logging messages. Defaults to None.
        """
        os.makedirs(os.path.join(self.project_dir, "build"), exist_ok=True)
        thread = threading.Thread(target=self.try_export_rom, args=(logger,))
        thread.start()

    def try_export_rom(self, logger: Signal):
        """
        Tries to export a ROM file based on the project information.

        Args:
            logger (Signal): The logger object used to emit log signals.

        Returns:
            None
        """
        # Emit log signal to indicate progress
        logger.emit("5")

        # Get the version information from the project
        version = self.project_info["version"]

        # Get the number of processors from the Docker container
        nproc = self.try_get_nproc_from_container()

        # Emit log signal to indicate progress
        logger.emit("10")

        rom_name = f'{self.project_dir_name}_v{version["major"]}_{version["minor"]}_{version["patch"]}.gba'

        make_args = ["make", f"ROM_NAME={rom_name}", f"MODERN_ROM_NAME={rom_name}"]

        # Add the -j flag to make_args if the number of processors is specified
        if nproc is not None:
            make_args.insert(1, f"-j{nproc}")

        # Run the docker container command to build the ROM
        self.run_docker_container_command(
            wdir=f"/root/projects/{self.project_dir_name}/source",
            args=make_args,
            logger=logger
        )

        # Emit log signal to indicate progress
        logger.emit("90")

        # Copy the built ROM to the build directory
        if sys.platform == "win32":
            source_rom_path = f"source/{rom_name}"
        else:
            source_rom_path = os.path.join("source", rom_name)
        build_rom_path = os.path.join("build", rom_name)
        self.copy_file_to_host(source_rom_path, build_rom_path)
        self.removefile(source_rom_path)

        # Emit log signal to indicate completion and the path of the exported ROM
        logger.emit(f"Exported ROM: {os.path.join(self.project_dir, build_rom_path)}")

    def open_terminal(self):
        """
        Opens a terminal and starts a new thread to execute the try_open_terminal function.
        """
        thread = threading.Thread(target=self.try_open_terminal)
        thread.start()

    def try_open_terminal(self):
        """
        Opens a terminal and runs a Docker command in it.
        """
        project_dir_container = f"/root/projects/{self.project_dir_name}"
        command = f"docker run --rm -i -t --mount type=bind,source=\"{self.project_dir}\",target=\"{project_dir_container}\" " \
                  f"--workdir '{project_dir_container}' porysuiteimage"
        if sys.platform == "darwin":
            subprocess.run(["osascript", "-e", f'tell app "Terminal" to do script "{command}"'])
            subprocess.run(["osascript", "-e", 'tell app "Terminal" to activate'])
        elif sys.platform == "win32":
            command = f"docker run --rm -i -t -v porysuite_{self.project_dir_name}:/root/projects/{self.project_dir_name}"
            subprocess.run(["start", "cmd", "/k", command], shell=True)
        else:
            subprocess.run(command, shell=True)
