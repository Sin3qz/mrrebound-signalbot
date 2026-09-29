# ============================================================================
#  MR-Rebound-GTAA (vormals reverseGTAA / MR-Dip) — freigegeben 29.09.2026
#  Single Source of Truth fuer alle Parameter und Anzeigen.
#
#  Duo: 50 % Korb A = Nasdaq 100 + Emerging Markets + TLT
#       50 % Korb B = Nasdaq 100 + India + TLT
#  Invest: Nasdaq 3x, EM 3x, India 3x, TLT 5x (volle Quote im 5x-TLT-Produkt, freigegeben 29.09.2026)
#  Signale auf 1x-Kursen wie im Backtest: ^NDX, EEM, ^BSESN (Sensex, INR), TLT.
#
#  Zeitplan: Signal = Schlusskurse des LETZTEN Handelstags des Monats,
#            Handel  = 1. Handelstag des Folgemonats (NYSE-Kalender).
#
#  Regel je Korb und Variante (S, L, R, G), gemittelt ueber 34.884 Varianten:
#     Kurz-SMA S = 75..125, Lang-SMA L = 175..250 (1er), Rebound R = 42/50/56 Tage,
#     Gate G = Kurs > SMA100 / SMA200 / SMA250.
#     Flop 2 nach SMA_S/SMA_L - 1 (die zwei schwaechsten), bestaetigt wenn
#     Rebound > 0 UND Gate; beide -> 1/3 (schwaechstes) + 2/3 (2.-schwaechstes);
#     nur eines -> max(Slot, 50 %); sonst Cash.  Kein Vol-Target.
#
#  Backtest 1995+ mit exakt diesen 34.884 Varianten (1er-Schritte), TLT-Quote voll in 5x-TLT:
#     21 Tranchen:          CAGR 19,4 %, MaxDD -47,6 %, Sortino 0,85, z31 2,68, z4 2,01, P(DD<-50 %) 6,1 %, P(DD<-75 %) 0 %
#     nur letzter Handelstag: CAGR 21,1 %, MaxDD -45,3 %, Sortino 0,88, z31 2,82, z4 2,09, P(DD<-50 %) 11,1 %, P(DD<-75 %) 0,1 %
#  KEINE ANLAGEBERATUNG.
# ============================================================================
STRAT_NAME = "MR-Rebound-GTAA"
STRAT_LONG = "MR-Rebound-GTAA (Mean-Reversion, monatlich)"
STRAT_ASCII = "MR-Rebound-GTAA"
STRAT_KEY = "mrreboundgtaa"

# Reihenfolge = Spaltenreihenfolge im Backtest (U = [Q, EM, IN, T])
ASSETS = {
    "NASDAQ100": dict(signal="^NDX", leverage=3, display="Nasdaq 100", short="Nasdaq",
                      product="WisdomTree NASDAQ 100 3x Daily Leveraged", isin="IE00BLRPRL42"),
    "EM":        dict(signal="EEM", leverage=3, display="Emerging Markets", short="EM",
                      product="WisdomTree Emerging Markets 3x Daily Leveraged", isin="IE00BYTYHN28"),
    "INDIA":     dict(signal="^BSESN", leverage=3, display="India", short="India",
                      product="Leverage Shares 3x Long India (INDA)", isin="XS2595675302", us_market=False),
    "TLT_LONG":  dict(signal="TLT", leverage=5, display="US-Treasury 20y+", short="TLT",
                      product="Leverage Shares 5x Long 20+ Year Treasury Bond", isin="XS2595672036"),
}
BASKETS = [["NASDAQ100", "EM", "TLT_LONG"], ["NASDAQ100", "INDIA", "TLT_LONG"]]
BASKET_LABELS = ["A: Nasdaq · EM · TLT", "B: Nasdaq · India · TLT"]

SMA_SHORT = list(range(75, 126))        # 51 Laengen
SMA_LONG = list(range(175, 251))        # 76 Laengen
REBOUND_DAYS = [42, 50, 56]
GATE_SMA = [100, 200, 250]
TILT = (1 / 3, 2 / 3)                   # schwaechstes, 2.-schwaechstes; Slotfloor 50 %


GRID_START = "1999-01-04"
HISTORY_START = "2004-01-01"
TRY_COUNT = 3
NTFY_LATE_DAYS = 7
INFO_FOOTER = "Hebel-ETPs: Pfad-/Emittentenrisiko. KEINE ANLAGEBERATUNG."

# Datenpruefung: Mindestanzahl Kurse je Signalreihe (Strategie braucht SMA/Momentum-Fenster + Reserve). Beginnt eine Reihe
# spaeter als beim letzten Lauf (abgeschnittene Yahoo-Antwort), wird ebenfalls nicht entschieden (Retry).
MIN_ROWS = 600
