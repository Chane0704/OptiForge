"""Domain models with type checking."""
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from typing_extensions import Annotated, TypeAlias

UserId = int
