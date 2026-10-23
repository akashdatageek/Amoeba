import pandas as pd
import numpy as np

# Define expected readings for 12 probes
# Assume 24 readings expected per probe (1 per hour)
expected_readings = {
    "P1": [20.0] * 24,
    "P2": [19.99] * 24,
    "P3": [],
    "P4": [-5, 140] + [25.0] * 22,
    "P5": [25.0] * 12,
    "P6": [30.0] * 24,
    "P7": [30.0] * 24,
    "P8": [30.0] * 24,
    "P9": [30.0] * 24,
    "P10": [30.0] * 24,
    "P11": [30.0] * 24,
    "P12": [30.0] * 24,
}

results = []
for probe, readings in expected_readings.items():
    # Filter 0-100
    filtered = [r for r in readings if 0 <= r <= 100]
    n_readings = len(filtered)
    
    # Mean
    avg = np.mean(filtered) if n_readings > 0 else np.nan
    
    # Below 20 (strict)
    below_20 = avg < 20.0 if not np.isnan(avg) else False
    
    # Coverage
    coverage = (len(readings) / 24) * 100 if len(readings) > 0 else 0
    
    # Status
    status = "PULLED"
    if len(readings) == 0:
        status = "NOT PULLED"
    elif coverage <= 50:
        status = "LOW COVERAGE"
        
    results.append({
        "probe_id": probe,
        "n_readings": n_readings,
        "coverage_pct": coverage,
        "avg_vwc_pct": avg,
        "below_20": below_20,
        "status": status
    })

df = pd.DataFrame(results)
df.to_csv("expected_synthetic_results.csv", index=False)
print(df.to_string())
