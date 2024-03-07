from typing import override
from plugin_abstract import pokemon_data
from plugin_abstract.pokemon_data import ReadSourceFile, WriteSourceFile
from plugins import pokeemerald_expansion as pee


class SpeciesData(pokemon_data.SpeciesData):
    """
    A class that represents the data for a species of Pokemon.

    This class provides methods for retrieving and setting information about a species, as well as
    processing generation operations and values. It also includes a method for parsing the species
    information for C code generation.

    Attributes:
        GEN_CONSTANTS (dict): A dictionary mapping generation constants to their corresponding values.
    """
    GEN_CONSTANTS = {
        "GEN_1": 0,
        "GEN_2": 1,
        "GEN_3": 2,
        "GEN_4": 3,
        "GEN_5": 4,
        "GEN_6": 5,
        "GEN_7": 6,
        "GEN_8": 7,
        "GEN_9": 8,
        "GEN_LATEST": 8,
    }

    def __init__(self, project_info, parent=None):
        # Files to back up must be added first
        # These are source files that will be changed with new data
        self.add_file_to_backup("src/data/pokemon/species_info.h", file_key="SPECIES_INFO_H")

        # Files to generate must be added second
        # These are new source files that did not exist before
        self.add_generated_file("src/data/pokemon/species_info/pory_species.h", file_key="PORY_SPECIES_H")

        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.SpeciesDataExtractor)

    def process_gen_operation(self, operation: dict) -> any:
        """
        Process the given operation of GEN_CONSTANTS and return the result.

        Args:
            operation (dict): The operation to be processed.

        Returns:
            any: The result of the operation.
        """
        if "param1" not in operation:
            return operation

        value = 0
        condition = operation["condition"]
        if condition == ">=":
            if self.GEN_CONSTANTS[operation["param1"]] >= self.GEN_CONSTANTS[operation["param2"]]:
                value = operation["true_value"]
            else:
                value = operation["false_value"]
        elif condition == "==":
            if self.GEN_CONSTANTS[operation["param1"]] == self.GEN_CONSTANTS[operation["param2"]]:
                value = operation["true_value"]
            else:
                value = operation["false_value"]
        elif condition == "<=":
            if self.GEN_CONSTANTS[operation["param1"]] <= self.GEN_CONSTANTS[operation["param2"]]:
                value = operation["true_value"]
            else:
                value = operation["false_value"]
        try:
            value = int(value)
        except ValueError:
            pass
        return value

    def process_value(self, value: dict | list) -> any:
        """
        Process the given value by applying the `process_gen_operation` method to each element in a list,
        or directly to the value if it is a dictionary.

        Args:
            value (list or dict): The value to be processed.

        Returns:
            The processed value.
        """
        if isinstance(value, list):
            for i in range(len(value)):
                if isinstance(value[i], dict):
                    value[i] = self.process_gen_operation(value[i])
        elif isinstance(value, dict):
            value = self.process_gen_operation(value)

        return value

    @override
    def get_species_info(self, species, key, form=None, index=None):
        """
        Retrieve information about a species.

        Args:
            species (str): The name of the species.
            key (str): The key of the information to retrieve.
            form (str, optional): The form of the species. Defaults to None.
            index (int, optional): The index of the value to retrieve if the value is a list. Defaults to None.

        Returns:
            The requested information about the species.
        """
        try:
            if form is None:
                value = self.data[species]["species_info"][key]
            else:
                value = self.data[species]["forms"][form]["species_info"][key]

            if isinstance(value, list) or isinstance(value, dict):
                value = self.process_value(value)

        except KeyError:
            if key.startswith("item"):
                value = "ITEM_NONE"
            elif key.startswith("description"):
                value = ""
            else:
                value = 0

        if index is not None and isinstance(value, list):
            try:
                value = value[index]
            except (TypeError, IndexError):
                value = 0

        return value

    @override
    def set_species_info(self, species, key, value, form=None):
        """
        Sets the information of a species or form.

        Overrides abstract method in the parent class.

        Args:
            species (str): The species name.
            key (str): The key of the information to be set.
            value (any): The value to be set.
            form (str, optional): The form name. Defaults to None.

        Returns:
            None
        """
        if form is None:
            self.data[species]["species_info"][key] = value
        else:
            self.data[species]["forms"][form]["species_info"][key] = value

    @override
    def get_species_ability(self, species, ability_index, form=None) -> str:
        """
        Retrieves the ability of a species at a given ability index.

        Args:
            species (str): The species of the Pokemon.
            ability_index (int): The index of the ability.
            form (str, optional): The form of the Pokemon. Defaults to None.

        Returns:
            str: The ability of the species at the given ability index.
        """
        if form is None:
            species_info = self.data.get(species, {}).get("species_info", {})
        else:
            species_info = self.data.get(species, {}).get("forms", {}).get(form, {}).get("species_info", {})

        abilities = species_info.get("abilities", [])
        try:
            ability_value = abilities[ability_index]
        except IndexError:
            ability_value = "ABILITY_NONE"

        try:
            index = int(ability_value)
            if self.parent is not None:
                ability_value = self.parent.get_ability_by_id(index)
        except ValueError:
            pass

        return ability_value

    @override
    def species_info_key_exists(self, species, key, form=None):
        """
        Check if a specific key exists in the species_info dictionary for a given species and form.

        Args:
            species (str): The species of the Pokemon.
            key (str): The key to check for existence in the species_info dictionary.
            form (str, optional): The form of the Pokemon. Defaults to None.

        Returns:
            bool: True if the key exists in the species_info dictionary, False otherwise.
        """
        if form is None:
            species_info = self.data.get(species, {}).get("species_info", {})
        else:
            species_info = self.data.get(species, {}).get("forms", {}).get(form, {}).get("species_info", {})

        return key in species_info

    @override
    def parse_species_info(self, species_name, form_name=None):
        """
        Parses the species information for a given species and form.

        Args:
            species_name (str): The name of the species.
            form_name (str, optional): The name of the form. Defaults to None.

        Returns:
            str: The formatted C code for the species information.
        """

        def get(key, index=None):
            return self.get_species_info(species_name, key, form=form_name, index=index)

        if form_name is not None:
            species_constant = form_name
        else:
            species_constant = species_name

        # Split the species description into lines and format them for C code
        species_description = get("description").split("\n")
        species_description = [f'{" " * 12}"{line}' for line in species_description]
        species_description = "COMPOUND_STRING(\n" + "\\n\"\n".join(species_description) + "\")"

        # Get the evolution data and format it for C code
        evolutions = get("evolutions")
        if isinstance(evolutions, list):
            evolutions = ("EVOLUTION(" +
                          (", ".join([f"{{ {evo['method']}, {evo['param']}, {evo['targetSpecies']} }}"
                                      for evo in evolutions])) + ")")
        else:
            evolutions = 0

        code = f'''
    [{species_constant}] =
    {{
        .baseHP = {get("baseHP")},
        .baseAttack = {get("baseAttack")},
        .baseDefense = {get("baseDefense")},
        .baseSpeed = {get("baseSpeed")},
        .baseSpAttack = {get("baseSpAttack")},
        .baseSpDefense = {get("baseSpDefense")},
        .types = {{ {get("types", 0)}, {get("types", 1)} }},
        .catchRate = {get("catchRate")},
        .expYield = {get("expYield")},
        .evYield_HP = {get("evYield_HP")},
        .evYield_Attack = {get("evYield_Attack")},
        .evYield_Defense = {get("evYield_Defense")},
        .evYield_Speed = {get("evYield_Speed")},
        .evYield_SpAttack = {get("evYield_SpAttack")},
        .evYield_SpDefense = {get("evYield_SpDefense")},
        .itemCommon = {get("itemCommon")},
        .itemRare = {get("itemRare")},
        .genderRatio = {get("genderRatio")},
        .eggCycles = {get("eggCycles")},
        .friendship = {get("friendship")},
        .growthRate = {get("growthRate")},
        .eggGroups = {{ {get("eggGroups", 0)}, {get("eggGroups", 1)} }},
        .abilities = {{ {get("abilities", 0)}, {get("abilities", 1)}, {get("abilities", 2)} }},
        .safariZoneFleeRate = {get("safariZoneFleeRate")},
        .categoryName = _("{get("categoryName")}"),
        .speciesName = _("{get("speciesName")}"),
        .cryId = {get("cryId")},
        .natDexNum = {get("natDexNum")},
        .height = {get("height")},
        .weight = {get("weight")},
        .pokemonScale = {get("pokemonScale")},
        .pokemonOffset = {get("pokemonOffset")},
        .trainerScale = {get("trainerScale")},
        .trainerOffset = {get("trainerOffset")},
        .description = {species_description},
        .bodyColor = {get("bodyColor")},
        .noFlip = {get("noFlip")},
        .frontPic = {get("frontPic")}, .frontPicSize = MON_COORDS_SIZE({get("frontPicSize", 0)}, {get("frontPicSize", 1)}),
        .frontPicFemale = {get("frontPicFemale")},
        .frontPicSizeFemale = MON_COORDS_SIZE({get("frontPicSizeFemale", 0)}, {get("frontPicSizeFemale", 1)}),
        .frontPicYOffset = {get("frontPicYOffset")},
        .frontAnimFrames = {get("frontAnimFrames")},
        .frontAnimId = {get("frontAnimId")},
        .enemyMonElevation = {get("enemyMonElevation")},
        .frontAnimDelay = {get("frontAnimDelay")},
        .backPic = {get("backPic")}, .backPicSize = MON_COORDS_SIZE({get("backPicSize", 0)}, {get("backPicSize", 1)}),
        .backPicFemale = {get("backPicFemale")},
        .backPicSizeFemale = MON_COORDS_SIZE({get("backPicSizeFemale", 0)}, {get("backPicSizeFemale", 1)}),
        .backPicYOffset = {get("backPicYOffset")},
        .backAnimId = {get("backAnimId")},
        .palette = {get("palette")}, .shinyPalette = {get("shinyPalette")},
        .paletteFemale = {get("paletteFemale")}, .shinyPaletteFemale = {get("shinyPaletteFemale")},
        .iconSprite = {get("iconSprite")},
        .iconSpriteFemale = {get("iconSpriteFemale")},
        .iconPalIndex = {get("iconPalIndex")},
        .iconPalIndexFemale = {get("iconPalIndexFemale")},
        .footprint = {get("footprint")},
        .levelUpLearnset = {get("levelUpLearnset")}, .teachableLearnset = {get("teachableLearnset")},
        .evolutions = {evolutions},
        .formSpeciesIdTable = {get("formSpeciesIdTable")},
        .formChangeTable = {get("formChangeTable")},
        .isLegendary = {get("isLegendary")},
        .isMythical = {get("isMythical")},
        .isUltraBeast = {get("isUltraBeast")},
        .isParadoxForm = {get("isParadoxForm")},
        .isMegaEvolution = {get("isMegaEvolution")},
        .isPrimalReversion = {get("isPrimalReversion")},
        .isUltraBurst = {get("isUltraBurst")},
        .isGigantamax = {get("isGigantamax")},
        .isAlolanForm = {get("isAlolanForm")},
        .isGalarianForm = {get("isGalarianForm")},
        .isHisuianForm = {get("isHisuianForm")},
        .isPaldeanForm = {get("isPaldeanForm")},
        .cannotBeTraded = {get("cannotBeTraded")},
        .allPerfectIVs = {get("allPerfectIVs")},
    }},
        '''
        return code

    @override
    def parse_to_c_code(self):
        """
        Parses the data into C code format and writes it to the appropriate files.

        This method reads the contents of the file "SPECIES_INFO_H" and inserts an include statement
        for "species_info/pory_species.h" if it doesn't already exist. It then writes the modified
        contents back to the file.

        It also generates C code for each species and form in the data and writes it to the files
        "SPECIES_INFO_H" and "PORY_SPECIES_H" respectively.

        Returns:
            None
        """
        super().parse_to_c_code()

        lines = []
        with ReadSourceFile(self.project_info, self.get_file_path("SPECIES_INFO_H", True)) as f:
            include_inserted = False
            for line in f:
                if line.strip().startswith("#include \"species_info/gen_"):
                    if not include_inserted:
                        include_inserted = True
                        lines.append("    #include \"species_info/pory_species.h\"\n")
                    continue
                lines.append(line)

        # Open species_info.h and write the lines
        with WriteSourceFile(self.project_info, self.get_file_path("SPECIES_INFO_H")) as f:
            f.writelines(lines)

        # Open species_info/pory_species.h and write the lines
        with WriteSourceFile(self.project_info, self.get_generated_file_path("PORY_SPECIES_H")) as f:
            lines = []
            for species in self.data:
                # Write the species info for each species and form
                if self.data[species]["species_info"]:
                    lines.append(self.parse_species_info(species))
                for form in self.data[species]["forms"]:
                    lines.append(self.parse_species_info(species, form_name=form))
            lines.insert(0, "#ifdef __INTELLISENSE__\nconst struct SpeciesInfo gSpeciesInfoDecompUtil[] =\n{\n#endif\n")
            lines.append("#ifdef __INTELLISENSE__\n};\n#endif")
            f.writelines(lines)


class SpeciesGraphics(pokemon_data.SpeciesGraphics):
    """
    A class that represents the graphics data for a species of Pokemon.

    Not yet fully implemented.
    """

    def __init__(self, project_info, parent=None):
        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.SpeciesGraphicsDataExtractor)

    @override
    def parse_to_c_code(self):
        super().parse_to_c_code()
        ...


class PokemonAbilities(pokemon_data.PokemonAbilities):
    """
    A class that represents the abilities data for Pokemon.

    Not yet fully implemented.
    """

    def __init__(self, project_info, parent=None):
        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.AbilitiesDataExtractor)

    @override
    def parse_to_c_code(self):
        super().parse_to_c_code()
        ...


class PokemonItems(pokemon_data.PokemonItems):
    """
    A class that represents items data.

    Not yet fully implemented.
    """

    def __init__(self, project_info, parent=None):
        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.ItemsDataExtractor)

    @override
    def parse_to_c_code(self):
        super().parse_to_c_code()
        ...


class PokemonConstants(pokemon_data.PokemonConstants):
    """
    A class that represents general constants data in the game.

    Not yet fully implemented.
    """

    def __init__(self, project_info, parent=None):
        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.PokemonConstantsExtractor)

    @override
    def parse_to_c_code(self):
        super().parse_to_c_code()
        ...


class PokemonStarters(pokemon_data.PokemonStarters):
    """
    A class that represents the starter Pokemon data.

    This class provides methods for retrieving and setting information about the starter Pokemon.
    The location of this data is in the files "src/starter_choose.c" and "src/battle_setup.c",
    and the data is parsed and updated in these files.
    """

    def __init__(self, project_info, parent=None):
        # Files to back up must be added first
        # These are source files that will be changed with new data
        self.add_file_to_backup("src/starter_choose.c", file_key="STARTER_CHOOSE_C")

        # Files to generate must be added second
        # These are new source files that did not exist before
        self.add_file_to_backup("src/battle_setup.c", file_key="BATTLE_SETUP_C")

        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.StartersDataExtractor)

    @override
    def parse_to_c_code(self):
        """
        Parses the Pokemon data into C code.

        This method calls the base class's `parse_to_c_code` method and then updates the starter choose C file
        and the battle setup C file.
        """
        super().parse_to_c_code()
        self.__update_starter_choose_c_file()
        self.__update_battle_setup_c_file()

    def __update_starter_choose_c_file(self):
        """
        Updates the STARTER_CHOOSE_C file with new starter data.

        Reads the existing STARTER_CHOOSE_C file, finds the starter array, and replaces it with the new data.
        The new data is obtained from the 'data' attribute of the class.
        """
        starter_choose_lines = []
        with ReadSourceFile(self.project_info, self.get_file_path("STARTER_CHOOSE_C", True)) as f:
            inside_starter_array = False
            for line in f:
                if "const u16 sStarterMon" in line:
                    inside_starter_array = True
                    starter_choose_lines.append(line)
                elif inside_starter_array:
                    if "}" in line:
                        inside_starter_array = False
                    elif "{" in line:
                        # Replace the starter array with the new data
                        starter_lines = [f"    {starter['species']},\n" for starter in self.data]
                        starter_choose_lines.append("{\n")
                        starter_choose_lines.extend(starter_lines)
                if not inside_starter_array:
                    starter_choose_lines.append(line)

        with WriteSourceFile(self.project_info, self.get_file_path("STARTER_CHOOSE_C")) as f:
            f.writelines(starter_choose_lines)

    def __update_battle_setup_c_file(self):
        """
        Updates the battle setup C file by modifying specific lines of code.
        This method reads the existing file, makes the necessary modifications,
        and writes the updated lines back to the file.
        """
        battle_setup_lines = []
        with ReadSourceFile(self.project_info, self.get_file_path("BATTLE_SETUP_C", True)) as f:
            inside_give_starter_function = False
            for line in f:
                if line.startswith("static void CB2_GiveStarter(void)"):
                    inside_give_starter_function = True
                    battle_setup_lines.append(line)
                    continue
                if inside_give_starter_function:
                    if line.startswith("}"):
                        inside_give_starter_function = False
                        battle_setup_lines.append(line)
                        continue
                    elif "u16 starterMon" in line:
                        if any(starter["ability_num"] != -1 for starter in self.data):
                            line += "\n    u16 abilityNum;\n"
                    elif "ScriptGiveMon(starterMon" in line:
                        line = self.__generate_switch_case_code()
                if not inside_give_starter_function:
                    battle_setup_lines.append(line)

        with WriteSourceFile(self.project_info, self.get_file_path("BATTLE_SETUP_C")) as f:
            f.writelines(battle_setup_lines)

    def __generate_switch_case_code(self):
        """
        Generates the switch case code for assigning starter Pokémon based on the value of gSpecialVar_Result.

        Returns:
            str: The generated switch case code.
        """
        switch_case_code = '    switch(gSpecialVar_Result)\n    {\n'
        for i, starter in enumerate(self.data):
            switch_case_code += f'        case {i}: // {starter["species"]}\n' \
                                f'            ScriptGiveMon(starterMon, {starter["level"]}, {starter["item"]}, 0, 0, 0);\n'
            if starter["custom_move"] != "MOVE_NONE":
                switch_case_code += f'            GiveMoveToMon(&gPlayerParty[0], {starter["custom_move"]});\n'
            if starter["ability_num"] != -1:
                switch_case_code += f'            abilityNum = {starter["ability_num"]};\n'
                switch_case_code += f'            SetMonData(&gPlayerParty[0], MON_DATA_ABILITY_NUM, &abilityNum);\n'
            switch_case_code += f'            break;\n'
        switch_case_code += '    }\n'
        return switch_case_code


class PokemonMoves(pokemon_data.PokemonMoves):
    def __init__(self, project_info, parent=None):
        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.MovesDataExtractor)

    @override
    def parse_to_c_code(self):
        super().parse_to_c_code()
        ...


class Pokedex(pokemon_data.Pokedex):
    def __init__(self, project_info, parent=None):
        # Files to back up must be added first
        # These are source files that will be changed with new data
        self.add_file_to_backup("include/constants/pokedex.h", file_key="POKEDEX_H")

        # Must call the parent class' __init__ method after all files have been added
        super().__init__(project_info, parent)

        # Instantiate your corresponding extractor class
        self.instantiate_extractor(pee.PokedexDataExtractor)

    @override
    def parse_to_c_code(self):
        super().parse_to_c_code()
        ...


class PokemonDataManager(pokemon_data.PokemonDataManager):
    """
    A class that manages the data for Pokemon.
    
    This class holds instances of each of the data classes for Pokemon and other info
    in the game. This is how the UI interfaces with the plugin's data classes.
    """

    def __init__(self, project_info):
        # Must call the parent class' __init__ method before adding your data classes
        super().__init__(project_info)

        # Add your data classes
        self.add_species_data_class(SpeciesData)
        self.add_species_graphics_class(SpeciesGraphics)
        self.add_pokemon_abilities_class(PokemonAbilities)
        self.add_pokemon_items_class(PokemonItems)
        self.add_pokemon_constants_class(PokemonConstants)
        self.add_pokemon_starters_class(PokemonStarters)
        self.add_pokemon_moves_class(PokemonMoves)
        self.add_pokedex_class(Pokedex)
