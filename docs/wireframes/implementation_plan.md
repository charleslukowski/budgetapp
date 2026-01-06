# Fuel Model UI Implementation Plan

## Overview

Build the guided workflow UI for fuel forecasting in 6 phases, with each phase delivering usable functionality.

**Total Estimated Duration**: 4-6 weeks  
**Tech Stack**: FastAPI backend (existing), Jinja2 templates + HTMX for interactivity, Chart.js for visualizations

---

## Phase 0: Foundation (Already Complete ✓)

### What's Done
- [x] Driver framework (`src/engine/drivers.py`)
- [x] Default drivers defined (`src/engine/default_drivers.py`)
- [x] Database models for driver values (`src/models/driver.py`)
- [x] Scenario driver management (`src/engine/scenario_drivers.py`)
- [x] Multi-year projections (`src/engine/projections.py`)
- [x] API endpoints for drivers (`src/api/routes/drivers_api.py`)
- [x] Excel import capability (`src/etl/fuel_excel_import.py`)

### What's Ready to Use
- Create/copy scenarios via API
- Store/retrieve monthly driver values
- Calculate fuel costs from drivers
- Export/import driver sets as JSON
- Multi-year projections with escalation

---

## Phase 1: Workflow Shell & Navigation
**Duration**: 3-4 days

### Goal
Create the 5-step workflow navigation and basic page structure.

### Deliverables

#### 1.1 Workflow Layout Template
```
templates/
├── fuel_forecast/
│   ├── _layout.html          # Base layout with step navigation
│   ├── _step_nav.html        # Reusable step indicator component
│   ├── step1_start.html      # Start point selection
│   ├── step2_coal.html       # Coal position (placeholder)
│   ├── step3_generation.html # Generation profile (placeholder)
│   ├── step4_other.html      # Other costs (placeholder)
│   └── step5_review.html     # Review & save (placeholder)
```

#### 1.2 API Routes
```python
# src/api/routes/forecast_workflow.py

@router.get("/forecast/new")
async def start_new_forecast() -> HTMLResponse

@router.get("/forecast/{session_id}/step/{step_num}")
async def get_step(session_id: str, step_num: int) -> HTMLResponse

@router.post("/forecast/{session_id}/step/{step_num}")
async def save_step(session_id: str, step_num: int, ...) -> HTMLResponse
```

#### 1.3 Session State Management
```python
# src/engine/forecast_session.py

@dataclass
class ForecastSession:
    session_id: str
    created_at: datetime
    base_scenario_id: Optional[int]  # Roll forward source
    target_scenario_id: Optional[int]  # Where we're saving
    as_of_date: date
    forecast_through: date
    current_step: int
    step_status: Dict[int, str]  # "pending", "done", "changed"
    driver_changes: Dict[str, Any]  # Uncommitted changes
```

#### 1.4 Step Navigation Component
- Visual step indicator (1-5)
- Status icons (✓ done, ⚠️ needs review, ○ pending)
- Click to navigate between steps
- Progress preserved when moving between steps

### Acceptance Criteria
- [ ] Can start a new forecast workflow
- [ ] Can navigate between all 5 steps
- [ ] Step progress is preserved in session
- [ ] Visual indicator shows current step and status

---

## Phase 2: Step 1 - Start Point Selection
**Duration**: 2-3 days

### Goal
Implement the starting point selection with roll-forward capability.

### Deliverables

#### 2.1 Start Point Options
```html
<!-- step1_start.html -->
- Roll forward from last forecast (recommended)
  - Shows what carries forward
  - Shows what needs updating
- Copy from another scenario (dropdown)
- Start fresh with defaults
```

#### 2.2 Scenario Loader
```python
# API to load existing scenario for roll-forward
@router.get("/api/scenarios/{scenario_id}/summary")
async def get_scenario_summary(scenario_id: int) -> dict:
    return {
        "name": "November 2025 Forecast",
        "created_at": "2025-10-28",
        "as_of_date": "2025-10-01",
        "key_assumptions": {
            "coal_price_eastern": 55.00,
            "use_factor_avg": 72,
            ...
        }
    }
```

#### 2.3 Roll-Forward Logic
```python
# src/engine/forecast_session.py

def create_roll_forward_session(
    source_scenario_id: int,
    as_of_date: date,
) -> ForecastSession:
    """Create a new session pre-populated from source scenario."""
    # Copy all driver values
    # Mark actuals as locked (can't change past months)
    # Flag items that typically need updating
```

### Acceptance Criteria
- [ ] Can select "Roll Forward" and see source scenario details
- [ ] Can select "Copy From" and choose a scenario
- [ ] Can select "Start Fresh"
- [ ] "Continue" advances to Step 2 with session initialized

---

## Phase 3: Step 2 - Coal Position & Pricing
**Duration**: 5-7 days

### Goal
Build the coal inventory, contracts, and pricing interface with monthly input support.

### Deliverables

#### 3.1 Inventory Input Component
```html
<!-- components/inventory_input.html -->
- Plant-specific inventory inputs (KC/CC)
- Shows prior value for comparison
- Days of supply auto-calculated
- Visual bar showing vs. target
```

#### 3.2 Contract Summary Component
```html
<!-- components/contract_summary.html -->
- Collapsible table of contracts
- Remaining deliveries for current year
- Full year schedule for next year
- "Keep Prior" checkbox
- Link to detailed grid editor
```

#### 3.3 Monthly Price Input Component (Key!)
```html
<!-- components/monthly_price_input.html -->
Implements Pattern 1: Annual with Monthly Override

- Annual base price input
- Pattern selector (Flat, Quarterly Step-Up, Seasonal)
- Sparkline preview of monthly values
- Click-to-override individual months
- Variance display vs. prior
```

#### 3.4 Uncommitted Coal Calculator
```python
# Auto-calculates uncommitted needs
def calculate_uncommitted_needs(
    projected_burn: List[Decimal],  # Monthly
    contracted: List[Decimal],      # Monthly
    beginning_inventory: Decimal,
    ending_target_days: int,
) -> List[Decimal]:
    """Returns monthly uncommitted coal needs."""
```

#### 3.5 Interactive Price Pattern
```javascript
// static/js/price_pattern.js
- Pattern dropdown changes preview
- Sparkline updates live
- Click month to show override modal
- HTMX partial refresh for recalculation
```

### Acceptance Criteria
- [ ] Can update inventory positions for both plants
- [ ] Can view/edit contract delivery schedule
- [ ] Can set coal prices with annual + pattern
- [ ] Can override specific months with reasons
- [ ] Uncommitted needs auto-calculate
- [ ] "Keep Prior" works for each section
- [ ] Changes show variance from prior

---

## Phase 4: Step 3 - Generation Profile
**Duration**: 4-5 days

### Goal
Build the use factor and outage schedule interface.

### Deliverables

#### 4.1 Use Factor Curve Editor
```html
<!-- components/use_factor_curve.html -->
Implements Pattern 2: Visual Curve Editor

- SVG chart with draggable points
- Quick-set buttons (60%, 70%, 80%, etc.)
- Preset patterns (Historical, Budget, Flat)
- Annual average display
```

#### 4.2 Outage Schedule Component
```html
<!-- components/outage_schedule.html -->
- Timeline view by unit
- Highlight changes from prior
- Accept/reject change toggle
- Modal to edit outage dates
```

#### 4.3 Heat Rate Display
```html
<!-- components/heat_rate.html -->
- Baseline, SUF correction, PRB penalty
- Effective heat rate (calculated)
- "Keep Prior" with values shown
- Rarely needs changes
```

#### 4.4 Curve Editor JavaScript
```javascript
// static/js/curve_editor.js
- D3.js or Chart.js for draggable points
- Snap to 5% increments
- Double-click for exact value
- Real-time average recalculation
```

### Acceptance Criteria
- [ ] Can drag points on use factor curve
- [ ] Can use preset patterns
- [ ] Outage changes are highlighted
- [ ] Can accept/reject outage changes
- [ ] Heat rate shows effective calculated value

---

## Phase 5: Steps 4 & 5 - Other Costs and Review
**Duration**: 4-5 days

### Goal
Complete the workflow with reagent costs and final review/save.

### Deliverables

#### 5.1 Other Costs Summary (Step 4)
```html
<!-- step4_other.html -->
- Reagents & consumables (collapsed, "Keep Prior")
- Byproduct credits (collapsed, "Keep Prior")
- Escalation rates (collapsed, "Keep Prior")
- Summary of all changes made so far
```

#### 5.2 Review & Calculate (Step 5)
```html
<!-- step5_review.html -->
- Input summary (all key values)
- "Calculate Forecast" button
- Results display (4 key metrics)
- Comparison to prior forecast
- Variance waterfall (optional)
```

#### 5.3 Results Display Component
```html
<!-- components/forecast_results.html -->
- Big numbers: Total Cost, $/MWh, MWh, Cap Factor
- Each shows: current, prior, variance
- Monthly breakdown (collapsed)
- Plant breakdown (KC vs CC)
```

#### 5.4 Save Dialog
```html
<!-- components/save_dialog.html -->
- Scenario name input
- Notes textarea (pre-filled with changes)
- Save options: Save, Export Excel, Run Multi-Year
```

#### 5.5 Comparison View
```html
<!-- components/variance_comparison.html -->
- Table: This Forecast vs Prior
- Key drivers of change
- Waterfall chart (stretch goal)
```

### Acceptance Criteria
- [ ] Can review all inputs in summary form
- [ ] Calculate button runs and shows results
- [ ] Results compare to prior forecast
- [ ] Can save with name and notes
- [ ] Monthly detail available on expand

---

## Phase 6: Polish & Advanced Features
**Duration**: 3-4 days

### Goal
Add refinements and advanced capabilities.

### Deliverables

#### 6.1 Multi-Year Projection View
```html
<!-- multi_year_projection.html -->
- Table: 2026-2040 by year
- Chart: Cost trend over time
- Escalation assumption display
- Export to Excel
```

#### 6.2 Scenario Comparison Tool
```html
<!-- scenario_compare.html -->
- Side-by-side two scenarios
- Highlight differences
- Export comparison PDF
```

#### 6.3 Excel Import Wizard
```html
<!-- import_wizard.html -->
- File upload
- Preview of what will be imported
- Mapping confirmation
- Import progress
```

#### 6.4 Mobile/Tablet Responsive
- Collapsible sections
- Touch-friendly inputs
- Simplified views for quick updates

#### 6.5 Keyboard Navigation
- Tab through inputs
- Enter to continue
- Escape to cancel modals

### Acceptance Criteria
- [ ] Multi-year projection works from saved scenario
- [ ] Can compare two scenarios side-by-side
- [ ] Excel import works with confirmation
- [ ] Mobile layout is usable

---

## File Structure (Final)

```
templates/
├── fuel_forecast/
│   ├── _layout.html
│   ├── _step_nav.html
│   ├── step1_start.html
│   ├── step2_coal.html
│   ├── step3_generation.html
│   ├── step4_other.html
│   ├── step5_review.html
│   ├── multi_year.html
│   └── compare.html
│
├── components/
│   ├── inventory_input.html
│   ├── contract_summary.html
│   ├── monthly_price_input.html
│   ├── use_factor_curve.html
│   ├── outage_schedule.html
│   ├── heat_rate.html
│   ├── forecast_results.html
│   ├── save_dialog.html
│   └── variance_comparison.html

static/
├── js/
│   ├── forecast_workflow.js
│   ├── price_pattern.js
│   ├── curve_editor.js
│   └── htmx.min.js
│
├── css/
│   └── fuel_forecast.css

src/
├── api/routes/
│   └── forecast_workflow.py
│
├── engine/
│   └── forecast_session.py
```

---

## Technical Decisions

### Frontend Approach: HTMX + Jinja2

**Why not React/Vue?**
- Existing codebase uses Jinja2 templates
- HTMX provides interactivity without build step
- Simpler mental model for form-heavy workflows
- SSR by default (good for initial load)

**Where we use JavaScript:**
- Curve editor (drag interactions)
- Sparkline charts
- Real-time calculations

### Session Storage

**Option A: Server-side sessions (Redis/DB)**
- Pros: Survives page refresh, shareable
- Cons: More infrastructure

**Option B: Browser localStorage + session cookie**
- Pros: Simple, no server state
- Cons: Lost if user clears storage

**Recommendation**: Start with Option B, migrate to A if multi-user becomes important.

### Real-Time Calculation

**Approach**: HTMX partial updates
```html
<input hx-post="/api/forecast/{id}/calculate-partial"
       hx-trigger="change delay:500ms"
       hx-target="#results-preview">
```

When user changes an input:
1. 500ms debounce
2. POST to server with current values
3. Server calculates affected outputs
4. Partial HTML response updates preview

---

## Dependencies

| Phase | Depends On |
|-------|------------|
| Phase 1 | Phase 0 (complete) |
| Phase 2 | Phase 1 |
| Phase 3 | Phase 1 |
| Phase 4 | Phase 1 |
| Phase 5 | Phases 2, 3, 4 |
| Phase 6 | Phase 5 |

Phases 2, 3, 4 can be worked in parallel after Phase 1.

---

## Milestones

| Milestone | Phases | Deliverable |
|-----------|--------|-------------|
| **M1: Walkable** | 1, 2 | Can start and choose source scenario |
| **M2: Coal Entry** | 3 | Can enter coal prices with monthly granularity |
| **M3: Full Input** | 4 | All inputs can be entered |
| **M4: Calculate** | 5 | Can calculate and save a forecast |
| **M5: Complete** | 6 | Multi-year, compare, polish |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Curve editor too complex | Fall back to table input + sparkline preview |
| Session state gets corrupted | Auto-save every step, recovery option |
| Calculation too slow | Cache intermediate results, show spinner |
| Mobile too different | Defer mobile to Phase 6, focus on desktop first |

---

## Next Steps

1. **Review this plan** - Any missing pieces?
2. **Start Phase 1** - Create workflow shell and navigation
3. **Parallel design** - While Phase 1 builds, finalize component designs
4. **Build Phase 2/3/4** - Can work these in parallel with 2-3 people
5. **Integrate Phase 5** - Bring it all together
6. **Polish Phase 6** - Based on user feedback

---

## Quick Win Path (MVP in 2 weeks)

If we want a working MVP faster:

**Week 1:**
- Phase 1 (3 days)
- Phase 2 simplified (4 days)
  - Skip curve editor, use table
  - Skip contract grid, use totals only

**Week 2:**
- Phase 3 simplified (2 days)
  - Table input for use factors
  - Simple outage list
- Phase 4 (1 day)
  - Just "Keep Prior" checkboxes
- Phase 5 (4 days)
  - Calculate and display
  - Save with notes

This gets a working forecast workflow in 2 weeks, with enhanced input patterns (curves, patterns) added later.

