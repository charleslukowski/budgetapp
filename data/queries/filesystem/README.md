# File System Sources

CSV files and other file-based data sources from network shares.

## Network Paths

| File | Network Path | Purpose | Frequency |
|------|--------------|---------|-----------|
| Account Master | `\\OVEC-IKEC.com\OVECData\FinPlanRpt\Public\Data\Infinium\all_active_accounts.csv` | GL account list | Periodic |

## Processing

```python
import pandas as pd

# Account master
account_path = r"\\OVEC-IKEC.com\OVECData\FinPlanRpt\Public\Data\Infinium\all_active_accounts.csv"
accounts_df = pd.read_csv(account_path)
```

## Notes

- G: drive maps to `\\OVEC-IKEC.com\OVECData`
- Files are read-only from application perspective
