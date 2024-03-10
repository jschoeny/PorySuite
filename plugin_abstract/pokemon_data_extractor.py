import os
from abc import ABC, abstractmethod

from docker_integration import DockerUtil


class PokemonDataExtractor(ABC):
    """
    Abstract base class for extracting Pokémon data from game files.

    Attributes:
        DATA_FILE (str): The name of the exported JSON file.
        FILES (dict): A dictionary of source files used for extracting data.
        project_info (dict): The project information dictionary.
        project_dir (str): The project directory.
    """

    DATA_FILE: str = None
    FILES = {}

    def __init__(self, project_info: dict, data_file: str = None, files: dict = None):
        """
        Initializes a new instance of the PokemonDataExtractor class.
        
        :param project_info: A dictionary containing project information.
        :param data_file: The name of the exported JSON file.
        :param files: A dictionary of files used for extracting data.
        """
        self.project_info = project_info
        self.project_dir = project_info["dir"]
        self.DATA_FILE = data_file
        self.FILES = files
        self.docker_util = DockerUtil(self.project_info)

    def get_data_file_path(self) -> str:
        """
        Gets the path of the data file.

        :returns: The path of the data file.
        """
        return os.path.join(self.project_dir, "data", self.DATA_FILE)

    def check_json_newer_than_files(self) -> bool:
        """
        Checks if the JSON file is newer than the files it was generated from.

        :returns: True if the JSON file is newer than the files it was generated from, False otherwise.
        """
        json_file = self.get_data_file_path()
        if not os.path.isfile(json_file):
            return False
        json_file_mod_time = os.path.getmtime(json_file)
        for file in self.FILES:
            backup_file = os.path.join(self.project_dir, "source", self.FILES[file]["backup"])
            if not os.path.isfile(backup_file):
                return False
            file_path = os.path.join(self.project_dir, "source", self.FILES[file]["original"])
            if os.path.isfile(file_path):
                file_mod_time = os.path.getmtime(file_path)
                if file_mod_time > json_file_mod_time:
                    return False
        return True

    def should_extract(self) -> bool:
        """
        Checks if the data can be extracted.

        :returns: True if the data can be extracted, False otherwise.
        """
        return not self.check_json_newer_than_files()

    @abstractmethod
    def extract_data(self) -> dict:
        """
        Extracts data from the decompiled Pokémon game files and returns relevant information in a dictionary.
        
        :returns: A dictionary containing Pokémon data.
        """
        pass

    @abstractmethod
    def parse_value_by_key(self, key: str, value: str) -> tuple:
        """
        Takes a value and parses it based on the key. This method should be overridden in subclasses.

        :param key: The key of the data.
        :param value: The value to parse according to the key.

        :returns: A tuple containing the key and parsed value
        """
        return key, value
