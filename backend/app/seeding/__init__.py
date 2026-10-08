"""Public synthetic entity seed interface."""

from app.seeding.generation import SeedConfig, generate_entities
from app.seeding.persistence import SeedConflict, SeedResult, seed_database

__all__ = ["SeedConfig", "SeedConflict", "SeedResult", "generate_entities", "seed_database"]
