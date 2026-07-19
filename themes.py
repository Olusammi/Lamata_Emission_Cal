"""
themes.py — visual themes for the Fleet Emissions Console
=========================================================
Four presets, each with a matched dark and light variant plus its own
font pairing. Every preset defines the same CSS variable set, so the
whole interface (cards, badges, banners, tables, sidebar) restyles
consistently when the user switches.

Status colours (Good / Monitor / Over) stay in the green / amber / red
family in every theme — in a compliance tool those meanings must never
depend on the user's aesthetic choice.
"""

FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Oswald:wght@400;500;600;700&"
    "family=IBM+Plex+Mono:wght@400;500;600&"
    "family=Inter:wght@400;500;600&"
    "family=Archivo:wght@400;500;600;700&"
    "family=JetBrains+Mono:wght@400;500;600&"
    "family=Sora:wght@400;500;600;700&"
    "family=Fira+Code:wght@400;500&display=swap"
)


def _vars(p: dict) -> str:
    """Expand a compact palette dict into the app's CSS variable block."""
    return f"""
    --bg-app:{p['bg']}; --bg-main:{p['card']}; --bg-card:{p['card']}; --bg-card2:{p['card2']};
    --border:{p['bdr']}; --border2:{p['bdr2']};
    --text-prim:{p['t1']}; --text-sec:{p['t2']}; --text-tert:{p['t3']};
    --accent:{p['acc']}; --accent2:{p['acc2']};
    --sidebar-bg:{p['side']};
    --metric-bg:{p['card']}; --metric-bdr:{p['bdr']}; --metric-val:{p['t1']}; --metric-lbl:{p['t3']};
    --banner-bg:linear-gradient(135deg,{p['banner1']} 0%,{p['banner2']} 100%);
    --banner-bdr:{p['bdr2']}; --banner-text:{p['bt']};
    --banner-code-bg:{p['codebg']}; --banner-code:{p['code']};
    --tip-bg:{p['card2']}; --tip-bdr:{p['bdr2']}; --tip-text:{p['t2']}; --tip-strong:{p['acc2']};
    --badge-good-bg:{p['gbg']}; --badge-good-text:{p['g']};
    --badge-mon-bg:{p['mbg']}; --badge-mon-text:{p['m']};
    --badge-over-bg:{p['obg']}; --badge-over-text:{p['o']};
    --filter-bg:{p['card2']}; --filter-bdr:{p['bdr2']}; --filter-text:{p['t2']};
    --autorename-bg:{p['mbg']}; --autorename-bdr:{p['bdr2']}; --autorename-text:{p['m']};
    --expander-bg:{p['card2']}; --table-bdr:{p['bdr']};
    --disp:{p['fd']}; --body:{p['fb']}; --mono:{p['fm']};
    """


_BADGES_DARK = dict(g="#3DDC84", gbg="#0D2E1E", m="#FFB84D", mbg="#3A2D0D",
                    o="#FF6B6B", obg="#3A1010")
_BADGES_LIGHT = dict(g="#15803D", gbg="#DCFCE7", m="#92400E", mbg="#FEF3C7",
                     o="#B91C1C", obg="#FEE2E2")

THEMES = {
    # ── the original terminal-green look ──
    "Emerald Terminal": {
        "fonts": dict(fd="'Archivo',sans-serif", fb="'Inter',sans-serif",
                      fm="'JetBrains Mono',monospace"),
        "dark": dict(bg="#05100B", card="#091A12", card2="#0D2418",
                     bdr="#16352A", bdr2="#1E4636",
                     t1="#EEF3F0", t2="#8FA49A", t3="#5C7268",
                     acc="#2FD58C", acc2="#63E6AE", side="#05100B",
                     banner1="#0D2418", banner2="#05100B", bt="#CDE8DA",
                     codebg="rgba(47,213,140,0.16)", code="#7EE8B8",
                     **_BADGES_DARK),
        "light": dict(bg="#F2F7F4", card="#FFFFFF", card2="#E8F1EC",
                      bdr="#D6E5DC", bdr2="#BCD6C6",
                      t1="#0A241A", t2="#3A5D4C", t3="#7C978A",
                      acc="#0E8F5F", acc2="#0A6B47", side="#05100B",
                      banner1="#0E8F5F", banner2="#0A241A", bt="#EAF7F0",
                      codebg="rgba(255,255,255,0.18)", code="#D7F4E6",
                      **_BADGES_LIGHT),
    },
    # ── the deep-navy look the app currently ships with ──
    "Ocean Console": {
        "fonts": dict(fd="'Oswald',sans-serif", fb="'Inter',sans-serif",
                      fm="'IBM Plex Mono',monospace"),
        "dark": dict(bg="#000C44", card="#051449", card2="#0A1D5C",
                     bdr="#16285F", bdr2="#1E3270",
                     t1="#F2F5FB", t2="#8FA0C9", t3="#5A6EA0",
                     acc="#1E73BE", acc2="#4A96DA", side="#000C44",
                     banner1="#0A1D5C", banner2="#000C44", bt="#CDD9F2",
                     codebg="rgba(30,115,190,0.18)", code="#6FB3EC",
                     **_BADGES_DARK),
        "light": dict(bg="#F3F6FB", card="#FFFFFF", card2="#EEF3FA",
                      bdr="#DBE4F3", bdr2="#C2D2EC",
                      t1="#000C44", t2="#3A4F7A", t3="#8294B8",
                      acc="#1E73BE", acc2="#155A99", side="#000C44",
                      banner1="#1E73BE", banner2="#000C44", bt="#EAF1FB",
                      codebg="rgba(255,255,255,0.18)", code="#D9ECFB",
                      **_BADGES_LIGHT),
    },
    # ── warm charcoal & amber ──
    "Ember": {
        "fonts": dict(fd="'Sora',sans-serif", fb="'Inter',sans-serif",
                      fm="'Fira Code',monospace"),
        "dark": dict(bg="#141009", card="#1D1610", card2="#261D14",
                     bdr="#3A2D1E", bdr2="#4A3A26",
                     t1="#F5EFE6", t2="#C4B39B", t3="#8A7A62",
                     acc="#E08A2E", acc2="#F2A94F", side="#141009",
                     banner1="#261D14", banner2="#141009", bt="#EFDFC8",
                     codebg="rgba(224,138,46,0.16)", code="#F2C078",
                     **_BADGES_DARK),
        "light": dict(bg="#FAF6F0", card="#FFFFFF", card2="#F3EBDF",
                      bdr="#E6DACA", bdr2="#D4C2A8",
                      t1="#2A1F10", t2="#6B5638", t3="#9C8A6E",
                      acc="#B45309", acc2="#92400E", side="#141009",
                      banner1="#B45309", banner2="#2A1F10", bt="#FDF3E3",
                      codebg="rgba(255,255,255,0.18)", code="#FBE3BD",
                      **_BADGES_LIGHT),
    },
    # ── near-monochrome, one blue accent, system fonts (fastest) ──
    "Slate Minimal": {
        "fonts": dict(fd="system-ui,sans-serif", fb="system-ui,sans-serif",
                      fm="ui-monospace,'Cascadia Mono',Consolas,monospace"),
        "dark": dict(bg="#0F1115", card="#151920", card2="#1C222B",
                     bdr="#262E3A", bdr2="#334050",
                     t1="#E7EAEF", t2="#9AA6B5", t3="#64707F",
                     acc="#3B82F6", acc2="#6AA5F8", side="#0F1115",
                     banner1="#1C222B", banner2="#0F1115", bt="#D6DEE9",
                     codebg="rgba(59,130,246,0.16)", code="#93BEF9",
                     **_BADGES_DARK),
        "light": dict(bg="#F5F6F8", card="#FFFFFF", card2="#ECEFF3",
                      bdr="#DCE1E8", bdr2="#C3CCD8",
                      t1="#14181F", t2="#45505E", t3="#7E8896",
                      acc="#2563EB", acc2="#1D4ED8", side="#0F1115",
                      banner1="#2563EB", banner2="#14181F", bt="#E8F0FE",
                      codebg="rgba(255,255,255,0.18)", code="#CFE0FC",
                      **_BADGES_LIGHT),
    },
}

DEFAULT_THEME = "Emerald Terminal"


def css_vars(preset: str, dark: bool) -> str:
    """Full CSS variable block for a preset + mode."""
    t = THEMES.get(preset, THEMES[DEFAULT_THEME])
    palette = dict(t["dark" if dark else "light"])
    palette.update(t["fonts"])
    return _vars(palette)


def accent(preset: str, dark: bool = True) -> str:
    t = THEMES.get(preset, THEMES[DEFAULT_THEME])
    return t["dark" if dark else "light"]["acc"]
