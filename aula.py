import json
import os
import re
import shutil
import time
from pathlib import Path

import gemini_lezione as gl
import invio
import slide as sl
import video
import voce

INIZIO = time.time()
AVVISO = "Lezione generata con l'AI sul sommario dei libri: controlla i dettagli sul testo."


def passo(t):
    print("[%4.1f min] %s" % ((time.time() - INIZIO) / 60, t), flush=True)


def nome_corso(testo):
    m = re.search(r"^\s*corso\s*:\s*(.+)$", testo, re.I | re.M)
    return m.group(1).strip() if m else "Lezione"


def genera_slide(corso, argomento, minuti):
    p = gl.piano(corso, argomento, minuti)
    passo("Scaletta pronta: %d sezioni" % len(p["sezioni"]))
    slides, riassunto = [], ""
    for i in range(len(p["sezioni"])):
        s = gl.sezione(corso, argomento, p, i, riassunto)
        lista, note = gl.verifica(s)
        passo("Sezione %d/%d scritta%s" % (i + 1, len(p["sezioni"]), " e corretta dopo la verifica" if note else ""))
        slides += lista
        riassunto = str(s.get("riassunto", ""))[:400]
    obiettivi = p.get("obiettivi") or []
    nar = "Benvenuto. In questa lezione parliamo di %s." % p["titolo_lezione"]
    if obiettivi:
        nar += " Alla fine saprai: " + "; ".join(o.rstrip(".") for o in obiettivi) + "."
    copertina = {"tipo": "titolo", "titolo": p["titolo_lezione"], "sottotitolo": nome_corso(corso),
                 "nota": AVVISO, "narrazione": nar}
    return p["titolo_lezione"], [sl.normalizza(copertina)] + [sl.normalizza(s) for s in slides]


def costruisci_frames(slides, titolo, lavoro):
    lavori, frames = [], []
    for si, s in enumerate(slides):
        for fi, (rev, nar) in enumerate(sl.frames(s)):
            nar = nar if nar and nar.strip() else (s["titolo"] or "...")
            img = os.path.join(lavoro, "s%03d_%d.png" % (si, fi))
            mp3 = os.path.join(lavoro, "s%03d_%d.mp3" % (si, fi))
            wav = os.path.join(lavoro, "s%03d_%d.wav" % (si, fi))
            sl.render(s, rev, img, (si + 0.5) / len(slides), titolo)
            lavori.append((nar, mp3))
            frames.append({"img": img, "mp3": mp3, "wav": wav, "slide": si})
    passo("Disegnate %d immagini per %d slide" % (len(frames), len(slides)))
    motore = voce.sintetizza(lavori)
    passo("Voce sintetizzata (%s)" % motore)
    for f in frames:
        f["dur"] = video.prepara_audio(f["mp3"], f["wav"])
    return frames


def produci_lezione(slides, titolo, base, lavoro):
    frames = costruisci_frames(slides, titolo, lavoro)
    durata = sum(f["dur"] for f in frames)
    passo("Durata del parlato: %.1f minuti" % (durata / 60))
    risultati = video.produci(frames, base, lavoro, invio.TG_MAX)
    return risultati, durata


INTRO = ("Lezione introduttiva al corso: presentazione del corso e del percorso di studio, a cosa serve la materia, "
         "esempi di vita reale che creano una connessione e suscitano curiosità, i concetti chiave che si incontreranno "
         "e come studiare. Nessun calcolo difficile: serve a prendere dimestichezza con la materia.")


def carica_piano(corso_nome, corso):
    f = Path("piani") / (corso_nome + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))["lezioni"]
    return None


def crea_piano(corso_nome, corso):
    lezioni = gl.piano_corso(corso)
    Path("piani").mkdir(exist_ok=True)
    (Path("piani") / (corso_nome + ".json")).write_text(
        json.dumps({"lezioni": lezioni}, ensure_ascii=False, indent=1), encoding="utf-8")
    righe = ["Aula: ecco il percorso di studio (%d lezioni dopo l'introduzione):" % len(lezioni), "0. Lezione introduttiva"]
    righe += ["%d. %s (%d min)" % (k, x["titolo"], x["minuti"]) for k, x in enumerate(lezioni, 1)]
    righe.append("Per ogni lezione: Actions, Aula, Run workflow, scrivi nella casella lezione intro, 1, 2, 3 e così via.")
    invio.telegram("\n".join(righe))
    return lezioni


def contesto(lezioni, n):
    elenco = "\n".join("%d) %s" % (k, x["titolo"]) for k, x in enumerate(lezioni, 1))
    t = "PERCORSO DI STUDIO COMPLETO (lezione introduttiva e poi):\n" + elenco + "\n"
    if n == 0:
        t += "Questa è la LEZIONE INTRODUTTIVA, prima del percorso.\n"
    else:
        t += "Questa è la LEZIONE %d di %d.%s\n" % (n, len(lezioni),
             " La precedente era: " + lezioni[n - 2]["titolo"] + "." if n > 1 else " Segue l'introduzione.")
        if n < len(lezioni):
            t += "La prossima sarà: " + lezioni[n]["titolo"] + ".\n"
    return t + "\n"


def main():
    corso_nome = os.environ.get("CORSO", "economia_internazionale").strip()
    argomento = os.environ.get("ARGOMENTO", "").strip()
    lez = os.environ.get("LEZIONE", "").strip().lower()
    minuti_in = os.environ.get("MINUTI", "").strip()
    percorso = Path("corsi") / (corso_nome + ".txt")
    if not percorso.exists():
        raise RuntimeError("Non trovo il file del corso: corsi/%s.txt" % corso_nome)
    corso = percorso.read_text(encoding="utf-8")
    ctx_piano, etichetta, prossima = "", "", ""
    minuti = None
    if not argomento:
        if lez in ("piano", "percorso"):
            lezioni = crea_piano(corso_nome, corso)
            passo("Piano creato: %d lezioni" % len(lezioni))
            return
        lezioni = carica_piano(corso_nome, corso)
        if lezioni is None:
            invio.telegram("Aula: creo prima il percorso di studio del corso.")
            lezioni = crea_piano(corso_nome, corso)
        if lez in ("", "intro", "0", "introduzione"):
            n, argomento, minuti = 0, INTRO, 15
            etichetta = "Lezione introduttiva"
        elif lez.isdigit() and 1 <= int(lez) <= len(lezioni):
            n = int(lez)
            x = lezioni[n - 1]
            argomento = "%s. %s" % (x["titolo"], x["scopo"])
            minuti = x["minuti"]
            etichetta = "Lezione %d" % n
        else:
            raise RuntimeError("Lezione non valida: scrivi intro oppure un numero da 1 a %d" % len(lezioni))
        ctx_piano = contesto(lezioni, n)
        if n < len(lezioni):
            prossima = "Prossima: scrivi %d (%s)." % (n + 1, lezioni[n]["titolo"])
        else:
            prossima = "Era l'ultima lezione del percorso."
        titolo_base = etichetta + ": " + (lezioni[n - 1]["titolo"] if n else "introduzione al corso")
    else:
        titolo_base = argomento
    if minuti_in:
        minuti = int(float(minuti_in))
    minuti = max(10, min(int(minuti or 15), 40))
    invio.telegram("Aula: preparo «%s» (circa %d minuti). Ci vorrà qualche decina di minuti." % (titolo_base, minuti))
    lavoro = Path("lavoro")
    if lavoro.exists():
        shutil.rmtree(lavoro)
    lavoro.mkdir()
    titolo, slides = genera_slide(ctx_piano + corso, argomento, minuti)
    if etichetta:
        titolo = etichetta + ": " + titolo if not titolo.lower().startswith(etichetta.lower()) else titolo
    slug = re.sub(r"[^A-Za-z0-9]+", "_", titolo)[:40].strip("_") or "lezione"
    risultati, durata = produci_lezione(slides, titolo, "Aula_" + slug, str(lavoro))
    indice = [s["titolo"] for s in slides[1:] if s["titolo"]]
    parti = len(risultati)
    esiti = []
    for k, (out, dim, dur) in enumerate(risultati, 1):
        oggetto = "Aula - %s%s" % (titolo, " (Parte %d di %d)" % (k, parti) if parti > 1 else "")
        canale, err = invio.consegna(out, oggetto, titolo, dur, indice, k, parti)
        esiti.append((canale, err))
        if canale is None:
            invio.telegram("Aula: non sono riuscito a consegnare «%s»: %s" % (oggetto, err))
        elif err:
            passo("Nota consegna: " + err[:160])
    ok = [c for c, _ in esiti if c]
    riga = "Aula: «%s» pronta. Durata circa %.0f minuti%s. Consegna: %s." % (
        titolo, durata / 60, " in %d parti" % parti if parti > 1 else "", ", ".join(ok) if ok else "non riuscita")
    if durata / 60 < 9.5:
        riga += " Attenzione: è più corta dei 10 minuti richiesti."
    if prossima:
        riga += " " + prossima
    invio.telegram(riga)
    passo(riga)
    shutil.rmtree(lavoro, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        invio.telegram("Aula: errore, la lezione non è stata completata: %s: %s" % (type(e).__name__, str(e)[:300]))
        raise
