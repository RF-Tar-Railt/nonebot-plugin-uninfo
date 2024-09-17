from nonebot_plugin_uninfo.constraint import SupportAdapter
from nonebot_plugin_uninfo.fetch import InfoFetcher
from nonebot_plugin_uninfo.loader import BaseLoader


class Loader(BaseLoader):
    def get_adapter(self) -> SupportAdapter:
        return SupportAdapter.discord

    def get_fetcher(self) -> InfoFetcher:
        from .main import fetcher

        return fetcher
