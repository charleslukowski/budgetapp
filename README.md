# OVEC Budget System

Financial planning and forecasting system for Kyger Creek and Clifty Creek coal-fired power plants.

## Overview

This system provides:
- **Generation-based forecasting** - Track MWh generation as the primary output metric
- **Cost category management** - Organize costs by Fuel, Operating, Non-Operating, and Capital
- **$/MWhr metrics** - Calculate and display cost per megawatt-hour across all categories
- **Sponsor reporting** - Generate Excel reports with configurable time horizons (1-15 years)
- **Scenario management** - Maintain Budget, Internal Forecast, and External Forecast versions
- **Driver-based fuel model** - Calculate fuel costs based on configurable input drivers

## Plant Details

| Plant | Capacity | Units |
|-------|----------|-------|
| Kyger Creek | 1,000 MW | 5 x 200 MW |
| Clifty Creek | 1,200 MW | 6 x 200 MW |

## Quick Start

### Prerequisites

- Python 3.10+
- PostgreSQL 14+

### Installation

1. **Clone the repository**
   ```bash
   cd budgetapp
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # or: source venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure database**
   
   Create a `.env` file in the project root:
   ```
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_DATABASE=ovec_budget
   ```

5. **Create database**
   ```bash
   createdb ovec_budget
   ```

6. **Run migrations**
   ```bash
   alembic upgrade head
   ```

7. **Seed initial data**
   ```bash
   python -m src.etl.seed_data
   ```

8. **Start the server**
   ```bash
   python -m uvicorn src.api.main:app --reload
   ```

9. **Access the API**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs

## Project Structure

```
budgetapp/
├── src/
│   ├── api/              # FastAPI endpoints
│   │   ├── main.py       # Application entry point
│   │   └── routes/       # API route handlers
│   ├── models/           # SQLAlchemy models
│   │   ├── plant.py      # Kyger Creek, Clifty Creek
│   │   ├── period.py     # Time periods (monthly/annual)
│   │   ├── cost_category.py  # Cost hierarchy
│   │   ├── scenario.py   # Forecast versions
│   │   └── forecast.py   # Forecast data points
│   ├── engine/           # Calculation engines
│   │   └── fuel_model.py # Driver-based fuel calculations
│   ├── etl/              # Data import/export
│   │   ├── seed_data.py  # Initial data setup
│   │   └── excel_import.py  # Import from Excel
│   ├── reports/          # Report generation
│   │   └── excel_generator.py  # Sponsor Excel reports
│   ├── config.py         # Application settings
│   └── database.py       # Database connection
├── migrations/           # Alembic database migrations
├── tests/                # Test suite
├── docs/
│   └── REQUIREMENTS.md   # Business requirements
├── requirements.txt
└── alembic.ini
```

## API Endpoints

### Plants
- `GET /api/plants` - List all plants
- `GET /api/plants/{id}` - Get plant details

### Scenarios
- `GET /api/scenarios` - List scenarios (with optional filters)
- `POST /api/scenarios` - Create new scenario
- `GET /api/scenarios/{id}` - Get scenario details
- `POST /api/scenarios/{id}/clone` - Clone a scenario
- `PUT /api/scenarios/{id}/lock` - Lock scenario for publishing

### Forecasts
- `GET /api/forecasts/scenario/{id}` - Get all forecasts for a scenario
- `GET /api/forecasts/scenario/{id}/summary` - Get summary by cost section
- `PUT /api/forecasts/{id}` - Update a forecast value

### Reports
- `GET /api/reports/sponsor/{scenario_id}` - Generate sponsor Excel report
  - Query params: `years` (1-16), `include_monthly` (true/false)

## Cost Categories

### Fuel Costs
- Coal Procurement (Eastern & ILB)
- Coal Transportation
- Coal Handling
- Fuel Oil/Gas
- Emissions Allowances
- Environmental Compliance

### Operating Costs
- Plant Labor
- Plant Maintenance
- Materials & Supplies
- Major Maintenance
- Asset Health Items
- Transmission Costs
- Water & Wastewater

### Non-Operating Costs
- Administrative & General
- Insurance
- Property Taxes
- Regulatory Fees
- Professional Services

### Capital Costs
- Depreciation (Existing Assets)
- Depreciation (New Projects)
- Return on Investment
- Capital Project Billing

## Time Horizons

- **Years 1-2**: Monthly granularity (sponsor requirement)
- **Years 3-16**: Annual granularity (through 2040 contract end)

## Scenarios

Three concurrent scenario types are supported:
1. **Budget** - Official approved budget
2. **Internal Forecast** - Working forecast for management
3. **External Forecast** - Forecast shared with sponsors

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black src tests
isort src tests
```

## License

Proprietary - OVEC Internal Use Only

