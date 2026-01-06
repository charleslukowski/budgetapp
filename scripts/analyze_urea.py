"""Analyze urea calculations for Q4 2025."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.postgres import get_session
from src.engine.fuel_model import calculate_fuel_costs

with get_session() as db:
    # Clifty Analysis
    print('CLIFTY Q4 2025 UREA ANALYSIS')
    print('=' * 60)
    
    q4_urea_total = 0
    
    for month in [10, 11, 12]:
        result = calculate_fuel_costs(db, plant_id=2, year=2025, month=month, inputs=None)
        
        print(f'\nMonth {month}:')
        print(f'  Net Generation: {float(result.net_delivered_mwh):,.0f} MWh')
        print(f'  Coal MMBtu: {float(result.coal_mmbtu_consumed):,.0f}')
        print(f'  Urea Cost: ${float(result.urea_cost):,.0f}')
        
        q4_urea_total += float(result.urea_cost)
    
    print(f'\nQ4 Total Urea Cost: ${q4_urea_total:,.0f}')
    print(f'Excel Q4 Total: $1,021,165')
    print(f'Variance: ${q4_urea_total - 1021165:,.0f} ({(q4_urea_total/1021165 - 1)*100:.1f}%)')
    
    # Kyger Analysis
    print('\n' + '=' * 60)
    print('KYGER Q4 2025 UREA ANALYSIS')
    print('=' * 60)
    
    q4_urea_total = 0
    
    for month in [10, 11, 12]:
        result = calculate_fuel_costs(db, plant_id=1, year=2025, month=month, inputs=None)
        
        print(f'\nMonth {month}:')
        print(f'  Net Generation: {float(result.net_delivered_mwh):,.0f} MWh')
        print(f'  Coal MMBtu: {float(result.coal_mmbtu_consumed):,.0f}')
        print(f'  Urea Cost: ${float(result.urea_cost):,.0f}')
        
        q4_urea_total += float(result.urea_cost)
    
    print(f'\nQ4 Total Urea Cost: ${q4_urea_total:,.0f}')
    print(f'Excel Q4 Total: $1,169,684')
    print(f'Variance: ${q4_urea_total - 1169684:,.0f} ({(q4_urea_total/1169684 - 1)*100:.1f}%)')
