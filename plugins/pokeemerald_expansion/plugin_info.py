from typing import override
from plugin_abstract.plugin_info import PorySuitePlugin
from plugins.pokeemerald_expansion.pokemon_data import PokemonDataManager


class PokeemeraldExpansionPlugin(PorySuitePlugin):
    """
    Plugin for Pokeemerald Expansion.
    """
    @staticmethod
    @override
    def create_data_manager(project_info: dict) -> PokemonDataManager:
        """
        Creates a new instance of the PokemonDataManager class.

        :param project_info: A dictionary containing project information.
        :returns: A new instance of the PokemonDataManager class.
        """
        return PokemonDataManager(project_info)
