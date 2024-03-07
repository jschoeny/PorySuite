import os
import json
import shutil
from abc import ABC, abstractmethod
from typing import Type

from PySide6.QtGui import QImage, QPixmap

from plugin_abstract.pokemon_data_extractor import PokemonDataExtractor


class ReadSourceFile(object):
    """
    A context manager for reading a source file.

    Uses the project_info dictionary to determine the absolute path to the file.

    Args:
        project_info (dict): A dictionary containing project information.
        file_path (str): The path to the file to be read.

    Usage:
        with ReadSourceFile(project_info, file_path) as file:
            # Perform operations on the file
    """

    def __init__(self, project_info: dict, file_path: str):
        self.file_path = os.path.join(project_info["dir"], "source", file_path)

    def __enter__(self):
        self.file = open(self.file_path, "r")
        return self.file

    def __exit__(self, *args):
        self.file.close()


class WriteSourceFile(object):
    """
    A context manager for writing source files.

    This class provides a convenient way to write source files by automatically opening and closing the file.
    It also adds a header to the file indicating that it was generated by PorySuite.

    Args:
        project_info (dict): A dictionary containing project information.
        file_path (str): The path to the file to be written.

    Example:
        with WriteSourceFile(project_info, file_path) as file:
            file.write("Hello, world!")
    """

    def __init__(self, project_info: dict, file_path: str):
        self.file_path = os.path.join(project_info["dir"], "source", file_path)

    def __enter__(self):
        self.file = open(self.file_path, "w")
        self.file.write("// *** IMPORTANT ***\n")
        self.file.write("// This file was generated by PorySuite.\n")
        self.file.write("// Any changes made to this file will be lost when recompiling the project.\n\n")
        return self.file

    def __exit__(self, *args):
        self.file.close()


class AbstractPokemonData(ABC):
    """
    Abstract base class for Pokémon data.

    This class provides methods for extracting, saving, and parsing Pokémon data.

    All data is stored in a JSON file in the 'data' directory. The filename is
    determined by the `DATA_FILE` attribute.

    Attributes:
        DATA_FILE (str): The name of the exported JSON file.
        FILES (dict): A dictionary of files used for extracting data.
        GENERATED_FILES (dict): A dictionary of generated files to be deleted after compiling.
        EXTRACTOR (PokemonDataExtractor): The data extractor.
        project_info (dict): The project information dictionary.
        parent (AbstractPokemonData): The parent object.
        data (dict): The Pokémon data.
        original_data (dict): The original Pokémon data.
        pending_changes (bool): Whether or not there are pending changes.
    """
    DATA_FILE: str = None
    FILES = {}
    GENERATED_FILES = {}
    EXTRACTOR: PokemonDataExtractor = None

    def __init__(self, project_info: dict, parent=None):
        self.project_info = project_info
        self.parent = parent
        self.data = None
        self.original_data = None
        self.pending_changes = False

    def __load_data(self) -> bool:
        if self.EXTRACTOR is not None and self.EXTRACTOR.should_extract():
            self.data = self.EXTRACTOR.extract_data()
            self.original_data = json.loads(json.dumps(self.data))
            self.save()
            return True

        if self.DATA_FILE is not None:
            path = os.path.join(self.project_info["dir"], "data", self.DATA_FILE)
            try:
                with open(path) as f:
                    self.data = json.load(f)
                    self.original_data = json.loads(json.dumps(self.data))
                return True
            except FileNotFoundError:
                pass
            except json.decoder.JSONDecodeError:
                pass
        return False

    def instantiate_extractor(self, func: callable):
        """
        Takes the extractors constructor and instantiates it as self.EXTRACTOR

        Args:
            func (callable): The extractor's constructor method.
        """
        self.EXTRACTOR = func(self.project_info, self.DATA_FILE, self.FILES)
        self.__load_data()

    def get_data(self) -> dict:
        return self.data

    def get_file_path(self, file_key: str, use_backup: bool = False) -> str:
        if use_backup:
            return self.FILES[file_key]["backup"]
        return self.FILES[file_key]["original"]

    def get_generated_file_path(self, file_key: str) -> str:
        return self.GENERATED_FILES[file_key]

    def add_file_to_backup(self, file_path: str, file_key: str):
        """
        Adds a file to the backup dictionary.

        Args:
            file_path (str): The path of the file to be added to the backup.
            file_key (str): The key to be used for the file in the backup dictionary.
        """
        if file_key not in self.FILES:
            self.FILES[file_key] = {
                "original": file_path,
                "backup": file_path + ".bak",
            }
        else:
            raise ValueError(f"Key {file_key} already exists in the files dictionary.")

    def add_generated_file(self, file_path: str, file_key: str):
        """
        Adds a generated file to the list of files to be deleted after compiling.

        Args:
            file_path (str): The file path starting from the project's source directory.
            file_key (str): The key to use for retrieving the file path.
        """
        if file_key not in self.GENERATED_FILES:
            self.GENERATED_FILES[file_key] = file_path
        else:
            raise ValueError(f"Key {file_key} already exists in the generated files dictionary.")

    def save(self):
        """
        Save the data to a JSON file.

        If the `DATA_FILE` attribute is not None and either the data has been modified
        or the file does not exist, the data is saved to a JSON file. The file path is
        determined by the `project_info` attribute.
        """
        if self.DATA_FILE is not None:
            # Check if the data has been modified or the file does not exist
            should_save = self.original_data is not None and self.data != self.original_data
            file_path = os.path.join(self.project_info["dir"], "data", self.DATA_FILE)
            if not os.path.isfile(file_path) or should_save:
                # Convert the data to a JSON string with indentation
                json_str = json.dumps(self.data, indent=4)
                # Write the JSON string to the file
                with open(file_path, 'w') as json_file:
                    json_file.write(json_str)
                # Update the original data and set pending changes flag
                self.original_data = json.loads(json_str)
                self.pending_changes = True
                print(f"Saved {self.DATA_FILE} file.")

    def should_parse_to_c_code(self) -> bool:
        """
        Checks if the data should be parsed into C code.

        Returns:
            bool: True if the data should be parsed into C code, False otherwise.
        """
        if not self.data or not self.original_data:
            return False

        parse_needed = self.pending_changes

        for file in self.FILES:
            original = os.path.join(self.project_info["dir"], "source", self.FILES[file]["original"])
            backup = os.path.join(self.project_info["dir"], "source", self.FILES[file]["backup"])
            if not os.path.isfile(backup) or not os.path.isfile(original):
                parse_needed = True

        return parse_needed

    def try_parse_to_c_code(self):
        """
        Tries to parse the source files to C code.
        If an exception occurs, it attempts to use backup files and parse again.
        """
        try:
            self.parse_to_c_code()
        except Exception as e:
            print(f"Error parsing source files for {self.DATA_FILE}: {e}")
            print("Attempting to use backup files...")
            self.restore_source_code()
            self.parse_to_c_code()
            pass

    @abstractmethod
    def parse_to_c_code(self):
        """
        An abstract method for parsing the source files to C code.

        This method should be overridden by subclasses to parse the source files to C code. Always call the
        superclass method first to ensure that the original source files are backed up before making changes.

        If the data has been modified, it saves the changes. For each file, if a backup file doesn't exist,
        it copies the original file to create one.

        After completing these operations, it sets the `pending_changes` flag to False.
        """
        if self.data != self.original_data:
            self.save()

        for file in self.FILES:
            original = os.path.join(self.project_info["dir"], "source", self.FILES[file]["original"])
            backup = os.path.join(self.project_info["dir"], "source", self.FILES[file]["backup"])
            if not os.path.isfile(backup):
                shutil.copyfile(original, backup)

        self.pending_changes = False

    def restore_source_code(self):
        for file in self.FILES:
            original = os.path.join(self.project_info["dir"], "source", self.FILES[file]["original"])
            backup = os.path.join(self.project_info["dir"], "source", self.FILES[file]["backup"])
            if os.path.isfile(backup):
                shutil.copyfile(backup, original)
                os.remove(backup)
        for file in self.GENERATED_FILES:
            path = os.path.join(self.project_info["dir"], "source", self.GENERATED_FILES[file])
            if os.path.isfile(path):
                os.remove(path)


class SpeciesData(AbstractPokemonData, ABC):
    """
    A class representing species data for Pokemon.

    This class provides methods to retrieve and manipulate species data.

    All data is stored in 'species.json' in the 'data' directory.

    Args:
        project_info (dict): Information about the project.
        parent (Optional): The parent object.

    Attributes:
        DATA_FILE (str): The name of the data file.

    """

    DATA_FILE = "species.json"

    def __init__(self, project_info: dict, parent=None):
        """
        Initializes a new instance of the SpeciesData class.

        Args:
            project_info (dict): Information about the project.
            parent (Optional): The parent object.

        """
        super().__init__(project_info, parent)

    def get_species(self, species: str, form: str = None) -> dict | None:
        """
        Retrieves the dictionary data for a specific species.

        Args:
            species (str): The name of the species.
            form (str, optional): The name of the form.

        Returns:
            dict | None: The data for the species, or None if not found.

        """
        if species in self.data:
            if form is not None and form in self.data[species]["forms"]:
                return self.data[species]["forms"][form]
            return self.data[species]
        return None

    def get_species_data(self, species: str, key: str, form: str = None) -> str | int | dict | list | None:
        """
        Retrieves a specific piece of data for a species.

        Args:
            species (str): The name of the species.
            key (str): The key of the data to retrieve.
            form (str, optional): The name of the form.

        Returns:
            str | int | dict | list | None: The value of the data, or None if not found.

        """
        try:
            if form is None or key == "dex_num":
                value = self.data[species][key]
            else:
                value = self.data[species]["forms"][form][key]
        except KeyError:
            value = None
        return value

    @abstractmethod
    def get_species_info(self, species: str, key: str,
                         form: str = None, index: int = None) -> str | int | dict | list | None:
        """
        Retrieves additional information for a species.

        This method should be implemented by subclasses.

        Args:
            species (str): The name of the species.
            key (str): The key of the information to retrieve.
            form (int, optional): The name of the form.
            index (int, optional: The index of the information.

        Returns:
            str | int | dict | list | None: The additional information, or None if not found.

        """
        pass

    @abstractmethod
    def set_species_info(self, species: str, key: str, value: str | int | dict | list, form: str = None):
        """
        Sets additional information for a species.

        This method should be implemented by subclasses.

        Args:
            species (str): The name of the species.
            key (str): The key of the information to set.
            value (str | int | dict | list): The value of the information.
            form (str, optional): The name of the form.

        """
        pass

    @abstractmethod
    def get_species_ability(self, species: str, ability_index: int, form: str = None) -> str:
        """
        Retrieves the ability of a species.

        This method should be implemented by subclasses.

        Args:
            species (str): The name of the species.
            ability_index (int): The index of the ability.
            form (str, optional): The name of the form.

        Returns:
            str: The ability of the species.

        """
        pass

    @abstractmethod
    def species_info_key_exists(self, species: str, key: str, form: str = None) -> bool:
        """
        Checks if a specific key exists in the species information.

        This method should be implemented by subclasses.

        Args:
            species (str): The name of the species.
            key (str): The key to check.
            form (str, optional): The name of the form.

        Returns:
            bool: True if the key exists, False otherwise.

        """
        pass

    @abstractmethod
    def parse_species_info(self, species_name: str, form_name: str = None) -> str:
        """
        Parses the species information.

        This method should be implemented by subclasses.

        Args:
            species_name (str): The name of the species.
            form_name (str, optional): The name of the form.

        Returns:
            str: The parsed species information.

        """
        pass


class SpeciesGraphics(AbstractPokemonData, ABC):
    """
    A class representing the graphics data for a species of Pokemon.

    This class provides methods to retrieve and manipulate images associated with a Pokemon species.

    All data is stored in 'species_graphics.json' in the 'data' directory.

    Attributes:
        DATA_FILE (str): The name of the data file containing the species graphics information.

    Args:
        project_info (dict): A dictionary containing project information.
        parent (Optional): The parent object. Defaults to None.
    """

    DATA_FILE = "species_graphics.json"

    def __init__(self, project_info: dict, parent=None):
        """
        Initializes a new instance of the SpeciesGraphics class.

        Args:
            project_info (dict): A dictionary containing project information.
            parent (Optional): The parent object. Defaults to None.
        """
        super().__init__(project_info, parent)
        self.project_dir = project_info["dir"]

    def get_image(self, key, index=-1) -> QPixmap | None:
        """
        Retrieves the image associated with the specified key.

        Args:
            key (str): The key of the image to retrieve.
            index (int, optional): The index of the frame to retrieve. Defaults to -1.

        Returns:
            QPixmap | None: The retrieved image as a QPixmap object, or None if the image is not found.
        """
        if key in self.data:
            img_data = self.data[key]
            if "png" in img_data:
                path = os.path.join(self.project_dir, "source", img_data["png"])
                if os.path.exists(path):
                    img = QImage(path)
                    if index == -1:
                        return QPixmap.fromImage(img)
                    else:
                        # Get the image size
                        width = img.width()
                        # Calculate the frame size
                        frame_width = width
                        frame_height = width
                        # Calculate the frame offset
                        frame_offset = index * frame_height
                        # Create a new image
                        new_img = QImage(img.width(), img.height(), QImage.Format_ARGB32)
                        # Copy the frame from the original image to the new image
                        new_img.fill(0)
                        for y in range(frame_height):
                            for x in range(frame_width):
                                new_img.setPixelColor(x, y, img.pixelColor(x, y + frame_offset))
                        return QPixmap.fromImage(new_img)
        return None


class PokemonAbilities(AbstractPokemonData, ABC):
    """
    A class representing the data for Pokémon abilities.

    This class provides functionality for managing and accessing abilities data.

    All data is stored in 'abilities.json' in the 'data' directory.

    Attributes:
        DATA_FILE (str): The name of the JSON file containing abilities data.
    """
    DATA_FILE = "abilities.json"


class PokemonItems(AbstractPokemonData, ABC):
    """
    A class representing the data for Pokémon items.
    
    This class provides functionality for managing and accessing items data.

    All data is stored in 'items.json' in the 'data' directory.

    Attributes:
        DATA_FILE (str): The name of the data file containing the items information.
    """
    DATA_FILE = "items.json"


class PokemonConstants(AbstractPokemonData, ABC):
    """
    A class representing the data for important game constants.
    
    This class provides functionality for managing and accessing game constants data.
    
    All data is stored in 'constants.json' in the 'data' directory.
    
    Attributes:
        DATA_FILE (str): The name of the data file containing the constants information.
    """
    DATA_FILE = "constants.json"


class PokemonStarters(AbstractPokemonData, ABC):
    """
    A class representing the data for the starter Pokémon.
    
    This class provides functionality for managing and accessing starter Pokémon data.
    
    All data is stored in 'starters.json' in the 'data' directory.
    
    Attributes:
        DATA_FILE (str): The name of the data file containing the starters information.
    """
    DATA_FILE = "starters.json"


class PokemonMoves(AbstractPokemonData, ABC):
    """
    A class representing the data for Pokémon moves.

    This class provides functionality for managing and accessing moves data.

    All data is stored in 'moves.json' in the 'data' directory.

    Attributes:
        DATA_FILE (str): The name of the data file containing the moves information.
    """
    DATA_FILE = "moves.json"


class Pokedex(AbstractPokemonData, ABC):
    """
    A class representing the data for the Pokédex.

    This class provides functionality for managing and accessing Pokédex data.

    All data is stored in 'pokedex.json' in the 'data' directory.

    Attributes:
        DATA_FILE (str): The name of the data file containing the Pokédex information.
    """
    DATA_FILE = "pokedex.json"


class PokemonDataManager(ABC):
    """
    A class that manages game data for a PorySuite project.

    This class provides methods to add, retrieve, and manipulate various types of game data, such as species data,
    graphics, abilities, items, constants, starters, moves, and Pokédex information.

    The `PokemonDataManager` class serves as a central hub for accessing and modifying different types of Pokemon data
    within a project.
    """
    def __init__(self, project_info: dict):
        self.project_info = project_info
        self.data = {}
        
    def __add_data_class(self, class_obj: Type, key: str):
        self.data[key] = class_obj(self.project_info, self)

    def add_species_data_class(self, class_obj: Type[SpeciesData]):
        self.__add_data_class(class_obj, "species_data")

    def add_species_graphics_class(self, class_obj: Type[SpeciesGraphics]):
        self.__add_data_class(class_obj, "species_graphics")

    def add_pokemon_abilities_class(self, class_obj: Type[PokemonAbilities]):
        self.__add_data_class(class_obj, "pokemon_abilities")

    def add_pokemon_items_class(self, class_obj: Type[PokemonItems]):
        self.__add_data_class(class_obj, "pokemon_items")

    def add_pokemon_constants_class(self, class_obj: Type[PokemonConstants]):
        self.__add_data_class(class_obj, "pokemon_constants")
    
    def add_pokemon_starters_class(self, class_obj: Type[PokemonStarters]):
        self.__add_data_class(class_obj, "pokemon_starters")
    
    def add_pokemon_moves_class(self, class_obj: Type[PokemonMoves]):
        self.__add_data_class(class_obj, "pokemon_moves")
    
    def add_pokedex_class(self, class_obj: Type[Pokedex]):
        self.__add_data_class(class_obj, "pokedex")

    def save(self):
        for data in self.data:
            self.data[data].save()
        
    def parse_to_c_code(self):
        for data in self.data:
            if self.data[data].should_parse_to_c_code():
                self.data[data].parse_to_c_code()

    def restore_source_code(self):
        for data in self.data:
            self.data[data].restore_source_code()

    def get_pokemon_data(self) -> dict:
        return self.data["species_data"].data

    def get_species(self, species: str, form: str = None) -> dict | None:
        return self.data["species_data"].get_species(species, form)

    def get_species_by_dex_constant(self, dex_constant: str) -> str | None:
        for species in self.data["species_data"].data:
            if self.data["species_data"].data[species]["dex_constant"] == dex_constant:
                return species
        return None

    def get_species_data(self, species: str, key: str, form: str = None) -> str | int | dict | list | None:
        return self.data["species_data"].get_species_data(species, key, form)

    def get_species_info(self, species: str, key: str, form: str = None):
        return self.data["species_data"].get_species_info(species, key, form)

    def set_species_info(self, species: str, key: str, value, form: str = None):
        self.data["species_data"].set_species_info(species, key, value, form)

    def get_species_ability(self, species: str, ability_index: int, form: str = None):
        return self.data["species_data"].get_species_ability(species, ability_index, form)

    def get_species_image(self, species: str, key: str, index: int = -1, form: str = None):
        image_name = self.get_species_info(species, key, form)
        return self.data["species_graphics"].get_image(image_name, index)

    def get_species_image_path(self, species: str, key: str, form: str = None) -> str:
        image_name = self.get_species_info(species, key, form)
        image_url = self.data["species_graphics"].data[image_name]["png"]
        return str(os.path.join(self.project_info["dir"], "source", image_url))

    def species_info_key_exists(self, species: str, key: str, form: str = None) -> bool:
        return self.data["species_data"].species_info_key_exists(species, key, form)

    def get_pokemon_abilities(self) -> dict:
        return self.data["pokemon_abilities"].data

    def get_ability(self, ability: str) -> dict:
        return self.data["pokemon_abilities"].data[ability]

    def get_ability_by_id(self, ability_id: int) -> dict:
        abilities = self.data["pokemon_abilities"].data
        for ability in abilities:
            if abilities[ability]["id"] == ability_id:
                return ability

    def get_ability_data(self, ability: str, key: str) -> str | int:
        return self.data["pokemon_abilities"].data[ability][key]

    def get_ability_data_by_id(self, ability_id: int, key: str) -> str | int:
        abilities = self.data["pokemon_abilities"].data
        for ability in abilities:
            if abilities[ability]["id"] == ability_id:
                return abilities[ability][key]

    def get_pokemon_items(self) -> dict:
        return self.data["pokemon_items"].data

    def get_item(self, item: str) -> dict:
        return self.data["pokemon_items"].data[item]

    def get_item_data(self, item: str, key: str) -> str | int:
        return self.data["pokemon_items"].data[item][key]

    def get_pokemon_constants(self) -> dict:
        return self.data["pokemon_constants"].data

    def get_constant(self, constant: str) -> dict | str | int:
        return self.data["pokemon_constants"].data[constant]

    def get_constant_data(self, constant: str, key: str) -> str | int:
        return self.data["pokemon_constants"].data[constant][key]

    def get_pokemon_starters(self) -> dict:
        return self.data["pokemon_starters"].data

    def get_starter(self, index: int) -> dict:
        return self.data["pokemon_starters"].data[index]

    def get_starter_data(self, index: int, key: str) -> str | int:
        return self.data["pokemon_starters"].data[index][key]

    def set_starter_data(self, index: int, key: str, value: str | int):
        self.data["pokemon_starters"].data[index][key] = value

    def get_pokemon_moves(self) -> dict:
        return self.data["pokemon_moves"].data["moves"]

    def get_move(self, move: str) -> dict:
        return self.data["pokemon_moves"].data["moves"][move]

    def get_move_data(self, move: str, key: str) -> str | int:
        return self.data["pokemon_moves"].data["moves"][move][key]

    def get_move_description(self, move: str) -> str:
        description_var = self.data["pokemon_moves"].data["moves"][move]["description_var"]
        return self.data["pokemon_moves"].data["descriptions"][description_var]

    def set_move_data(self, move: str, key: str, value: str | int | bool):
        self.data["pokemon_moves"].data["moves"][move][key] = value

    def get_national_dex(self) -> list:
        return self.data["pokedex"].data["national_dex"]

    def get_regional_dex(self) -> list:
        return self.data["pokedex"].data["regional_dex"]
