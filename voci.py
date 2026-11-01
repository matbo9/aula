import asyncio
import os

import edge_tts
import requests

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")
TESTO = ("Immaginate di entrare in un negozio e trovare lo stesso paio di scarpe a quaranta euro in meno di un anno fa. "
         "Come è possibile? Il motivo è il commercio internazionale: ogni paese produce ciò che sa fare meglio, "
         "e tutti ci guadagnano. Vediamo insieme come funziona, partendo da un esempio semplice.")
PREFERITE = ["it-IT-GiuseppeMultilingualNeural", "it-IT-ElsaNeural", "it-IT-IsabellaNeural", "it-IT-DiegoNeural",
             "en-US-AvaMultilingualNeural", "en-US-EmmaMultilingualNeural", "en-US-AndrewMultilingualNeural",
             "en-US-BrianMultilingualNeural", "fr-FR-VivienneMultilingualNeural", "fr-FR-RemyMultilingualNeural",
             "de-DE-SeraphinaMultilingualNeural", "de-DE-FlorianMultilingualNeural"]


def invia(testo=None, audio=None, titolo=""):
    if not TOKEN or not CHAT:
        print(testo or titolo)
        return
    base = "https://api.telegram.org/bot%s/" % TOKEN
    if audio:
        with open(audio, "rb") as f:
            requests.post(base + "sendAudio", data={"chat_id": CHAT, "title": titolo, "caption": titolo},
                          files={"audio": (titolo + ".mp3", f)}, timeout=120)
    else:
        requests.post(base + "sendMessage", json={"chat_id": CHAT, "text": testo}, timeout=30)


async def main():
    esistenti = {v["ShortName"] for v in await edge_tts.list_voices()}
    scelte = [v for v in PREFERITE if v in esistenti]
    invia("Prova voci: invio %d campioni. Dimmi il nome della voce che preferisci." % len(scelte))
    for v in scelte:
        try:
            nome = "/tmp/%s.mp3" % v
            await edge_tts.Communicate(TESTO, v, rate="-4%").save(nome)
            invia(audio=nome, titolo=v)
        except Exception as e:
            print(v, type(e).__name__)


asyncio.run(main())
