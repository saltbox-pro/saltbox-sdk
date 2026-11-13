from importlib.resources import files


class LuaScript:
    def __init__(self, resource_path: str) -> None:
        self.resource_path = resource_path
        self._content: str | None = None

    @property
    def content(self) -> str:
        if self._content is None:
            self._content = files('saltbox_sdk').joinpath(self.resource_path).read_text(encoding='utf-8')
        return self._content
