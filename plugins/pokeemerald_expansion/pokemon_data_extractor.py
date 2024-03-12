import os
import re

from plugin_abstract.pokemon_data_extractor import PokemonDataExtractor
from plugin_abstract.pokemon_data import ReadSourceFile


class SpeciesDataExtractor(PokemonDataExtractor):
    """
    A class used to extract species data from the source files.
    """

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        def parse_types(val):
            return [t.strip() for t in val.strip("{}").split(",")]

        def parse_gender_ratio(val):
            if isinstance(val, int):
                return val
            elif "min" in val:
                match = re.match(r'min\(254, \(\((.*) \* 255\) \/ 100\)\)', val)
                return int(round((float(match.group(1)) * 255) / 100))
            elif val == "MON_MALE":
                return 0
            elif val == "MON_FEMALE":
                return 254
            elif val == "MON_GENDERLESS":
                return 255

        def parse_egg_groups(val):
            return [eg.strip() for eg in val.strip("{}").split(",")]

        def parse_abilities(val):
            return [a.strip() for a in val.strip("{}").split(",")]

        def parse_species_name(val):
            return re.sub(r'_\("(.*)"\)', r'\1', val)

        def parse_category_name(val):
            return re.sub(r'_\("(.*)"\)', r'\1', val)

        def parse_description(val):
            return val.replace("\\n", "\n")

        def parse_flags(val):
            return [f.strip() for f in val.split(" | ")]

        def parse_pic_size(val):
            match = re.match(r'MON_COORDS_SIZE\((.*), (.*)\)', val)
            return match.groups()

        def parse_evolutions(val):
            if isinstance(val, str):
                evos = re.sub(r'\(const struct Evolution\[\]\)\s*\{\s*\{(.*)\},\s*\}', r'\1', val).strip()
                evos = evos.split("}, {")
                result = []
                for evo in evos:
                    evo = evo.strip().split(", ")
                    method = evo[0].strip()
                    if len(evo) == 3:
                        try:
                            param = int(evo[1].strip())
                        except ValueError:
                            param = evo[1].strip()
                        target_species = evo[2].strip()
                        evo_dict = {
                            "method": method,
                            "param": param,
                            "targetSpecies": target_species,
                        }
                    else:
                        if method == "EVOLUTIONS_END":
                            continue
                        evo_dict = {
                            "method": evo[0].strip(),
                            "param": None,
                            "targetSpecies": None,
                        }
                    result.append(evo_dict)
                return result
            return val

        def parse_conditionals(val):
            # Check if the value is a list or tuple
            if isinstance(val, list):
                value_list = val
            elif isinstance(val, tuple):
                value_list = list(val)
            else:
                value_list = [val]

            # Iterate through each value in the list
            for i in range(len(value_list)):
                # Check if the value is a string
                if not isinstance(value_list[i], str):
                    continue

                # Use regex to match conditional expressions
                matches = re.findall(r'(?:\b|\()\s*(.+?)\s+(.+?)\s+(.+?)\s+(\?)\s+(.+?)\s+(:)\s+(.+?)(?:\)|$)',
                                     value_list[i])

                # If there is a single match, extract the parameters
                if len(matches) == 1:
                    match = matches[0]
                    param1, condition, param2, _, true_value, _, false_value = match
                    to_add = 0
                    to_subtract = 0

                    # Check if there is a value to add or subtract
                    if value_list[i].split(" ")[-2] == "+":
                        to_add = int(value_list[i].split(" ")[-1])
                    elif value_list[i].split(" ")[-2] == "-":
                        to_subtract = int(value_list[i].split(" ")[-1])

                    # Create a dictionary of parameters
                    parameters = {
                        "param1": param1,
                        "condition": condition,
                        "param2": param2,
                        "true_value": true_value,
                        "false_value": false_value,
                        "to_add": to_add,
                        "to_subtract": to_subtract
                    }

                    # Update the value with the parameters
                    if isinstance(val, str):
                        val = parameters
                    else:
                        value_list[i] = parameters

            # Return the updated value
            if isinstance(val, list) or isinstance(val, tuple):
                return value_list
            return val

        # Dictionary of parsers
        parsers = {
            "types": parse_types,
            "genderRatio": parse_gender_ratio,
            "friendship": lambda val: 70 if val == "STANDARD_FRIENDSHIP" else val,
            "eggGroups": parse_egg_groups,
            "abilities": parse_abilities,
            "speciesName": parse_species_name,
            "categoryName": parse_category_name,
            "description": parse_description,
            "flags": parse_flags,
            "frontPicSize": parse_pic_size,
            "backPicSize": parse_pic_size,
            "frontPicSizeFemale": parse_pic_size,
            "backPicSizeFemale": parse_pic_size,
            "evolutions": parse_evolutions,
        }

        try:
            value = int(value)
        except ValueError:
            pass
        if key in parsers:
            value = parse_conditionals(parsers[key](value))

        return key, value

    def extract_data(self) -> dict:
        # Preprocess files
        self.docker_util.preprocess_c_file(
            "src/data/pokemon/species_info.h",
            ["include/config/pokemon.h"]
        )

        # Parse Species dex numbers
        # with open(os.path.join(self.project_dir, "source", "include", "constants", "pokedex.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/include/constants/pokedex.h") as file:
            lines = file.readlines()

        dex_num = 1
        pokemon_species = {}
        array_found = False
        for line in lines:
            if "NATIONAL_DEX_NONE" in line:
                array_found = True
                continue
            if not array_found:
                continue
            if "}" in line:
                break
            # Match the species name
            match = re.match(r'\s*NATIONAL_DEX_(.*?),', line)
            if match:
                species = match.group(1)
                if species.isnumeric():
                    continue
                species_name = species.replace("_", " ").strip().title()
                dex_constant = "NATIONAL_DEX_" + species
                species_data = {
                    "name": species_name,
                    "dex_num": dex_num,
                    "dex_constant": dex_constant,
                    "forms": {},
                    "species_info": {}
                }
                dex_num += 1
                pokemon_species["SPECIES_" + species] = species_data

        # Parse species info
        # with open(os.path.join(self.project_dir, "processed", "src", "data", "pokemon", "species_info.h"), 'r', encoding="utf-8", errors='ignore') as file:
        with ReadSourceFile(self.project_info, "processed/src/data/pokemon/species_info.h") as file:
            lines = file.readlines()

        current_species = None
        species_info = {}
        is_compound_string = False
        compound_string = ""
        pokedex_entries = {}
        current_pokedex_entry = None
        for line in lines:
            if current_pokedex_entry is not None:
                if line.strip().endswith(");"):
                    pokedex_entries[current_pokedex_entry] += line.strip().rstrip(");").strip("\"")
                    current_pokedex_entry = None
                else:
                    pokedex_entries[current_pokedex_entry] += line.strip().strip("\"")
                continue
            match = re.match(r'\s*const u8 g(.+?)PokedexText\[\] = _\(', line)
            if match:
                current_pokedex_entry = f'g{match.group(1)}PokedexText'
                pokedex_entries[current_pokedex_entry] = ""
                continue
            match = re.match(r'\s*\[(SPECIES_.+?)\]\s=\s*', line)
            if match:
                if current_species is not None:
                    if current_species in pokemon_species:
                        pokemon_species[current_species]["species_info"] = species_info
                        pokemon_species[current_species]["name"] = species_info["speciesName"]
                    else:
                        base_species = "SPECIES_" + species_info["natDexNum"].replace("NATIONAL_DEX_", "")
                        if base_species in pokemon_species:
                            form_name = (current_species.replace(base_species, "")
                                         .replace(base_species, "")
                                         .replace("_", " ").strip().title())
                            pokemon_species[base_species]["forms"][current_species] = {
                                "name": form_name, "species_info": species_info
                            }
                    species_info = {}
                current_species = match.group(1)
                if current_species == "SPECIES_NONE" or current_species == "SPECIES_EGG":
                    current_species = None
                    species_info = {}
                if not line.endswith("},\n"):
                    continue
            if current_species is not None:
                if is_compound_string:
                    compound_string += line.strip().strip("\"")
                    if compound_string.endswith("),"):
                        is_compound_string = False
                        compound_string = compound_string.rstrip("),").strip("\"")
                        key, value = self.parse_value_by_key("description", compound_string)
                        species_info[key] = value
                        compound_string = ""
                    continue
                values = line.strip().lstrip(".").rstrip(",").split(", .")
                if len(values) > 1:
                    match = re.match(r'\s*\[(SPECIES_.+?)\]\s=\s*\{.*', line)
                    if match:
                        values[0] = values[0].split("{")[1].strip()
                        values[-1] = values[-1].rstrip(", }")
                    for v in values:
                        key = v.split(" = ")[0].strip()
                        value = v.split(" = ")[1].strip()
                        if key == "description" and value in pokedex_entries:
                            value = pokedex_entries[value]
                        key, value = self.parse_value_by_key(key, value)
                        species_info[key] = value
                else:
                    if line.strip().endswith("COMPOUND_STRING("):
                        is_compound_string = True
                        continue
                    if len(values) == 0 or "=" not in values[0]:
                        continue
                    key = values[0].split(" = ")[0].strip().lstrip(".")
                    value = values[0].split(" = ")[1].strip().rstrip(",")
                    if key == "description" and value in pokedex_entries:
                        value = pokedex_entries[value]
                    key, value = self.parse_value_by_key(key, value)
                    species_info[key] = value

        return pokemon_species


class SpeciesGraphicsDataExtractor(PokemonDataExtractor):
    """
    A class used to extract species graphics data from the source files.
    """

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        return key, value

    def extract_data(self) -> dict:
        # with open(os.path.join(self.project_dir, "source", "src", "data", "graphics", "pokemon.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/src/data/graphics/pokemon.h") as file:
            lines = file.readlines()

        species_graphics = {}
        for line in lines:
            if line.strip().startswith("const"):
                data = line.strip().split(" ")
                if len(data) == 5:
                    variable_name = data[2].strip("[]")
                    image_path = re.sub(r'INCBIN_U32\("(.*)"\);', r'\1', data[4]).split(".")[0]
                    # Remove file extension
                    png_path = image_path.split(".")[0] + ".png"
                    species_graphics[variable_name] = {"path": image_path, "png": png_path}

        return species_graphics


class AbilitiesDataExtractor(PokemonDataExtractor):
    """
    A class used to extract abilities data from the source files.
    """

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        return key, value

    def extract_data(self) -> dict:
        # with open(os.path.join(self.project_dir, "source", "include", "constants", "abilities.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/include/constants/abilities.h") as file:
            lines = file.readlines()

        abilities = {}
        for line in lines:
            match = re.match(r'#define ABILITY_(.*?) (.*?)\n', line)
            if match:
                ability = match.group(1)
                ability_name = ability.replace("_", " ").strip().title()
                abilities["ABILITY_" + ability] = {"name": ability_name, "id": int(match.group(2))}

        return abilities


class ItemsDataExtractor(PokemonDataExtractor):
    """
    A class used to extract items data from the source files.
    """

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        return key, value

    def extract_data(self) -> dict:
        # with open(os.path.join(self.project_dir, "source", "src", "data", "items.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/src/data/items.h") as file:
            lines = file.readlines()

        items = {}
        current_item = None
        item_index = 0
        for line in lines:
            match = re.match(r'\s*\[ITEM_(.+)\] =', line)
            if match:
                item = "ITEM_" + match.group(1)
                items[item] = {"name": '', "data": {}, "id": item_index}
                current_item = item
                item_index += 1
                continue
            if current_item is not None:
                match = re.match(r'\s*\.(.*) = (.*),', line)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    if key == "name":
                        if current_item == "ITEM_NONE":
                            value = "None"
                        else:
                            value = re.sub(r'_\("(.*)"\)', r'\1', value)
                        items[current_item]["name"] = value
                        continue
                    elif key == "price":
                        value = int(value)
                    elif key == "holdEffectParam":
                        try:
                            value = int(value)
                        except ValueError:
                            pass
                    elif key == "flingPower":
                        value = int(value)
                    items[current_item]["data"][key] = value
        return items


class PokemonConstantsExtractor(PokemonDataExtractor):
    """
    A class used to extract game constants from the source files.
    """

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        return key, value

    @staticmethod
    def __parse_data(name: str, value, description: str) -> dict:
        return {
            "name": name,
            "value": value,
            "description": description
        }

    def extract_data(self) -> dict:
        # with open(os.path.join(self.project_dir, "source", "include", "constants", "pokemon.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/include/constants/pokemon.h") as file:
            lines = file.readlines()

        pokemon_types = {}
        pokemon_egg_groups = {}
        pokemon_natures = {}
        shiny_odds = 8
        standard_friendship = 70
        move_splits = {}
        pokemon_growth_rates = {}
        pokemon_body_colors = {}
        pokemon_evolution_types = {}
        pokemon_evolution_mode = {}
        pokemon_species_flags = {}
        legendary_perfect_iv_count = 3
        for line in lines:
            match = re.match(r'\s*#define (.*?)\s+(.*?)\n', line)
            if match:
                constant = match.group(1)
                contant_name = constant.replace("_", " ").strip().title()
                value = match.group(2)
                description = ""
                if "//" in value:
                    v = value.split("//")
                    value = v[0].strip()
                    description = v[1].strip()
                try:
                    value = int(value)
                except ValueError:
                    pass
                if constant.startswith("TYPE_"):
                    if constant == "TYPE_NONE":
                        continue
                    pokemon_types[constant] = self.__parse_data(contant_name.replace("Type ", ""),
                                                                value, description)
                elif constant.startswith("EGG_GROUP_"):
                    pokemon_egg_groups[constant] = self.__parse_data(contant_name.replace("Egg Group ", ""),
                                                                     value, description)
                elif constant.startswith("NATURE_"):
                    pokemon_natures[constant] = self.__parse_data(contant_name.replace("Nature ", ""),
                                                                  value, description)
                elif constant.startswith("SHINY_ODDS"):
                    shiny_odds = value
                elif constant.startswith("STANDARD_FRIENDSHIP"):
                    standard_friendship = value
                elif constant.startswith("SPLIT_"):
                    move_splits[constant] = self.__parse_data(contant_name.replace("Split ", ""),
                                                              value, description)
                elif constant.startswith("GROWTH_"):
                    pokemon_growth_rates[constant] = self.__parse_data(contant_name.replace("Growth ", ""),
                                                                       value, description)
                elif constant.startswith("BODY_COLOR_"):
                    pokemon_body_colors[constant] = self.__parse_data(contant_name.replace("Body Color ", ""),
                                                                      value, description)
                elif constant.startswith("EVO_"):
                    pokemon_evolution_types[constant] = self.__parse_data(contant_name.replace("Evo ", ""),
                                                                          value, description)
                elif constant.startswith("EVO_MODE_"):
                    pokemon_evolution_mode[constant] = self.__parse_data(contant_name.replace("Evo Mode ", ""),
                                                                         value, description)
                elif constant.startswith("SPECIES_FLAG_"):
                    pokemon_species_flags[constant] = self.__parse_data(contant_name.replace("Species Flag ", ""),
                                                                        value, description)
                elif constant.startswith("LEGENDARY_PERFECT_IV_COUNT"):
                    legendary_perfect_iv_count = value

        pokemon_constants = {
            "types": pokemon_types,
            "egg_groups": pokemon_egg_groups,
            "natures": pokemon_natures,
            "shiny_odds": shiny_odds,
            "standard_friendship": standard_friendship,
            "move_splits": move_splits,
            "growth_rates": pokemon_growth_rates,
            "body_colors": pokemon_body_colors,
            "evolution_types": pokemon_evolution_types,
            "evolution_modes": pokemon_evolution_mode,
            "species_flags": pokemon_species_flags,
            "legendary_perfect_iv_count": legendary_perfect_iv_count
        }
        return pokemon_constants


class StartersDataExtractor(PokemonDataExtractor):
    """
    A class used to extract starter Pokémon data from the source files.
    """

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        return key, value

    def extract_data(self) -> list:
        # with open(os.path.join(self.project_dir, "source", "src", "starter_choose.c"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/src/starter_choose.c") as file:
            lines = file.readlines()

        starters = []
        inside_starter_array = False
        for line in lines:
            if "const u16 sStarterMon" in line:
                inside_starter_array = True
                continue
            if inside_starter_array:
                if "}" in line:
                    break
                match = re.match(r'\s*SPECIES_(.*),', line)
                if match:
                    species = "SPECIES_" + match.group(1)
                    starter_data = {
                        "species": species,
                        "level": 5,
                        "item": "ITEM_NONE",
                        "custom_move": "MOVE_NONE",
                        "ability_num": -1,
                    }
                    starters.append(starter_data)
        return starters


class MovesDataExtractor(PokemonDataExtractor):
    """
    A class used to extract moves data from the source files.
    """

    def __init__(self, project_info: dict, data_file: str = None, files: dict = None):
        super().__init__(project_info, data_file, files)
        self.moves_data = {
            "moves": {},
            "move_descriptions": {},
            "constants": {}
        }

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        return key, value

    def __parse_macro(self, val):
        if type(val) is int:
            return val
        val = re.sub(r'\((.*)\)', r'\1', val)
        values = val.split(" ")
        if len(values) == 3:
            if values[1] == "+":
                value1 = values[0]
                value2 = values[2]
                try:
                    val = int(self.__parse_macro(value1)) + int(self.__parse_macro(value2))
                except ValueError:
                    val = -1
        elif len(values) == 1:
            try:
                while val in self.moves_data["constants"] or val in self.moves_data["moves"]:
                    if val in self.moves_data["constants"]:
                        val = self.moves_data["constants"][val]
                    elif val in self.moves_data["moves"]:
                        val = self.moves_data["moves"][val]["id"]
                val = int(val)
            except ValueError:
                val = self.__parse_macro(val)
        return val

    def extract_data(self) -> dict:
        # with open(os.path.join(self.project_dir, "source", "include", "constants", "moves.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/include/constants/moves.h") as file:
            lines = file.readlines()

        for line in lines:
            match = re.match(r'#define MOVE_(.*?) (.*?)\n', line)
            if match:
                move = match.group(1)
                move_name = move.replace("_", " ").strip().title()
                value = match.group(2)
                try:
                    if move == "UNAVAILABLE":
                        continue
                    else:
                        value = int(value)
                except ValueError:
                    if "//" in value:
                        continue
                    pass
                self.moves_data["moves"]["MOVE_" + move] = {
                    "name": move_name,
                    "id": value,
                    "battle_data": {},
                    "contest_data": {},
                    "description_var": "",
                }
                continue
            match = re.match(r'\s*#define (.*?)\s+(.*?)\n', line)
            if match:
                constant = match.group(1)
                value = match.group(2)
                try:
                    value = int(value)
                except ValueError:
                    pass
                self.moves_data["constants"][constant] = value

        for moves in self.moves_data["moves"]:
            try:
                self.moves_data["moves"][moves]["id"] = int(self.moves_data["moves"][moves]["id"])
            except ValueError:
                self.moves_data["moves"][moves]["id"] = self.__parse_macro(
                    self.moves_data["moves"][moves]["id"].strip())
        for constant in self.moves_data["constants"]:
            try:
                self.moves_data["constants"][constant] = int(self.moves_data["constants"][constant])
            except ValueError:
                self.moves_data["constants"][constant] = self.__parse_macro(
                    self.moves_data["constants"][constant].strip())

        self.docker_util.preprocess_c_file(
            "src/data/text/move_descriptions.h",
            ["include/config/battle.h"]
        )
        # with open(os.path.join(self.project_dir, "processed", "src", "data", "text", "move_descriptions.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "processed/src/data/text/move_descriptions.h") as file:
            lines = file.readlines()

        current_move = None
        for line in lines:
            match = re.match(r'\s*static const u8 (.*?)\[\]\s*=\s*_\(', line)
            if match:
                current_move = match.group(1)
                self.moves_data["move_descriptions"][current_move] = ""
                continue
            if current_move is not None:
                if line.strip().endswith(");"):
                    self.moves_data["move_descriptions"][current_move] += line.strip().rstrip(");").strip("\"")
                    current_move = None
                else:
                    self.moves_data["move_descriptions"][current_move] += line.strip().strip("\"").replace("\\n", "\n")
                continue
            match = re.match(r'\s*\[MOVE_(.*?) - 1\]\s*=\s*(.*?),', line)
            if match:
                move = "MOVE_" + match.group(1)
                self.moves_data["moves"][move]["description_var"] = match.group(2).strip()
                continue

        # with open(os.path.join(self.project_dir, "source", "src", "data", "battle_moves.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "source/src/data/battle_moves.h") as file:
            lines = file.readlines()

        current_move = None
        for line in lines:
            match = re.match(r'\s*\[MOVE_(.*?)\]\s*=\s*', line)
            if match:
                current_move = "MOVE_" + match.group(1)
                if current_move not in self.moves_data["moves"]:
                    current_move = None
                continue
            if current_move is not None:
                match = re.match(r'\s*\.(.*) = (.*),', line)
                if match:
                    key = match.group(1).strip()
                    value = match.group(2).strip()
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                    if value == "TRUE":
                        value = True
                    elif value == "FALSE":
                        value = False
                    self.moves_data["moves"][current_move]["battle_data"][key] = value
                elif line.strip().endswith("},"):
                    current_move = None

        return self.moves_data


class PokedexDataExtractor(PokemonDataExtractor):
    """
    A class used to extract pokedex data from the source files.
    """

    def parse_value_by_key(self, key: str, value: str) -> tuple:
        return key, value

    def extract_data(self) -> dict:
        self.docker_util.preprocess_c_file(
            "include/constants/pokedex.h",
            ["include/config/species_enabled.h"]
        )

        # with open(os.path.join(self.project_dir, "processed", "include", "constants", "pokedex.h"), 'r', encoding="utf-8") as file:
        with ReadSourceFile(self.project_info, "processed/include/constants/pokedex.h") as file:
            lines = file.readlines()

        pokedex_entries = {
            "national_dex": [],
            "regional_dex": [],
        }
        for line in lines:
            match = re.match(r'\s*NATIONAL_DEX_(.*?),', line)
            if match:
                species = match.group(1)
                if species == "NONE":
                    continue
                pokedex_entries["national_dex"].append("NATIONAL_DEX_" + species)
                continue
            match = re.match(r'\s*HOENN_DEX_(.*?),', line)
            if match:
                species = match.group(1)
                if species == "NONE":
                    continue
                pokedex_entries["regional_dex"].append("HOENN_DEX_" + species)

        return pokedex_entries
