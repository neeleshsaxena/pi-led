"""Static IATA-code -> preference tier, for prioritizing the flight board.

AeroDataBox's flight movement airport node gives us an IATA code, name and
city for the other airport, but no country/continent field to key off of —
so tiering is a curated list of major-hub IATA codes rather than a live
lookup. Unknown codes (small/regional fields not in the list) default to
DOMESTIC, the safe assumption since most flights at any given airport are.

Tiers: Europe + India (TOP) > other international (INTERNATIONAL) > DOMESTIC.
"""
from __future__ import annotations

DOMESTIC = 0
INTERNATIONAL = 1
TOP = 2  # Europe + India

_EUROPE = {
    # UK & Ireland
    "LHR", "LGW", "LCY", "STN", "LTN", "MAN", "EDI", "GLA", "BHX", "DUB", "SNN", "ORK",
    # France
    "CDG", "ORY", "NCE", "LYS", "MRS", "TLS",
    # Germany
    "FRA", "MUC", "TXL", "BER", "DUS", "HAM", "STR", "CGN",
    # Benelux & Luxembourg
    "AMS", "BRU", "LUX",
    # Alps
    "ZRH", "GVA", "BSL", "VIE",
    # Iberia
    "MAD", "BCN", "AGP", "PMI", "VLC", "SVQ", "LIS", "OPO", "FAO",
    # Italy
    "FCO", "MXP", "VCE", "NAP", "BLQ", "LIN", "CTA",
    # Greece, Cyprus & Malta
    "ATH", "SKG", "HER", "LCA", "MLA",
    # Turkey
    "IST", "SAW", "ADB",
    # Nordics & Iceland
    "CPH", "OSL", "ARN", "GOT", "HEL", "KEF",
    # Central/Eastern Europe
    "WAW", "KRK", "PRG", "BUD", "OTP", "ZAG", "DBV", "SPU",
}

_INDIA = {
    "DEL", "BOM", "BLR", "MAA", "CCU", "HYD", "AMD", "COK", "PNQ", "GOI",
    "JAI", "TRV", "IXC", "LKO", "GAU",
}

_OTHER_INTERNATIONAL = {
    # Canada
    "YYZ", "YVR", "YUL", "YYC", "YOW", "YEG", "YHZ",
    # Mexico
    "MEX", "CUN", "GDL", "MTY", "TIJ", "SJD", "PVR",
    # Central/South America
    "GRU", "GIG", "EZE", "SCL", "BOG", "LIM", "UIO", "PTY", "SJO",
    # Caribbean
    "NAS", "HAV", "SDQ", "PUJ",
    # Middle East
    "DXB", "AUH", "DOH", "JED", "RUH", "AMM", "BEY", "TLV", "KWI", "BAH", "MCT",
    # Africa
    "CAI", "JNB", "CPT", "NBO", "ADD", "LOS", "CMN", "TUN",
    # Asia-Pacific (non-India)
    "NRT", "HND", "KIX", "ICN", "GMP", "PVG", "PEK", "PKX", "CAN", "SZX",
    "HKG", "TPE", "SIN", "KUL", "BKK", "DMK", "CGK", "MNL", "SGN", "HAN", "RGN",
    # Oceania
    "SYD", "MEL", "BNE", "PER", "AKL", "NAN",
}


def tier(iata: str) -> int:
    """Preference tier for the *other* airport on a flight, by IATA code."""
    code = str(iata or "").strip().upper()
    if code in _EUROPE or code in _INDIA:
        return TOP
    if code in _OTHER_INTERNATIONAL:
        return INTERNATIONAL
    return DOMESTIC
