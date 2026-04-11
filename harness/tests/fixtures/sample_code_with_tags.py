"""Sample code for testing AST analysis - tag management module."""

from dataclasses import dataclass


@dataclass
class Tag:
    """A tag that can be attached to items."""
    name: str
    color: str = "blue"


class TagService:
    """Service for managing tags."""

    def __init__(self):
        self.tags: dict[str, Tag] = {}

    def add_tag(self, name: str, color: str = "blue") -> Tag:
        """Add a new tag."""
        tag = Tag(name=name, color=color)
        self.tags[name] = tag
        return tag

    def list_tags(self) -> list[Tag]:
        """List all tags."""
        return list(self.tags.values())

    def get_tag(self, name: str) -> Tag | None:
        """Get a tag by name."""
        return self.tags.get(name)
