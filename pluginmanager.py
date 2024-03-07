import os
import sys
import json
import pkgutil
import importlib
import platformdirs

from app_info import APP_NAME, AUTHOR
from plugin_abstract.plugin_info import PorySuitePlugin


def get_plugin(plugin_identifier, plugin_version=None) -> (tuple[PorySuitePlugin, str]
                                                           | tuple[None, str] | tuple[None, None]):
    """
    Gets a plugin from its identifier.

    :param plugin_identifier: The identifier of the plugin.
    :param plugin_version: The version of the plugin.
    :returns: The plugin.
    """
    # If debug mode is enabled, use the local plugins
    if "debug" in sys.argv:
        plugins_path = os.path.join(os.getcwd(), "plugins")
    else:
        plugins_path = str(os.path.join(platformdirs.user_data_path(APP_NAME, AUTHOR), "plugins"))
    
    # Check if the plugins directory exists
    if not os.path.exists(plugins_path):
        return None, None

    sys.path.append(plugins_path)
    
    discovered_plugins = {
        name: importlib.import_module(name)
        for _, name, _ in pkgutil.iter_modules(path=[str(plugins_path)])
    }

    # Sort the plugins by version
    sorted_plugins = []
    for plugin in discovered_plugins:
        version = discovered_plugins[plugin].PLUGIN_INFO.version.split(".")
        sorted_plugins.append((plugin, version))
    sorted_plugins.sort(key=lambda x: x[1], reverse=True)

    # Find the plugin
    newest = None
    for plugin in sorted_plugins:
        module = discovered_plugins[plugin[0]]
        if module.PLUGIN_INFO.identifier == plugin_identifier:
            if newest is None:
                newest = module
            if plugin_version is None or module.PLUGIN_INFO.version == plugin_version:
                return module.PLUGIN_INFO, newest.PLUGIN_INFO.version
    if newest is not None:
        # If the plugin was not found, return the newest version
        return None, newest.PLUGIN_INFO.version
    return None, None


def get_plugins_info() -> list[dict]:
    """
    Gets info of all plugins in the plugins directory from their plugin_info.json file.
    """
    def verify_plugin_info(info: dict):
        if "name" not in info:
            raise ValueError("The plugin info must contain a name.")
        if "author" not in info:
            raise ValueError("The plugin info must contain an author.")
        if "version" not in info:
            raise ValueError("The plugin info must contain a version.")
        if "identifier" not in info:
            raise ValueError("The plugin info must contain an identifier.")
        if "rom_base" not in info:
            raise ValueError("The plugin info must contain a rom base.")
        if "project_base_repo" not in info:
            raise ValueError("The plugin info must contain a project base repository.")

    # If debug mode is enabled, use the local plugins
    if "debug" in sys.argv:
        plugins_path = os.path.join(os.getcwd(), "plugins")
    else:
        plugins_path = str(os.path.join(platformdirs.user_data_path(APP_NAME, AUTHOR), "plugins"))

    # Check if the plugins directory exists
    if not os.path.exists(plugins_path):
        return []

    plugins_info = []
    for plugin in os.listdir(plugins_path):
        if os.path.isdir(os.path.join(plugins_path, plugin)):
            plugin_info_path = os.path.join(plugins_path, plugin, "plugin_info.json")
            if os.path.exists(plugin_info_path):
                with open(plugin_info_path, "r") as f:
                    plugin_info = json.load(f)
                    plugin_info["dir"] = os.path.join(plugins_path, plugin)
                    try:
                        verify_plugin_info(plugin_info)
                        plugin_info["readme"] = ""
                        readme_path = os.path.join(plugins_path, plugin, "README.md")
                        if os.path.exists(readme_path):
                            with open(readme_path, "r") as f_readme:
                                plugin_info["readme"] = f_readme.read()
                        plugins_info.append(plugin_info)
                    except Exception as e:
                        print(f"Plugin {plugin} is invalid: {e}")
    return plugins_info
