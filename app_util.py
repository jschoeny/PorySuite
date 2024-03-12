import os
import sys
import subprocess

from PySide6.QtWidgets import QMessageBox


def reveal_directory(directory, is_file=False):
    """
    Opens the file explorer on the given file path and selects the file.
    Supports Windows, macOS, and Linux (with xdg-open).
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"The file {directory} does not exist.")

    if sys.platform == 'win32':  # Windows
        if is_file:
            # Using explorer and /select flag to open the folder and select the file
            subprocess.Popen(fr'explorer /select,"{os.path.normpath(directory)}"')
        else:
            # Using explorer to open the folder
            subprocess.run(['explorer', os.path.normpath(directory)], check=True)
    elif sys.platform == 'darwin':  # macOS
        if is_file:
            # Using open and -R to reveal the file in Finder
            subprocess.run(['open', '-R', directory], check=True)
        else:
            # Using open to open the folder in Finder
            subprocess.run(['open', directory], check=True)
    else:
        # Linux or other Unix-like systems can be trickier because of the
        # variety of file managers, but xdg-open is a good guess.
        if 'XDG_CURRENT_DESKTOP' in os.environ:
            try:
                file_manager = {
                    'GNOME': 'nautilus',
                    'Unity': 'nautilus',
                    'XFCE': 'thunar',
                    'KDE': 'dolphin',
                }[os.environ['XDG_CURRENT_DESKTOP']]

                # Attempt to use the file manager directly to open the folder
                subprocess.run([file_manager, directory], check=True)
            except KeyError:
                # If the desktop environment is unknown, fall back to xdg-open
                subprocess.run(['xdg-open', directory], check=True)
            except subprocess.CalledProcessError:
                # If the guessed file manager fails, fall back to xdg-open
                subprocess.run(['xdg-open', directory], check=True)
        else:
            # When $XDG_CURRENT_DESKTOP is not set, use xdg-open as a last resort
            subprocess.run(['xdg-open', directory], check=True)


def condense_path(full_path: str) -> str:
    """
    Condenses a full path by replacing the home directory with a tilde (~).

    Args:
        full_path (str): The full path to be condensed.

    Returns:
        str: The condensed path with the home directory replaced by a tilde (~).
    """
    home_dir = os.path.expanduser("~")
    condensed_path = os.path.relpath(full_path, home_dir)
    if not condensed_path.startswith(".."):
        condensed_path = "~" + os.path.sep + condensed_path
    return condensed_path


def create_unsaved_changes_dialog(parent, message: str = None) -> int:
    """
    Creates a dialog to ask the user if they want to save changes.

    Args:
        parent: The parent widget.
        message (str): The message to display in the dialog.

    Returns:
        int: The QMessageBox button that was clicked. (QMessageBox.Save, QMessageBox.Discard, or QMessageBox.Cancel)
    """
    if message is None:
        message = "Your project has unsaved changes. Would you like to save?"
    dialog = QMessageBox(parent)
    dialog.setWindowTitle("Unsaved Changes")
    dialog.setText(message)
    dialog.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
    dialog.setDefaultButton(QMessageBox.Save)
    return dialog.exec()
