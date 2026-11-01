import base64
import html
import os

import requests

CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
RESEND = os.environ.get("RESEND_API_KEY", "")
EMAIL_TO = os.environ.get("EMAIL_TO", "")
EMAIL_MAX = float(os.environ.get("AULA_EMAIL_MAX_MB", "23")) * 1e6
TG_MAX = float(os.environ.get("AULA_TG_MAX_MB", "46")) * 1e6


def telegram(testo):
    if not TOKEN or not CHAT:
        return
    try:
        requests.post("https://api.telegram.org/bot%s/sendMessage" % TOKEN,
                      json={"chat_id": CHAT, "text": testo[:4000]}, timeout=30)
    except Exception as e:
        print("Telegram: avviso non inviato (%s)" % type(e).__name__, flush=True)


def _telegram_video(percorso, didascalia):
    with open(percorso, "rb") as f:
        r = requests.post("https://api.telegram.org/bot%s/sendVideo" % TOKEN,
                          data={"chat_id": CHAT, "caption": didascalia[:1000], "supports_streaming": "true"},
                          files={"video": (os.path.basename(percorso), f)}, timeout=600)
    if r.status_code == 200:
        return True, ""
    with open(percorso, "rb") as f:
        r2 = requests.post("https://api.telegram.org/bot%s/sendDocument" % TOKEN,
                           data={"chat_id": CHAT, "caption": didascalia[:1000]},
                           files={"document": (os.path.basename(percorso), f)}, timeout=600)
    return r2.status_code == 200, "Telegram %d" % r2.status_code


def _email(percorso, oggetto, corpo_html):
    if not RESEND or not EMAIL_TO:
        return False, "chiave Resend o indirizzo email mancanti"
    with open(percorso, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    r = requests.post("https://api.resend.com/emails",
                      headers={"Authorization": "Bearer " + RESEND, "Content-Type": "application/json",
                               "User-Agent": "aula/1.0"},
                      json={"from": "Aula <onboarding@resend.dev>", "to": [EMAIL_TO], "subject": oggetto,
                            "html": corpo_html, "attachments": [{"filename": os.path.basename(percorso),
                                                                  "content": b64}]}, timeout=600)
    if r.status_code in (200, 201):
        return True, ""
    return False, "Resend %d: %s" % (r.status_code, r.text[:140].replace("\n", " "))


def corpo(titolo, durata_min, indice, parte, parti):
    righe = "".join("<li>%s</li>" % html.escape(t) for t in indice[:40])
    p = " (Parte %d di %d)" % (parte, parti) if parti > 1 else ""
    return ("<p><b>%s</b>%s<br>Durata: circa %.0f minuti.</p><p>Indice della lezione:</p><ol>%s</ol>"
            "<p><small>Lezione generata con l'AI a partire dal sommario dei libri: controlla i dettagli sul testo.</small></p>"
            % (html.escape(titolo), p, durata_min, righe))


def consegna(percorso, oggetto, titolo, durata_s, indice, parte, parti):
    """Sceglie il canale in base alla dimensione. Restituisce (canale, messaggio_errore)."""
    dim = os.path.getsize(percorso)
    mb = dim / 1e6
    errori = []
    if dim <= EMAIL_MAX:
        ok, err = _email(percorso, oggetto, corpo(titolo, durata_s / 60, indice, parte, parti))
        if ok:
            return "email (%.1f MB)" % mb, ""
        errori.append(err)
    if dim <= TG_MAX:
        ok, err = _telegram_video(percorso, oggetto)
        if ok:
            return "Telegram (%.1f MB)" % mb, " | ".join(errori)
        errori.append(err)
    return None, " | ".join(errori) or "file troppo grande (%.1f MB)" % mb
