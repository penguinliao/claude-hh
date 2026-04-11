"""A well-formatted Python module with no issues."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    """Represents a user in the system."""

    name: str
    age: int
    email: str

    def greet(self) -> str:
        """Return a greeting message."""
        return f"Hello, {self.name}!"

    def is_adult(self) -> bool:
        """Check if the user is an adult."""
        return self.age >= 18


def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b


def process_items(items: list[str]) -> list[str]:
    """Filter and uppercase items."""
    return [item.upper() for item in items if item.strip()]
