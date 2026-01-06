# Workflow to Driver Framework Mapping

This document shows the alignment between the Fuel Forecast Workflow inputs and the underlying driver framework defined in `src/engine/default_drivers.py`.

## Summary

| Workflow Step | Fields Captured | Drivers Mapped | Coverage |
|---------------|-----------------|----------------|----------|
| Step 2: Coal | 15 fields | 15 drivers | **100%** |
| Step 3: Generation | 13 fields | 13 drivers | **100%** |
| Step 4: Other Costs | 11 fields | 11 drivers | **100%** |
| **Total** | **39 fields** | **39 drivers** | ✅ Complete |

---

## Step 2: Coal Position

### Inventory Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `inventory_beginning_kc` | `inventory_beginning_tons` (KC) | VOLUME | tons | 180,000 |
| `inventory_beginning_cc` | `inventory_beginning_tons` (CC) | VOLUME | tons | 150,000 |
| `inventory_target_days` | `inventory_target_days` | VOLUME | days | 50 |
| `contracted_deliveries_tons` | `contracted_deliveries_tons` | VOLUME | tons | 75,000 |

### Coal Price Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `coal_price_eastern` | `coal_price_eastern` | PRICE_INDEX | $/ton | 55.00 |
| `coal_price_ilb` | `coal_price_ilb` | PRICE_INDEX | $/ton | 45.00 |
| `coal_price_prb` | `coal_price_prb` | PRICE_INDEX | $/ton | 15.00 |

### Coal Blend Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `coal_blend_eastern_pct` | `coal_blend_eastern_pct` | PERCENTAGE | % | 100 |
| `coal_blend_ilb_pct` | `coal_blend_ilb_pct` | PERCENTAGE | % | 0 |
| `coal_blend_prb_pct` | `coal_blend_prb_pct` | PERCENTAGE | % | 0 |

### Coal Quality Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `coal_btu_eastern` | `coal_btu_eastern` | RATE | BTU/lb | 12,600 |
| `coal_btu_ilb` | `coal_btu_ilb` | RATE | BTU/lb | 11,400 |

### Transportation Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `barge_rate_ohio` | `barge_rate_ohio` | RATE | $/ton | 6.00 |
| `barge_rate_upper_ohio` | `barge_rate_upper_ohio` | RATE | $/ton | 7.50 |
| `rail_rate_prb` | `rail_rate_prb` | RATE | $/ton | 30.00 |

### Calculated Drivers (Displayed Only)

| Display Field | Driver Name | Calculation |
|---------------|-------------|-------------|
| `blended_price` | `coal_price_blended` | Weighted avg based on blend % |
| `delivered_cost` | `delivered_cost` | Blended price + barge rate |

---

## Step 3: Generation

### Capacity Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `capacity_mw_kc` | `capacity_mw` (KC) | VOLUME | MW | 1,025 |
| `capacity_mw_cc` | `capacity_mw` (CC) | VOLUME | MW | 1,025 |

### Use Factor Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `use_factor` | `use_factor` | PERCENTAGE | % | 85 |
| `capacity_factor_target` | `capacity_factor_target` | PERCENTAGE | % | 70 |

### Heat Rate Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `heat_rate_baseline_kc` | `heat_rate_baseline_kc` | RATE | BTU/kWh | 9,850 |
| `heat_rate_baseline_cc` | `heat_rate_baseline_cc` | RATE | BTU/kWh | 9,900 |
| `heat_rate_suf_correction` | `heat_rate_suf_correction` | RATE | BTU/kWh | 0 |
| `heat_rate_prb_penalty` | `heat_rate_prb_penalty` | RATE | BTU/kWh/% | 100 |

### Outage Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `outage_days_planned` | `outage_days_planned` | VOLUME | days | 0 |
| `outage_days_forced` | `outage_days_forced` | VOLUME | days | 0 |

### Deduction Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `fgd_aux_pct` | `fgd_aux_pct` | PERCENTAGE | % | 2.5 |
| `gsu_loss_pct` | `gsu_loss_pct` | PERCENTAGE | % | 0.5545 |
| `reserve_mw` | `reserve_mw` | VOLUME | MW | 10 |

### Calculated Drivers (Displayed Only)

| Display Field | Driver Name | Calculation |
|---------------|-------------|-------------|
| `est_generation` | `generation_mwh` | capacity × hours × use_factor |
| Net Deduction | `net_delivered_mwh` | generation × (1-fgd) × (1-gsu) - reserve |

---

## Step 4: Other Costs & Escalation

### Escalation Drivers

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `escalation_coal_annual` | `escalation_coal_annual` | PERCENTAGE | %/yr | 2.0 |
| `escalation_transport_annual` | `escalation_transport_annual` | PERCENTAGE | %/yr | 2.5 |
| `escalation_reagent_annual` | `escalation_reagent_annual` | PERCENTAGE | %/yr | 2.0 |

### Consumables/Reagent Drivers (Optional - if not keeping prior)

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `urea_price_per_ton` | (consumables module) | PRICE_INDEX | $/ton | 350 |
| `limestone_price_per_ton` | (consumables module) | PRICE_INDEX | $/ton | 25 |
| `hydrated_lime_price_per_ton` | (consumables module) | PRICE_INDEX | $/ton | 150 |
| `mercury_reagent_cost_monthly` | (consumables module) | PRICE_INDEX | $/month | 5,000 |

### Byproduct Drivers (Optional - if not keeping prior)

| Workflow Field | Driver Name | Type | Unit | Default |
|----------------|-------------|------|------|---------|
| `ash_sale_price_per_ton` | (byproducts module) | PRICE_INDEX | $/ton | 8.00 |
| `ash_disposal_cost_per_ton` | (byproducts module) | PRICE_INDEX | $/ton | 15.00 |
| `gypsum_sale_price_per_ton` | (byproducts module) | PRICE_INDEX | $/ton | 5.00 |
| `fly_ash_sale_pct` | (byproducts module) | PERCENTAGE | % | 50 |

---

## Drivers Not Yet Exposed in Workflow

These drivers exist in the framework but are not directly editable in the workflow (using defaults or derived values):

| Driver Name | Reason Not Exposed |
|-------------|-------------------|
| `coal_price_blended` | CALCULATED from blend inputs |
| `coal_mmbtu_eastern` | CALCULATED from price/BTU |
| `coal_mmbtu_ilb` | CALCULATED from price/BTU |
| `delivered_cost` | CALCULATED (displayed) |
| `heat_rate_effective` | CALCULATED from baseline + corrections |
| `generation_mwh` | CALCULATED (displayed) |
| `net_delivered_mwh` | CALCULATED from deductions |
| `inventory_ending_tons` | CALCULATED from balance |
| `uncommitted_tons_needed` | CALCULATED from target gap |
| `coal_deliveries_tons` | Derived from contracted + uncommitted |
| `coal_consumption_tons` | Derived from generation/heat rate |

---

## Phase 2+ Enhancements

### Monthly Variation Support

Currently, inputs are annual/single values. Phase 2+ should add:

1. **Monthly coal prices** - Price curves for contract/spot coal
2. **Monthly use factors** - Seasonal generation shape
3. **Monthly outages** - Specific outage schedules by month
4. **Monthly blend changes** - Variable coal sourcing

### Advanced Features

1. **Price curve editor** - Visual editing of monthly price trends
2. **Scenario comparison** - Side-by-side driver value comparison
3. **Sensitivity analysis** - Impact of driver changes on total cost
4. **Historical import** - Pre-populate from actual data

