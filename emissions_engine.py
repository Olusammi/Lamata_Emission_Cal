import pandas as pd

# Base Factors for LAMATA Fleet
BASE_FACTORS = {
    "High Capacity": {
        "Diesel": {"CO2": 1200.0, "NOx": 6.0, "PM": 0.22},
        "CNG": {"CO2": 950.0, "NOx": 2.5, "PM": 0.02},
        "Electric": {"CO2": 0.0, "NOx": 0.0, "PM": 0.0},
        "Biogas": {"CO2": 150.0, "NOx": 2.2, "PM": 0.02}
    },
    "Midi": {
        "Diesel": {"CO2": 800.0, "NOx": 4.2, "PM": 0.15},
        "CNG": {"CO2": 600.0, "NOx": 1.8, "PM": 0.01},
        "Electric": {"CO2": 0.0, "NOx": 0.0, "PM": 0.0}
    },
    "Mini": {
        "Petrol": {"CO2": 350.0, "NOx": 0.4, "PM": 0.005},
        "Diesel": {"CO2": 400.0, "NOx": 1.5, "PM": 0.04},
        "CNG": {"CO2": 280.0, "NOx": 0.3, "PM": 0.001}
    }
}

def get_speed_modifier(speed, pollutant):
    if speed <= 0: return 2.5
    if pollutant == "CO2": 
        return 1.0 + (30.0 / speed) * 0.1 if speed < 30 else 1.0 + (speed / 30.0) * 0.05
    elif pollutant in ["NOx", "PM"]: 
        return max(0.5, 3.5 - (speed / 12.0))
    return 1.0

def calculate_row(row, methodology, target_pollutants):
    bus_type = row.get('Bus_Category')
    fuel = row.get('Fuel_Type')
    distance = row.get('Route_Distance_km', 0)
    speed = row.get('Avg_Speed_kmh', 25)
    ridership = max(1, row.get('Ridership', 1))
    is_revenue = row.get('Revenue_Trip', True)
    
    results = {}
    fuel_profile = BASE_FACTORS.get(bus_type, {}).get(fuel, {"CO2": 1000.0, "NOx": 4.0, "PM": 0.1})
    
    for pol in ['CO2', 'NOx', 'PM']:
        if pol not in target_pollutants:
            results[f'{pol}_kg'] = 0.0
            results[f'{pol}_g_pkm'] = 0.0
            continue
            
        base = fuel_profile.get(pol, 0.0)
        # Apply the methodology rules
        modifier = 1.0 if methodology == "IPCC" or (methodology == "Hybrid" and pol == "CO2") else get_speed_modifier(speed, pol)
        final_factor = base * modifier
        
        results[f'{pol}_kg'] = (final_factor * distance) / 1000.0
        results[f'{pol}_g_pkm'] = final_factor / ridership if is_revenue else 0.0
            
    return pd.Series(results)
