"""Create scenario-related tables if they don't exist."""

import sys
sys.path.insert(0, ".")

from src.database import engine, Base
from src.models.scenario import Scenario
from src.models.scenario_inputs import ScenarioInputSnapshot

# Create tables
print("Creating tables...")
Base.metadata.create_all(bind=engine, tables=[
    Scenario.__table__,
    ScenarioInputSnapshot.__table__,
])
print("Done!")
