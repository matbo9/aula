import os
import subprocess

import voce

QUALITA = [(1280, 720, 28), (1280, 720, 33), (960, 540, 35), (854, 480, 37)]


def ff(args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + args, check=True)


def silenzio(percorso, secondi):
    ff(["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "%.2f" % secondi, percorso])


def prepara_audio(mp3, wav):
    ff(["-i", mp3, "-af", "apad=pad_dur=0.45", "-ar", "24000", "-ac", "1", wav])
    return voce.durata(wav)


def costruisci(frames, out, lavoro, qualita):
    """frames: lista di dict(img, wav, dur). Crea un mp4 con audio e immagini sincronizzati."""
    w, h, crf = qualita
    lista_a = os.path.join(lavoro, "audio.txt")
    lista_v = os.path.join(lavoro, "immagini.txt")
    with open(lista_a, "w") as fa, open(lista_v, "w") as fv:
        for f in frames:
            fa.write("file '%s'\n" % os.path.abspath(f["wav"]))
            fv.write("file '%s'\nduration %.3f\n" % (os.path.abspath(f["img"]), f["dur"]))
        fv.write("file '%s'\n" % os.path.abspath(frames[-1]["img"]))
    audio = os.path.join(lavoro, "audio_unito.wav")
    ff(["-f", "concat", "-safe", "0", "-i", lista_a, "-c", "copy", audio])
    ff(["-f", "concat", "-safe", "0", "-i", lista_v, "-i", audio,
        "-vf", "scale=%d:%d:flags=lanczos,fps=5,format=yuv420p" % (w, h),
        "-c:v", "libx264", "-preset", "veryfast", "-tune", "stillimage", "-crf", str(crf), "-g", "50",
        "-c:a", "aac", "-b:a", "48k", "-ar", "24000", "-ac", "1", "-movflags", "+faststart", out])
    return os.path.getsize(out)


def produci(frames, base, lavoro, tg_max, n=1, risultati=None):
    """Restituisce lista di (percorso_mp4, dimensione, durata_secondi, parte, parti)."""
    risultati = [] if risultati is None else risultati
    durata = sum(f["dur"] for f in frames)
    out = "%s_P%d.mp4" % (base, len(risultati) + 1) if n > 1 else base + ".mp4"
    dim = None
    for q in QUALITA:
        dim = costruisci(frames, out, lavoro, q)
        print("Codifica %dx%d crf %d: %.1f MB" % (q[0], q[1], q[2], dim / 1e6), flush=True)
        if dim <= tg_max:
            break
    if dim <= tg_max or len(frames) < 4:
        risultati.append([out, dim, durata])
        return risultati
    os.remove(out)
    tot, met, taglio = durata, durata / 2, 0
    acc = 0.0
    for i, f in enumerate(frames):
        acc += f["dur"]
        if acc >= met and (i + 1 >= len(frames) or frames[i + 1].get("slide") != f.get("slide")):
            taglio = i + 1
            break
    if taglio <= 0 or taglio >= len(frames):
        taglio = len(frames) // 2
    a, b = frames[:taglio], frames[taglio:]
    produci(a, base, lavoro, tg_max, risultati=risultati, n=2)
    produci(b, base, lavoro, tg_max, risultati=risultati, n=2)
    return risultati
