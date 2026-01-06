# Financial Planning Software Requirements Document

**Document Version:** 1.0  
**Date:** December 23, 2024  
**Organization Type:** Coal-Fired Power Generation Utility  

---

## 1. Executive Summary

This document outlines the requirements for a financial planning and forecasting system designed for a small utility operating two coal-fired power plants. The system must support long-term projections through 2040 (contract end date) with detailed monthly granularity for the first two years to satisfy sponsor reporting requirements.

### Key Differentiators from Standard Utility Software
- **Generation-centric reporting** rather than revenue-centric (owners purchase all energy)
- **$/MWhr metrics** as the primary performance indicators across all cost categories
- **Driver-based fuel cost modeling** requiring complex multi-variable calculations
- **Asset Health integration** for operating cost projections
- **Depreciation-based capital billing** (recently transitioned from cash flow billing)

---

## 2. Business Context

### 2.1 Organizational Structure
| Component | Description |
|-----------|-------------|
| Generation Assets | 2 coal-fired power plants |
| Cost Centers | Fuel, Transmission, Operating, Non-Operating, Administrative, Capital |
| Ownership Model | Power Purchase Agreement - owners buy all generated energy |
| Contract Duration | Through 2040 |

### 2.2 Primary Stakeholders
- **Sponsors/Owners:** Require monthly projections for 2-year horizon
- **Operations:** Need driver-based fuel cost forecasting
- **Finance:** Manage depreciation schedules and billing transitions
- **Asset Management:** Maintain Asset Health system data

---

## 3. Functional Requirements

### 3.1 Generation Forecasting (Primary Output)

**FR-GEN-001:** System shall project generation (MWh) as the primary output metric rather than revenue.

**FR-GEN-002:** Generation forecasts shall be available at:
- Monthly granularity for Years 1-2
- [TBD] granularity for Years 3-16 (through 2040)

**FR-GEN-003:** Generation shall be forecastable by:
- Individual plant (Plant 1, Plant 2)
- Combined total
- Time period (monthly, quarterly, annual)

**FR-GEN-004:** System shall support capacity factor assumptions and planned/unplanned outage modeling.

---

### 3.2 Cost Category Structure

The system shall organize costs into the following hierarchy with $/MWhr calculations at each level:

```
├── GENERATION (MWh)
│
├── FUEL COSTS
│   ├── Coal Procurement
│   ├── Coal Transportation
│   ├── Coal Handling
│   ├── Emissions/Environmental
│   └── [Driver-Based Model Components - TBD]
│   └── SUBTOTAL + $/MWhr
│
├── OPERATING COSTS
│   ├── Plant 1 Operating
│   ├── Plant 2 Operating
│   ├── Transmission Costs
│   ├── Asset Health-Driven Costs
│   └── SUBTOTAL + $/MWhr
│
├── NON-OPERATING COSTS
│   ├── Administrative Costs
│   ├── Insurance
│   ├── Property Taxes
│   ├── [Other Non-Operating - TBD]
│   └── SUBTOTAL + $/MWhr
│
├── CAPITAL COSTS
│   ├── Depreciation Schedule Items
│   ├── Capital Project Billing
│   └── SUBTOTAL + $/MWhr
│
└── TOTAL ALL-IN COST + $/MWhr
```

---

### 3.3 Fuel Cost Module (Driver-Based Model)

**FR-FUEL-001:** System shall support a comprehensive driver-based model for fuel cost projections.

**FR-FUEL-002:** The fuel model shall accommodate multiple input drivers including (but not limited to):
- Coal commodity price indices
- Transportation rates
- Heat rate assumptions
- Generation volume
- Inventory management
- Contract escalation factors

**FR-FUEL-003:** Driver relationships shall be configurable without code changes.

**FR-FUEL-004:** System shall support scenario analysis with different driver assumption sets.

**FR-FUEL-005:** Model shall handle the complexity of the existing "sprawling" driver-based model while providing structure and auditability.

---

### 3.4 Operating Costs & Asset Health Integration

**FR-OPS-001:** System shall integrate with existing Asset Health system to inform operating cost projections.

**FR-OPS-002:** Asset Health integration should enable:
- Predictive maintenance cost forecasting
- Equipment condition-based budget adjustments
- Remaining useful life considerations
- Major maintenance timing projections

**FR-OPS-003:** System shall support both routine O&M and major maintenance cost categories.

**FR-OPS-004:** Transmission costs shall be separately trackable from plant operating costs.

---

### 3.5 Capital & Depreciation Module

**FR-CAP-001:** System shall support depreciation-based billing methodology (current approach).

**FR-CAP-002:** System shall maintain depreciation schedules for all capital assets.

**FR-CAP-003:** Capital module shall support:
- Existing asset depreciation tracking
- New capital project additions
- Asset retirement projections
- Book vs. Tax depreciation (if applicable)

**FR-CAP-004:** System shall provide clear audit trail for cash flow vs. depreciation billing transition.

---

### 3.6 Projection Horizons & Granularity

| Time Horizon | Granularity | Purpose |
|--------------|-------------|---------|
| Years 1-2 | Monthly | Sponsor reporting requirement |
| Years 3-5 | [TBD - Quarterly/Annual?] | Medium-term planning |
| Years 6-16 (to 2040) | [TBD - Annual?] | Contract life planning |

**FR-TIME-001:** System shall support monthly projections for minimum 24-month rolling horizon.

**FR-TIME-002:** Long-term projections shall extend through contract end (2040).

**FR-TIME-003:** System shall support flexible fiscal year definitions.

---

### 3.7 Reporting & Analysis

**FR-RPT-001:** All cost sections shall display $/MWhr metrics prominently.

**FR-RPT-002:** Standard reports shall include:
- Generation summary by plant and period
- Cost summary by category with $/MWhr
- Variance analysis (actual vs. budget vs. prior forecast)
- Long-term trend analysis
- Sponsor reporting package (monthly detail for 2 years)

**FR-RPT-003:** System shall support drill-down from summary to detail levels.

**FR-RPT-004:** Export capabilities to Excel and PDF required.

---

### 3.8 Scenario & Sensitivity Analysis

**FR-SCEN-001:** System shall support multiple forecast scenarios (e.g., Base, High, Low).

**FR-SCEN-002:** Sensitivity analysis on key drivers:
- Generation volume
- Fuel prices
- Capacity factors
- Inflation rates

**FR-SCEN-003:** Scenario comparison reporting.

---

## 4. Data Requirements

### 4.1 Input Data Sources
| Data Category | Source | Frequency |
|---------------|--------|-----------|
| Actual Generation | PI/Historian or SCADA | Daily/Monthly |
| Fuel Costs | ERP/Accounting System | Monthly |
| Operating Costs | ERP/Accounting System | Monthly |
| Asset Health Data | Asset Health System | [TBD] |
| Market/Index Data | External Provider | [TBD] |

### 4.2 Historical Data
- Minimum historical data required for trending: [TBD] years
- Historical data migration requirements: [TBD]

---

## 5. Non-Functional Requirements

### 5.1 Usability
- **NFR-USE-001:** Finance team shall be able to update assumptions without IT support
- **NFR-USE-002:** Model logic shall be auditable and transparent
- **NFR-USE-003:** Version control for forecast iterations

### 5.2 Performance
- **NFR-PERF-001:** Full 16-year projection calculation in < [TBD] seconds

### 5.3 Security
- **NFR-SEC-001:** Role-based access control
- **NFR-SEC-002:** Audit logging for all changes

### 5.4 Integration
- **NFR-INT-001:** Asset Health system integration capability
- **NFR-INT-002:** ERP data import (actuals)
- **NFR-INT-003:** Excel export/import for driver assumptions

---

## 6. Technical Considerations

### 6.1 Architecture Options
| Option | Pros | Cons |
|--------|------|------|
| Web Application | Accessible anywhere, centralized | Requires hosting |
| Desktop Application | Offline capability, Excel-like feel | Distribution challenges |
| Excel Add-in/Enhancement | Familiar interface, flexible | Scalability, version control |
| Hybrid (Web + Excel) | Best of both worlds | Complexity |

### 6.2 Database Considerations
- Time-series optimization for 16 years × 12 months × multiple cost lines
- Version/scenario storage
- Historical audit trail

---

## 7. Implementation Phases (Proposed)

### Phase 1: Core Forecasting Engine
- Generation projection framework
- Basic cost category structure
- $/MWhr calculations
- Monthly granularity for Years 1-2

### Phase 2: Fuel Model Migration
- Driver-based model implementation
- Scenario support
- Model documentation/auditability

### Phase 3: Asset Health Integration
- Connect to Asset Health system
- Predictive O&M cost modeling

### Phase 4: Advanced Reporting & Analysis
- Sponsor reporting package
- Variance analysis
- Long-term visualization

---

## 8. Open Questions for Requirements Refinement

### Business Model Questions

1. **Generation Specifics:**
   - What are the nameplate capacities of each plant? Kyger: 5 x 200MW, Clifty: 6 x 200MW
   - What are typical capacity factors by plant? 60-80%
   - How are planned outages currently scheduled and modeled? Spring/Fall mix of timing
   - Do you have seasonal generation patterns? Summer and winter peaks, winter higher lately. We are in PJM.

2. **Fuel Model Complexity:**
   - How many individual drivers does the current fuel model have? Like 100
   - Is the current model in Excel? How many worksheets/tabs? Yes, 40 tabs roughly
   - What are the primary price indices you track (NYMEX, regional coal indices)? mmbtu for eastern and ILB coal.
   - How are coal transportation contracts structured (take-or-pay, variable)? Tons per year but sometimes they miss.
   - Do you hedge any fuel costs? If so, how should hedges be reflected? No

3. **Asset Health System:**
   - What is the Asset Health system platform (IBM Maximo, SAP PM, etc.)? Custom DB. Engineeers are filling out projected repairs for critical equipment (year, risk, description, amount)
   - What data points are available that could inform cost projections? Year of repair, risk, dollar estimate
   - Is there an API or export capability? SQL yeah
   - What "better utilization" would look like for operating cost planning? Not make plants budget those twice

4. **Depreciation/Capital Transition:**
   - When did the transition from cash flow to depreciation billing occur? starting in 2026
   - Do you need to maintain both methodologies for comparison? we do need cashflow but it is lower priority
   - What depreciation methods are used (straight-line, MACRS, etc.)? straight line for now, trying to keep tax income matching
   - How are new capital projects approved and added to the plan? yearly reviews and justification model with NPV/IRR/payback

### Reporting & Stakeholder Questions

5. **Sponsor Reporting:**
   - What specific format do sponsors expect for monthly projections? Excel is their only requirement for monthly
   - Do sponsors receive variance explanations? 1 that asks for it does
   - Is there a specific deadline for sponsor reports? Mostly when they ask
   - Do different sponsors have different reporting needs? They ask for different time frames (1 year, 5 years, 15 year, etc.)

6. **$/MWhr Metrics:**
   - Are there target $/MWhr benchmarks you manage to? No
   - How do you want to handle months with very low generation ($/MWhr distortion)? We have a contract that says to bill our costs. 
   - Do you need $/MWhr trending over time? Not really

### Technical & Operational Questions

7. **Current State:**
   - What tools are currently used for financial planning (Excel, specific software)? Excel, a database where that data is stored
   - How many people need to access/edit the forecasting system? 4 
   - What is the current pain point or catalyst for this project? Struggling reconciling so many excel files and databases

8. **Data & Integration:**
   - What ERP/accounting system is in use? infinium
   - How are actuals currently imported into forecasts? Process in budget database that pulls and combines with maximo erp data (work orders, POs, vendors, invoices)
   - What is the generation data source (PI, OSIsoft, manual)? OATI/WebAccounting

9. **Projection Granularity:**
   - For years 3-16, is annual granularity sufficient? yes
   - Or would you prefer quarterly for years 3-5, annual for 6-16?see above
   - How often are long-term projections updated? twice/year

10. **Scenarios & Sensitivities:**
    - What scenarios are typically run (regulatory changes, fuel price spikes)? THey do a few coal/generation scenarios
    - Do you need Monte Carlo simulation capability or is deterministic sufficient? no idea
    - How many active scenarios need to be maintained simultaneously? budget version, internal forecast, external forecast

### Organizational Questions

11. **Users & Workflow:**
    - Who owns the forecasting process today? I would say us, but CFO
    - What is the typical forecast update cycle (monthly, quarterly)? monthly for operational, coal/generation twice/year
    - How many people typically collaborate on a forecast? 10-12

12. **Change Management:**
    - Is there resistance to moving away from current tools (Excel)? Nah
    - What training/documentation expectations exist? Scattered
    - Are there IT infrastructure constraints (on-premise vs. cloud)? On premise

---

## 9. Glossary

| Term | Definition |
|------|------------|
| $/MWhr | Cost per megawatt-hour of generation |
| Capacity Factor | Actual generation ÷ maximum possible generation |
| Driver-Based Model | Forecast methodology where outputs are calculated from underlying operational/market inputs |
| Heat Rate | BTU of fuel required to generate 1 kWh of electricity |
| Asset Health | Condition-based assessment of equipment used for maintenance planning |
| PPA | Power Purchase Agreement |

---

## 10. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-23 | [Your Name] | Initial draft |

---

*This document should be reviewed and refined based on answers to the open questions in Section 8.*

