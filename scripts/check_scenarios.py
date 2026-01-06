"""Check what scenarios exist in the database."""

import sys
sys.path.insert(0, ".")

from src.db.postgres import get_session
from src.models.scenario import Scenario
from src.models.scenario_inputs import ScenarioInputSnapshot

with get_session() as db:
    scenarios = db.query(Scenario).all()
    
    print("=" * 60)
    print(f"SCENARIOS IN DATABASE: {len(scenarios)}")
    print("=" * 60)
    
    if not scenarios:
        print("No scenarios found. Need to create some for testing.")
    else:
        for s in scenarios:
            snapshot = db.query(ScenarioInputSnapshot).filter(
                ScenarioInputSnapshot.scenario_id == s.id
            ).first()
            
            print(f"\n{s.id}: {s.name}")
            print(f"   Type: {s.scenario_type.value if s.scenario_type else 'N/A'}")
            print(f"   Status: {s.status.value if s.status else 'N/A'}")
            print(f"   Created: {s.created_at}")
            print(f"   Has Snapshot: {'Yes' if snapshot else 'No'}")
            if snapshot:
                print(f"   Year: {snapshot.year}")
