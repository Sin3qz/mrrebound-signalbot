# -*- coding: utf-8 -*-
"""
MR-Rebound-GTAA — LIVE-Runner.

Vertrag fuer main.py:  run_strategy() -> (signal, ntfy_text, discord_text)
    None -> nur Discord-Tagesstatus;  BUY/SELL/SWITCH/HOLD/NOCHANGE -> Monatswechsel (ntfy IMMER);  "Error"
ntfy: genau EINMAL je Monat, am 1. NYSE-Handelstag (morgens) mit den Schlusskursen des letzten
Handelstags des Vormonats (keine zweite Meldung mehr am Monatsletzten). Nur mit frischen Daten;
sonst holt der naechste Lauf die Meldung nach (max. NTFY_LATE_DAYS Tage, "verspaetet").
"""
import numpy as np
import pandas as pd

from . import common as U
from . import dip_core as DC
from .constants import (STRAT_NAME, STRAT_LONG, STRAT_KEY, ASSETS, BASKETS, BASKET_LABELS, SMA_SHORT, SMA_LONG,
                        REBOUND_DAYS, GATE_SMA, TILT, GRID_START, HISTORY_START, TRY_COUNT,
                        NTFY_LATE_DAYS, INFO_FOOTER, MIN_ROWS)

STATUS_FILE = f"status_{STRAT_KEY}.json"
NOTIFY_FILE = f"notify_state_{STRAT_KEY}.json"
HISTORY_FILE = f"history_{STRAT_KEY}.txt"
AL = list(ASSETS.keys())
PENDING_STATE = {}


def mark_error(e):
    """Lauf fehlgeschlagen: Status als needsRetry markieren (letzter gueltiger Stand bleibt)."""
    U.mark_status_error(STATUS_FILE, e)


def commit_notify_state():
    if PENDING_STATE:
        U.save_json(NOTIFY_FILE, dict(PENDING_STATE))


# ==========================================================================
#  Daten
# ==========================================================================
def load_data(fetch=U.fetch_close):
    return {m["signal"]: fetch(m["signal"], TRY_COUNT) for m in ASSETS.values()}


def prepare(raw):
    prev_first = U.load_json(STATUS_FILE).get("firstDates", {})         # Erkennung abgeschnittener Yahoo-Antworten
    grid = U.build_grid(GRID_START, us_series=[raw[ASSETS[a]["signal"]] for a in AL if ASSETS[a].get("us_market", True)])
    P = pd.DataFrame({a: U.oncal(raw[ASSETS[a]["signal"]], grid) for a in AL})
    fresh, warns, fr = True, [], {}
    for a in AL:
        m = ASSETS[a]; t = m["signal"]
        us = m.get("us_market", True)
        # Sensex: indischer Kalender -> 'frisch', wenn der Kurs hoechstens 4 Kalendertage aelter ist als die NYSE-Sitzung
        f, last, w = U.check_series(f"{m['short']} ({t})", raw[t], grid, us_market=us,
                                    index_level=t.startswith("^"), max_age_days=(None if us else 4),
                                    min_rows=MIN_ROWS, prev_first=prev_first.get(t))
        fr[t] = {"last": last, "fresh": bool(f)}
        fresh &= bool(f); warns += w
    return grid, P, (not fresh), sorted(set(warns)), fr


def compute(P, rows):
    return DC.dip_weights(P, rows, BASKETS, SMA_SHORT, SMA_LONG, REBOUND_DAYS, GATE_SMA, TILT)


def trade_view(w):
    """Zielquoten = Signalquoten, je Baustein mit seinem Invest-Hebel (Nasdaq/EM/India 3x, TLT 5x —
    volle TLT-Quote im 5x-Produkt, freigegeben 29.09.2026). Rest (nur wenn Slots leer) = Cash."""
    out = [dict(asset=a, signal=w[k], trade=w[k], lev=ASSETS[a]["leverage"]) for k, a in enumerate(AL) if w[k] > U.W_EPS]
    return sorted(out, key=lambda x: -x["signal"])


# ==========================================================================
#  Nachricht
# ==========================================================================
def _alloc_lines(w):
    tv = trade_view(w); lines = []
    for x in tv:
        a = x["asset"]
        lines.append(f"• {U.w1(x['trade']):>5}  {x['lev']}x {ASSETS[a]['display']}")
    cash = 1 - sum(x["trade"] for x in tv)
    if cash > 0.0005:
        lines.append(f"• {U.w1(cash):>5}  Cash")
    return lines


def _delta_lines(w_new, w_old):
    out = []
    for k in np.argsort(-(np.abs(w_new - w_old))):
        if abs(w_new[k] - w_old[k]) >= 0.005:
            out.append(f"  {ASSETS[AL[k]]['short']}: {U.w1(w_old[k])} -> {U.w1(w_new[k])}")
    return out


def _change_type(w_new, w_old):
    s_new = {a for a, x in zip(AL, w_new) if x > U.W_EPS}
    s_old = {a for a, x in zip(AL, w_old) if x > U.W_EPS}
    if s_new == s_old:
        return "HOLD" if _delta_lines(w_new, w_old) else "NOCHANGE"
    if not s_new:
        return "SELL"
    if not s_old:
        return "BUY"
    return "SWITCH"


HEAD = {"BUY": "🟢 BUY — neu investiert", "SELL": "🔴 SELL — alles in Cash", "SWITCH": "🔄 UMSCHICHTUNG",
        "HOLD": "🔁 Gleiche Bausteine — Gewichte anpassen", "NOCHANGE": "⚪ KEINE ÄNDERUNG zum Vormonat"}


def _sig_rows(info, w, j):
    order = sorted(AL, key=lambda a: info["rank"][j][AL.index(a)] if info["rank"][j][AL.index(a)] == info["rank"][j][AL.index(a)] else 9)
    rows = [[ASSETS[a]["short"], U.pct0(info["rank"][j][AL.index(a)]), U.pct0(info["rebound"][j][AL.index(a)]),
             f"{int(info['gates'][j][AL.index(a)])}/{len(GATE_SMA)}",
             (U.w1(w[AL.index(a)]) if w[AL.index(a)] > U.W_EPS else "–")] for a in order]
    return order, rows


def build_messages(c):
    L = []
    if c["signal"]:
        late = f" (verspätet; regulär {U.de(c['trade'])})" if c["late"] else ""
        L += [f"🔔 {STRAT_NAME} — MONATSWECHSEL{late}", HEAD[c["signal"]],
              (f"Heute handeln ({U.de(c['today'])}), Signal: Schluss {U.de(c['dec'])}" if c["late"] else f"Handeln am {U.de(c['trade'])} (Signal: Schluss {U.de(c['dec'])})"), "", "Neue Zielquoten:"]
        L += _alloc_lines(c["w"])
        dl = _delta_lines(c["w"], c["w_prev"])
        L += ["Änderung ggü. Vormonat:"] + (dl if dl else ["  keine (< 0,5 Pp.)"])
    else:
        if c.get("pend_dec"):
            L += [f"⏳ Monatssignal (Schluss {U.de(c['pend_dec'])}) AUSSTEHEND — Kursdaten fehlen/veraltet, Retry läuft.",
                  f"Handel regulär am {U.de(c['pend_trade'])}; die ntfy-Meldung kommt, sobald die Daten da sind (ggf. „verspätet“).",
                  "Bis dahin gilt noch:", ""]
        L += [f"📊 {STRAT_LONG} — Tagesstatus",
              f"Ziel {'ab' if c['today'] < c['trade'] else 'seit'} {U.de(c['trade'])} (Signal {U.de_short(c['dec'])}):"]
        L += _alloc_lines(c["w"])
    if c["next_dec"]:
        L += [f"Nächstes Signal: Schluss {U.de_short(c['next_dec'])} → Handel {U.de(c['next_trade'])}"]
    order, rows = _sig_rows(c["info"], c["w"], -1)
    tab = U.table(["Asset", "Rang", "Rebnd", "Gate", "Ziel"], rows, "lrrrr")
    legend = ["Rang = Ø SMA75–125/SMA175–250 (tiefster = Flop)", "Rebnd = Ø 42/50/56-Tage-Rendite",
              "Gate = Kurs > SMA100/200/250", "Ziel = Quote (Nasdaq/EM/India 3x, TLT 5x)"]
    disc = L + ["", f"Signale (1x-Kurse, Stand {U.de_short(c['asof'])}):", "```"] + tab + ["```"] + legend
    ntfy = L + ["", f"Signale (Stand {U.de_short(c['asof'])}):"] + [
        f"{r[0]}: Rang {r[1]}, Rebnd {r[2]}, Gate {r[3]}, Ziel {r[4]}" for r in rows]
    tail = []
    if c["stale"]:
        tail += ["", "⚠️ Kursdaten evtl. veraltet — Retry läuft; ntfy erst mit frischen Daten."]
    if c["warns"]:
        tail += ["", "⚠️ Datenprüfung:"] + [f"• {x}" for x in c["warns"][:6]]
    tail += ["", INFO_FOOTER]
    return "\n".join(ntfy + tail), "\n".join(disc + tail)


# ==========================================================================
#  Hauptfunktion
# ==========================================================================
def run_strategy(raw=None, write_files=True):
    if raw is None:
        try:
            raw = load_data()
        except Exception as e:
            mark_error(e)
            return ("Error", None, f"{STRAT_NAME}: Daten konnten nicht geladen werden: {e}" + "\n" + U.ERROR_HINT)
    grid, P, stale, warns, fr = prepare(raw)
    idx = P.index
    flags = U.month_end_flags(idx)
    rows = np.where(flags & (idx >= pd.Timestamp(HISTORY_START)))[0]
    i_last = len(idx) - 1
    calc_rows = rows if rows[-1] == i_last else np.append(rows, i_last)     # letzter Tag nur fuer Anzeige
    Wall, info = compute(P, calc_rows)
    WF = Wall[:len(rows)]
    k = len(rows) - 1
    dec = idx[rows[k]].date()
    trade = U.next_session_after(dec)
    w, w_prev = WF[k], (WF[k - 1] if k > 0 else np.zeros(len(AL)))
    nd = [d for d in U.nyse_sessions(trade, trade + pd.Timedelta(days=45)) if (d.month, d.year) != (trade.month, trade.year)]
    next_trade = nd[0] if nd else None
    next_dec = max(d for d in U.nyse_sessions(trade, next_trade) if d < next_trade) if next_trade else None

    # Fehlt der Schlusskurs des juengsten Monatsletzten noch (veraltete Daten), ist das neue Monatssignal ausstehend
    me = U.last_month_end_session(U.expected_session_date())
    pend_dec = me if (me is not None and me > dec) else None
    pend_trade = U.next_session_after(pend_dec) if pend_dec else None
    today = U.berlin_today()
    state = U.load_json(NOTIFY_FILE)
    signal, late = None, False
    if state.get("lastDecision") != dec.isoformat():
        if today > trade + pd.Timedelta(days=NTFY_LATE_DAYS):
            state["lastDecision"] = dec.isoformat(); state["skipped"] = today.isoformat()
            if write_files:
                U.save_json(NOTIFY_FILE, state)
        elif today >= trade and not stale and U.is_session(today):      # ntfy nur an NYSE-Handelstagen
            signal = _change_type(w, w_prev)
            late = today > trade
            state.update(lastDecision=dec.isoformat(), sentOn=today.isoformat(), signal=signal)
            PENDING_STATE.clear(); PENDING_STATE.update(state)

    ctx = dict(signal=signal, late=late, today=today, dec=dec, trade=trade, w=w, w_prev=w_prev, pend_dec=pend_dec, pend_trade=pend_trade,
               next_dec=next_dec, next_trade=next_trade, info=info, asof=idx[-1].date(), stale=stale, warns=warns)
    ntfy_text, disc_text = build_messages(ctx)

    hist = []
    for j in range(len(rows)):
        held = [a for a in AL if WF[j][AL.index(a)] > U.W_EPS]
        lead = min(held, key=lambda a: info["rank"][j][AL.index(a)]) if held else "CASH"   # "Platz 3 von 3"
        hist.append(dict(date=idx[rows[j]].date().isoformat(),
                         trade=(trade.isoformat() if j == k else idx[rows[j] + 1].date().isoformat()),
                         allocation=DC.signature(AL, WF[j], eps=U.W_EPS), lead=lead))
    order, trows = _sig_rows(info, w, -1)
    tv = trade_view(w)
    status = {
        "strategy": STRAT_LONG, "name": STRAT_NAME, "key": STRAT_KEY,
        "updated": pd.Timestamp.now(tz=U.TZ).isoformat(),
        "rebalance": "monthly", "rebalanceLabel": "Signal Monatsletzter → Handel 1. Handelstag",
        "asOf": idx[-1].date().isoformat(), "needsRetry": bool(stale), "dataWarnings": warns,
        "decisionDate": dec.isoformat(), "tradeDate": trade.isoformat(),
        "nextDecision": next_dec.isoformat() if next_dec else None,
        "nextRebalance": next_trade.isoformat() if next_trade else None,
        "changedToday": bool(signal in ("BUY", "SELL", "SWITCH", "HOLD")), "changeType": signal,
        "monthlyNotifyToday": bool(signal is not None), "late": bool(late), "pendingDecision": pend_dec.isoformat() if pend_dec else None,
        "pendingTrade": pend_trade.isoformat() if pend_trade else None, "cooldown": 0, "weightDecimals": 1,
        "baskets": BASKET_LABELS,
        "allocation": ([{"asset": x["asset"], "display": ASSETS[x["asset"]]["display"], "weight": round(float(x["trade"]), 4),
                         "leverage": x["lev"], "product": ASSETS[x["asset"]]["product"],
                         "isin": ASSETS[x["asset"]]["isin"]} for x in tv]
                       or [{"asset": "CASH", "display": "Cash", "weight": 1.0, "leverage": 1, "product": "—", "isin": ""}]),
        "signals": {a: {"display": ASSETS[a]["display"], "leverage": ASSETS[a]["leverage"],
                        "rankValue": U.num(info["rank"][-1][AL.index(a)]), "rebound": U.num(info["rebound"][-1][AL.index(a)]),
                        "gates": int(info["gates"][-1][AL.index(a)]), "target": U.num(w[AL.index(a)], 4)} for a in AL},
        "table": {"head": ["Baustein", "Ø Rang", "Rebound", "Gate", "Ziel"],
                  "note": (f"Ø Rang = Mittel SMA_S/SMA_L − 1 über S={SMA_SHORT[0]}–{SMA_SHORT[-1]}, L={SMA_LONG[0]}–{SMA_LONG[-1]} "
                           f"(tiefster = Flop) · Rebound = Ø Rendite über {'/'.join(map(str, REBOUND_DAYS))} Handelstage · "
                           f"Gate = Kurs > SMA{'/'.join(map(str, GATE_SMA))} (erfüllt/3) · Ziel = Zielquote (TLT 5x, Rest 3x)"),
                  "rows": [[f"{ASSETS[a]['leverage']}x {ASSETS[a]['short']}", U.num(info["rank"][-1][AL.index(a)]), U.num(info["rebound"][-1][AL.index(a)]),
                            f"{int(info['gates'][-1][AL.index(a)])}/{len(GATE_SMA)}", U.num(w[AL.index(a)], 4)] for a in order],
                  "kinds": ["text", "spct", "spct", "text", "pct1"]},
        "timeline": {"span": "letzte 120 Monatsentscheidungen",
                     "what": "welches gehaltene Asset auf Platz 3 von 3 lag (schwächster SMA-Rang = Flop)",
                     "items": [{"date": h["date"], "lead": h["lead"], "allocation": h["allocation"]} for h in hist[-120:]]},
        "freshness": fr, "firstDates": U.merge_first(U.load_json(STATUS_FILE).get("firstDates"), {t: U.first_date(s) for t, s in raw.items()}),
    }
    if write_files:
        U.save_json(STATUS_FILE, status)
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write("decision_date,trade_date,allocation,platz3\n")
                for h in hist:
                    f.write(f"{h['date']},{h['trade']},{h['allocation']},{h['lead']}\n")
        except Exception as e:
            print(f"History-Schreibfehler (ignoriert): {e}")
    return signal, ntfy_text, disc_text
