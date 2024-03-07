import os
import json
import inspect

from abc import ABC, abstractmethod

from plugin_abstract.pokemon_data import PokemonDataManager


class PorySuitePlugin(ABC):
    """
    Abstract base class for PorySuite plugins.
    """
    ROM_BASES = {
        "emerald": {
            "id": "emerald",
            "name": "Emerald",
            "repo": "https://github.com/pret/pokeemerald.git",
        },
        "firered": {
            "id": "firered",
            "name": "FireRed",
            "repo": "https://github.com/pret/pokefirered.git",
        },
        "ruby": {
            "id": "ruby",
            "name": "Ruby",
            "repo": "https://github.com/pret/pokeruby.git",
        },
    }

    def __init__(self):
        self.__info = {}
        self.__verified = False
        self.__readme_markdown = ""
        self.__load_plugin_info()
        self.__verify()

    def __load_plugin_info(self):
        """
        Loads the plugin info from the plugin_info.json file. Also loads the README.md file if it exists.
        """
        plugin_module = inspect.getmodule(self).__file__
        plugin_dir = os.path.dirname(os.path.abspath(plugin_module))
        plugin_info_path = os.path.join(plugin_dir, "plugin_info.json")
        with open(plugin_info_path, "r") as f:
            self.__info = json.load(f)
        readme_path = os.path.join(plugin_dir, "README.md")
        if os.path.isfile(readme_path):
            with open(readme_path, "r") as f:
                self.__readme_markdown = f.read()

    def __verify(self):
        """
        Verifies the plugin.
        """
        if "name" not in self.__info:
            raise ValueError("The plugin info must contain a name.")
        if "author" not in self.__info:
            raise ValueError("The plugin info must contain an author.")
        if "version" not in self.__info:
            raise ValueError("The plugin info must contain a version.")
        if "identifier" not in self.__info:
            raise ValueError("The plugin info must contain an identifier.")
        if "rom_base" not in self.__info:
            raise ValueError("The plugin info must contain a rom base.")
        elif self.__info["rom_base"] not in self.ROM_BASES:
            raise ValueError("The plugin info must contain a valid rom base.")
        if "project_base_repo" not in self.__info:
            raise ValueError("The plugin info must contain a project base repository.")
        self.__verified = True

    @property
    def name(self) -> str:
        """
        The name of the plugin.
        """
        if not self.__verified:
            return ""
        return self.__info["name"]

    @property
    def description(self) -> str:
        """
        A short description of the plugin.
        """
        if not self.__verified:
            return ""
        return self.__info["description"]

    @property
    def author(self) -> str:
        """
        The name of the plugin author.
        """
        if not self.__verified:
            return ""
        return self.__info["author"]

    @property
    def version(self) -> str:
        """
        The version of the plugin.
        """
        if not self.__verified:
            return ""
        return self.__info["version"]

    @property
    def identifier(self) -> str:
        """
        The identifier of the plugin, i.e. com.example.plugin
        """
        if not self.__verified:
            return ""
        return self.__info["identifier"]

    @property
    def rom_base(self) -> dict:
        """
        The base of the project. Should be one of the ROM_BASES.
        For example, if the plugin is for FireRed, this should return self.ROM_BASES["firered"].
        """
        if not self.__verified:
            return {}
        return self.ROM_BASES[self.__info["rom_base"]]

    @property
    def project_base_repo(self) -> str:
        """
        The repository of the project base.
        """
        if not self.__verified:
            return ""
        return self.__info["project_base_repo"]

    @property
    def project_base_branch(self) -> str | None:
        """
        The branch or version tag of the project base. If None, the latest version will be used.
        """
        if not self.__verified:
            return None
        if "project_base_branch" not in self.__info:
            return None
        return self.__info["project_base_branch"]

    @property
    def dependencies(self) -> list[str]:
        """
        The dependencies of the plugin. Should be a list of plugin identifiers.
        """
        if not self.__verified:
            return []
        if "dependencies" not in self.__info:
            return []
        return self.__info["dependencies"]

    @property
    def readme(self) -> str:
        """
        The README.md file of the plugin.
        """
        if not self.__verified:
            return ""
        return self.__readme_markdown

    @property
    def verified(self) -> bool:
        """
        Whether the plugin is verified.
        """
        return self.__verified

    @staticmethod
    @abstractmethod
    def create_data_manager(project_info: dict) -> PokemonDataManager:
        """
        Creates a new instance of your PokemonDataManagement subclass.
        """
        pass
