from abc import ABC, abstractmethod


class PluginFeature(ABC):

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def description(self):
        pass

    @abstractmethod
    def install(self):
        pass

    @abstractmethod
    def uninstall(self):
        pass