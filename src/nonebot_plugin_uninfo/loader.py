from abc import ABCMeta, abstractmethod

from .constraint import SupportAdapter
from .fetch import InfoFetcher


class BaseLoader(metaclass=ABCMeta):
    @abstractmethod
    def get_adapter(self) -> SupportAdapter: ...

    @abstractmethod
    def get_fetcher(self) -> InfoFetcher: ...
