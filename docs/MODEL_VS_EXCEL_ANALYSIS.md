# Fuel Model vs Excel Comparison Analysis

## Summary

This document analyzes discrepancies between the Python fuel model and the Excel budget workbook 
for Q4 2025 (October-December).

## Key Metrics Comparison (Q4 2025)

| Metric | Kyger Excel | Kyger Model | Kyger Var | Clifty Excel | Clifty Model | Clifty Var |
|--------|-------------|-------------|-----------|--------------|--------------|------------|
| Net Generation (MWh) | 1,375,247 | 1,522,259 | -10.7% | 1,586,114 | 1,864,259 | -17.5% |
| Urea Cost ($) | $1.17M | $1.31M | -12.3% | $1.02M | $1.33M | -30.4% |
| Byproduct Net ($) | -$87K | -$292K | -235.7% | -$1.21M | -$602K | +50.1% |

## Root Cause Analysis

### 1. Generation Discrepancy (Model 10-17% Higher)

The model calculates higher generation than Excel for both plants. This cascades to:
- Higher coal consumption
- Higher consumables (urea, limestone)
- Higher byproduct production

**Contributing Factors:**

1. **Use Factors**: Model may use different monthly use factors
   - Excel stores use factors in Generation sheets (rows 5-9 for units)
   - Model uses `use_factor_inputs` table which may have different values

2. **Outage Application**: Unit outages may be applied differently
   - Excel has specific rows for "Planned Outages" 
   - Model derates capacity based on outage days

3. **Heat Rate Application**: 
   - Model now uses 10,350 BTU/kWh (with SUF correction)
   - Excel applies 10,302-10,420 BTU/kWh depending on unit and period

### 2. Coal Contract Pricing (Loaded)

Excel 2025 coal contracts have been imported to the database:

| Contract | Tons | BTU/lb | Coal $/ton | Barge $/ton | Delivered $/ton |
|----------|------|--------|------------|-------------|-----------------|
| Alliance 31-10-22-001 | 66K | 11,450 | $52.50 | $7.89 | $60.39 |
| Alliance 31-10-23-001 | 258K | 11,350 | $74.00 | $7.89 | $81.89 |
| Knight Hawk 31-10-21-002 | 48K | 11,200 | $48.00 | $13.45 | $61.45 |
| Peabody 31-10-22-002 | 48K | 11,000 | $54.13 | $13.61 | $67.74 |
| Foresight 31-10-25-001 | 62K | 11,250 | $40.00 | $7.62 | $47.62 |

**Weighted average: $71.09/ton delivered**

Contracts are split 50/50 between Kyger and Clifty plants.

### 3. Byproduct Calculation

Byproducts now include:
- Ash net cost (typically negative = revenue)
- Gypsum net cost (typically negative = revenue due to sales)
- Misc. byproduct expenses ($310,000/month fixed)

**Fixed in this analysis:**
- SO2 rate updated from 1.2 to 5.60 lb/MMBtu (matches Excel KC Emissions)
- Added $310K/month misc byproduct expense

**Remaining variance** is due to:
- Different coal burn volumes (from generation discrepancy)
- Gypsum production tied to limestone consumption

### 4. Urea Consumption

Model uses: 0.075 lb/MMBtu
Excel shows: Similar rate, but lower total due to lower generation

Variance is proportional to generation difference.

## Fixes Applied

| Area | Fix | Status |
|------|-----|--------|
| Heat Rate | Added SUF correction (150 BTU/kWh) | ✓ Complete |
| Use Factors | Loaded Q4 2025 values from database | ✓ Complete |
| SO2 Rate | Updated from 1.2 to 5.60 lb/MMBtu | ✓ Complete |
| Misc Byproduct | Added $310K/month fixed expense | ✓ Complete |
| Urea Pricing | Updated to $458/ton (Excel rate) | ✓ Complete |
| Coal Contracts | Imported 5 contracts from Excel for 2025 | ✓ Complete |
| Coal Pricing | Fixed calculation to use consumption × weighted avg | ✓ Complete |

## Remaining Work

### High Priority

1. **Reconcile Use Factors**: Compare monthly use factors
   - Check October-December 2025 values specifically
   - Model generates ~10-17% higher than Excel

### Medium Priority

2. **Outage Calendar**: Verify planned outage application
   - Check `unit_outages` table matches Excel outage schedule

3. **Monthly Granularity**: Add monthly comparison output
   - Compare each month's generation to identify which months diverge

## Methodology Differences

### Generation Calculation

**Model Approach:**
```
Net MWh = Σ(unit_capacity × hours × use_factor × (1 - outage_derate))
```

**Excel Approach:**
- Uses actual/budget mix for recent months
- May include actual generation data for Oct-Nov 2025
- Applies unit-specific adjustments

### Coal Burn Calculation

**Model Approach:**
```
MMBtu = Net MWh × 1000 × heat_rate / 1,000,000
Tons = MMBtu × 1,000,000 / (BTU_per_lb × 2000)
```

**Excel Approach:**
- May use different heat rate per unit
- Blended coal quality from multiple contracts

### Consumables

**Both use similar approaches:**
- Urea: lb/MMBtu × MMBtu × $/ton
- Limestone: Based on SO2 removed and FGD efficiency

## Current Status

After fixes, the key metrics are:

| Metric | Variance |
|--------|----------|
| Avg $/MWh | 7.6% |
| Total Fuel Cost (Q4) | 22.1% |
| Generation (MWh) | 10-17% high |

## Conclusion

The primary remaining discrepancy is **generation volume** (~10-17% higher in model).
This drives proportional differences in coal consumption, consumables, and byproducts.

The average $/MWh is now within 8% of Excel after importing coal contracts 
with accurate pricing ($71.09/ton weighted average).

To achieve <5% variance:
1. Review monthly use factors for Q4 2025
2. Compare unit-level generation breakdown
3. Verify outage calendar matches Excel
