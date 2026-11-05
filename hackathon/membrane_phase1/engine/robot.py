# Defines the small robot interface shared by the mock and future PyBullet engine.
# The server uses only these methods, never private scene data.
from abc import ABC, abstractmethod


class Robot(ABC):
    @abstractmethod
    def move(self, distance: float) -> dict: ...

    @abstractmethod
    def turn(self, degrees: float) -> dict: ...

    @abstractmethod
    def pickup(self) -> dict: ...

    @abstractmethod
    def drop(self) -> dict: ...

    @abstractmethod
    def state(self) -> dict: ...

    @abstractmethod
    def look(self) -> bytes: ...

    @abstractmethod
    def depth(self) -> float | None: ...
