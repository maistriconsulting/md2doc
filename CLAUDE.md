# MD in documento: stato del progetto

Applicativo locale, senza intelligenza artificiale, che converte file markdown in PDF, Word (.docx) e PowerPoint (.pptx) su carta intestata. Le regole di impaginazione si definiscono una volta per marchio e modello.

## Regole dell'utente
- Rispondere e scrivere in italiano, linguaggio diretto, senza inglesismi inutili.
- Niente emoticon. Niente trattini lunghi (em dash, en dash) in italiano: usare virgola, parentesi o due punti.
- Non inventare nulla: ogni dato deve essere verificabile, ogni affermazione con fonte.
- Documenti in markdown, non PDF o Word, quando si tratta di documentazione.
- Dire le cose come stanno, anche se scomode. Meno teoria, piu' sostanza.

## Architettura
- `app.py`: interfaccia web locale (Flask, solo 127.0.0.1:5055). Rotte: `/`, `/api/brands`, `/api/convert`.
- `cli.py`: stesso motore da terminale.
- `engine/config.py`: legge `templates/<marchio>/brand.yaml`, unisce marchio e modello, compone il footer dai dati societari.
- `engine/parser.py`: markdown-it-py in blocchi (usato da DOCX e PPTX). Front matter YAML opzionale.
- `engine/pdf.py`: markdown in HTML con CSS `@page`, poi WeasyPrint. Copertina e indice opzionali. Fetcher delle risorse limitato a data:, https: e cartella del marchio.
- `engine/docx_.py`: python-docx, con riordino degli elementi XML secondo lo schema OOXML (Word e' rigido).
- `engine/pptx_.py`: python-pptx, slide 16:9 disegnate da zero. H2 = una slide (H1 se non ci sono H2), H1 = slide di sezione, divisione automatica di elenchi e tabelle lunghi.
- `templates/<marchio>/brand.yaml` + `logo.png`: ogni marchio ha piu' modelli. Aggiungere un marchio = copiare una cartella.
- `esempi/prova.md`: markdown di prova con tutti gli elementi.

## Stato
Funzionante e provato su due marchi (esempio-cliente e uno privato) e tre formati. Verifica visiva fatta convertendo con LibreOffice, NON con Word e PowerPoint reali.

I marchi con dati societari reali restano fuori dal repository pubblico: `.gitignore` esclude tutto in `templates/` tranne `esempio-cliente`. Per un marchio privato si copia `templates/esempio-cliente` in una nuova cartella locale.

## Da fare, in ordine
1. Chiedere all'utente logo, colori e font ufficiali del marchio privato e configurarlo in locale (resta fuori da Git).
2. Aprire gli output in Word e PowerPoint reali e correggere eventuali differenze rispetto a LibreOffice.
3. Provare con 3 o 4 markdown reali generati da IA (relazioni, proposte, offerte) e sistemare i casi che si rompono.
4. Test automatici minimi (pytest): un markdown per ogni elemento, controllo che i tre formati si generino.
5. Opzionale: immagini nelle slide, numeri di pagina nell'indice del PDF, schermata per creare un marchio senza modificare il YAML, eseguibile con doppio clic (PyInstaller).
6. Pubblicazione su GitHub (vedi sotto).

## Pubblicazione su GitHub pubblico
- Prima di ogni push: `git grep -nE "[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]|P\.?IVA|@"` per assicurarsi che non ci siano codici fiscali, partite IVA o email reali. Nel repo devono restare solo dati fittizi.
- Chiedere all'utente nome del repository e licenza prima di creare il repository. Non scegliere la licenza al suo posto.
- Creare con `gh repo create <nome> --public --source . --push` (richiede `gh auth login` valido).
