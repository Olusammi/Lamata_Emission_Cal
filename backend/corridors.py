"""
backend/corridors.py — schematic Lagos BRT corridor geometry + aggregation.

Port of app.py:1274-1330 (the CORRIDORS dict, match_corridor,
corridor_aggregate). Geometry is served as-is to the frontend, which
draws it with deck.gl/MapLibre instead of pydeck.
"""
import pandas as pd

CORRIDORS = {
    "Abule Egba – Oshodi – TBS": {
        "path": [[3.2938, 6.6480], [3.3050, 6.6100], [3.3480, 6.5560],
                 [3.3690, 6.5310], [3.4053, 6.4433]],
        "keywords": ["abule", "sango", "abesan", "iyana-ipaja", "iyana ipaja", "dopemu", "meiran"],
    },
    "Ikorodu – TBS": {
        "path": [[3.5116, 6.6194], [3.4400, 6.6050], [3.3900, 6.5960],
                 [3.3860, 6.5870], [3.3690, 6.5310], [3.4053, 6.4433]],
        "keywords": ["ikorodu", "elepe", "igbogbo", "odogunyan", "odongunyan",
                     "agric", "isawo", "ogolonto", "fadeyi"],
    },
    "Ikeja Axis": {
        "path": [[3.2635, 6.6155], [3.3376, 6.6018], [3.3565, 6.6187],
                 [3.3200, 6.6250], [3.3480, 6.5560]],
        "keywords": ["ikeja", "agege", "ayobo", "egbeda", "ikotun", "igando",
                     "baruwa", "alausa", "allen", "ijaiye", "iju", "kola"],
    },
    "Ajah – CMS / Marina": {
        "path": [[3.5670, 6.4667], [3.4730, 6.4410], [3.4270, 6.4290],
                 [3.4059, 6.4488], [3.3890, 6.4500]],
        "keywords": ["ajah", "marina", "eko hotel", "cms", "lekki", "falomo",
                     "tinubu", "adeola"],
    },
    "Oshodi / Berger – Inner City": {
        "path": [[3.3776, 6.6413], [3.3860, 6.5870], [3.3792, 6.5095],
                 [3.3480, 6.5560], [3.2989, 6.4666]],
        "keywords": ["berger", "ojota", "yaba", "unilag", "oshodi", "cele",
                     "mile 2", "okokomaiko", "obalende", "ogba", "olowora",
                     "maryland", "magodo", "ketu", "dalemo", "joke-ayo"],
    },
}

FLEET_LAT, FLEET_LON = 6.52, 3.37
MAP_STYLES = {
    "Dark": "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
    "Light": "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    "Voyager": "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
}


def match_corridor(route_name) -> str:
    r = str(route_name).lower()
    for cname, cdef in CORRIDORS.items():
        if any(k in r for k in cdef["keywords"]):
            return cname
    return "Oshodi / Berger – Inner City"


def corridor_aggregate(rows: list[dict], pollutant: str = "CO2") -> list[dict]:
    """rows: list of computed trip records (as returned by /data/upload).
    Returns per-corridor totals for the map + league table."""
    if not rows:
        return []
    mdf = pd.DataFrame(rows)
    mdf["Corridor"] = mdf["Route_Name"].apply(match_corridor)
    kg_col, eff_col = f"{pollutant}_kg", f"{pollutant}_g_pkm"

    agg_kwargs = {
        "Total_kg": (kg_col, "sum") if kg_col in mdf.columns else ("Bus_ID", "count"),
        "Eff": (eff_col, "mean") if eff_col in mdf.columns else ("Bus_ID", "count"),
        "Trips": ("Bus_ID", "count"),
        "Buses": ("Bus_ID", "nunique"),
        "Pax": ("Ridership", "sum"),
    }
    agg = mdf.groupby("Corridor").agg(**agg_kwargs).reset_index()
    agg["Total_kg"] = agg["Total_kg"].fillna(0)
    agg["Eff"] = agg["Eff"].fillna(0)
    return agg.round(2).to_dict("records")
