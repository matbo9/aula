import re
from functools import lru_cache

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.textpath import TextPath

plt.rcParams["font.family"] = "DejaVu Sans"

W, H, DPI = 1280, 720, 100
PT = DPI / 72.0
BG, CARD, TXT, SOFT = "#0e1a2b", "#16263d", "#f2f6fb", "#9fb3c8"
ACC, ACC2, OK, BAD = "#4cc3d9", "#f4a261", "#5cc98a", "#ef6f6c"
SERIE = [ACC, ACC2, OK, "#c792ea", "#f2cc60"]
LISTE = {"punti": "punti", "esempio": "passi", "schema": "riquadri", "riepilogo": "punti"}
_FP = {False: FontProperties(family="DejaVu Sans"), True: FontProperties(family="DejaVu Sans", weight="bold")}


def pul(t):
    t = str(t if t is not None else "")
    t = re.sub(r"[*`#]", "", t)
    t = re.sub(r"\$\s*(\d[\d.,]*)", r"\1 USD", t)
    t = t.replace("$", "")
    return re.sub(r"[ \t]+", " ", t).strip()


@lru_cache(maxsize=50000)
def larg(parola, fs, bold=False):
    if not parola.strip():
        return 0.0
    try:
        return TextPath((0, 0), parola, size=fs, prop=_FP[bold]).get_extents().width * PT
    except Exception:
        return len(parola) * fs * PT * 0.6


def spazio(fs, bold=False):
    return max(larg("a a", fs, bold) - larg("aa", fs, bold), fs * PT * 0.3)


def spezza(testo, fs, max_w, bold=False):
    righe = []
    sp = spazio(fs, bold)
    for par in pul(testo).split("\n"):
        cur, curw = "", 0.0
        for p in par.split():
            w = larg(p, fs, bold)
            if cur and curw + sp + w > max_w:
                righe.append(cur)
                cur, curw = p, w
            else:
                curw += (sp if cur else 0) + w
                cur = (cur + " " + p) if cur else p
        if cur:
            righe.append(cur)
    return righe or [""]


def alt(righe, fs, lh=1.32):
    return len(righe) * fs * PT * lh


def adatta(items, w, h_max, fs0, fs_min, gap, bold=False):
    fs = fs0
    while True:
        blocchi = [spezza(t, fs, w, bold) for t in items]
        h = sum(alt(b, fs) + gap for b in blocchi) - (gap if blocchi else 0)
        if h <= h_max or fs <= fs_min:
            return fs, blocchi, h
        fs -= 1


def testo(ax, x, y, righe, fs, colore=TXT, bold=False, lh=1.32, ha="left"):
    for j, r in enumerate(righe):
        ax.text(x, y + j * fs * PT * lh, r, fontsize=fs, color=colore, va="top", ha=ha,
                fontweight="bold" if bold else "normal")
    return y + alt(righe, fs, lh)


def stringhe(lista):
    out = []
    for v in lista or []:
        if isinstance(v, dict):
            v = v.get("testo") or v.get("titolo") or " ".join(str(x) for x in v.values())
        out.append(pul(v))
    return [v for v in out if v]


def normalizza(s):
    s = dict(s) if isinstance(s, dict) else {"tipo": "punti", "titolo": "", "punti": [pul(s)]}
    tipo = str(s.get("tipo", "punti")).lower().strip()
    if tipo not in ("titolo", "punti", "definizione", "esempio", "tabella", "grafico", "formula", "schema",
                    "confronto", "riepilogo"):
        tipo = "punti"
    s["tipo"] = tipo
    s["titolo"] = pul(s.get("titolo", ""))[:90]
    if tipo in ("punti", "riepilogo"):
        s["punti"] = stringhe(s.get("punti") or s.get("passi") or [s.get("testo", "")])[:6]
        if not s["punti"]:
            s["punti"] = [s["titolo"] or "..."]
    if tipo == "esempio":
        s["scenario"] = pul(s.get("scenario", ""))
        s["passi"] = stringhe(s.get("passi") or s.get("punti"))[:7]
        s["risultato"] = pul(s.get("risultato", ""))
        if not s["passi"]:
            s["passi"] = [s["scenario"] or "..."]
    if tipo == "schema":
        s["riquadri"] = stringhe(s.get("riquadri") or s.get("punti"))[:5]
        if len(s["riquadri"]) < 2:
            s["tipo"] = "punti"
            s["punti"] = s["riquadri"] or [s["titolo"] or "..."]
    if tipo == "definizione":
        s["termine"] = pul(s.get("termine", s["titolo"]))
        s["definizione"] = pul(s.get("definizione", ""))
        s["nota"] = pul(s.get("nota", ""))
    if tipo == "formula":
        s["formula"] = str(s.get("formula", "")).strip()
        s["spiegazione"] = stringhe(s.get("spiegazione"))[:4]
    if tipo == "confronto":
        for lato in ("sinistra", "destra"):
            d = s.get(lato) if isinstance(s.get(lato), dict) else {}
            s[lato] = {"titolo": pul(d.get("titolo", lato)), "punti": stringhe(d.get("punti"))[:5]}
    if tipo == "tabella":
        col = [pul(c) for c in (s.get("colonne") or [])]
        righe = [[pul(c) for c in r] for r in (s.get("righe") or []) if isinstance(r, list)]
        if not col or not righe:
            s["tipo"] = "punti"
            s["punti"] = [s["titolo"] or "..."]
        else:
            n = len(col)
            s["colonne"] = col
            s["righe"] = [(r + [""] * n)[:n] for r in righe][:8]
            s["nota"] = pul(s.get("nota", ""))
    if tipo == "grafico":
        s["nota"] = pul(s.get("nota", ""))
    nar = s.get("narrazione", "")
    if isinstance(nar, list):
        nar = [pul(x) for x in nar if pul(x)]
    else:
        nar = pul(nar)
    s["narrazione"] = nar
    return s


def frames(s):
    campo = LISTE.get(s["tipo"])
    nar = s["narrazione"]
    if campo is None:
        return [(None, nar if isinstance(nar, str) else " ".join(nar))]
    n = len(s[campo])
    if isinstance(nar, str):
        return [(n, nar)]
    if len(nar) == n + 1:
        return [(k, nar[k]) for k in range(n + 1)]
    if len(nar) == n:
        return [(k + 1, nar[k]) for k in range(n)]
    return [(n, " ".join(nar))]


def titolo_slide(ax, titolo, fs=34):
    righe = spezza(titolo, fs, 1160, True)
    while len(righe) > 2 and fs > 24:
        fs -= 2
        righe = spezza(titolo, fs, 1160, True)
    y = testo(ax, 60, 36, righe[:2], fs, TXT, True, 1.18)
    ax.add_patch(Rectangle((60, y + 8), 110, 5, color=ACC))
    return y + 40


def sfondo(ax, progresso, nome):
    ax.add_patch(Rectangle((0, 0), W, H, color=BG, zorder=-5))
    ax.text(60, 688, pul(nome)[:90], fontsize=12, color=SOFT, va="top")
    ax.add_patch(Rectangle((0, H - 6), W, 6, color="#1d3250"))
    ax.add_patch(Rectangle((0, H - 6), W * max(min(progresso, 1), 0), 6, color=ACC))


def d_titolo(ax, s):
    righe = spezza(s["titolo"], 50, 1080, True)
    y = 190
    y = testo(ax, 100, y, righe[:3], 50, TXT, True, 1.2)
    ax.add_patch(Rectangle((100, y + 14), 140, 6, color=ACC))
    sotto = spezza(s.get("sottotitolo", ""), 26, 1080)
    y = testo(ax, 100, y + 50, sotto[:5], 26, SOFT)
    nota = spezza(s.get("nota", ""), 17, 1080)
    testo(ax, 100, 610, nota[:3], 17, SOFT)


def d_lista(ax, s, reveal, y0, campo, segno=None):
    items = s[campo]
    fs, blocchi, h = adatta(items, 1100, 680 - y0, 32, 19, 18)
    y = y0
    for i, b in enumerate(blocchi):
        if i < reveal:
            col = ACC2 if i == reveal - 1 else ACC
            cy = y + fs * PT * 0.62
            if segno:
                ax.text(62, y, segno, fontsize=fs, color=OK, va="top", fontweight="bold")
            else:
                ax.add_patch(Circle((76, cy), 10, color=col))
            testo(ax, 118, y, b, fs)
        y += alt(b, fs) + 18


def d_definizione(ax, s, y0):
    ter = spezza(s["termine"], 40, 1040, True)
    dfs, dbl, dh = adatta([s["definizione"]], 1040, 330, 30, 20, 0)
    hcard = alt(ter, 40) + 28 + dh + 70
    ax.add_patch(FancyBboxPatch((60, y0), 1160, hcard, boxstyle="round,pad=0,rounding_size=18", color=CARD))
    ax.add_patch(Rectangle((60, y0 + 14), 8, hcard - 28, color=ACC))
    y = testo(ax, 100, y0 + 30, ter, 40, ACC, True)
    y = testo(ax, 100, y + 24, dbl[0], dfs, TXT)
    if s.get("nota"):
        nl = spezza(s["nota"], 22, 1100)
        testo(ax, 60, y0 + hcard + 30, nl[:3], 22, SOFT)


def d_esempio(ax, s, reveal, y0):
    ax.add_patch(FancyBboxPatch((60, y0 - 6), 128, 30, boxstyle="round,pad=0,rounding_size=8", color=ACC2))
    ax.text(124, y0 + 9, "ESEMPIO", fontsize=14, color=BG, va="center", ha="center", fontweight="bold")
    sfs, sbl, sh = adatta([s["scenario"] or " "], 1090, 150, 26, 18, 0)
    hs = sh + 36
    ax.add_patch(FancyBboxPatch((60, y0 + 34), 1160, hs, boxstyle="round,pad=0,rounding_size=14", color=CARD))
    testo(ax, 90, y0 + 52, sbl[0], sfs)
    ry = y0 + 34 + hs + 22
    res = s["risultato"]
    rfs, rbl, rh = adatta([res], 1080, 100, 26, 18, 0, True) if res else (24, [[]], 0)
    bx_h = rh + 34 if res else 0
    ybox = 684 - bx_h - 6
    fs, blocchi, h = adatta(s["passi"], 1060, ybox - 16 - ry, 26, 17, 12)
    y = ry
    for i, b in enumerate(blocchi):
        if i < reveal:
            cy = y + fs * PT * 0.62
            ax.add_patch(Circle((82, cy), 17, color=ACC if i < reveal - 1 else ACC2))
            ax.text(82, cy, str(i + 1), fontsize=15, color=BG, ha="center", va="center", fontweight="bold")
            testo(ax, 120, y, b, fs)
        y += alt(b, fs) + 12
    if res and reveal >= len(s["passi"]):
        ax.add_patch(FancyBboxPatch((60, ybox), 1160, bx_h, boxstyle="round,pad=0,rounding_size=14",
                                    facecolor="none", edgecolor=OK, linewidth=3))
        testo(ax, 90, ybox + 16, rbl[0], rfs, OK, True)


def d_tabella(ax, s, y0):
    col, righe = s["colonne"], s["righe"]
    ev = set()
    for p in s.get("evidenzia") or []:
        try:
            ev.add((int(p[0]), int(p[1])))
        except Exception:
            pass
    fs = 26
    while True:
        ws = [max([larg(col[c], fs, True)] + [larg(r[c], fs) for r in righe]) + 44 for c in range(len(col))]
        rh = fs * PT * 1.9
        if (sum(ws) <= 1160 and rh * (len(righe) + 1) <= 400) or fs <= 14:
            break
        fs -= 1
    tot = sum(ws)
    if tot < 760:
        ws = [w * 760 / tot for w in ws]
        tot = 760
    if tot > 1160:
        ws = [w * 1160 / tot for w in ws]
        tot = 1160
    x0 = (W - tot) / 2
    x = x0
    for c, w in enumerate(ws):
        ax.add_patch(Rectangle((x, y0), w, rh, color="#1f5666"))
        ax.text(x + w / 2, y0 + rh / 2, col[c], fontsize=fs, color=TXT, ha="center", va="center", fontweight="bold")
        x += w
    for i, r in enumerate(righe):
        yy = y0 + rh * (i + 1)
        x = x0
        for c, w in enumerate(ws):
            ax.add_patch(Rectangle((x, yy), w, rh, color=CARD if i % 2 == 0 else "#122238"))
            if (i, c) in ev:
                ax.add_patch(Rectangle((x + 2, yy + 2), w - 4, rh - 4, facecolor=ACC2 + "40", edgecolor=ACC2,
                                       linewidth=3))
            ax.text(x + w / 2, yy + rh / 2, r[c], fontsize=fs, color=TXT, ha="center", va="center")
            x += w
    if s.get("nota"):
        testo(ax, 60, y0 + rh * (len(righe) + 1) + 26, spezza(s["nota"], 22, 1160)[:3], 22, SOFT)


def d_grafico(fig, ax, s, y0):
    g = s.get("grafico") if isinstance(s.get("grafico"), dict) else {}
    serie = g.get("serie") or []
    if not serie:
        raise ValueError("serie mancanti")
    a = fig.add_axes([0.075, 0.13, 0.60, 1 - 0.13 - (y0 + 10) / H])
    a.set_facecolor(CARD)
    for sp in a.spines.values():
        sp.set_color(SOFT)
    a.tick_params(colors=TXT, labelsize=13)
    a.grid(alpha=0.18)
    tipo = str(g.get("tipo", "linee")).lower()
    if tipo.startswith("barre"):
        cat = [pul(c) for c in (g.get("categorie") or serie[0].get("x") or [])]
        n = len(serie)
        lar = 0.8 / n
        for i, se in enumerate(serie):
            ys = [float(v) for v in se["y"]]
            xs = [k + (i - (n - 1) / 2) * lar for k in range(len(ys))]
            a.bar(xs, ys, width=lar * 0.92, color=SERIE[i % 5], label=pul(se.get("nome", "")))
        a.set_xticks(range(len(cat)))
        a.set_xticklabels(cat, fontsize=13)
    else:
        for i, se in enumerate(serie):
            xs = [float(v) for v in se["x"]]
            ys = [float(v) for v in se["y"]]
            a.plot(xs, ys, color=SERIE[i % 5], lw=3.2, marker="o" if len(xs) <= 8 else None, ms=7,
                   label=pul(se.get("nome", "")))
        if g.get("da_zero", True):
            a.set_xlim(left=0 if min(float(v) for se in serie for v in se["x"]) >= 0 else None)
            a.set_ylim(bottom=0 if min(float(v) for se in serie for v in se["y"]) >= 0 else None)
    for an in g.get("annotazioni") or []:
        try:
            a.annotate(pul(an.get("testo", "")), (float(an["x"]), float(an["y"])), xytext=(12, 14),
                       textcoords="offset points", color=ACC2, fontsize=13, fontweight="bold",
                       arrowprops=dict(arrowstyle="-", color=ACC2))
            a.plot([float(an["x"])], [float(an["y"])], "o", color=ACC2, ms=9)
        except Exception:
            pass
    a.set_xlabel(pul(g.get("x_label", "")), color=SOFT, fontsize=14)
    a.set_ylabel(pul(g.get("y_label", "")), color=SOFT, fontsize=14)
    if any(se.get("nome") for se in serie):
        leg = a.legend(fontsize=13, facecolor=BG, edgecolor=SOFT, labelcolor=TXT, loc="best")
        leg.get_frame().set_alpha(0.9)
    nota = spezza(s.get("nota", ""), 22, 310)
    testo(ax, 910, y0 + 20, nota[:14], 22, TXT)


def d_formula(fig, ax, s, y0):
    f = s["formula"]
    ax.add_patch(FancyBboxPatch((60, y0), 1160, 170, boxstyle="round,pad=0,rounding_size=18", color=CARD))
    ft = f if "$" in f else "$" + f + "$"
    fs = 46
    t = ax.text(W / 2, y0 + 85, ft, fontsize=fs, color=ACC, ha="center", va="center")
    try:
        fig.canvas.draw()
        while t.get_window_extent().width > 1080 and fs > 22:
            fs -= 4
            t.set_fontsize(fs)
            fig.canvas.draw()
    except Exception:
        t.remove()
        raw = pul(f.replace("$", "").replace("\\", ""))
        ax.text(W / 2, y0 + 85, raw[:90], fontsize=34, color=ACC, ha="center", va="center")
    sp = s.get("spiegazione") or []
    if sp:
        fs2, bl, h = adatta(sp, 1100, 680 - (y0 + 200), 27, 18, 12)
        y = y0 + 200
        for b in bl:
            ax.add_patch(Circle((76, y + fs2 * PT * 0.62), 9, color=ACC))
            y = testo(ax, 112, y, b, fs2) + 12


def d_schema(ax, s, reveal, y0):
    items = s["riquadri"]
    n = len(items)
    gap = 64
    w = (1160 - gap * (n - 1)) / n
    fs, bl, h = adatta(items, w - 36, 420, 28, 16, 0)
    hbox = max(alt(b, fs) for b in bl) + 48
    ytop = y0 + (660 - y0 - hbox) / 2 - 10
    for i, b in enumerate(bl):
        x = 60 + i * (w + gap)
        if i < reveal:
            ax.add_patch(FancyBboxPatch((x, ytop), w, hbox, boxstyle="round,pad=0,rounding_size=16",
                                        facecolor=CARD, edgecolor=ACC if i < reveal - 1 else ACC2, linewidth=3))
            testo(ax, x + 18, ytop + 24, b, fs, TXT, False)
            if i > 0:
                ax.add_patch(FancyArrowPatch((x - gap + 10, ytop + hbox / 2), (x - 8, ytop + hbox / 2),
                                             arrowstyle="-|>", mutation_scale=28, color=ACC, lw=3))


def d_confronto(ax, s, y0):
    for k, lato in enumerate(("sinistra", "destra")):
        d = s[lato]
        x = 60 + k * 600
        col = ACC if k == 0 else ACC2
        fs, bl, h = adatta(d["punti"] or [" "], 500, 460 - 70, 25, 17, 14)
        ax.add_patch(FancyBboxPatch((x, y0), 560, 460, boxstyle="round,pad=0,rounding_size=16", color=CARD))
        ax.add_patch(Rectangle((x, y0 + 60), 560, 4, color=col))
        testo(ax, x + 24, y0 + 14, spezza(d["titolo"], 27, 510, True)[:1], 27, col, True)
        y = y0 + 84
        for b in bl:
            ax.add_patch(Circle((x + 32, y + fs * PT * 0.62), 7, color=col))
            y = testo(ax, x + 54, y, b, fs) + 14


def render(slide, reveal, percorso, progresso=0.0, nome_lezione=""):
    s = slide
    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    sfondo(ax, progresso, nome_lezione)
    tipo = s["tipo"]
    try:
        if tipo == "titolo":
            d_titolo(ax, s)
        else:
            y0 = titolo_slide(ax, s["titolo"])
            if tipo in ("punti", "riepilogo"):
                d_lista(ax, s, reveal if reveal is not None else len(s["punti"]), y0, "punti",
                        "✓" if tipo == "riepilogo" else None)
            elif tipo == "definizione":
                d_definizione(ax, s, y0)
            elif tipo == "esempio":
                d_esempio(ax, s, reveal if reveal is not None else len(s["passi"]), y0)
            elif tipo == "tabella":
                d_tabella(ax, s, y0)
            elif tipo == "grafico":
                d_grafico(fig, ax, s, y0)
            elif tipo == "formula":
                d_formula(fig, ax, s, y0)
            elif tipo == "schema":
                d_schema(ax, s, reveal if reveal is not None else len(s["riquadri"]), y0)
            elif tipo == "confronto":
                d_confronto(ax, s, y0)
    except Exception as e:
        print("Slide di tipo " + tipo + " non disegnabile (" + type(e).__name__ + "): uso la versione semplice",
              flush=True)
        for a in list(fig.axes)[1:]:
            a.remove()
        ax.clear()
        ax.set_xlim(0, W)
        ax.set_ylim(H, 0)
        ax.axis("off")
        sfondo(ax, progresso, nome_lezione)
        y0 = titolo_slide(ax, s["titolo"] or "...")
        pezzi = []
        for k in ("scenario", "definizione", "nota", "risultato"):
            if s.get(k):
                pezzi.append(s[k])
        pezzi += s.get("passi", []) + s.get("punti", []) + s.get("riquadri", []) + s.get("spiegazione", [])
        if not pezzi and isinstance(s["narrazione"], str):
            pezzi = [s["narrazione"][:240]]
        d_lista(ax, {"punti": pezzi[:6] or ["..."]}, 99, y0, "punti")
    fig.savefig(percorso, dpi=DPI, facecolor=BG)
    plt.close(fig)
