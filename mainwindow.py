import os
import json
import datetime
import platformdirs

from PySide6.QtCore import Signal, Qt, QEvent
from PySide6.QtGui import QFont, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidgetItem, QLabel,
    QProgressBar, QListWidgetItem, QMessageBox
)

import app_util
from docker_integration import DockerUtil
from app_info import APP_NAME, AUTHOR
import pluginmanager as pm
from newproject import NewProject
from exportingwindow import Exporting
from ui.delegates.pokedexitemdelegate import PokedexItemDelegate
from ui.ui_mainwindow import Ui_MainWindow


class MainWindow(QMainWindow):
    """
    The main window of the PorySuite application.

    This class represents the main window of the application and handles the initialization of the user interface,
    loading and saving project data, interfacing with the data extractor/parser plugin, and other related functionality.

    Attributes:
        loadAndSaveProjectSignal (Signal): A signal used to load and save project data.
        logSignal (Signal): A signal used to log messages.
    """
    loadAndSaveProjectSignal = Signal(dict)
    logSignal = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        # Initialize UI
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.logOutput.setFont(QFont("Source Code Pro", 11))

        # Initialize instance variables
        self.project_info = None
        self.source_data = None
        self.plugin = None
        self.docker_util = None
        self.previous_main_tab = self.ui.mainTabs.currentIndex()
        self.previous_selected_species = None
        self.previous_selected_form = None

        # Initialize status bar widgets
        self.statusbar_progressbar = QProgressBar()
        self.statusbar_progressbar.setMaximum(100)
        self.statusbar_progressbar.setMaximumWidth(100)
        self.statusbar_project_label = QLabel("Unknown Project Type")
        self.ui.statusbar.addPermanentWidget(self.statusbar_progressbar, 0)
        self.ui.statusbar.addPermanentWidget(self.statusbar_project_label, 0)

        # Connect signals to slots
        self.loadAndSaveProjectSignal.connect(self.load_save_data)
        self.logSignal.connect(self.log)

        # Install event filters
        self.ui.species_description.installEventFilter(self)
        self.ui.ability1.installEventFilter(self)
        self.ui.ability2.installEventFilter(self)
        self.ui.ability_hidden.installEventFilter(self)
        self.ui.held_item_common.installEventFilter(self)
        self.ui.held_item_rare.installEventFilter(self)
        self.ui.evo_species.installEventFilter(self)
        self.ui.starter1_species.installEventFilter(self)
        self.ui.starter1_item.installEventFilter(self)
        self.ui.starter2_species.installEventFilter(self)
        self.ui.starter2_item.installEventFilter(self)
        self.ui.starter3_species.installEventFilter(self)
        self.ui.starter3_item.installEventFilter(self)

    def load_save_data(self, project_info):
        """
        Loads the save data for the specified project_info and saves the data afterwards.
        Used as a slot for the loadAndSaveProjectSignal.
        
        Parameters:
            project_info: The project information to load the save data for.
        """
        # Check if there are unsaved changes
        if self.isWindowModified():
            # Open dialog asking to save first
            ret = app_util.create_unsaved_changes_dialog(self)
            if ret == QMessageBox.Cancel:
                return
            if ret == QMessageBox.Save:
                self.update_save()

        self.load_data(project_info)
        self.save_data()

    def save_data(self):
        """
        Save the source data and update project information.

        This method saves the source data, updates the date_modified field in the project_info dictionary,
        updates the projects.json file, and saves the local project info in the project.json file.
        It also updates the window title with the project name.

        Parameters:
        - None

        Returns:
        - None
        """
        # Save the source data
        self.source_data.save()

        # Update the date_modified field
        self.project_info["date_modified"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Load the projects.json file
        d_dir = platformdirs.user_data_dir(APP_NAME, AUTHOR)
        p_file = os.path.join(d_dir, "projects.json")
        with open(p_file, "r") as f:
            p = json.load(f)

        # Remove the project from the list if it already exists
        for i in range(len(p["projects"])):
            if p["projects"][i]["dir"] == self.project_info["dir"]:
                p["projects"].pop(i)
                break

        # Create the project info for the projects.json file
        d_dir_project_info = {
            "name": self.project_info["name"],
            "project_name": self.project_info["project_name"],
            "dir": self.project_info["dir"],
            "last_opened": self.project_info["last_opened"],
        }

        # Insert the project info at the beginning of the list
        p["projects"].insert(0, d_dir_project_info)

        # Save the updated projects.json file
        with open(p_file, "w") as f:
            json.dump(p, f, indent=4)

        # Save the local project info in the project.json file
        with open(os.path.join(self.project_info["dir"], "project.json"), "w") as f:
            local_project_info = {
                "name": self.project_info["name"],
                "project_name": self.project_info["project_name"],
                "version": self.project_info["version"],
                "plugin_identifier": self.project_info["plugin_identifier"],
                "plugin_version": self.project_info["plugin_version"],
                "date_created": self.project_info["date_created"],
                "date_modified": self.project_info["date_modified"],
            }
            json.dump(local_project_info, f, indent=4)

        # Update the window title
        self.setWindowTitle(f"PorySuite - {self.project_info['name']}")

        # Reset the unsaved changes flag
        self.setWindowModified(False)

    def parse_data_to_c_code(self):
        """
        Parses the source data and generates C code.
        """
        self.source_data.parse_to_c_code()

    def load_data(self, combined_project_info):
        """
        Loads data for the main window of the PorySuite application.

        Parameters:
            combined_project_info (dict): A dictionary containing the combined project information.

        Returns:
            None
        """
        self.project_info = combined_project_info
        self.setWindowTitle(f"PorySuite - {self.project_info['name']}")
        self.statusbar_project_label.setText(self.project_info["plugin_identifier"])
        self.statusBar().showMessage(f"Loaded project {self.project_info['name']}")

        # Get the plugin and its version
        __plugin, __version = pm.get_plugin(self.project_info["plugin_identifier"], self.project_info["plugin_version"])

        if __plugin is None:
            if __version is not None:
                # Show dialog to update project base
                qm = QMessageBox
                ret = qm.question(
                    self, "Project Update Available",
                    f"The plugin {self.project_info['plugin_identifier']} has a new version {__version}.\n"
                    f"You are currently using version {self.project_info['plugin_version']}.\n"
                    f"You must update your project to continue.\n\n"
                    f"Would you like to update your project to use the latest version?",
                    qm.Yes | qm.No
                )
                if ret == qm.Yes:
                    # Update project base
                    self.statusBar().showMessage(f"Updating project base {self.project_info['plugin_identifier']}...")
                    __plugin, __version = pm.get_plugin(self.project_info["plugin_identifier"], __version)
                    self.project_info["plugin_identifier"] = __version
                    self.statusBar().showMessage(f"Project plugin updated to use {__version}.")
            else:
                # Plugin not found
                qm = QMessageBox
                qm.critical(self, "Plugin Not Found",
                            f"The plugin {self.project_info['plugin_identifier']} was not found.")
                plugins_dir = os.path.join(platformdirs.user_data_dir(APP_NAME, AUTHOR), "plugins")
                if not os.path.exists(plugins_dir):
                    os.makedirs(plugins_dir)
                os.startfile(plugins_dir)
                QApplication.instance().exit(1)
        else:
            if __version.split(".") > self.project_info["plugin_version"].split("."):
                # Show dialog to update plugin
                qm = QMessageBox
                ret = qm.question(
                    self, "Plugin Update Available",
                    f"The plugin {self.project_info['plugin_identifier']} has a new version {__version}.\n"
                    f"You are currently using version {self.project_info['plugin_version']}.\n\n"
                    f"Would you like to update your project to use the latest version?",
                    qm.Yes | qm.No
                )
                if ret == qm.Yes:
                    # Update plugin
                    self.statusBar().showMessage(f"Updating plugin {self.project_info['plugin_identifier']}...")
                    __plugin, __version = pm.get_plugin(self.project_info["plugin_identifier"], __version)
                    self.project_info["plugin_version"] = __version
                    self.statusBar().showMessage(f"Plugin {self.project_info['plugin_identifier']} updated.")
                else:
                    self.statusBar().showMessage(f"Plugin {self.project_info['plugin_identifier']} not updated.")

        self.plugin = __plugin
        self.source_data = self.plugin.create_data_manager(combined_project_info)

        # Set item delegates and fonts for the UI elements
        self.ui.list_pokedex_national.setItemDelegate(PokedexItemDelegate(self.ui.list_pokedex_national))
        self.ui.list_pokedex_national.setFont(QFont("Source Code Pro", 11))
        self.ui.list_pokedex_regional.setItemDelegate(PokedexItemDelegate(self.ui.list_pokedex_regional))
        self.ui.list_pokedex_regional.setFont(QFont("Source Code Pro", 11))
        self.ui.tree_pokemon.setItemDelegate(PokedexItemDelegate(self.ui.tree_pokemon))
        self.ui.tree_pokemon.setFont(QFont("Source Code Pro", 11))
        self.ui.species_description.setFont(QFont("Source Code Pro", 11))

        # Add Pokemon species
        self.ui.tree_pokemon.clear()
        pokemon_data = self.source_data.get_pokemon_data()
        for species in sorted(pokemon_data.keys(), key=lambda x: self.source_data.get_species_data(x, "dex_num")):
            self.add_species(species, self.source_data.get_species_data(species, "forms").keys())

        # Add abilities to ability combo boxes
        abilities = self.source_data.get_pokemon_abilities()
        for ability in sorted(abilities.keys(), key=lambda x: self.source_data.get_ability_data(x, "id")):
            self.ui.ability1.addItem(self.source_data.get_ability_data(ability, "name"), ability)
            self.ui.ability2.addItem(self.source_data.get_ability_data(ability, "name"), ability)
            self.ui.ability_hidden.addItem(self.source_data.get_ability_data(ability, "name"), ability)

        # Add items to item combo boxes
        items = self.source_data.get_pokemon_items()
        for item in items.keys():
            self.ui.held_item_common.addItem(self.source_data.get_item_data(item, "name"), item)
            self.ui.held_item_rare.addItem(self.source_data.get_item_data(item, "name"), item)
            self.ui.starter1_item.addItem(self.source_data.get_item_data(item, "name"), item)
            self.ui.starter2_item.addItem(self.source_data.get_item_data(item, "name"), item)
            self.ui.starter3_item.addItem(self.source_data.get_item_data(item, "name"), item)

        # Add types to type combo boxes
        for poke_type in self.source_data.get_constant("types").keys():
            name = self.source_data.get_constant_data("types", poke_type)["name"]
            # TODO: Add type icons
            self.ui.type1.addItem(name, poke_type)
            self.ui.type2.addItem(name, poke_type)

        # Add egg groups to egg group combo boxes
        for egg_group in self.source_data.get_constant("egg_groups").keys():
            name = self.source_data.get_constant_data("egg_groups", egg_group)["name"]
            self.ui.egg_group_1.addItem(name, egg_group)
            self.ui.egg_group_2.addItem(name, egg_group)

        # Add growth rates to growth rate combo box
        for growth_rate in self.source_data.get_constant("growth_rates").keys():
            name = self.source_data.get_constant_data("growth_rates", growth_rate)["name"]
            self.ui.exp_growth_rate.addItem(name, growth_rate)

        # Add evolution methods to evolution method combo box
        for evolution_method in self.source_data.get_constant("evolution_types").keys():
            name = self.source_data.get_constant_data("evolution_types", evolution_method)["name"]
            self.ui.evo_method.addItem(name, evolution_method)

        # Set starter data
        starter = self.source_data.get_pokemon_starters()
        self.ui.starter1_species.setCurrentIndex(self.ui.starter1_species.findData(starter[0]["species"]))
        self.ui.starter1_level.setValue(starter[0]["level"])
        self.ui.starter1_item.setCurrentIndex(self.ui.starter1_item.findData(starter[0]["item"]))
        self.ui.starter2_species.setCurrentIndex(self.ui.starter2_species.findData(starter[1]["species"]))
        self.ui.starter2_level.setValue(starter[1]["level"])
        self.ui.starter2_item.setCurrentIndex(self.ui.starter2_item.findData(starter[1]["item"]))
        self.ui.starter3_species.setCurrentIndex(self.ui.starter3_species.findData(starter[2]["species"]))
        self.ui.starter3_level.setValue(starter[2]["level"])
        self.ui.starter3_item.setCurrentIndex(self.ui.starter3_item.findData(starter[2]["item"]))

        # Add moves to move combo boxes
        moves = self.source_data.get_pokemon_moves()
        for move in sorted(moves.keys(), key=lambda x: self.source_data.get_move_data(x, "id")):
            self.ui.starter1_move.addItem(self.source_data.get_move_data(move, "name"), move)
            self.ui.starter2_move.addItem(self.source_data.get_move_data(move, "name"), move)
            self.ui.starter3_move.addItem(self.source_data.get_move_data(move, "name"), move)

        # Add species to national dex list
        natdex = self.source_data.get_national_dex()
        for dex_const in natdex:
            species = self.source_data.get_species_by_dex_constant(dex_const)
            if species is not None:
                name = self.source_data.get_species_data(species, "name")
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, dex_const)
                self.ui.list_pokedex_national.addItem(item)
            else:
                item = QListWidgetItem(dex_const + " (Not Used)")
                item.setData(Qt.UserRole, dex_const)
                self.ui.list_pokedex_national.addItem(item)

        # Add species to regional dex list
        regdex = self.source_data.get_regional_dex()
        for dex_const in regdex:
            species = self.source_data.get_species_by_dex_constant(dex_const.replace("HOENN_DEX_", "NATIONAL_DEX_"))
            if species is not None:
                name = self.source_data.get_species_data(species, "name")
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, dex_const)
                self.ui.list_pokedex_regional.addItem(item)
            else:
                item = QListWidgetItem(dex_const + " (Not Used)")
                item.setData(Qt.UserRole, dex_const)
                self.ui.list_pokedex_regional.addItem(item)

        # Setup the DockerUtil
        self.docker_util = DockerUtil(self.project_info)

    def add_species(self, species, forms):
        """
        Adds a species and its forms to the UI tree and dropdown menus.

        Parameters:
        - species (str): The species identifier.
        - forms (list): A list of form identifiers for the species.

        Returns:
        - species_item (QTreeWidgetItem): The added species item in the UI tree.
        """
        species_name = self.source_data.get_species_data(species, "name")
        species_item = QTreeWidgetItem([species_name, species])
        self.ui.tree_pokemon.addTopLevelItem(species_item)
        self.ui.evo_species.addItem(species, species)
        self.ui.starter1_species.addItem(species, species)
        self.ui.starter2_species.addItem(species, species)
        self.ui.starter3_species.addItem(species, species)

        # Add forms as child items and to the dropdown menus
        if len(forms) > 0:
            for form in forms:
                form_name = self.source_data.get_species_data(species, "name", form)
                form_item = QTreeWidgetItem([form_name, form, species])
                species_item.addChild(form_item)
                self.ui.evo_species.addItem("    " + form, form, species)
                self.ui.starter1_species.addItem("    " + form, form, species)
                self.ui.starter2_species.addItem("    " + form, form, species)
                self.ui.starter3_species.addItem("    " + form, form, species)
            species_item.setExpanded(False)

        return species_item

    def update_data(self, species, form=None):
        """
        Update the data displayed in the UI for a given species and form.

        Parameters:
        - species (str): The name of the species.
        - form (str, optional): The form of the species. Defaults to None.

        Returns:
        None
        """
        try:
            # Update species information
            self.ui.species_name.setText(self.source_data.get_species_info(species, "speciesName", form))
            self.ui.dex_num.setText(f"{self.source_data.get_species_data(species, 'dex_num', form):0>{4}}")
            self.ui.species_category.setText(self.source_data.get_species_info(species, "categoryName", form))
            self.ui.species_description.setPlainText(self.source_data.get_species_info(species, "description", form))
            self.ui.base_hp.setValue(self.source_data.get_species_info(species, "baseHP", form))
            self.ui.base_atk.setValue(self.source_data.get_species_info(species, "baseAttack", form))
            self.ui.base_def.setValue(self.source_data.get_species_info(species, "baseDefense", form))
            self.ui.base_speed.setValue(self.source_data.get_species_info(species, "baseSpeed", form))
            self.ui.base_spatk.setValue(self.source_data.get_species_info(species, "baseSpAttack", form))
            self.ui.base_spdef.setValue(self.source_data.get_species_info(species, "baseSpDefense", form))

            # Update types
            types = self.source_data.get_species_info(species, "types", form)
            self.ui.type1.setCurrentIndex(self.source_data.get_constant_data("types", types[0])["value"])
            self.ui.type2.setCurrentIndex(self.source_data.get_constant_data("types", types[1])["value"])

            # Update abilities
            self.ui.ability1.setCurrentIndex(
                self.source_data.get_ability_data(self.source_data.get_species_ability(species, 0, form), "id"))
            self.ui.ability2.setCurrentIndex(
                self.source_data.get_ability_data(self.source_data.get_species_ability(species, 1, form), "id"))
            self.ui.ability_hidden.setCurrentIndex(
                self.source_data.get_ability_data(self.source_data.get_species_ability(species, 2, form), "id"))

            # Update EVs
            self.ui.evs_hp.setValue(self.source_data.get_species_info(species, "evYield_HP", form))
            self.ui.evs_atk.setValue(self.source_data.get_species_info(species, "evYield_Attack", form))
            self.ui.evs_def.setValue(self.source_data.get_species_info(species, "evYield_Defense", form))
            self.ui.evs_speed.setValue(self.source_data.get_species_info(species, "evYield_Speed", form))
            self.ui.evs_spatk.setValue(self.source_data.get_species_info(species, "evYield_SpAttack", form))
            self.ui.evs_spdef.setValue(self.source_data.get_species_info(species, "evYield_SpDefense", form))

            # Update other attributes
            self.ui.catch_rate.setValue(self.source_data.get_species_info(species, "catchRate", form))
            self.ui.exp_yield.setValue(self.source_data.get_species_info(species, "expYield", form))
            self.ui.gender_ratio.setValue(self.source_data.get_species_info(species, "genderRatio", form))
            self.update_gender_ratio(self.source_data.get_species_info(species, "genderRatio", form))
            item_common = self.source_data.get_species_info(species, "itemCommon", form)
            self.ui.held_item_common.setCurrentIndex(self.source_data.get_item_data(item_common, "id"))
            item_rare = self.source_data.get_species_info(species, "itemRare", form)
            self.ui.held_item_rare.setCurrentIndex(self.source_data.get_item_data(item_rare, "id"))
            self.ui.egg_cycles.setValue(self.source_data.get_species_info(species, "eggCycles", form))
            egg_groups = self.source_data.get_species_info(species, "eggGroups", form)
            self.ui.egg_group_1.setCurrentIndex(
                self.source_data.get_constant_data("egg_groups", egg_groups[0])["value"])
            self.ui.egg_group_2.setCurrentIndex(
                self.source_data.get_constant_data("egg_groups", egg_groups[1])["value"])
            growth_rate = self.source_data.get_species_info(species, "growthRate", form)
            growth_rate_index = self.source_data.get_constant_data("growth_rates", growth_rate)["value"]
            self.ui.exp_growth_rate.setCurrentIndex(growth_rate_index)
            self.ui.base_friendship.setValue(self.source_data.get_species_info(species, "friendship", form))
            self.ui.safari_zone_flee_rate.setValue(
                self.source_data.get_species_info(species, "safariZoneFleeRate", form))

            # Update graphics
            front_pic = self.source_data.get_species_image_path(species, "frontPic", form=form)
            if front_pic is not None:
                self.ui.frontPic_0.setStyleSheet(f"background-image: url({front_pic}); background-position: top;")
                self.ui.frontPic_1.setStyleSheet(f"background-image: url({front_pic}); background-position: bottom;")
            back_pic = self.source_data.get_species_image_path(species, "backPic", form=form)
            if back_pic is not None:
                self.ui.backPic.setStyleSheet(f"background-image: url({back_pic}); background-position: center;")

            # Update evolutions
            self.ui.evolutions.clear()
            evolutions = self.source_data.get_species_info(species, "evolutions", form)
            if type(evolutions) is list:
                for evolution in evolutions:
                    method_name = self.source_data.get_constant_data("evolution_types", evolution["method"])["name"]
                    item = QTreeWidgetItem([evolution["targetSpecies"], method_name, str(evolution["param"])])
                    self.ui.evolutions.addTopLevelItem(item)
            self.ui.evolutions.addTopLevelItem(QTreeWidgetItem(["Add New Evolution..."]))

            # Resize all columns to fit the contents
            for i in range(self.ui.evolutions.columnCount()):
                self.ui.evolutions.resizeColumnToContents(i)

            self.ui.tab_pokemon_data.setEnabled(True)
        except TypeError:
            self.ui.tab_pokemon_data.setEnabled(False)

    def update_gender_ratio(self, value):
        """
        Update the gender ratio label based on the given value.

        Args:
            value (int): The value out of 255 representing the gender ratio.

        Returns:
            None
        """
        if value == 0:
            self.ui.gender_ratio_label.setText("Male Only")
        elif value == 254:
            self.ui.gender_ratio_label.setText("Female Only")
        elif value == 255:
            self.ui.gender_ratio_label.setText("Genderless")
        else:
            percent = (value / 256) * 100
            self.ui.gender_ratio_label.setText(f"{percent:.1f}% Female")

    def save_species_data(self, species, form=None):
        """
        Saves the data for a specific species.

        Parameters:
        - species (str): The name of the species.
        - form (str, optional): The form of the species. Defaults to None.

        Returns:
        - bool: True if the data was updated, False otherwise.
        """
        updated = False

        def update_if_needed(attribute, ui_value):
            nonlocal updated
            if self.source_data.get_species_info(species, attribute, form) != ui_value:
                self.source_data.set_species_info(species, attribute, ui_value, form=form)
                updated = True

        # Check and update base stats
        update_if_needed("baseHP", self.ui.base_hp.value())
        update_if_needed("baseAttack", self.ui.base_atk.value())
        update_if_needed("baseDefense", self.ui.base_def.value())
        update_if_needed("baseSpeed", self.ui.base_speed.value())
        update_if_needed("baseSpAttack", self.ui.base_spatk.value())
        update_if_needed("baseSpDefense", self.ui.base_spdef.value())

        # Check and update types
        types = [self.ui.type1.currentData(), self.ui.type2.currentData()]
        update_if_needed("types", types)

        # Check and update abilities
        abilities = [
            str(self.source_data.get_ability(self.ui.ability1.currentData())['id']),
            str(self.source_data.get_ability(self.ui.ability2.currentData())['id']),
            str(self.source_data.get_ability(self.ui.ability_hidden.currentData())['id'])
        ]
        update_if_needed("abilities", abilities)

        # Check and update EV yields
        update_if_needed("evYield_HP", self.ui.evs_hp.value())
        update_if_needed("evYield_Attack", self.ui.evs_atk.value())
        update_if_needed("evYield_Defense", self.ui.evs_def.value())
        update_if_needed("evYield_Speed", self.ui.evs_speed.value())
        update_if_needed("evYield_SpAttack", self.ui.evs_spatk.value())
        update_if_needed("evYield_SpDefense", self.ui.evs_spdef.value())

        # Check and update other attributes
        update_if_needed("catchRate", self.ui.catch_rate.value())
        update_if_needed("expYield", self.ui.exp_yield.value())
        update_if_needed("genderRatio", self.ui.gender_ratio.value())
        update_if_needed("itemCommon", self.ui.held_item_common.currentData())
        update_if_needed("itemRare", self.ui.held_item_rare.currentData())
        update_if_needed("eggCycles", self.ui.egg_cycles.value())

        egg_groups = [self.ui.egg_group_1.currentData(), self.ui.egg_group_2.currentData()]
        update_if_needed("eggGroups", egg_groups)

        update_if_needed("growthRate", self.ui.exp_growth_rate.currentData())
        update_if_needed("friendship", self.ui.base_friendship.value())
        update_if_needed("safariZoneFleeRate", self.ui.safari_zone_flee_rate.value())

        return updated

    def update(self):
        origin = self.sender()
        if origin == self.ui.gender_ratio:
            value = self.ui.gender_ratio.value()
            self.update_gender_ratio(value)

    def update_tree_pokemon(self):
        """
        Updates the tree view with the selected Pokemon's data.
        
        If a single species is selected, it saves the data of the previously selected species (if it exists),
        adds "*" to the displayed name of the previously selected species, and updates the data of the selected Pokemon.
        If a form of a species is selected, it saves the data of the base species, updates the data of the base species
        with the selected form, and updates the tree view with the data of the base species.
        """
        selected_species = self.ui.tree_pokemon.selectedItems()

        # Check if a single species is selected
        if len(selected_species) == 1:
            # Save the data of the previously selected species if it exists
            if self.previous_selected_species is not None:
                updated = self.save_species_data(self.previous_selected_species, form=self.previous_selected_form)
                if updated:
                    # Add "*" to the displayed name of the previously selected species
                    for i in range(self.ui.tree_pokemon.topLevelItemCount()):
                        item = self.ui.tree_pokemon.topLevelItem(i)
                        if item.text(1) == self.previous_selected_species:
                            if item.text(0)[-1] != "*":
                                item.setText(0, item.text(0) + "*")
                                self.setWindowModified(True)
                            break

            # Get the selected Pokemon
            pokemon = selected_species[0].text(1)

            # Check if the Pokemon exists in the source data
            if pokemon in self.source_data.get_pokemon_data():
                self.previous_selected_species = pokemon
                self.previous_selected_form = None
                self.update_data(pokemon)
            else:
                # Get the base species and form of the selected Pokemon
                base_species = selected_species[0].text(2)
                self.previous_selected_species = base_species
                self.previous_selected_form = pokemon
                self.update_data(base_species, pokemon)

    def update_gender_ratio_minus1(self):
        """
        Decreases the gender ratio value by 1 and updates the gender ratio.

        This method retrieves the current value of the gender ratio from the UI,
        substracts 1 from it, and sets the updated value back to the UI. It then calls
        the `update_gender_ratio` method to update the gender ratio label.
        """
        value = max(0, self.ui.gender_ratio.value() - 1)
        self.ui.gender_ratio.setValue(value)
        self.update_gender_ratio(value)
        self.setWindowModified(True)

    def update_gender_ratio_plus1(self):
        """
        Increases the gender ratio value by 1 and updates the gender ratio.

        This method retrieves the current value of the gender ratio from the UI,
        adds 1 to it, and sets the updated value back to the UI. It then calls
        the `update_gender_ratio` method to update the gender ratio label.
        """
        value = min(255, self.ui.gender_ratio.value() + 1)
        self.ui.gender_ratio.setValue(value)
        self.update_gender_ratio(value)
        self.setWindowModified(True)

    def update_evolutions(self):
        """
        Updates the selected evolution of the current species based on the UI input.
        """
        selected_evolution = self.ui.evolutions.selectedItems()

        # If a single evolution is selected
        if len(selected_evolution) == 1:
            species = selected_evolution[0].text(0)
            method = selected_evolution[0].text(1)
            param = selected_evolution[0].text(2)

            # Enable the evolution species, method, and delete button
            self.ui.evo_species.setEnabled(True)
            self.ui.evo_method.setEnabled(True)
            self.ui.evoDeleteButton.setEnabled(True)

            # If "Add New Evolution..." is selected
            if selected_evolution[0].text(0) == "Add New Evolution...":
                self.ui.evo_species.setCurrentIndex(0)
                self.ui.evo_method.setCurrentIndex(0)
                self.ui.evo_param.setEnabled(False)
                self.ui.evo_param.setCurrentIndex(0)
            else:
                # Set the selected species and method in the dropdown menus
                self.ui.evo_species.setCurrentIndex(self.ui.evo_species.findText(species))
                self.ui.evo_method.setCurrentIndex(self.ui.evo_method.findText(method))

        # If no evolution is selected
        elif len(selected_evolution) == 0:
            # Disable the evolution species, method, and delete button
            self.ui.evo_species.setEnabled(False)
            self.ui.evo_species.setCurrentIndex(0)
            self.ui.evo_method.setEnabled(False)
            self.ui.evo_method.setCurrentIndex(0)
            self.ui.evo_param.setEnabled(False)
            self.ui.evo_param.setCurrentIndex(0)
            self.ui.evoDeleteButton.setEnabled(False)

    def update_main_tabs(self):
        """
        Updates source data based on the previous main tab.
        """
        try:
            if self.previous_main_tab == 0:  # Pokedex
                pass
            elif self.previous_main_tab == 1:  # Pokemon
                pass
            elif self.previous_main_tab == 2:  # Items
                pass
            elif self.previous_main_tab == 3:  # Starters
                # Update starter data for each starter
                self.source_data.set_starter_data(0, "species", self.ui.starter1_species.currentData())
                self.source_data.set_starter_data(0, "level", self.ui.starter1_level.value())
                self.source_data.set_starter_data(0, "item", self.ui.starter1_item.currentData())
                self.source_data.set_starter_data(0, "custom_move", self.ui.starter1_move.currentData())

                self.source_data.set_starter_data(1, "species", self.ui.starter2_species.currentData())
                self.source_data.set_starter_data(1, "level", self.ui.starter2_level.value())
                self.source_data.set_starter_data(1, "item", self.ui.starter2_item.currentData())
                self.source_data.set_starter_data(1, "custom_move", self.ui.starter2_move.currentData())

                self.source_data.set_starter_data(2, "species", self.ui.starter3_species.currentData())
                self.source_data.set_starter_data(2, "level", self.ui.starter3_level.value())
                self.source_data.set_starter_data(2, "item", self.ui.starter3_item.currentData())
                self.source_data.set_starter_data(2, "custom_move", self.ui.starter3_move.currentData())
            elif self.previous_main_tab == 4:  # Trainers
                pass
            elif self.previous_main_tab == 5:  # UI
                pass
            elif self.previous_main_tab == 6:  # Config
                pass
        except AttributeError:
            pass

        # Update the previous main tab
        self.previous_main_tab = self.ui.mainTabs.currentIndex()

    def update_action(self):
        """
        Performs an action based on the ui action.
        """
        origin = self.sender()
        if origin == self.ui.actionNew_Project:
            # Open dialog asking to save first
            qm = QMessageBox
            ret = qm.question(self, "Save Project",
                              "Would you like to save your current project before creating a new one?",
                              qm.Yes | qm.No)
            if ret == qm.Yes:
                self.update_save()
            d = NewProject(parent=self)
            d.show()
        elif origin == self.ui.actionExport_to_ROM:
            if self.docker_util is None:
                self.docker_util = DockerUtil(self.project_info)
            # Show dialog with warning message about exporting to ROM file
            msg_box = QMessageBox()
            msg_box.setText("Sharing the compiled GBA ROM file is illegal!")
            msg_box.setInformativeText("This ROM file will contain cheats for debugging. "
                                       "You should only use it for testing purposes.\n\n"
                                       "Use the 'Export to Patch file' option to create a patch file instead.\n\n"
                                       "Do you want to continue?")
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.No)
            msg_box.setEscapeButton(QMessageBox.No)
            ret = msg_box.exec()
            if ret == QMessageBox.Yes:
                # Export source code to ROM
                self.ui.logOutput.clear()
                self.log("Building ROM...")
                exporting_dialog = Exporting(parent=self)
                self.source_data.parse_to_c_code()
                self.docker_util.export_rom(exporting_dialog.logSignal)
                exporting_dialog.exec()
        elif origin == self.ui.actionOpen_in_Terminal:
            if self.docker_util is None:
                self.docker_util = DockerUtil(self.project_info)
            # Open terminal in project directory
            self.docker_util.open_terminal()

    def update_save(self):
        """
        Updates the save data for the previously selected species, saves general data,
        parses data to C code, and removes "*" from the names of modified Pokémon.
        """
        # Save data for the previously selected species
        if self.previous_selected_species is not None:
            self.save_species_data(self.previous_selected_species)

        # Save general data
        self.save_data()

        # Parse data to C code
        self.source_data.parse_to_c_code()

        # Remove "*" from the names of modified Pokemon
        for i in range(self.ui.tree_pokemon.topLevelItemCount()):
            item = self.ui.tree_pokemon.topLevelItem(i)
            if item.text(0)[-1] == "*":
                item.setText(0, item.text(0)[0:-1])

    def eventFilter(self, watched, event):
        """
        Filters and handles events for the specified watched object.

        Parameters:
            watched: The object being watched for events.
            event: The event being filtered.

        Returns:
            bool: True if the event is handled, False otherwise.
        """
        # Handle events on species_description object to limit the number of lines and characters per line
        if watched == self.ui.species_description:
            # Check if the event is a Paste KeySequence
            if event.type() == QEvent.KeyPress or event.type() == QEvent.ShortcutOverride:
                key_event = QKeyEvent(event)
                key_text = key_event.text()
                clipboard = QApplication.clipboard().text()
                clipboard_newline = "\n" in clipboard or "\r" in clipboard
                # Check if the key is Enter, Return, or Paste with newline characters in clipboard
                if key_event.key() == Qt.Key_Enter or key_event.key() == Qt.Key_Return or \
                        (key_event.matches(QKeySequence.Paste) and clipboard_newline):
                    if self.ui.species_description.blockCount() == 4:
                        return True
                # Check if the key is a letter, number, space, or letter with an accent
                elif key_text.isprintable() or key_event.matches(QKeySequence.Paste):
                    # Get selection length
                    cursor = self.ui.species_description.textCursor()
                    selection_length = cursor.selectionEnd() - cursor.selectionStart()
                    # Check if there is no selection and the key is not Backspace or Delete
                    if selection_length == 0 and not key_event.key() == Qt.Key_Backspace \
                            and not key_event.key() == Qt.Key_Delete:
                        # Get the current line from the text cursor
                        text = cursor.block().text()
                        # Check if the line is already at the maximum length
                        if len(text) == 48:
                            if key_event.matches(QKeySequence.Paste):
                                self.ui.statusbar.showMessage("Contents of clipboard are too long to paste.", 5000)
                            return True
                        # Check if pasting the clipboard content will exceed the maximum length
                        elif key_event.matches(QKeySequence.Paste) and len(text) + len(clipboard) >= 48:
                            self.ui.statusbar.showMessage("Contents of clipboard are too long to paste.", 5000)
                            return True
        # Handle events on other watched objects
        elif watched == self.ui.ability1 or watched == self.ui.ability2 or watched == self.ui.ability_hidden \
                or watched == self.ui.held_item_common or watched == self.ui.held_item_rare \
                or watched == self.ui.evo_species or watched == self.ui.starter1_species \
                or watched == self.ui.starter2_species or watched == self.ui.starter3_species \
                or watched == self.ui.starter1_item or watched == self.ui.starter2_item \
                or watched == self.ui.starter3_item:
            if event.type() == QEvent.KeyPress or event.type() == QEvent.ShortcutOverride:
                key_event = QKeyEvent(event)
                # Check if the key is Enter or Return
                if key_event.key() == Qt.Key_Enter or key_event.key() == Qt.Key_Return:
                    # Find closest match to the text in the combo box
                    text = watched.currentText()
                    for i in range(watched.count()):
                        if text.lower() in watched.itemText(i).strip().lower():
                            watched.setCurrentIndex(i)
                            watched.setEditText(watched.itemText(i))
                            break
                    return True
            elif event.type() == QEvent.FocusIn:
                if watched == self.ui.evo_species and watched.currentIndex() == 0:
                    self.ui.evo_species.clearEditText()
        return super().eventFilter(watched, event)

    def log(self, message):
        """
        Appends the given message to the log output widget.

        Parameters:
            message (str): The message to be logged.
        """
        self.ui.logOutput.append(message)

    def try_save_before_closing(self):
        """
        Saves the project before closing the application.

        This method opens a dialog asking to save first, and then closes the application if the user chooses to do so.
        """
        if self.isWindowModified():
            # Open dialog asking to save first
            ret = app_util.create_unsaved_changes_dialog(
                self, "You have unsaved changes. Would you like to save before exiting?"
            )
            if ret == QMessageBox.Save:
                self.update_save()
            return ret != QMessageBox.Cancel
        return True

    def closeEvent(self, event):
        """
        Closes the application.

        This method is called when the application is about to close.
        It calls the save_before_closing method to save the project before closing the application.
        """
        if self.try_save_before_closing():
            event.accept()
        else:
            event.ignore()
