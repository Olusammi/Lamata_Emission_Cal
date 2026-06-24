import pandas as pd

# Baseline CO2 emission factors (grams per km)
EMISSION_FACTORS = {
    "High Capacity": {
        "Diesel": 1200.0,
        "CNG": 950.0,
        "Electric": 0.0,
        "Biogas": 150.0 
    },
    "Midi": {
        "Diesel": 800.0,
        "CNG": 600.0,
        "Electric": 0.0
    },
    "Mini": {
        "Petrol": 350.0,
        "Diesel": 400.0,
        "CNG": 280.0
    }
}

def calculate_row_emissions(row):
    """Calculates total and per-passenger emissions for a single trip record."""
    bus_type = row.get('Bus_Category')
    fuel = row.get('Fuel_Type')
    distance = row.get('Route_Distance_km', 0)
    ridership = row.get('Ridership', 1) 
    is_revenue = row.get('Revenue_Trip', True)
    
    factor_g_per_km = EMISSION_FACTORS.get(bus_type, {}).get(fuel, 1000.0)
    
    total_co2_kg = (factor_g_per_km * distance) / 1000.0
    
    if is_revenue and ridership > 0:
        co2_per_passenger_g = factor_g_per_km / ridership
    else:
        co2_per_passenger_g = 0.0 
        
    return pd.Series([total_co2_kg, co2_per_passenger_g])