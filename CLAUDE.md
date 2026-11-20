# MD in documento: stato del progetto

Applicativo locale, senza intelligenza artificiale, che converte file markdown in PDF e Word (.docx) su carta intestata. Le regole di impaginazione si definiscono una volta per marchio e modello.

## Regole dell'utente
- Rispondere e scrivere in italiano, linguaggio diretto, senza inglesismi inutili.
- Niente emoticon. Niente trattini lunghi (em dash, en dash) in italiano: usare virgola, parentesi o due punti.
- Non inventare nulla: ogni dato deve essere verificabile, ogni affermazione con fonte.
- Documenti in markdown, non PDF o Word, quando si tratta di documentazione.
- Dire le cose come stanno, anche se scomode. Meno teoria, piu' sostanza.

## Architettura
- `app.py`: interfaccia web locale (Flask, solo 127.0.0.1:5055). Rotte: `/`, `/api/brands`, `/api/convert`, `/api/brand...` (gestione marchi).
- `cli.py`: stesso motore da terminale.
- `engine/config.py`: legge `templates/<marchio>/brand.yaml`, unisce marchio e modello, compone il footer dai dati societari.
- `engine/parser.py`: markdown-it-py in blocchi (usato da DOCX). Front matter YAML opzionale.
- `engine/pdf.py`: markdown in HTML con CSS `@page`, poi WeasyPrint. Copertina e indice opzionali. Fetcher delle risorse limitato a data:, https: e cartella del marchio.
- `engine/docx_.py`: python-docx, con riordino degli elementi XML secondo lo schema OOXML (Word e' rigido).
- `templates/<marchio>/brand.yaml` + `logo.png`: ogni marchio ha piu' modelli. Si gestiscono dalla scheda "Marchi e modelli" dell'app o copiando una cartella.
- `engine/gestione.py`: lettura, validazione e scrittura dei marchi (crea, salva, logo, elimina in `templates/_eliminati/`). Rotte `/api/brand...` in `app.py`: accettano solo richieste dalla stessa pagina (host locale, Origin, intestazione `X-MD2DOC`).
- `esempi/prova.md`: markdown di prova con tutti gli elementi.

## Stato
Funzionante e provato su due marchi (esempio-cliente e uno privato) e due formati (PDF, Word). PowerPoint rimosso il 20/11 su decisione dell'utente (configurazione troppo elaborata): il codice resta nella cronologia Git (engine/pptx_.py). Verifica visiva fatta convertendo con LibreOffice, NON con Word reale.

I marchi con dati societari reali restano fuori dal repository pubblico: `.gitignore` esclude tutto in `templates/` tranne `esempio-cliente`. Per un marchio privato si copia `templates/esempio-cliente` in una nuova cartella locale.

## Da fare, in ordine
1. Chiedere all'utente logo, colori e font ufficiali del marchio privato e configurarlo in locale (resta fuori da Git).
2. Aprire gli output in Word reale e correggere eventuali differenze rispetto a LibreOffice.
3. Provare con 3 o 4 markdown reali generati da IA (relazioni, proposte, offerte) e sistemare i casi che si rompono.
4. Test automatici minimi (pytest): un markdown per ogni elemento, controllo che i tre formati si generino.
5. Opzionale: numeri di pagina nell'indice del PDF, eseguibile con doppio clic (PyInstaller). Fatto: schermata per creare marchi e modelli, icona e app per Mac.
6. Pubblicazione su GitHub (vedi sotto).

## Pubblicazione su GitHub pubblico
- Prima di ogni push: `git grep -nE "[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]|P\.?IVA|@"` per assicurarsi che non ci siano codici fiscali, partite IVA o email reali. Nel repo devono restare solo dati fittizi.
- Chiedere all'utente nome del repository e licenza prima di creare il repository. Non scegliere la licenza al suo posto.
- Creare con `gh repo create <nome> --public --source . --push` (richiede `gh auth login` valido).
