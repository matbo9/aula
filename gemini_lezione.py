import json
import os
import re
import time

import requests

MODELLO = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
CHIAVE = os.environ.get("GEMINI_API_KEY", "")
PAROLE_MIN = 155

FORMATO = """Ogni slide è un oggetto JSON con "tipo", "titolo" (breve, max 70 caratteri) e "narrazione" (ciò che la voce dice).
Tipi disponibili:
1. "punti": {"tipo":"punti","titolo":"...","punti":["voce breve (max 14 parole)", ...3-5 voci],"narrazione":["introduzione","commento voce 1","commento voce 2",...]}
2. "definizione": {"tipo":"definizione","titolo":"...","termine":"...","definizione":"una o due frasi","nota":"facoltativa","narrazione":"testo"}
3. "esempio": esempio svolto passo per passo con numeri o un caso di vita quotidiana: {"tipo":"esempio","titolo":"Esempio: ...","scenario":"la situazione in 1-2 frasi","passi":["Passo 1: ... (con i calcoli)","Passo 2: ...", ...da 2 a 5 passi],"risultato":"conclusione in una frase","narrazione":["introduzione sullo scenario","spiegazione passo 1","spiegazione passo 2",...]}
4. "tabella": {"tipo":"tabella","titolo":"...","colonne":["...","..."],"righe":[["..","..."],...max 6 righe],"evidenzia":[[riga,colonna]] (facoltativo, indici da 0),"nota":"facoltativa","narrazione":"testo"}
5. "grafico": {"tipo":"grafico","titolo":"...","grafico":{"tipo":"linee" oppure "barre","x_label":"...","y_label":"...","serie":[{"nome":"...","x":[numeri],"y":[numeri]}],"categorie":["solo per le barre"],"annotazioni":[{"x":numero,"y":numero,"testo":"breve"}]},"nota":"2-3 frasi che spiegano come leggere il grafico","narrazione":"testo"}
6. "formula": {"tipo":"formula","titolo":"...","formula":"espressione in stile LaTeX semplice, per esempio $\\\\frac{a}{b} = c$","spiegazione":["significato dei simboli", ...],"narrazione":"testo"}
7. "schema": catena o processo (causa -> effetto), 2-5 riquadri: {"tipo":"schema","titolo":"...","riquadri":["...","..."],"narrazione":["introduzione","riquadro 1","riquadro 2",...]}
8. "confronto": {"tipo":"confronto","titolo":"...","sinistra":{"titolo":"...","punti":["..."]},"destra":{"titolo":"...","punti":["..."]},"narrazione":"testo"}
9. "riepilogo": {"tipo":"riepilogo","titolo":"...","punti":["concetto 1",...],"narrazione":["introduzione","concetto 1","concetto 2",...]}
Per i tipi con liste (punti, esempio, schema, riepilogo) la narrazione è una lista: la prima voce introduce la slide, poi una voce per ogni elemento che compare. Per gli altri tipi è un testo unico."""


def chiama(prompt, max_token=16000, temperatura=0.5):
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % MODELLO
    corpo = {"contents": [{"parts": [{"text": prompt}]}],
             "generationConfig": {"temperature": temperatura, "maxOutputTokens": max_token,
                                  "responseMimeType": "application/json"}}
    for t in range(6):
        try:
            r = requests.post(url, headers={"x-goog-api-key": CHIAVE, "Content-Type": "application/json"},
                              json=corpo, timeout=300)
        except Exception as e:
            print("Gemini: errore di rete (%s), riprovo" % type(e).__name__, flush=True)
            time.sleep(15 * (t + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            print("Gemini occupato (%d), riprovo tra %d s" % (r.status_code, 25 * (t + 1)), flush=True)
            time.sleep(25 * (t + 1))
            continue
        if r.status_code != 200:
            raise RuntimeError("Gemini errore %d: %s" % (r.status_code, r.text[:160].replace("\n", " ")))
        try:
            d = r.json()
            return "".join(p.get("text", "") for p in d["candidates"][0]["content"]["parts"])
        except Exception:
            raise RuntimeError("Risposta di Gemini vuota o bloccata")
    raise RuntimeError("Gemini non risponde (troppe richieste o servizio occupato)")


def json_da_testo(t):
    t = t.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    for tentativo in (t, re.sub(r",\s*([}\]])", r"\1", t)):
        try:
            return json.loads(tentativo)
        except Exception:
            pass
    a, b = t.find("{"), t.rfind("}")
    if a >= 0 and b > a:
        s = re.sub(r",\s*([}\]])", r"\1", t[a:b + 1])
        return json.loads(s)
    raise ValueError("JSON non valido")


def chiedi_json(prompt, valido, tentativi=3, max_token=16000, temperatura=0.5):
    ultimo = ""
    for t in range(tentativi):
        time.sleep(6)
        try:
            obj = json_da_testo(chiama(prompt + ultimo, max_token, temperatura))
            if valido(obj):
                return obj
            ultimo = "\n\nATTENZIONE: la risposta precedente non rispettava il formato richiesto. Rispetta esattamente il formato JSON."
        except ValueError:
            ultimo = "\n\nATTENZIONE: la risposta precedente non era un JSON valido e completo. Rispondi solo con JSON valido."
    raise RuntimeError("Gemini non ha restituito un risultato valido")


def piano(corso, argomento, minuti):
    prompt = """Sei un professore universitario italiano che prepara una lezione video per uno studente di livello triennale che deve superare l'esame.

DESCRIZIONE DEL CORSO E DEI LIBRI:
%s

ARGOMENTO DELLA LEZIONE: %s
DURATA TARGET: %d minuti di parlato.

Prepara la scaletta della lezione. Rispetta il livello (nessun approfondimento da magistrale, solo ciò che serve all'esame, spiegato bene e senza complicazioni inutili). Usa i titoli dei capitoli del sommario per restare aderente al programma.
Regole: da 4 a 7 sezioni; la prima apre con un esempio della vita quotidiana che rende curioso (perché l'argomento è importante); le centrali spiegano i concetti in ordine logico, ognuna con almeno un esempio concreto; l'ultima è il riepilogo con i 5 concetti da ricordare. La somma dei minuti delle sezioni deve essere %d.
Rispondi SOLO con JSON: {"titolo_lezione":"...","obiettivi":["2-3 obiettivi di apprendimento, frasi brevi"],"sezioni":[{"titolo":"...","scopo":"cosa si spiega in 1-2 frasi","minuti":numero}]}""" % (
        corso[:12000], argomento, minuti, minuti)
    p = chiedi_json(prompt, lambda o: isinstance(o, dict) and isinstance(o.get("sezioni"), list)
                    and len(o["sezioni"]) >= 2 and all(isinstance(s, dict) and s.get("titolo") for s in o["sezioni"]))
    tot = sum(float(s.get("minuti") or 1) for s in p["sezioni"]) or 1
    for s in p["sezioni"]:
        s["minuti"] = max(1.5, float(s.get("minuti") or 1) * minuti / tot)
    p["obiettivi"] = [str(o) for o in (p.get("obiettivi") or [])][:3]
    return p


def sezione(corso, argomento, p, i, riassunto, livello_note=""):
    sez = p["sezioni"][i]
    n = len(p["sezioni"])
    parole = int(sez["minuti"] * PAROLE_MIN)
    extra = ""
    if i == 0:
        extra = "Questa è la sezione di apertura: parti da una situazione di vita quotidiana che mostra perché l'argomento conta, poi presenta i capitoli e la struttura della lezione in modo schematico (usa una slide 'schema' o 'punti')."
    if i == n - 1:
        extra += " Questa è l'ultima sezione: chiudi con una slide 'riepilogo' di 5 concetti da ricordare e con un breve collegamento alla lezione successiva."
    prompt = """Sei un professore universitario italiano che scrive le slide e il parlato di una lezione video per uno studente di triennale.

CORSO E LIBRI:
%s

LEZIONE: %s (argomento: %s)
Obiettivi: %s
Scaletta: %s

SEZIONE DA SCRIVERE: %d di %d - "%s". Scopo: %s
Durata di questa sezione: %.1f minuti, cioè circa %d parole di narrazione in totale e circa %d slide.
Cosa è già stato detto nelle sezioni precedenti: %s
%s

REGOLE:
- Spiega bene ma senza complicare: solo quello che serve all'esame di una triennale, definizioni chiare, un esempio per ogni concetto importante. Gli esempi devono essere concreti (vita quotidiana, aziende, paesi) e, dove c'è un calcolo, svolti passo per passo con numeri semplici e CONTI ESATTI.
- Usa il formato giusto per ogni contenuto: grafici per relazioni tra grandezze (con coordinate precise), tabelle per confronti numerici, schemi per catene causa-effetto, formule solo se necessarie.
- Narrazione: parlato naturale in italiano, come un professore che spiega a voce; non leggere le tabelle voce per voce ma commentale; non usare simboli, elenchi o markdown nel parlato; ogni voce di narrazione al massimo 110 parole; ricorda i concetti chiave ripetendoli a parole diverse. La narrazione deve capirsi anche senza guardare lo schermo.
- Non inventare dati o citazioni del libro: se usi numeri, sono esempi inventati e scrivilo ("supponiamo che...").
- Nessuna slide con più di 5 voci o con frasi lunghe: il testo sullo schermo è breve, il resto lo dice la voce.

FORMATO DELLE SLIDE:
%s

Rispondi SOLO con JSON: {"slide":[...],"riassunto":"2 frasi su cosa hai spiegato in questa sezione"}""" % (
        corso[:9000], p["titolo_lezione"], argomento, "; ".join(p.get("obiettivi", [])),
        "; ".join("%d) %s" % (k + 1, s["titolo"]) for k, s in enumerate(p["sezioni"])), i + 1, n, sez["titolo"],
        sez.get("scopo", ""), sez["minuti"], parole, max(3, int(parole / 85)), riassunto or "niente, è l'inizio",
        extra, FORMATO)
    return chiedi_json(prompt, lambda o: isinstance(o, dict) and isinstance(o.get("slide"), list)
                       and len(o["slide"]) >= 1 and all(isinstance(s, dict) and s.get("tipo") for s in o["slide"]),
                       max_token=20000)


def verifica(sez_json):
    prompt = """Sei un revisore di economia. Controlla questa parte di lezione (slide in JSON) per uno studente di triennale.
Cerca: errori nei calcoli degli esempi, numeri nella slide diversi da quelli nella narrazione, affermazioni economiche sbagliate, grafici con coordinate incoerenti con il testo, frasi che non hanno senso a voce.
Se è tutto corretto rispondi {"ok":true}.
Se trovi errori rispondi {"ok":false,"note":"cosa hai corretto","slide":[... la lista COMPLETA delle slide corretta, nello stesso formato ...]}.

%s""" % json.dumps(sez_json["slide"], ensure_ascii=False)
    try:
        r = chiedi_json(prompt, lambda o: isinstance(o, dict) and "ok" in o, tentativi=2, max_token=20000,
                        temperatura=0.2)
    except Exception as e:
        print("Verifica saltata: " + str(e)[:80], flush=True)
        return sez_json["slide"], None
    if r.get("ok") is False and isinstance(r.get("slide"), list) and r["slide"]:
        return r["slide"], str(r.get("note", ""))[:200]
    return sez_json["slide"], None


def piano_corso(corso):
    prompt = """Sei un professore universitario italiano che progetta il percorso di studio completo per uno studente di livello triennale che deve superare l'esame.

DESCRIZIONE DEL CORSO E DEI LIBRI:
%s

Crea il percorso di lezioni video che copre TUTTI gli argomenti dei libri indicati, nell'ordine più adatto per imparare (da ciò che serve per capire il resto fino ai temi più avanzati), senza approfondimenti da magistrale. Ogni lezione dura da 12 a 30 minuti: un capitolo grande può diventare due lezioni, capitoli brevi o collegati possono stare insieme. Tra 12 e 30 lezioni in tutto. NON includere la lezione introduttiva e non includere il ripasso finale: li aggiungo io.
Rispondi SOLO con JSON: {"lezioni":[{"titolo":"titolo breve","scopo":"cosa si spiega, 1-2 frasi","capitoli":"capitoli dei libri a cui corrisponde","minuti":numero}]}""" % corso[:12000]
    p = chiedi_json(prompt, lambda o: isinstance(o, dict) and isinstance(o.get("lezioni"), list)
                    and len(o["lezioni"]) >= 3 and all(isinstance(x, dict) and x.get("titolo") for x in o["lezioni"]))
    out = []
    for x in p["lezioni"]:
        try:
            m = float(x.get("minuti") or 20)
        except Exception:
            m = 20
        out.append({"titolo": str(x["titolo"])[:100], "scopo": str(x.get("scopo", ""))[:300],
                    "capitoli": str(x.get("capitoli", ""))[:150], "minuti": int(max(12, min(m, 30)))})
    return out
