# MD in documento

Trasforma i file markdown (anche quelli generati da un'intelligenza artificiale) in PDF, Word o PowerPoint su carta intestata. L'applicativo non usa intelligenza artificiale e non fa chiamate esterne: applica regole di impaginazione definite una volta sola.

## Avvio

- Windows: doppio clic su `avvia.bat`
- Mac o Linux: `./avvia.sh`

Alla prima esecuzione installa le librerie (serve Python 3.10 o superiore). Su Mac serve anche Pango per il PDF: `brew install pango`. Poi si apre `http://127.0.0.1:5055`: scegli marchio, modello e formato, incolla il markdown, scarica il file. Raggiungibile solo dal tuo computer.

Da terminale: `python cli.py file.md --marchio mio-marchio --modello documento --formato pdf` (con `--elenco` mostra marchi e modelli).

## Test

```
.venv/bin/pip install pytest
.venv/bin/python -m pytest
```

I test generano PDF, Word e PowerPoint per ogni elemento markdown (titoli, elenchi, tabelle, codice, citazioni, front matter) con tutti i modelli del marchio di esempio.

## Marchi e modelli

Ogni marchio e' una cartella in `templates/`:

```
templates/
  mio-marchio/
    brand.yaml     identita', colori, font, modelli
    logo.png
  cliente-xyz/
    brand.yaml
    logo.png
```

Per aggiungere un marchio: copia una cartella esistente, cambia logo e `brand.yaml`. Compare da solo nel menu, senza toccare il codice.

Dentro `brand.yaml`:

- `marchio`: nome, ragione sociale, indirizzo, P.IVA, C.F., REA (il footer si compone da qui, oppure scrivi `footer:` a mano)
- `colori`, `font`, `logo`, `logo_altezza_mm`
- `modelli`: uno o piu' modelli per marchio. Ogni modello puo' attivare la copertina, cambiare margini e dimensione del testo per PDF e Word, dimensione del testo e livello di titolo per le slide, e perfino sovrascrivere colori e font del marchio.

## Intestazione opzionale nel markdown

In cima al file, tra due righe `---`: `title`, `subtitle`, `doc_type`, `date`, `client`, `author`, `version`, `slide_level`. Senza `title` si usa il primo titolo di livello 1. Senza `date` si usa la data di oggi.

## Regole di conversione

- PDF e Word: titoli, elenchi annidati, tabelle (intestazione ripetuta nelle pagine successive), citazioni, codice, collegamenti, numero di pagina e carta intestata su ogni pagina.
- PowerPoint: copertina automatica; i titoli di secondo livello (o di primo, se non ce ne sono) diventano una slide ciascuno; i titoli di primo livello diventano slide di sezione; contenuti troppo lunghi e tabelle si dividono su piu' slide con "(segue)". Le immagini del markdown non sono incluse nelle slide.
- L'HTML grezzo dentro il markdown non viene eseguito. Nel PDF le immagini sono ammesse solo da indirizzi https o dalla cartella del marchio.

## Da sapere

- Logo, colori e dati in `esempio-cliente` sono fittizi: copia la cartella, poi sostituisci `logo.png` e i valori in `brand.yaml`. Le cartelle dei marchi reali restano fuori da Git: `.gitignore` esclude tutto in `templates/` tranne `esempio-cliente`.
- I font indicati devono essere installati sul computer che apre il file (Word e PowerPoint) o che genera il PDF; altrimenti subentra un font di riserva.
- Sul PDF e' disponibile l'anteprima nel browser; Word e PowerPoint si controllano aprendoli.

## Licenza

MIT, vedi il file `LICENSE`.
