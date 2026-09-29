# -*- coding: utf-8 -*-
"""
MR-Rebound-GTAA (vormals reverseGTAA / MR-Dip) — Strategie-Kern (reine Funktionen, ohne I/O).

Exakte Nachbildung der freigegebenen Backtest-Regel (r10lib.w_dip, r10d.Wfun, Runde 12/14):
  zwei Koerbe je 50 %:  A = Nasdaq 100 + EM + TLT,  B = Nasdaq 100 + India + TLT
  je Korb und je Variante (Kurz-SMA S, Lang-SMA L, Rebound-Tage R, Gate-SMA G):
      Rangwert  = SMA_S / SMA_L - 1  (fehlend -> nicht gueltig)
      Flop 2    = die zwei NIEDRIGSTEN Rangwerte (schwaechstes zuerst; Gleichstand: Spaltenreihenfolge)
      bestaetigt, wenn Kurs/Kurs(vor R Handelstagen) - 1 > 0  UND  Kurs > SMA_G
      beide bestaetigt   -> schwaechstes 1/3, 2.-schwaechstes 2/3
      nur eines          -> max(Slot-Gewicht, 50 %)  (Slotfloor: 1/3 -> 50 %, 2/3 bleibt 2/3)
      keines             -> Cash
  Mittel ueber alle 51 x 76 x 3 x 3 = 34.884 Varianten; Gesamt = 1/2 Korb A + 1/2 Korb B.
  Kein Vol-Target. Entscheidung am letzten Handelstag des Monats, Handel am 1. Handelstag danach.
"""
import numpy as np
import pandas as pd


def dip_weights(P, rows, baskets, S_list, L_list, rebs, gates, tilt):
    """P: DataFrame 1x-Signalkurse (Spalten = alle Assets, feste Reihenfolge) auf dem US-Gitter.
    Gibt (W, info) zurueck; W: (len(rows) x n) Zielgewichte; info: Anzeige-Kennzahlen."""
    rows = np.asarray(rows, int)
    cols = list(P.columns)
    n, m = len(cols), len(rows)
    w0, w1 = tilt[0] / sum(tilt), tilt[1] / sum(tilt)
    ii = np.arange(m)
    SMA = {}
    for L in sorted(set(S_list) | set(L_list) | set(gates)):
        SMA[L] = P.rolling(L).mean().values[rows]
    Pr = P.values[rows]
    # Bestaetigung je (R, G) und Asset
    CONF = {}
    for R in rebs:
        rb = (P / P.shift(R) - 1).values[rows]
        for G in gates:
            g = np.nan_to_num(Pr / SMA[G] - 1, nan=-1) > 0
            CONF[(R, G)] = (np.nan_to_num(rb, nan=-1) > 0) & g
    W = np.zeros((m, n))
    nd = len(S_list) * len(L_list) * len(rebs) * len(gates)
    for b in baskets:
        J = [cols.index(a) for a in b]
        Wb = np.zeros((m, len(J)))
        for S in S_list:
            for L in L_list:
                Sx = SMA[S][:, J] / SMA[L][:, J] - 1
                valid = ~np.isnan(Sx)
                order = np.argsort(np.where(valid, Sx, np.inf), axis=1, kind="stable")[:, :2]
                v0 = valid[ii, order[:, 0]]; v1 = valid[ii, order[:, 1]]
                for key, cf in CONF.items():
                    c = cf[:, J]
                    c0 = v0 & c[ii, order[:, 0]]
                    c1 = v1 & c[ii, order[:, 1]]
                    both = c0 & c1; only0 = c0 & ~c1; only1 = c1 & ~c0
                    Wb[ii[both], order[both, 0]] += w0
                    Wb[ii[both], order[both, 1]] += w1
                    Wb[ii[only0], order[only0, 0]] += max(w0, 0.5)
                    Wb[ii[only1], order[only1, 1]] += max(w1, 0.5)
        W[:, J] += Wb / nd / len(baskets)
    # Anzeige: mittlerer Rangwert ueber alle (S, L), mittlerer Rebound, Anzahl bestandener Gates
    avg_rank = np.mean([SMA[S] / SMA[L] - 1 for S in S_list for L in L_list], axis=0)
    avg_reb = np.mean([(P / P.shift(R) - 1).values[rows] for R in rebs], axis=0)
    gates_ok = np.sum([np.nan_to_num(Pr / SMA[G] - 1, nan=-1) > 0 for G in gates], axis=0)
    return W, dict(rank=avg_rank, rebound=avg_reb, gates=gates_ok)


def signature(assets, w, eps=1e-9):
    parts = [f"{a}:{round(float(x), 4)}" for a, x in zip(assets, w) if x > eps]
    return "|".join(sorted(parts)) if parts else "CASH"
