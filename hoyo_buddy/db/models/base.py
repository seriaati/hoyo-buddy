from __future__ import annotations

from tortoise.models import Model


class BaseModel(Model):
    def __str__(self) -> str:
        return repr(self)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({', '.join(f'{field}={getattr(self, field)!r}' for field in self._meta.db_fields if hasattr(self, field))})"

    class Meta:
        abstract = True
