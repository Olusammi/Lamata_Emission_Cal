"""
Fleet Emissions Engine v4
==========================
Written to be READABLE first. Every step is plain arithmetic:

    total emissions  =  hot running  +  cold start  +  idling  +  A/C load

and every correction is a simple multiplier on a base factor.

──────────────────────────────────────────────────────────────
HOW A ROW IS READ  (important!)
──────────────────────────────────────────────────────────────
One row in the manifest = ONE BUS on ONE DAY.

    Route_Distance_km   → km the bus drove that day  (see DISTANCE_IS_DAILY_TOTAL)
    Num_Trips_Today     → trips completed that day
    Ridership           → passengers carried that day (all trips added up)

From those we derive:

    daily_km      = Route_Distance_km                  (default assumption)
    trip_km       = daily_km / Num_Trips_Today         (length of one trip)
    pax_per_trip  = Ridership / Num_Trips_Today        (people on board at once)
    passenger_km  = Ridership × trip_km                (each rider rides one trip)

Two efficiency views come out of every row:

    g/km   (vehicle view)   = total grams ÷ daily_km
    g/pkm  (passenger view) = total grams ÷ passenger_km

──────────────────────────────────────────────────────────────
METHODOLOGIES
──────────────────────────────────────────────────────────────
    IPCC    — flat emission factor × distance (no speed effect)
    COPERT  — factor × speed correction × distance (all pollutants)
    Hybrid  — CO₂ flat (IPCC style), NOx & PM speed-corrected (COPERT style)

The speed curves are NORMALISED: at the 50 km/h reference speed the
correction is exactly 1.0, so COPERT and IPCC agree at reference speed
and only diverge in congestion (slow) or free-flow (fast) conditions.
(v3 was missing this normalisation — it inflated COPERT results ~1.7×.)

Sources: IPCC 2006 Tier 2 base factors · EMEP/EEA Guidebook 2019 curve
shapes for urban buses · IEA 2023 Nigeria grid factor.
"""

import pandas as pd

# ══════════════════════════════════════════════════════════════
# SECTION 1 — BASE EMISSION FACTORS
# Grams emitted per km, for a Euro III vehicle at 50 km/h.
# Everything else in this file is a multiplier on these numbers.
# ══════════════════════════════════════════════════════════════
BASE_FACTORS = {
    "High Capacity": {
        "Diesel":   {"CO2": 1320.0, "NOx": 14.5, "PM": 0.28,  "capacity": 150},
        "CNG":      {"CO2":  980.0, "NOx":  5.2, "PM": 0.03,  "capacity": 150},
        "Electric": {"CO2":    0.0, "NOx":  0.0, "PM": 0.0,   "capacity": 150, "kwh_per_km": 2.1},
        "Biogas":   {"CO2":  110.0, "NOx":  4.8, "PM": 0.03,  "capacity": 150},
        "Petrol":   {"CO2": 1450.0, "NOx":  4.0, "PM": 0.05,  "capacity": 150},
    },
    "Midi": {
        "Diesel":   {"CO2":  860.0, "NOx":  8.8, "PM": 0.18,  "capacity": 80},
        "CNG":      {"CO2":  640.0, "NOx":  3.1, "PM": 0.02,  "capacity": 80},
        "Electric": {"CO2":    0.0, "NOx":  0.0, "PM": 0.0,   "capacity": 80,  "kwh_per_km": 1.2},
        "Hybrid":   {"CO2":  520.0, "NOx":  4.5, "PM": 0.09,  "capacity": 80},
    },
    "Mini": {
        "Petrol":   {"CO2":  400.0, "NOx":  0.9, "PM": 0.012, "capacity": 18},
        "Diesel":   {"CO2":  450.0, "NOx":  2.8, "PM": 0.06,  "capacity": 18},
        "CNG":      {"CO2":  300.0, "NOx":  0.6, "PM": 0.003, "capacity": 18},
    },
}
# Used when a row's category/fuel combination is unknown:
FALLBACK_FACTORS = {"CO2": 1100.0, "NOx": 7.0, "PM": 0.15, "capacity": 80}

# ══════════════════════════════════════════════════════════════
# SECTION 1b — RAW DATA NORMALISATION
# Real exports say "HC", "PMS", etc. Map them onto the canonical
# keys above. "Unknown" is deliberately NOT mapped — it gets
# flagged instead of guessed.
# ══════════════════════════════════════════════════════════════
CATEGORY_ALIASES = {
    "HC": "High Capacity", "High Capacity": "High Capacity",
    "MIDI": "Midi", "Midi": "Midi", "Mid": "Midi",
    "MINI": "Mini", "Mini": "Mini",
    "FLM": "Mini", "X30L": "Mini", "FLM X30L": "Mini",
}
FUEL_ALIASES = {
    "PMS": "Petrol", "Petrol": "Petrol", "Gasoline": "Petrol",
    "Diesel": "Diesel", "AGO": "Diesel",
    "CNG": "CNG", "Electric": "Electric", "EV": "Electric",
    "Biogas": "Biogas", "Hybrid": "Hybrid",
}


def normalize_category(raw):
    """Returns (canonical_category, was_mapped)."""
    raw = str(raw).strip()
    if raw in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[raw], True
    return raw, False


def normalize_fuel(raw):
    """Returns (canonical_fuel, was_mapped)."""
    raw = str(raw).strip()
    if raw in FUEL_ALIASES:
        return FUEL_ALIASES[raw], True
    return raw, False


def parse_revenue_trip(raw):
    """Revenue_Trip in real exports is fare revenue in Naira (e.g. 325080).
    Any positive number = a revenue trip. Also accepts True/False text."""
    s = str(raw).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no", "", "nan", "none"):
        return False
    try:
        return float(raw) > 0
    except (TypeError, ValueError):
        return False


# ══════════════════════════════════════════════════════════════
# SECTION 2 — EURO CLASS MULTIPLIERS  (NOx and PM only)
# Euro standards regulate after-treatment (catalysts, filters),
# which cuts NOx/PM — but NOT CO₂, which comes from burning fuel.
# Euro III = 1.0 because the base factors above are Euro III.
# Source: EEA COPERT V real-world factor ratios.
# ══════════════════════════════════════════════════════════════
EURO_FACTORS = {
    "Euro II":  {"NOx": 1.30, "PM": 1.45},
    "Euro III": {"NOx": 1.00, "PM": 1.00},   # ← reference
    "Euro IV":  {"NOx": 0.55, "PM": 0.45},
    "Euro V":   {"NOx": 0.30, "PM": 0.25},
    "Euro VI":  {"NOx": 0.05, "PM": 0.04},
    # Euro VII — EU Regulation 2024/1257 (adopted 29 Apr 2024). Type-approval
    # for buses/heavy trucks (M3/N3) phases in ~36 months after light-duty,
    # i.e. new type approvals from roughly 2028-29. Lab-cycle limits sit
    # close to Euro VI, but the regulation's real gain is much broader
    # real-driving-conditions testing and far longer durability requirements
    # (up to 875,000 km / 15 years for M3/N3, vs shorter Euro VI windows) —
    # intended to close most of the real-world NOx gap Euro VI still shows
    # (see REAL_WORLD_NOX_FACTOR below). Modelled here as a modest further
    # cut on top of Euro VI; this is an engineering estimate for planning
    # purposes, not a certified figure — no bus/truck has been type-approved
    # to Euro VII yet at time of writing.
    "Euro VII": {"NOx": 0.04, "PM": 0.03},
}
DEFAULT_EURO = "Euro III"
EURO_ORDER = {"Euro II": 2, "Euro III": 3, "Euro IV": 4, "Euro V": 5, "Euro VI": 6, "Euro VII": 7}

# ══════════════════════════════════════════════════════════════
# SECTION 3 — ENGINE MODEL CO₂ CORRECTION
# Small multiplier for known engine families (fuel-efficiency
# differences observed in operator fuel records).
# ══════════════════════════════════════════════════════════════
ENGINE_CO2_CORRECTION = {
    "Yuchai YC6K": 1.04, "Weichai WP7": 0.97, "Cummins ISB": 1.01,
    "Yuchai YC4G": 0.99, "Toyota 2TR": 0.95, "Toyota 1HZ": 1.02,
    "Yuchai YC4D": 0.98, "BYD D9": 1.00, "Higer KLQ6125": 1.00,
    "Scania OC9": 0.93,
}
DEFAULT_ENGINE_CORRECTION = 1.00


# ══════════════════════════════════════════════════════════════
# SECTION 4 — AGE DETERIORATION
# Older engines and worn after-treatment emit more per km.
#   NOx: +1.5 %/year (diesel/petrol), +0.8 %/year (gas fuels)
#   PM : +2.0 %/year (diesel/petrol), +0.5 %/year (gas fuels)
#   CO₂: +0.4 %/year — a fuel-economy-ageing assumption, NOT a
#        COPERT rule (COPERT degrades CO/HC/NOx only). Set
#        CO2_AGEING_PER_YEAR = 0.0 to switch it off.
# ══════════════════════════════════════════════════════════════
CO2_AGEING_PER_YEAR = 0.004


def age_deterioration(age_years, fuel_type):
    """Returns {'CO2': x, 'NOx': y, 'PM': z} multipliers, capped at 20 yrs."""
    age = max(0, min(int(age_years), 20))
    nox_rate = 0.015 if fuel_type in ("Diesel", "Petrol") else 0.008
    pm_rate  = 0.020 if fuel_type in ("Diesel", "Petrol") else 0.005
    return {
        "CO2": 1.0 + CO2_AGEING_PER_YEAR * age,
        "NOx": 1.0 + nox_rate * age,
        "PM":  1.0 + pm_rate * age,
    }


# ══════════════════════════════════════════════════════════════
# SECTION 5 — SPEED CORRECTION  (the COPERT part)
# Buses emit MORE per km when crawling in traffic (engine runs
# longer per km, stop-and-go) and slightly less in free flow.
# Curve shape: 1 + K/V — the classic "congestion penalty" shape
# from the EMEP/EEA urban-bus curves, then NORMALISED so the
# multiplier is exactly 1.0 at REF_SPEED_KMH.
#
#   speed_factor = raw(V) / raw(50)
#
# Example (CO₂): 10 km/h → ×2.17   ·   50 km/h → ×1.00   ·   80 km/h → ×0.93
# ══════════════════════════════════════════════════════════════
REF_SPEED_KMH = 50.0
SPEED_MIN, SPEED_MAX = 5.0, 85.0          # curves valid in this range

_CONGESTION_K = {"CO2": 25.0, "NOx": 18.0, "PM": 30.0}
_FREEFLOW_SLOPE = {"CO2": 1 / 400.0, "NOx": 0.0, "PM": 0.0}


def _raw_curve(pollutant, v):
    """Un-normalised emission-vs-speed shape."""
    k = _CONGESTION_K[pollutant]
    m = _FREEFLOW_SLOPE[pollutant]
    return 1.0 + k / v + m * v


def speed_factor(pollutant, speed_kmh):
    """Multiplier on the base factor for a given average speed.
    Equals 1.0 at 50 km/h by construction."""
    v = max(SPEED_MIN, min(float(speed_kmh or REF_SPEED_KMH), SPEED_MAX))
    return _raw_curve(pollutant, v) / _raw_curve(pollutant, REF_SPEED_KMH)


# Backward-compatible helpers (used by the Formula Explainer):
def _spd_co2(s): return speed_factor("CO2", s)
def _spd_nox(s): return speed_factor("NOx", s)
def _spd_pm(s):  return speed_factor("PM", s)
SPD_FN = {"CO2": _spd_co2, "NOx": _spd_nox, "PM": _spd_pm}


# ══════════════════════════════════════════════════════════════
# SECTION 5B — REAL COPERT SPEED-EMISSION CURVES  (buses)
# Source: EMEP/EEA Air Pollutant Emission Inventory Guidebook 2023,
# Update 2025 (COPERT 5.9), Chapter 1.A.3.b.i-iv "Road transport",
# Appendix 4 "Emission Factors" (Nov 2025 edition), sheet
# HOT_EMISSIONS_PARAMETERS. This replaces the single normalised
# curve above with REAL per-Euro-class curves, for the vehicle/fuel
# combinations the Guidebook actually covers as buses.
#
# Generic equation (Guidebook §3.4.2, Eq. 25):
#   EF(V) = (α·V² + β·V + γ + δ/V) / (ε·V² + ζ·V + η) × (1 - RF)
# Coefficients are for Slope=0%, Load=50% (matches this engine's own
# _load_corr() reference point, so the two compose correctly).
#
# Segment mapping (by capacity, the closest physical match):
#   "High Capacity" (150 seats+standing) → COPERT "Urban Buses
#       Articulated >18t"
#   "Midi" (80)                          → COPERT "Urban Buses
#       Standard 15-18t"
#   "Mini" (18) has no COPERT bus segment at all (COPERT's smallest
#       bus class is 15t+) — Mini stays on the simplified
#       BASE_FACTORS/EURO_FACTORS system below, by design.
#
# 'Euro VI' here uses the Guidebook's 'Euro VI D/E' coefficient set
# (the more current implementation step); 'Euro VI A/B/C' data exists
# in the source but isn't used. CNG coverage in the source itself is
# incomplete — full Euro I-VII curves only exist for Diesel; CNG has
# a generic (size-unspecified) curve for EEV/Euro I-III and separate
# size-specific curves for Euro VI D/E and Euro VII only. Where the
# guidebook itself has no coefficient (e.g. CNG Euro IV/V at either
# size), lookup falls through to the simplified system rather than
# guessing.
#
# Two real-COPERT facts this exposes that the simplified system above
# does NOT reflect:
#   1. Heavy-duty vehicles/buses get NO cold-start over-emission
#      modelling in COPERT (Guidebook Table 3-36, method "B1" =
#      "No Cold Start Overemission Calculations" — cold start is only
#      modelled for passenger cars/LCVs). When a real curve is used
#      below, cold start is skipped for that pollutant, matching
#      COPERT; idling and A/C uplift are still added on top, since
#      neither is part of the Guidebook's speed curve.
#   2. CO2 for heavy-duty vehicles isn't itself in this equation —
#      it's derived from energy consumption (pollutant "EC", MJ/km),
#      which IS speed-dependent, converted to CO2 via a fuel carbon
#      factor (IPCC 2006 Guidelines, Vol. 2, Table 1.4: Diesel/Gas
#      oil 74.1 g CO2/MJ, Natural gas/CNG 56.1 g CO2/MJ).
# ══════════════════════════════════════════════════════════════
FUEL_CO2_PER_MJ = {"Diesel": 74.1, "CNG": 56.1}  # IPCC 2006 Guidelines Vol.2 Table 1.4
_COPERT_CAT_KEY = {"High Capacity": "High_Capacity", "Midi": "Midi"}

# Tuple layout: (alpha, beta, gamma, delta, epsilon, zeta, eta, reduction_factor, min_speed, max_speed)
COPERT_BUS_COEFFS = {}

COPERT_BUS_COEFFS[('High_Capacity', 'Diesel', 'NOx')] = {
    'Euro I': (0.000195532436686655, 0.109812151361716, 4.66071689383795, 19.2667704614656, 9.22227500103027e-05, 0.0144651402712633, 0.224055530487258, 0, 11, 86),
    'Euro II': (-5.50851830714555e-05, 0.0254129577512646, 4.21292716596206, 33.3089748069781, -6.84759683482164e-06, 0.00717756449156061, 0.274777307792719, 0, 11, 86),
    'Euro III': (0.000763411676524867, 0.307437823357835, 4.66815627689041, -15.9637226340815, 0.00051512586531376, 0.0330068264882036, -0.123742694321276, 0, 11, 86),
    'Euro IV': (-0.000445085100891601, 0.0275476837985451, 1.24717347448867, -10.7885397391889, -0.00012413777027339, 0.0124143199514201, -0.0763460631567738, 0, 11, 86),
    'Euro V': (0.000448936394674791, -0.0698232216664305, 3.23351099234636, 3.50900649838609, -0.000108430347451541, 0.0113966775508668, 0.0731766087727267, 0, 5, 85),
    'Euro VI': (-7.289143631615881, 640.0828583578445, 13785.15089625432, -109902.1922219768, -1.475481308546263, 135.6939022337642, -837.4527868155939, 0.8552155015111091, 5, 70),
    'Euro VII': (-7.289143631615881, 640.0828583578445, 13785.15089625432, -109902.1922219768, -1.475481308546263, 135.6939022337642, -837.4527868155939, 0.9827968672469168, 5, 70),
}
COPERT_BUS_COEFFS[('High_Capacity', 'Diesel', 'PM')] = {
    'Euro I': (0.000465634661534354, 0.00298331462391513, -0.322790517321939, 4.25460766749388, 0.00241121321194577, -0.0703513062480048, 0.667429645241618, 0, 11, 86),
    'Euro II': (1.77955694497166e-06, 0.0104282889182441, 0.858929290049523, 3.44669292104467, -0.000455156457185917, 0.143189000721325, 1.45323626865616, 0, 11, 86),
    'Euro III': (0.000501047237555967, -0.0136648092753171, 0.176363500118427, 5.46320076057103, 0.00422916068072395, -0.154175794944945, 2.7386273940053, 0, 11, 86),
    'Euro IV': (9.41099911235173e-19, 1.47112469597986e-16, 0.528508623581499, 3.24860954892122e-14, -0.00116418020721057, 0.280386945749681, 2.48632108508629, 0, 11, 86),
    'Euro V': (0.0569254928417283, 4.86164520570646, 1.44286363604206, -0.70858277536769, 0.0103132948942481, 0.147261195595975, -0.0437043211566113, 0.996296324294868, 5, 85),
    'Euro VI': (0.0451235940688133, 2.3036639058463, -4.06494004790822, 5.87148659939171, 0.00678893767998712, 0.0337400558521148, 8.1336343673265e-14, 0.999606579865608, 5, 70),
    'Euro VII': (0.0451235940688133, 2.3036639058463, -4.06494004790822, 5.87148659939171, 0.00678893767998712, 0.0337400558521148, 8.1336343673265e-14, 0.9998348925337633, 5, 70),
}
COPERT_BUS_COEFFS[('High_Capacity', 'Diesel', 'EC')] = {
    'Euro I': (0.00750242313909769, 0.708124249106715, 0.506862042551121, -15.0427359906727, 0.00131971637286938, 0.0234671625116625, -0.11529326762189, 0, 11, 86),
    'Euro II': (-0.00103051312432459, 0.0755560339791729, 1.73770925901112, -21.255387898077, -0.000120348024664702, 0.0119465060453488, -0.0953957881013158, 0, 11, 86),
    'Euro III': (0.0202435674402851, 1.51420941493468, 5.83994344444744, 5.07864004860022, 0.00310367991886572, 0.0508529615404832, 0.049615103832913, 0, 11, 86),
    'Euro IV': (-0.00210744909983318, 0.111452734374685, 7.17599504640295, -11.0268007288627, -0.000248717473485706, 0.0212238398165323, 0.123715388381394, 0, 11, 86),
    'Euro V': (0.0569254928417283, 4.86164520570646, 1.44286363604206, -0.70858277536769, 0.0103132948942481, 0.147261195595975, -0.0437043211566113, 0, 5, 85),
    'Euro VI': (-7.289143631615881, 640.0828583578445, 13785.15089625432, -109902.1922219768, -1.475481308546263, 135.6939022337642, -837.4527868155939, -0.29737445741800195, 5, 70),
    'Euro VII': (-7.289143631615881, 640.0828583578445, 13785.15089625432, -109902.1922219768, -1.475481308546263, 135.6939022337642, -837.4527868155939, -0.29737445741800195, 5, 70),
}
COPERT_BUS_COEFFS[('Midi', 'Diesel', 'NOx')] = {
    'Euro I': (0.00204764855616657, 0.520675761907294, 3.51293072156612, -32.7300900799171, 0.000807873517542598, 0.0583792740097243, -0.33773418070682, 0, 11, 86),
    'Euro II': (0.00412402434651283, 0.530618573879136, 12.5540275765813, 18.0130664324151, 0.00106836919811916, 0.0682479516111295, 0.27296756282642, 0, 11, 86),
    'Euro III': (0.000962853827383582, 0.43283442172761, 7.09802501183916, 2.96198426932413, 0.000927291647143319, 0.0590819238383194, -0.109147145287551, 0, 11, 86),
    'Euro IV': (5.62810387454345e-05, 0.039286305754102, 1.96671452388567, 9.88657960075961, 7.77974796392815e-05, 0.012505766046485, 0.20147566016008, 0, 11, 86),
    'Euro V': (0.000353348102039702, -0.0561829022680765, 2.65091227404064, 7.87360468889005, -6.23807914060858e-05, 0.0065929959703913, 0.13094553823857, 0, 5, 85),
    'Euro VI': (181.6450509528872, 11196.70591002358, -86923.50339496524, -178082.241348017, 268.4244141309995, 5622.852151466637, -67105.02513131434, 0, 5, 70),
    'Euro VII': (181.6450509528872, 11196.70591002358, -86923.50339496524, -178082.241348017, 268.4244141309995, 5622.852151466637, -67105.02513131434, 0.881412468953943, 5, 70),
}
COPERT_BUS_COEFFS[('Midi', 'Diesel', 'PM')] = {
    'Euro I': (0.00054623434303941, -0.0100947610770257, 1.55050653202624, 1.83664463745264, 0.00215546731591781, 0.0511546546228944, 1.53598784038669, 0, 11, 86),
    'Euro II': (1.86821137266366e-05, 0.00650439682870461, 0.563592329320611, 2.81835485261303, -0.000451049200579574, 0.133144751468373, 1.26448085671401, 0, 11, 86),
    'Euro III': (-9.49544098476157e-06, 0.00640497538366598, 0.740307998518696, 3.42256439460857, -0.000527747624495991, 0.163394606462353, 1.53809792008495, 0, 11, 86),
    'Euro IV': (1.20775820717059e-15, 1.65813412025685e-14, 0.895448931282914, 2.37628806159087e-11, -0.00297923000651941, 0.573992238313472, 5.95453980806337, 0, 11, 86),
    'Euro V': (-0.000234263438032306, -0.010102311471057, 3.44647787320417, 4.53931683520842, -8.27687128466504e-05, 0.00655835406931008, 0.151315345197098, 0.996296324294868, 5, 85),
    'Euro VI': (-0.000313881923547988, -0.0145484315009182, 5.33927720306299, 4.32988739703353, -0.000119639044053958, 0.0102176505703206, 0.211097947587396, 0.999606579865608, 5, 70),
    'Euro VII': (-0.000313881923547988, -0.0145484315009182, 5.33927720306299, 4.32988739703353, -0.000119639044053958, 0.0102176505703206, 0.211097947587396, 0.9998348925337633, 5, 70),
}
COPERT_BUS_COEFFS[('Midi', 'Diesel', 'EC')] = {
    'Euro I': (-9.69247948896325e-05, 0.0285033921486055, 2.59488151004893, 9.20471392321822, -3.04306920399323e-05, 0.00785900076582361, 0.0895249413877887, 0, 11, 86),
    'Euro II': (-0.000210893799545693, 0.0309629204113653, 2.22901448191258, 4.49443122020401, -4.65895127733592e-05, 0.00806060580238086, 0.0612942559589402, 0, 11, 86),
    'Euro III': (-0.000240994412232972, 0.0338229795225614, 2.44327779207519, 4.65941312172263, -5.04965028853241e-05, 0.00852073434119492, 0.061276675893548, 0, 11, 86),
    'Euro IV': (0.0023623927278234, -0.0144788518494557, -0.427170645167993, 7.15496310200787, 0.000327568250882569, -0.00777932579733725, 0.0660570813937103, 0, 11, 86),
    'Euro V': (-0.000234263438032306, -0.010102311471057, 3.44647787320417, 4.53931683520842, -8.27687128466504e-05, 0.00655835406931008, 0.151315345197098, 0, 5, 85),
    'Euro VI': (-7.289143631615881, 640.0828583578445, 13785.15089625432, -109902.1922219768, -1.475481308546263, 135.6939022337642, -837.4527868155939, 0, 5, 70),
    'Euro VII': (-7.289143631615881, 640.0828583578445, 13785.15089625432, -109902.1922219768, -1.475481308546263, 135.6939022337642, -837.4527868155939, 0, 5, 70),
}
COPERT_BUS_COEFFS[('High_Capacity', 'CNG', 'NOx')] = {
    'Euro VI': (0.71534510928232, -73.5061715194338, 5434.84824992738, 0, 0, 116.814029314938, 3550.30720016334, 0, 5, 85),
    'Euro VII': (0.71534510928232, -73.5061715194338, 5434.84824992738, 0, 0, 116.814029314938, 3550.30720016334, 0.15, 5, 85),
}
COPERT_BUS_COEFFS[('High_Capacity', 'CNG', 'PM')] = {
    'Euro VI': (0.0444933787504169, -4.57198209232491, 338.038770000937, 0, 0, 538.892640609864, 16378.5858695107, 0, 5, 85),
    'Euro VII': (0.0444933787504169, -4.57198209232491, 338.038770000937, 0, 0, 538.892640609864, 16378.5858695107, 0.3, 5, 85),
}
COPERT_BUS_COEFFS[('High_Capacity', 'CNG', 'EC')] = {
    'Euro VI': (1984.1717701363, -203886.034517985, 15074781.6074066, 0, 0, 9019.17653416815, 274118.245438158, 0, 5, 85),
    'Euro VII': (1984.1717701363, -203886.034517985, 15074781.6074066, 0, 0, 9019.17653416815, 274118.245438158, 0, 5, 85),
}
COPERT_BUS_COEFFS[('Midi', 'CNG', 'NOx')] = {
    'Euro VI': (1.454364, 12.28338, -3572.43, 81982.7, 16.63304, -871.796, 13263.24, 0, 5, 85),
    'Euro VII': (1.454364, 12.28338, -3572.43, 81982.7, 16.63304, -871.796, 13263.24, 0.15, 5, 85),
}
COPERT_BUS_COEFFS[('Midi', 'CNG', 'PM')] = {
    'Euro VI': (0.00668361463754694, -0.905301305406419, 43.27101279318, 0, 0, 0, 3829.84944299177, 0, 5, 85),
    'Euro VII': (0.00668361463754694, -0.905301305406419, 43.27101279318, 0, 0, 0, 3829.84944299177, 0.3, 5, 85),
}
COPERT_BUS_COEFFS[('Midi', 'CNG', 'EC')] = {
    'Euro VI': (2.902952, -7.92778, -948.88, 8227.055, 0.309673, -7.13133, 43.29193, 0, 5, 85),
    'Euro VII': (2.902952, -7.92778, -948.88, 8227.055, 0.309673, -7.13133, 43.29193, 0, 5, 85),
}

# CNG generic (size-unspecified) curve — the only coverage for EEV/Euro I-III
COPERT_BUS_COEFFS_CNG_GENERIC = {
    "NOx": {
        'Euro I': (0, 0, 16.5, 0, 0, 0, 1, 0, 6, 75),
        'Euro II': (0, 0, 15, 0, 0, 0, 1, 0, 6, 75),
        'Euro III': (0, 0, 10, 0, 0, 0, 1, 0, 6, 75),
        'EEV': (0.00335581295550362, 1.01967944213972, 1.53109837593671, -59.7733124681003, 0.00594115413805745, 0.222318774051069, -1.86161421670294, 0, 11, 86),
    },
    "PM": {
        'Euro I': (0, 0, 0.02, 0, 0, 0, 1, 0, 6, 75),
        'Euro II': (0, 0, 0.01, 0, 0, 0, 1, 0, 6, 75),
        'Euro III': (0, 0, 0.01, 0, 0, 0, 1, 0, 6, 75),
        'EEV': (2.99508607917677e-05, 0.00432140568014104, 1.04889571499637, 4.09826315848808, -0.011483064903324, 3.52203270045111, 54.1727457325872, 0, 11, 86),
    },
    "EC": {
        'Euro I': (0, 0, 555, 0, 0, 0, 20.8333333333333, 0, 6, 75),
        'Euro II': (0, 0, 515, 0, 0, 0, 20.8333333333333, 0, 6, 75),
        'Euro III': (0, 0, 455, 0, 0, 0, 20.8333333333333, 0, 6, 75),
        'EEV': (-0.000186970637762985, 0.0687149794113224, 5.7022140873118, 19.4144566985669, -4.883540497789e-05, 0.0133456134788077, 0.153469463592991, 0, 11, 86),
    },
}

# Battery electric buses: a single generic curve (drivetrain has no combustion
# Euro class, so the Guidebook reuses one EC curve regardless of "Euro" label).
COPERT_BUS_COEFFS_ELECTRIC_EC = (0.018504, 1.4e-08, 6.914233, 1.538516, 9.64e-06, 0.000279, 0.000115, 0.9964, 5, 85)


def _eval_copert_curve(coeffs, speed_kmh):
    a, b, g, d, e, z, h, rf, min_v, max_v = coeffs
    v = max(min_v, min(float(speed_kmh or REF_SPEED_KMH), max_v))
    denom = e * v * v + z * v + h
    if denom == 0:
        return None
    ef = (a * v * v + b * v + g + d / v) / denom * (1.0 - rf)
    return max(0.0, ef)


def copert_ef(bus_cat, fuel, pollutant, euro, speed_kmh):
    """Real Guidebook speed-emission factor in g/km (NOx, PM) or MJ/km
    (EC), or None if this combination isn't covered by the source data
    — callers should fall back to the simplified BASE_FACTORS system."""
    if fuel == "Electric":
        return _eval_copert_curve(COPERT_BUS_COEFFS_ELECTRIC_EC, speed_kmh) if pollutant == "EC" else 0.0
    cat_key = _COPERT_CAT_KEY.get(bus_cat)
    if cat_key is None:
        return None
    coeffs = None
    table = COPERT_BUS_COEFFS.get((cat_key, fuel, pollutant))
    if table and euro in table:
        coeffs = table[euro]
    elif fuel == "CNG":
        coeffs = COPERT_BUS_COEFFS_CNG_GENERIC.get(pollutant, {}).get(euro)
    if coeffs is None:
        return None
    return _eval_copert_curve(coeffs, speed_kmh)


# ══════════════════════════════════════════════════════════════
# SECTION 6 — COLD START  (temperature-aware)
# A cold engine over-emits for the first few km. Buses running
# trips back-to-back stay warm, so we count COLD STARTS PER DAY
# (default 1 — the morning start), NOT one per trip.
#
# The penalty shrinks with ambient temperature and disappears at
# 30 °C. In Lagos (~28 °C) it is small — as it should be.
#
#   chill  = max(0, (30 − ambient) / 30)        0 at 30°C, 1 at 0°C
#   mult   = 1 + (mult_at_0°C − 1) × chill
#   extra  = EF × cold_km × (mult − 1) × starts_per_day
# ══════════════════════════════════════════════════════════════
COLD_STARTS_PER_DAY = 1
COLD_START_KM = 5.0                        # distance driven "cold"
COLD_START_MULT_AT_0C = {"CO2": 1.25, "NOx": 2.8, "PM": 3.2}
COLD_START_MULT = COLD_START_MULT_AT_0C    # legacy alias
DEFAULT_AMBIENT_C = 28.0                   # Lagos average


def cold_start_multiplier(pollutant, ambient_c=DEFAULT_AMBIENT_C):
    """Cold-start over-emission multiplier at a given ambient temp."""
    chill = max(0.0, (30.0 - float(ambient_c)) / 30.0)
    return 1.0 + (COLD_START_MULT_AT_0C[pollutant] - 1.0) * chill


# ══════════════════════════════════════════════════════════════
# SECTION 7 — IDLING  (grams per minute at idle)
# Terminals, traffic lights, boarding. Multiplied by the row's
# Idle_Minutes column, or DEFAULT_IDLE_MINUTES if absent.
# ══════════════════════════════════════════════════════════════
IDLING_EF = {
    "High Capacity": {
        "Diesel": {"CO2": 28.0, "NOx": 0.22, "PM": 0.006},
        "CNG":    {"CO2": 20.0, "NOx": 0.08, "PM": 0.001},
        "Biogas": {"CO2":  3.5, "NOx": 0.07, "PM": 0.001},
        "Petrol": {"CO2": 30.0, "NOx": 0.05, "PM": 0.001},
    },
    "Midi": {
        "Diesel": {"CO2": 18.0, "NOx": 0.14, "PM": 0.004},
        "CNG":    {"CO2": 12.0, "NOx": 0.05, "PM": 0.0005},
    },
    "Mini": {
        "Petrol": {"CO2":  9.0, "NOx": 0.03, "PM": 0.0005},
        "Diesel": {"CO2": 10.0, "NOx": 0.07, "PM": 0.002},
        "CNG":    {"CO2":  6.5, "NOx": 0.02, "PM": 0.0002},
    },
}
DEFAULT_IDLE_MINUTES = 10.0

# ══════════════════════════════════════════════════════════════
# SECTION 8 — A/C AND ELECTRIC
# ══════════════════════════════════════════════════════════════
AC_UPLIFT_CO2 = 0.08          # +8 % CO₂ when A/C is on (hot + idle)
AC_UPLIFT_KWH = 0.10          # +10 % electricity for A/C on e-buses
GRID_EF_KG_PER_KWH = 0.46     # Nigeria grid, kg CO₂e per kWh (IEA 2023)

# ══════════════════════════════════════════════════════════════
# SECTION 9 — PASSENGER LOAD CORRECTION
# A fuller bus is heavier → burns a little more fuel. Roughly
# +8 % from empty to full for city buses (COPERT load effect).
# Uses passengers ON BOARD (per trip), not the daily total.
# ══════════════════════════════════════════════════════════════
def _load_corr(pax_on_board, capacity):
    """Multiplier: 0.96 empty · 1.00 half-full · 1.04 full."""
    if capacity <= 0:
        return 1.0
    ratio = min(pax_on_board / capacity, 1.2)
    return 1.0 + 0.08 * (ratio - 0.5)


# ══════════════════════════════════════════════════════════════
# SECTION 9B — REAL-WORLD NOx GAP  (diesel, Euro V/VI/VII)
# Type-approval (lab-cycle) NOx is not what these engines emit in
# real urban driving — extensively documented since "dieselgate":
#   EEA, "Explaining road transport emissions" (2019)
#   ICCT working papers on real-world/type-approval NOx ratios
#     for heavy-duty diesel (2016-2018)
#
# Euro V had NO real-driving-emissions (RDE) test requirement at
# all: independent testing commonly found real-world NOx running
# 3-4x the type-approval limit for Euro V heavy-duty diesel.
# Euro VI phased in RDE testing with a legal "conformity factor"
# (2017+); measured real-world/lab ratios for RDE-tested Euro VI
# have fallen to roughly 1.1-1.5x, though the earliest Euro VI
# units (pre-RDE) skew higher.
# Euro VII broadens real-driving test coverage further still, so
# the gap is modelled as narrowing again — an engineering estimate,
# since no Euro VII heavy-duty vehicle has real-world data yet.
#
# Only diesel combustion shows this documented gap (it's a NOx
# after-treatment / driving-condition effect); CNG, electric and
# biogas are not adjusted.
#
# This multiplier is a published-literature CENTRAL ESTIMATE, not a
# certified per-vehicle figure — treat it as "how much worse should
# I assume real-world NOx is than the label", not a measured value
# for any specific bus.
# ══════════════════════════════════════════════════════════════
REAL_WORLD_NOX_FACTOR = {
    "Euro II":  1.0,   # pre-dates modern after-treatment; too little RDE literature to adjust
    "Euro III": 1.0,
    "Euro IV":  1.0,
    "Euro V":   3.5,   # no RDE requirement — largest documented gap
    "Euro VI":  1.3,   # RDE-tested, conformity-factor regime
    "Euro VII": 1.05,  # broadened real-driving coverage narrows the gap further (estimate)
}


def real_world_nox_multiplier(euro_standard, fuel_type):
    """Multiplier on top of the type-approval NOx figure, reflecting
    the documented real-world/lab gap. Returns 1.0 (no adjustment)
    for non-diesel fuels or an unrecognised Euro standard."""
    if fuel_type != "Diesel":
        return 1.0
    return REAL_WORLD_NOX_FACTOR.get(euro_standard, 1.0)


# ══════════════════════════════════════════════════════════════
# SECTION 9C — NON-EXHAUST PARTICULATES  (brake + tyre wear)
# As exhaust PM has fallen with particulate filters, brake and tyre
# wear are now a major — often the majority — share of a vehicle's
# real PM2.5/PM10, and NONE of it is captured by the tailpipe
# figures above.
#
# Euro VII (EU Reg. 2024/1257) introduces the first-ever regulatory
# brake-particle limits — but only for M1/N1 (cars/vans); buses
# (M3) are not yet limited. That's exactly why tracking it here is
# useful even without a compliance threshold to check it against.
#
# Base factors are representative CENTRAL ESTIMATES (mg per vehicle-km,
# PM10) from:
#   EEA, "Non-exhaust road traffic emissions" briefing (2019)
#   OECD, "Non-exhaust Particulate Emissions from Road Transport" (2020)
# Real-world values vary roughly 2-3x with brake type (disc vs
# drum), pad/lining material, tyre compound, and driving style —
# treat these as indicative, not measured, figures. Regenerative
# braking (electric/hybrid) is well-documented to cut brake wear by
# roughly half to two-thirds; it does not reduce tyre wear.
# ══════════════════════════════════════════════════════════════
NON_EXHAUST_PM10_MG_PER_KM = {
    "High Capacity": {"brake": 22.0, "tyre": 32.0},
    "Midi":          {"brake": 14.0, "tyre": 20.0},
    "Mini":          {"brake": 7.0,  "tyre": 10.0},
}
PM10_TO_PM25_BRAKE = 0.55   # fraction of brake-wear PM10 that is PM2.5 (finer particles)
PM10_TO_PM25_TYRE = 0.35    # fraction of tyre-wear PM10 that is PM2.5 (coarser particles)
REGEN_BRAKING_DISCOUNT = 0.6   # electric/hybrid regenerative braking cuts brake wear ~60%
_DEFAULT_NON_EXHAUST = NON_EXHAUST_PM10_MG_PER_KM["Midi"]


def non_exhaust_pm(bus_category, fuel_type, distance_km):
    """Brake + tyre wear PM for the row's distance — independent of
    (additive to) the combustion PM figures elsewhere in this file.
    Returns grams of PM10 and PM2.5."""
    base = NON_EXHAUST_PM10_MG_PER_KM.get(bus_category, _DEFAULT_NON_EXHAUST)
    brake_mg_km = base["brake"]
    if fuel_type in ("Electric", "Hybrid"):
        brake_mg_km *= (1.0 - REGEN_BRAKING_DISCOUNT)
    tyre_mg_km = base["tyre"]   # regenerative braking does not reduce tyre wear
    pm10_mg = (brake_mg_km + tyre_mg_km) * distance_km
    pm25_mg = (brake_mg_km * PM10_TO_PM25_BRAKE + tyre_mg_km * PM10_TO_PM25_TYRE) * distance_km
    return {
        "PM10_nonexhaust_g": round(pm10_mg / 1000.0, 4),
        "PM25_nonexhaust_g": round(pm25_mg / 1000.0, 4),
    }


# ══════════════════════════════════════════════════════════════
# SECTION 10 — ROW SEMANTICS SWITCH
# If your Route_Distance_km column is the length of ONE trip
# (not the whole day), set this to False — daily km then becomes
# distance × Num_Trips_Today.
# ══════════════════════════════════════════════════════════════
DISTANCE_IS_DAILY_TOTAL = True


def _derive_day(distance, num_trips, ridership):
    """Turn the raw columns into daily_km, trip_km, pax_per_trip, passenger_km."""
    num_trips = max(1, int(num_trips or 1))
    daily_km = distance if DISTANCE_IS_DAILY_TOTAL else distance * num_trips
    trip_km = daily_km / num_trips
    pax_per_trip = ridership / num_trips
    passenger_km = ridership * trip_km
    return daily_km, trip_km, pax_per_trip, passenger_km


# ══════════════════════════════════════════════════════════════
# SECTION 11 — MAIN ROW CALCULATOR
# ══════════════════════════════════════════════════════════════
def calculate_row(row, methodology, target_pollutants, ambient_c=DEFAULT_AMBIENT_C, real_world_nox=False):
    """Compute one bus-day. Returns a pandas Series of results.

    Recipe per pollutant:
        EF      = base × euro × age × engine  (whichever apply)
        hot     = EF × speed_factor × daily_km     (speed only in COPERT modes)
        cold    = EF × cold_km × (cold_mult − 1) × starts_per_day
        idle    = idle_EF × idle_minutes
        A/C     = +8 % of (hot + idle) CO₂, if A/C on
        total   = (hot + cold + idle + A/C) × load_correction

    real_world_nox=True additionally reports NOx_realworld_kg/g_km/g_pkm —
    the type-approval NOx figure above scaled by the documented real-world
    gap for diesel Euro V/VI/VII (see REAL_WORLD_NOX_FACTOR). The
    type-approval NOx_* columns are always the primary/legal figure; the
    real-world columns are an additional estimate, not a replacement.
    """
    # ── 1. Read the row ──
    bus_cat, cat_mapped = normalize_category(row.get("Bus_Category", ""))
    fuel, fuel_mapped   = normalize_fuel(row.get("Fuel_Type", ""))
    distance   = float(row.get("Route_Distance_km", 0) or 0)
    speed      = float(row.get("Avg_Speed_kmh", REF_SPEED_KMH) or REF_SPEED_KMH)
    ridership  = max(1, int(row.get("Ridership", 1) or 1))
    num_trips  = max(1, int(row.get("Num_Trips_Today", 1) or 1))
    euro       = str(row.get("Euro_Standard", DEFAULT_EURO)).strip()
    age        = int(row.get("Vehicle_Age_years", 0) or 0)
    ac_on      = str(row.get("AC_Status", "False")).strip().lower() in ("true", "1", "yes")
    engine     = str(row.get("Engine_Model", "")).strip()
    idle_min   = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES) or DEFAULT_IDLE_MINUTES)
    is_revenue = parse_revenue_trip(row.get("Revenue_Trip", "True"))

    daily_km, trip_km, pax_per_trip, passenger_km = _derive_day(distance, num_trips, ridership)

    # ── 2. Look up factors and multipliers ──
    fuel_profile = BASE_FACTORS.get(bus_cat, {}).get(fuel, FALLBACK_FACTORS)
    capacity   = int(fuel_profile.get("capacity", 80))
    euro_mults = EURO_FACTORS.get(euro, EURO_FACTORS[DEFAULT_EURO])
    age_mults  = age_deterioration(age, fuel)
    eng_corr   = ENGINE_CO2_CORRECTION.get(engine, DEFAULT_ENGINE_CORRECTION)
    load_c     = _load_corr(pax_per_trip, capacity)

    out = {
        "load_factor":      round(min(pax_per_trip / capacity, 1.2), 3) if capacity else 0.0,
        "euro_nox_mult":    euro_mults["NOx"],
        "age_co2_mult":     round(age_mults["CO2"], 3),
        "category_unmapped": not cat_mapped,
        "fuel_unmapped":     not fuel_mapped,
    }

    # ── 3. Electric buses: no tailpipe — grid ("Scope 2") CO₂ only ──
    if fuel == "Electric":
        _copert_mj = copert_ef(bus_cat, fuel, "EC", euro, speed)
        kwh_per_km = (_copert_mj / 3.6) if _copert_mj is not None else float(fuel_profile.get("kwh_per_km", 1.5))
        if ac_on:
            kwh_per_km *= (1.0 + AC_UPLIFT_KWH)
        co2_g = kwh_per_km * daily_km * GRID_EF_KG_PER_KWH * 1000.0 * load_c
        co2_g = co2_g if "CO2" in target_pollutants else 0.0
        for pol, grams in (("CO2", co2_g), ("NOx", 0.0), ("PM", 0.0)):
            out[f"{pol}_kg"]    = round(grams / 1000.0, 4)
            out[f"{pol}_g_km"]  = round(grams / daily_km, 2) if daily_km else 0.0
            out[f"{pol}_g_pkm"] = round(grams / passenger_km, 2) if (is_revenue and passenger_km) else float("nan")
        out["ac_uplift_kg"] = 0.0
        if real_world_nox:
            out["NOx_realworld_kg"] = 0.0
            out["NOx_realworld_g_km"] = 0.0
            out["NOx_realworld_g_pkm"] = float("nan") if not (is_revenue and passenger_km) else 0.0
        if "PM" in target_pollutants:
            out.update(non_exhaust_pm(bus_cat, fuel, daily_km))
        return pd.Series(out)

    # ── 4. Combustion buses: the four components, per pollutant ──
    ac_uplift_g = 0.0
    nox_total_g = 0.0
    for pol in ("CO2", "NOx", "PM"):
        # Prefer the real Guidebook curve (High Capacity/Midi, Diesel/CNG) —
        # it's already fully speed- and Euro-class-corrected, so none of
        # euro_mults/eng_corr/speed_factor apply on top of it. Age
        # deterioration is still layered on: it's real fleet wear that the
        # Guidebook's per-Euro fleet-average curve doesn't itself capture
        # (documented as a non-COPERT addition elsewhere in this file).
        # Cold start is skipped when the real curve is used, matching
        # COPERT's own methodology (buses get no cold-start modelling —
        # see SECTION 5B). Idling and A/C uplift are still added, since
        # neither is part of the Guidebook's speed curve either.
        copert_key = "EC" if pol == "CO2" else pol
        copert_raw = copert_ef(bus_cat, fuel, copert_key, euro, speed)
        using_copert = copert_raw is not None and pol in target_pollutants

        base_ef = float(fuel_profile.get(pol, 0.0))
        if pol not in target_pollutants or (not using_copert and base_ef == 0.0):
            out[f"{pol}_kg"] = 0.0
            out[f"{pol}_g_km"] = 0.0
            out[f"{pol}_g_pkm"] = 0.0
            continue

        if using_copert:
            ef = copert_raw * FUEL_CO2_PER_MJ.get(fuel, 0.0) if pol == "CO2" else copert_raw
            cold_g = 0.0
            hot_g = ef * age_mults[pol] * daily_km
        else:
            # Fallback: simplified system (Mini buses, fuels/Euro classes the
            # Guidebook extract above doesn't cover).
            ef = base_ef
            if pol in ("NOx", "PM"):
                ef *= euro_mults[pol]          # after-treatment quality
            if pol == "CO2":
                ef *= eng_corr                 # engine family efficiency
            ef *= age_mults[pol]               # wear and tear

            use_speed = (methodology == "COPERT") or (methodology == "Hybrid" and pol != "CO2")
            hot_g = ef * (speed_factor(pol, speed) if use_speed else 1.0) * daily_km

            cold_km = min(trip_km, COLD_START_KM)
            cold_g = ef * cold_km * (cold_start_multiplier(pol, ambient_c) - 1.0) * COLD_STARTS_PER_DAY

        # IDLING — grams/minute × minutes:
        idle_g = IDLING_EF.get(bus_cat, {}).get(fuel, {}).get(pol, 0.0) * idle_min

        # A/C — extra fuel burned to run the compressor (CO₂ only):
        ac_g = (hot_g + idle_g) * AC_UPLIFT_CO2 if (pol == "CO2" and ac_on) else 0.0
        if pol == "CO2":
            ac_uplift_g = ac_g

        total_g = (hot_g + cold_g + idle_g + ac_g) * load_c
        if pol == "NOx":
            nox_total_g = total_g

        out[f"{pol}_kg"]    = round(total_g / 1000.0, 4)
        out[f"{pol}_g_km"]  = round(total_g / daily_km, 2) if daily_km else 0.0
        # Efficiency only makes sense for revenue service — non-revenue rows
        # get NaN so they never pollute averages or compliance:
        out[f"{pol}_g_pkm"] = round(total_g / passenger_km, 2) if (is_revenue and passenger_km) else float("nan")

    out["ac_uplift_kg"] = round(ac_uplift_g / 1000.0, 4)

    if real_world_nox:
        rw_mult = real_world_nox_multiplier(euro, fuel)
        rw_g = nox_total_g * rw_mult
        out["NOx_realworld_kg"] = round(rw_g / 1000.0, 4)
        out["NOx_realworld_g_km"] = round(rw_g / daily_km, 2) if daily_km else 0.0
        out["NOx_realworld_g_pkm"] = round(rw_g / passenger_km, 2) if (is_revenue and passenger_km) else float("nan")

    if "PM" in target_pollutants:
        out.update(non_exhaust_pm(bus_cat, fuel, daily_km))

    return pd.Series(out)


# ══════════════════════════════════════════════════════════════
# SECTION 12 — SINGLE-TRIP CO₂ BREAKDOWN  (Trip Inspector)
# Same math as above, CO₂ only, returned as named components.
# ══════════════════════════════════════════════════════════════
def emission_breakdown(row, methodology="Hybrid", ambient_c=DEFAULT_AMBIENT_C):
    bus_cat, _ = normalize_category(row.get("Bus_Category", ""))
    fuel, _    = normalize_fuel(row.get("Fuel_Type", ""))
    distance  = float(row.get("Route_Distance_km", 0) or 0)
    speed     = float(row.get("Avg_Speed_kmh", REF_SPEED_KMH) or REF_SPEED_KMH)
    ridership = max(1, int(row.get("Ridership", 1) or 1))
    num_trips = max(1, int(row.get("Num_Trips_Today", 1) or 1))
    euro      = str(row.get("Euro_Standard", DEFAULT_EURO)).strip()
    age       = int(row.get("Vehicle_Age_years", 0) or 0)
    ac_on     = str(row.get("AC_Status", "False")).strip().lower() in ("true", "1", "yes")
    engine    = str(row.get("Engine_Model", "")).strip()
    idle_min  = float(row.get("Idle_Minutes", DEFAULT_IDLE_MINUTES) or DEFAULT_IDLE_MINUTES)

    daily_km, trip_km, pax_per_trip, _pkm = _derive_day(distance, num_trips, ridership)
    fuel_profile = BASE_FACTORS.get(bus_cat, {}).get(fuel, FALLBACK_FACTORS)
    capacity = int(fuel_profile.get("capacity", 80))
    load_c = _load_corr(pax_per_trip, capacity)

    if fuel == "Electric":
        _copert_mj = copert_ef(bus_cat, fuel, "EC", euro, speed)
        kwh_per_km = (_copert_mj / 3.6) if _copert_mj is not None else float(fuel_profile.get("kwh_per_km", 1.5))
        if ac_on:
            kwh_per_km *= (1.0 + AC_UPLIFT_KWH)
        total = kwh_per_km * daily_km * GRID_EF_KG_PER_KWH * 1000.0 * load_c
        return {"hot_running": 0, "cold_start": 0, "idling": 0, "ac_load": 0,
                "grid_electric": round(total, 1), "total_g": round(total, 1)}

    # Prefer the real Guidebook curve, same rule as calculate_row(): if it's
    # available for this category/fuel/Euro combo, it's already fully
    # speed-corrected and cold start doesn't apply (see SECTION 5B).
    copert_mj = copert_ef(bus_cat, fuel, "EC", euro, speed)
    using_copert = copert_mj is not None

    if using_copert:
        ef = copert_mj * FUEL_CO2_PER_MJ.get(fuel, 0.0)
        hot_g = ef * age_deterioration(age, fuel)["CO2"] * daily_km
        cold_g = 0.0
    else:
        ef = (float(fuel_profile.get("CO2", 0.0))
              * ENGINE_CO2_CORRECTION.get(engine, DEFAULT_ENGINE_CORRECTION)
              * age_deterioration(age, fuel)["CO2"])
        use_speed = (methodology == "COPERT")
        hot_g  = ef * (speed_factor("CO2", speed) if use_speed else 1.0) * daily_km
        cold_g = ef * min(trip_km, COLD_START_KM) \
                    * (cold_start_multiplier("CO2", ambient_c) - 1.0) * COLD_STARTS_PER_DAY

    idle_g = IDLING_EF.get(bus_cat, {}).get(fuel, {}).get("CO2", 0.0) * idle_min
    ac_g   = (hot_g + idle_g) * AC_UPLIFT_CO2 if ac_on else 0.0

    # Apply the same load-factor correction calculate_row() applies to the
    # total, per-component, so the breakdown bars shown in Trip Inspector
    # sum to the same total_g that calculate_row() reports elsewhere.
    hot_g, cold_g, idle_g, ac_g = (x * load_c for x in (hot_g, cold_g, idle_g, ac_g))

    return {"hot_running": round(hot_g, 1), "cold_start": round(cold_g, 1),
            "idling": round(idle_g, 1), "ac_load": round(ac_g, 1),
            "grid_electric": 0,
            "total_g": round(hot_g + cold_g + idle_g + ac_g, 1)}


# ══════════════════════════════════════════════════════════════
# SECTION 13 — COMPLIANCE FLAG  (two bases)
#   basis="passenger" → thresholds in g CO₂ per passenger-km
#   basis="vehicle"   → thresholds in g CO₂ per vehicle-km
# ══════════════════════════════════════════════════════════════
THRESHOLDS_PKM = {   # g CO₂ / passenger-km
    "High Capacity": {"good": 30, "monitor": 55},
    "Midi":          {"good": 45, "monitor": 75},
    "Mini":          {"good": 60, "monitor": 95},
}
THRESHOLDS_VKM = {   # g CO₂ / vehicle-km
    "High Capacity": {"good": 1500, "monitor": 2100},
    "Midi":          {"good": 1000, "monitor": 1400},
    "Mini":          {"good":  500, "monitor":  750},
}
_DEFAULT_PKM = {"good": 40, "monitor": 70}
_DEFAULT_VKM = {"good": 1200, "monitor": 1700}


def compliance_flag(value, bus_category, basis="passenger"):
    """'Good' / 'Monitor' / 'Over Limit' — NaN (non-revenue) → 'N/A'."""
    if value is None or pd.isna(value):
        return "N/A"
    table, default = (THRESHOLDS_VKM, _DEFAULT_VKM) if basis == "vehicle" \
                     else (THRESHOLDS_PKM, _DEFAULT_PKM)
    t = table.get(bus_category, default)
    if value <= t["good"]:
        return "Good"
    if value <= t["monitor"]:
        return "Monitor"
    return "Over Limit"


# ══════════════════════════════════════════════════════════════
# WORKED EXAMPLE — run `python emissions_engine.py` to see it
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    example = {
        "Bus_Category": "HC", "Fuel_Type": "Diesel",
        "Route_Distance_km": 180, "Avg_Speed_kmh": 22,
        "Ridership": 300, "Num_Trips_Today": 6,   # ≈50 pax on board per trip
        "Euro_Standard": "Euro VI", "Vehicle_Age_years": 5,
        "AC_Status": "False", "Engine_Model": "Yuchai YC6K",
        "Revenue_Trip": 258120, "Revenue_Naira": 258120,
    }
    for method in ("IPCC", "Hybrid", "COPERT"):
        r = calculate_row(example, method, ["CO2", "NOx", "PM"])
        print(f"{method:7s}  CO2 {r['CO2_kg']:8.1f} kg   "
              f"{r['CO2_g_km']:7.1f} g/km   {r['CO2_g_pkm']:5.1f} g/pkm   "
              f"NOx {r['NOx_kg']:6.2f} kg   flag={compliance_flag(r['CO2_g_pkm'], 'High Capacity')}")
