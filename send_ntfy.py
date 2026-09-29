"""
ntfy-Push (https://ntfy.sh, kostenlos, kein Account).
Setup: ntfy-App installieren, das Topic aus dem GitHub-Secret NTFY_TOPIC abonnieren.
Der Topic-Name ist wie ein Passwort (lang und nicht erratbar waehlen).
Gibt True (gesendet) / False (Fehler -> naechster Lauf wiederholt) / None (kein Topic) zurueck und wirft NIE (der Discord-Ablauf darf nie gestoert werden).
"""
import os
import urllib.request


def send_ntfy(title, message, tags="bell"):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("Kein NTFY_TOPIC gesetzt (ntfy uebersprungen).")
        return None                    # nicht konfiguriert: kein Fehler, Meldung gilt als erledigt (nur Discord)
    server = (os.environ.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    url = f"{server}/{topic}"
    try:
        req = urllib.request.Request(url, data=message.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "replace").decode("ascii"))   # Header muessen ASCII sein
        req.add_header("Priority", "high")
        req.add_header("Tags", tags)
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"ntfy OK ({resp.status})")
        return 200 <= resp.status < 300
    except Exception as e:
        print(f"ntfy failed: {e}")
        return False


if __name__ == "__main__":
    send_ntfy("TEST", "ntfy Test-Nachricht")
