import asyncio
import os
import re
import subprocess

VOCE = os.environ.get("AULA_VOCE") or "it-IT-IsabellaNeural"
PROVA = os.environ.get("AULA_TEST") == "1"


def parlato(t):
    t = str(t or "")
    t = re.sub(r"[*`#_]", "", t)
    for a, b in (("%", " per cento"), ("€", " euro"), ("$", " dollari"), ("&", " e "), ("→", ", quindi "),
                 ("≈", " circa "), ("×", " per "), ("≥", " maggiore o uguale a "), ("≤", " minore o uguale a "),
                 ("=", " uguale a "), ("<", " minore di "), (">", " maggiore di "), ("+", " più "),
                 ("(", ", "), (")", ", "), ("/", " su "), ("–", ", "), ("—", ", ")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t).strip()


def durata(percorso):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", percorso],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def _finta(testo, percorso):
    secondi = max(len(testo.split()) / 2.7, 0.8)
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                    "anoisesrc=d=%.2f:c=pink:a=0.05:r=24000" % secondi, "-ac", "1", "-b:a", "48k", percorso],
                   check=True)


async def _edge(testo, percorso, sem):
    import edge_tts
    async with sem:
        for t in range(3):
            try:
                await edge_tts.Communicate(testo, VOCE, rate="+0%").save(percorso)
                if os.path.exists(percorso) and os.path.getsize(percorso) > 500:
                    return True
            except Exception as e:
                print("edge-tts: " + type(e).__name__, flush=True)
            await asyncio.sleep(2 * (t + 1))
    return False


async def _tutti(lavori):
    sem = asyncio.Semaphore(4)
    return await asyncio.gather(*[_edge(t, p, sem) for t, p in lavori])


def _gtts(testo, percorso):
    from gtts import gTTS
    gTTS(testo, lang="it").save(percorso)


def sintetizza(lavori):
    """lavori: lista di (testo, percorso_mp3). Crea tutti i file audio."""
    pronti = [(parlato(t), p) for t, p in lavori]
    if PROVA:
        for t, p in pronti:
            _finta(t, p)
        return "prova"
    esiti = asyncio.run(_tutti(pronti))
    usato = "edge-tts"
    for (t, p), ok in zip(pronti, esiti):
        if not ok:
            usato = "edge-tts + gTTS"
            _gtts(t, p)
    return usato
