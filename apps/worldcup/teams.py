"""Flag-derived accent colors per team for FIFA WC 2026 qualifiers.

Each entry is (primary, secondary). Primary = dominant flag color; secondary
= a complementary accent. Used to paint thin stripes under team labels so
each match card feels distinct at a glance.
"""
from __future__ import annotations

# Punchy flag colors — the panel runs dim and blown-out, so push saturation and
# value high. These paint full-brightness team edge bars / chips against black.
_WHITE = (255, 255, 255)
_RED = (255, 44, 44)
_BLUE = (40, 96, 255)
_GREEN = (40, 220, 90)
_YELLOW = (255, 214, 36)
_BLACK = (24, 24, 24)
_ORANGE = (255, 130, 16)

TEAM_COLORS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    # CONCACAF
    "USA": (_RED, _BLUE),
    "MEX": (_GREEN, _RED),
    "CAN": (_RED, _WHITE),
    "CRC": (_RED, _BLUE),
    "PAN": (_RED, _BLUE),
    "JAM": (_GREEN, _YELLOW),
    "HON": (_BLUE, _WHITE),
    "HAI": (_RED, _BLUE),
    "SLV": (_BLUE, _WHITE),
    "CUR": (_BLUE, _YELLOW),
    # CONMEBOL
    "ARG": (_BLUE, _WHITE),
    "BRA": (_YELLOW, _GREEN),
    "URU": (_BLUE, _YELLOW),
    "COL": (_YELLOW, _BLUE),
    "CHI": (_RED, _BLUE),
    "ECU": (_YELLOW, _BLUE),
    "PAR": (_RED, _BLUE),
    "PER": (_RED, _WHITE),
    "VEN": (_YELLOW, _RED),
    "BOL": (_GREEN, _YELLOW),
    # UEFA
    "FRA": (_BLUE, _RED),
    "ESP": (_RED, _YELLOW),
    "GER": (_BLACK, _YELLOW),
    "ITA": (_GREEN, _RED),
    "ENG": (_WHITE, _RED),
    "POR": (_RED, _GREEN),
    "NED": (_ORANGE, _BLUE),
    "BEL": (_RED, _YELLOW),
    "POL": (_RED, _WHITE),
    "DEN": (_RED, _WHITE),
    "SWE": (_BLUE, _YELLOW),
    "NOR": (_RED, _BLUE),
    "CRO": (_RED, _WHITE),
    "SUI": (_RED, _WHITE),
    "AUT": (_RED, _WHITE),
    "CZE": (_BLUE, _RED),
    "SRB": (_RED, _BLUE),
    "HUN": (_RED, _GREEN),
    "SCO": (_BLUE, _WHITE),
    "WAL": (_RED, _GREEN),
    "IRL": (_GREEN, _ORANGE),
    "BIH": (_BLUE, _YELLOW),
    "TUR": (_RED, _WHITE),
    "GRE": (_BLUE, _WHITE),
    "UKR": (_BLUE, _YELLOW),
    # AFC
    "JPN": (_RED, _WHITE),
    "KOR": (_BLUE, _RED),
    "AUS": (_BLUE, _YELLOW),
    "IRN": (_GREEN, _RED),
    "KSA": (_GREEN, _WHITE),
    "QAT": (_RED, _WHITE),
    "UAE": (_RED, _GREEN),
    "IRQ": (_RED, _BLACK),
    "UZB": (_BLUE, _GREEN),
    # CAF
    "MAR": (_RED, _GREEN),
    "EGY": (_RED, _WHITE),
    "ALG": (_GREEN, _RED),
    "TUN": (_RED, _WHITE),
    "SEN": (_GREEN, _YELLOW),
    "CMR": (_GREEN, _YELLOW),
    "GHA": (_RED, _YELLOW),
    "NGA": (_GREEN, _WHITE),
    "CIV": (_ORANGE, _GREEN),
    "MLI": (_GREEN, _YELLOW),
    "RSA": (_GREEN, _YELLOW),
    # CONCACAF/Caribbean qualifiers
    "CUW": (_BLUE, _YELLOW),
    "CPV": (_BLUE, _RED),
    "SUR": (_GREEN, _WHITE),
    "TRI": (_RED, _BLACK),
    "GUA": (_BLUE, _WHITE),
    "NCA": (_BLUE, _WHITE),
    "ATG": (_RED, _BLUE),
    "GRN": (_RED, _GREEN),
    "BAR": (_BLUE, _YELLOW),
    "BLZ": (_BLUE, _RED),
    "DOM": (_BLUE, _RED),
    "DMA": (_GREEN, _YELLOW),
    "VIN": (_BLUE, _YELLOW),
    "GUY": (_GREEN, _YELLOW),
    "PUR": (_RED, _BLUE),
    # OFC
    "NZL": (_BLUE, _WHITE),
}

_FALLBACK = ((220, 140, 40), (140, 90, 30))
_VISIBILITY_MIN = 90
_PRIMARY_MIN_BRIGHTNESS = 240


def _brightness(c: tuple[int, int, int]) -> int:
    return c[0] + c[1] + c[2]


def _boost_to_min(c: tuple[int, int, int], min_sum: int) -> tuple[int, int, int]:
    b = _brightness(c)
    if b >= min_sum or b == 0:
        return c
    factor = min_sum / b
    return (
        min(255, int(c[0] * factor)),
        min(255, int(c[1] * factor)),
        min(255, int(c[2] * factor)),
    )


def colors_for(team_short: str | None) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if not team_short:
        primary, secondary = _FALLBACK
    else:
        primary, secondary = TEAM_COLORS.get(team_short.upper(), _FALLBACK)
        if _brightness(primary) < _VISIBILITY_MIN and _brightness(secondary) >= _VISIBILITY_MIN:
            primary, secondary = secondary, primary
    primary = _boost_to_min(primary, _PRIMARY_MIN_BRIGHTNESS)
    return primary, secondary
