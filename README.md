# MR-Rebound-GTAA (vormals reverseGTAA / MR-Dip) — Signalbot

Discord- und ntfy-Signalbot (GitHub Actions) für die freigegebene **MR-Rebound-GTAA**-Strategie
(Stand 29.09.2026). **KEINE ANLAGEBERATUNG.**

## Strategie
Duo aus zwei Körben zu je 50 %:  **A = Nasdaq 100 + Emerging Markets + TLT**,  **B = Nasdaq 100 + India + TLT**.

| Baustein | Signal (1x-Kurs, Yahoo) | Währung Signal | Invest (Produkt, ISIN) |
|---|---|---|---|
| Nasdaq 100 | `^NDX` | USD | 3x — WisdomTree NASDAQ 100 3x Daily Leveraged, IE00BLRPRL42 |
| Emerging Markets | `EEM` | USD | 3x — WisdomTree Emerging Markets 3x Daily Leveraged (3EML), IE00BYTYHN28 (Basis: MSCI-EM-Futures, USD) |
| India | `^BSESN` (Sensex) | INR = Lokalwährung, währungsneutral (wie „hedged“) | 3x — Leverage Shares 3x Long India (INDA), XS2595675302 |
| US-Treasury 20y+ | `TLT` | USD | **5x** — Leverage Shares 5x Long 20+ Year Treasury Bond, XS2595672036 (volle Quote) |

Die Signalreihen sind **exakt die des Backtests** (p5data.sig_px: `^NDX`, `EEM`, `^BSESN`, `TLT`). Kein Signal in
EUR-unhedged.

- **Zeitplan:** Signal = Schlusskurse des **letzten Handelstags** des Monats, Handel am **1. Handelstag** des Folgemonats.
- **Je Korb und Variante** — Kurz-SMA S = 75…125, Lang-SMA L = 175…250 (1er-Schritte), Rebound R = 42/50/56 Handelstage,
  Gate G = Kurs > SMA100/SMA200/SMA250 → **34.884 Varianten**, gemittelt:
  - Rangwert = SMA_S / SMA_L − 1; **Flop 2** = die zwei schwächsten.
  - bestätigt, wenn Rendite über R Tage > 0 **und** Kurs > SMA_G.
  - beide bestätigt → schwächstes 1/3, zweitschwächstes 2/3; nur eines → max(Slot; 50 %); keines → Cash.
- Gesamt = ½ Korb A + ½ Korb B. **Kein Vol-Target.**
- **TLT:** volle Signalquote im **5x-TLT** (freigegeben 29.09.2026).

Backtest 1995+ (genau diese Umsetzung, TLT 5x): 21 Tranchen CAGR 19,4 %, MaxDD −47,6 %, Sortino 0,85, z31 2,68, z4 2,01,
P(DD<−50 %) 6,1 %, P(DD<−75 %) 0 %; nur letzter Handelstag CAGR 21,1 %, MaxDD −45,3 %, Sortino 0,88, z31 2,82, z4 2,09,
P(DD<−50 %) 11,1 %, P(DD<−75 %) 0,1 %.

**Geprüft:** Der Bot-Kern reproduziert die Backtest-Funktion exakt (393 Monatsentscheidungen, alle 34.884 Varianten,
Abweichung 0).

## Benachrichtigungen
- **Discord:** jeden Tag.
- **ntfy:** **genau einmal pro Monat, am 1. Handelstag** morgens mit den Schlusskursen des Monatsletzten — auch ohne
  Änderung. (Die frühere zweite Meldung am Monatsletzten entfällt.) Bei veralteten Daten: 2 Retries, sonst Nachholung am
  nächsten **NYSE-Handelstag** („verspätet“, max. 7 Tage) — nie am Wochenende/Feiertag. Der Zustand
  `notify_state_mrreboundgtaa.json` wird erst **nach erfolgreichem Push** gespeichert.
- **Datenprüfung vor jeder Berechnung:** Datum des letzten Kurses je Signal, fehlende Handelstage, Tagessprünge > 30 %.
  Fehlt bei einem US-Signal der jüngste Tag, endet das Rechengitter am letzten gemeinsamen Tag (keine Entscheidung auf
  fortgeschriebenen Kursen).

## Dateien
```
main.py / send_ntfy.py
strategies/constants.py      ALLE Parameter
strategies/dip_core.py       Strategie-Kern (reine Funktionen)
strategies/runner.py         Download, Prüfung, Nachricht, status_mrreboundgtaa.json, History
strategies/common.py         Kalender, Download, Datenprüfung (gleich in allen Bots)
.github/workflows/notify.yaml
```

## Umbenennung des Repos (empfohlen)
Settings → General → Repository name: `mrreboundgtaa-signalbot`. Das Dashboard findet die Statusdatei unter dem neuen und
dem alten Namen (`reversegtaa-signalbot`).

Secrets: `DISCORD_WEBHOOK_URL`, `NTFY_TOPIC` (optional `NTFY_SERVER`), `PAT_PUSH`. Workflow permissions: Read and write.

## Ausfallsicherheit und Datenprüfung (Stand 29.09.2026)
- **Vor jeder Berechnung** je Kursreihe: Datum des letzten Kurses (US: zuletzt erwartete NYSE-Sitzung; Sensex/Xetra/FX:
  max. 4 Kalendertage alt), fehlende Handelstage, Sprünge > 30 %, Mindestlänge der Historie und Vergleich des
  Historienbeginns mit dem letzten Lauf (abgeschnittene Yahoo-Antwort), bei Indizes Schluss = Vortag (Platzhalter).
- **Keine Entscheidung und keine ntfy**, wenn eine Prüfung fehlschlägt (veraltet, abgeschnitten, unplausibler Sprung am
  jüngsten Tag, Kalender nicht ladbar): `needsRetry` → 2 Wiederholungen im Abstand von 30 Min, zusätzlich
  **Sicherheitslauf 11:47 UTC** (läuft nur, wenn der Morgenlauf nicht erfolgreich war). Fehlt bei einem US-Signal der
  jüngste Tag, rechnet der Bot nur bis zum letzten gemeinsamen Tag (keine fortgeschriebenen Kurse als Entscheidungsbasis).
- **Download fehlgeschlagen**: kein Handel, keine ntfy; letzter gültiger Stand bleibt im Dashboard (Handelsanweisung wird
  entfernt), Discord meldet den Fehler. Der nächste erfolgreiche Lauf rechnet alles aus der vollen Historie neu (auch den
  Cooldown) und holt eine fällige ntfy-Meldung am nächsten Handelstag nach („verspätet“).
- **Workflow-Fehler** (Installation/Start): Discord bekommt eine Fehlermeldung; Discord- und Commit-Schritt laufen immer
  (`if: always()`), Push mit 3 Versuchen — der ntfy-Zustand geht nicht verloren (keine Doppelmeldung).
- **Erststart/verlorener Zustand**: Ist ein Wechsel noch nicht gehandelt, wird er trotzdem gemeldet.
- Ist dauerhaft kein `NTFY_TOPIC` gesetzt, gilt die Meldung als erledigt (nur Discord), statt täglich „verspätet“ zu wiederholen.
