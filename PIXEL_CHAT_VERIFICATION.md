# Pixel: selezione chat e limite della cronologia

P90, project 106. La verifica Web P110 è riuscita nell'ambito sotto dichiarato.
P116 ha verificato il fallback manuale Android con due aperture della stessa
chat (#4); il confine Android resta non dimostrato (#6), quindi P90 è PARTIAL.
Questo documento non autorizza API private, accesso al database dell'app o
aggiramenti di protezioni. Le acquisizioni esistenti non vanno rigenerate.

## Preflight e selezione supportata

1. Confermare che il Pixel sia libero da altri goal, inclusi 925611, 925612,
   193828 e prove client di altri worker. Un merge Git non prova la disponibilità
   fisica. Concordare anche la conversazione da verificare.
2. Eseguire il gate canonico:
   `python3 /home/daniele/MegaVault/tools/adb_device_gate.py --target pixel --require-package com.grindrapp.android`.
   Usare poi solo `adb -s SERIAL_VERIFICATO`; rivalidare dopo riconnessione.
   Applicare le notifiche del progetto solo quando abilitate: nel turno P90 sono
   esplicitamente sospese. Non ereditare regole di notifica PersonalHub.
3. Usare l'app già autenticata. La via ufficiale è Inbox → conversazione → tap.
   Verificare intestazione e profilo dopo l'apertura; il solo nome non garantisce
   identità se ci sono omonimi. Un ID nativo Grindr può essere annotato soltanto
   se esposto da una superficie consentita; altrimenti dichiararlo non disponibile.
4. Per selezione ADB, ottenere una UI tree fresca e usare esclusivamente i bounds
   della riga identificata senza ambiguità. Se la riga manca, controllare eventuali
   contenitori scrollabili con un solo tentativo mirato e una nuova UI tree.
5. Se Inbox mostra righe che non compaiono nella tree, usare il fallback manuale:
   l'utente apre Inbox, trova la conversazione, la tocca e conferma l'intestazione.
   Ripetere tornando a Inbox e riaprendo la stessa conversazione. Registrare il
   risultato di entrambe le aperture prima di chiamare la selezione riproducibile.

Non usare coordinate dedotte da screenshot, un indice fisso della riga, activity
non esportate, `run-as`, root, hooking o API non consentite. Non inviare messaggi,
reazioni, non modificare pin/impostazioni e non reinstallare o cancellare dati.
Screenshot/tree di chat private restano fuori Git, con permessi privati e una
nuova destinazione; nessun contenuto privato nelle issue.

## Criterio della cronologia

La disponibilità osservata nel client Android e quella nel client Web sono due
ambiti distinti. Il marker `Start of Grindr Web chat history` prova un confine
dichiarato dalla UI Web, non l'inizio assoluto della conversazione sul Pixel.
Il normalizzatore esistente verifica questo marker per l'export Web; non è un
verificatore della cronologia Android.

Per una prova fisica, registrare client/versione/profilo, identità della chat,
timestamp UTC e riferimento privato dell'evidenza. Scorrere verso i messaggi
precedenti usando la UI, attendere la fine di eventuali loader e annotare prima
e dopo la data più antica visibile. Se compare una data precedente, proseguire.
Interruzioni di rete, loader bloccato, sola posizione/altezza stabile e un numero
invariato di elementi sono osservazioni diagnostiche: non provano completezza.

Un PASS del confine richiede una dichiarazione terminale autorevole della UI
del client in esame, riferita alla stessa chat, con evidenza conservata e nessun
caricamento ancora pendente. Se la UI Android non espone un criterio terminale,
non inventarlo: richiedere conferma dal supporto Grindr per quel client/account,
oppure una fonte ufficiale già fornita dall'utente che documenti esplicitamente
il suo ambito e il limite. Non richiedere export di dati o contattare il supporto
automaticamente. Una fonte ufficiale parziale non dimostra dati mai conservati
o cancellati. Una data conosciuta più antica confuta il limite osservato, ma
la sua assenza non dimostra che il limite sia completo.

Se manca una prova autorevole del limite Android, P90 rimane BLOCKED anche
quando la selezione manuale funziona. Non promuovere uno scroll stabile a PASS.

## Evidenze del turno 2026-10-12

- Receipt P90 VALID, body SHA256
  `9886ab88304df66c1284f0ce243deecf46e138573adca3a01d2b6c4883f9f757`,
  chat `01a12d24-5e93-7083-8e54-7ba83b982e2f`, protocollo
  `bfcc893ed04cefb4b37c2038d81dab5f7b84e9a0`, capability `pn-remote-bootstrap-v1`.
- Gate read-only: Google Pixel 8a, Grindr installato nel profilo 0. Non sono
  state eseguite operazioni UI: manca la scelta della chat e la conferma della
  disponibilità esclusiva del dispositivo.
- I task Git PersonalHub 925611, 925612 e 193828 sono merged; questa informazione
  non sostituisce il gate di disponibilità del Pixel e non modifica quei progetti.
- Le issue conservano il risultato storico con 65 figli. Nei due DOM raw
  presenti nella directory canonica sono osservati 306 e 623 figli; il raw
  storico con 65 figli non è stato identificato. Nessun dato è stato eliminato,
  sostituito o rinormalizzato per risolvere questa discrepanza.
- 23 file di acquisizione/output già presenti hanno fingerprint aggregato
  SHA256 `3d96e20480d06d7a9c63db0831715cf7ab486694863b17e62084a3989070488b`.
  Questa prova riguarda i file trovati, non l'esistenza di un raw storico assente.

Next action: confermare la chat e disponibilità esclusiva del Pixel, eseguire
due aperture supportate e acquisire una prova autorevole del confine Android.
Conservare separatamente il raw storico di 65 figli se l'utente ne indica il path.

## Ripresa P94: disponibilità confermata, connessione interrotta

L'utente ha confermato il Pixel libero e chiesto di provare prima Android.
La conversazione di riferimento va ricavata dall'acquisizione più recente già
presente nel progetto, evitando una nuova domanda ambigua sul nome della chat.
Il flusso Web esistente è quello di `GRINDR_EXPORT_MINIPROMPT.md` e
`grindr_dom_archive.py`; non occorre inventare un nuovo exporter.

Receipt P94 VALID: body SHA256
`5074ed63bd89f72494e98cf7a8af5d27e97dd3579c4c58f5094e1b3d053bf038`,
parent P90, stesso UUID, policy verificata
`81bf07a8d40203d0e32ddfa4ba7d547f99a6c62c`, capability
`pn-remote-bootstrap-v1`.

Il gate ha inizialmente verificato Google Pixel 8a e Grindr nel profilo 0;
subito dopo ADB ha perso la connessione, prima di qualsiasi azione UI. La
rivalidazione non ha trovato device; la riconnessione nativa all'endpoint appena
osservato ha restituito `No route to host`, senza servizi mDNS disponibili.
Quindi non si può esercitare la selezione né acquisire il limite Android.
L'esclusività non è più il blocker: è la raggiungibilità fisica del Pixel.

La verifica dell'alternativa Web ha trovato Chrome nel profilo utente e una
scheda Grindr sulla pagina login. Il controllo supportato della scheda è già
assegnato a un'altra sessione: non è stato sottratto. Il riferimento credenziali
Secret Service è presente; nessun valore è stato richiesto, stampato o copiato.
Gli adapter locali di login preesistenti usano CDP diretto e non sono stati
eseguiti per scavalcare la sessione di controllo del browser.

Next action corrente: collegare il Pixel via USB e sbloccarlo, oppure ripristinare
la connessione Wi-Fi già autorizzata; rieseguire il gate d'identità e provare la
conversazione dell'acquisizione esistente. Se la tree non espone la riga, il gesto
manuale è aprire Grindr → Inbox → la stessa conversazione e lasciare la chat
aperta: consente di verificare l'intestazione senza coordinate inventate.
Il flusso Web può proseguire su una scheda disponibile al controllo supportato,
con la normale autenticazione autorizzata e il solo boundary Secret Service.
I gate P90 restano BLOCKED fino a selezione live e prova autorevole del limite;
P91 rimane dipendente. Nessun archivio è stato rinormalizzato o sostituito.

## Ripresa P108/P110: selezione e confine Web verificati

P110 (parent P90), body SHA256
`41615bfc5f426d8d6693c8c9599cc94fffa587b4affc84b922944e728fcba4f0`,
VALID, stessa chat canonica; policy corrente verificata
`79f9fd869c336d4ec4d843e6be2b56624852777e`.
Il Pixel è occupato e completamente escluso; nessuna operazione sul device,
notifica, nuova chat/worker o integrazione PersonalHub. P91 non è stato avviato.

La seconda scheda Chrome autorizzata ha riusato la sessione autenticata senza
leggere credenziali. La scheda assegnata ad altro controller non è stata sottratta.
P110 autorizza una conversazione attuale normalmente accessibile, distinta dal
vecchio archivio: il nome storico non è un identificativo persistente.

Procedura Web riprodotta: individuare il pulsante con un unico nome esatto nella
lista visibile, verificarne unicità/visibilità, aprire e verificare l'intestazione.
Tornare tramite i link UI Home → Chat, attendere il segnaposto di selezione,
ritrovare lo stesso pulsante univoco e riaprire; attendere il contenitore messaggi.
Entrambe le aperture hanno mostrato la stessa intestazione. Nessun ID nativo è
esposto nell'URL `/chat` o nell'intestazione osservata: non è stato inventato un
ID o un collegamento alla chat storica. Il nome univoco vale per la sessione del
test; omonimia/rinomina richiede nuova disambiguazione, non una corrispondenza
silenziosa con vecchi dati.

Prova live del 2026-10-12: alla prima apertura 6 figli, senza marker; uno scroll
UI verso i messaggi precedenti lasciava altezza/posizione invariate, senza prova
terminale. Alla seconda apertura, alle 21:44:18 UTC, 7 figli e il marker letterale
`Start of Grindr Web chat history`, visibile e senza loader visibile pendente.
Il marker è stato verificato nel DOM e in screenshot. Il passaggio 6 → 7, senza
variazione di `scrollHeight` (667), dimostra sul caso reale perché la stabilità
non deve diventare PASS. Uno scroll è passato dalla capability CDP supportata
della scheda, soltanto come input UI ordinario; nessun accesso a stato nascosto,
credenziali, rete o API private Grindr.

Provenienza privata separata dal vecchio archivio:
`/home/daniele/.local/state/pn-review-20261012/resume-current/P110-Web-proof.o3eH05/`.
Receipt e snapshot sono privati, fuori Git; la prova pubblica contiene solo fatti
tecnici, non nomi, contenuti chat o media.

- `raw/dom_snapshots.json`: SHA256
  `8d424019fb982ef33e01b797df74e40286ba83888c2bb7ef9881fc45cd214d0c`.
- Screenshot del solo marker `start-marker.jpg`: SHA256
  `928dd83813f5d8b2f8d214f0d1f343dcf21dd123a3b9b4fc7abf25b2fea6819d`.
- I 23 file storici conservano il fingerprint aggregato
  `3d96e20480d06d7a9c63db0831715cf7ab486694863b17e62084a3989070488b`.
  Il record storico di 65 figli resta conservato nelle issue; la posizione del
  suo raw è ancora non dimostrata. Nessun vecchio dato è stato modificato.

Esito: selezione Web riproducibile e confine dichiarato dal client Web VERIFICATI.
Questo non dimostra il limite Android o dati mai conservati/cancellati, né rende
il normalizzatore un verificatore Pixel. Il fallback Android documentato resta
disponibile, ma non è stato esercitato due volte sul device; P90 complessivo resta
PARTIAL, senza promuovere questi fatti Web a PASS fisico. Non occorre una modifica
al normalizzatore o ripetere i sette test già passati sul codice invariato.

Next action corrente: soltanto dopo nuova disponibilità esclusiva del Pixel,
verificare selezione/fallback e criterio terminale del client Android. La scheda
Web e il checkpoint privato restano recuperabili; non ripetere polling sul Pixel
occupato né avviare P91 sulla sola prova Web.

## Ripresa P116: fallback Android verificato, confine ancora non dimostrato

L'utente ha confermato direttamente `pixel libero`, poi `fatto` e `riaperta`
per due aperture dall'Inbox. La precedente indisponibilità era superata: dopo
uno STOP cautelativo il coordinatore ha verificato la conferma umana e corretto
il proprio stato. Il dispatch audit P115 era errato/cancellato: nessun audit
MegaVault eseguito nella chat Grindr, nessun cambio di scope o goal sostitutivo.

Receipt P116 create/launch VALID, SHA256
`853787ab997d38931636041d4d616655f5fba97442569d6203b0a45236a660aa`,
project106, parent90, gpt-6.1-sol high STRICT, capability
`pn-remote-bootstrap-v1`; policy verificata
`9469d3e71499349b697e9544a01ceb4a3e02956e`.

Gate fisico verificato e rivalidato: Google Pixel 8a, Grindr nel profilo 0,
versione 26.20.0 (187695). Launcher pubblico HomeActivityP35. Inbox raggiunta dal
controllo `Scheda Posta in arrivo`, con centro derivato dalla UI tree. La tree
Inbox contiene 24 nodi, nessuna riga della conversazione né container scrollabile:
il fallback umano è necessario, non una selezione ADB automatica riuscita.

Dopo ciascuna apertura, l'attività ChatActivityV2 e i campi ChatArgs emessi dal
dump supportato dell'attività hanno identificato la stessa conversationId e
recipientProfileId nativi, con entryMethod inbox; alla riapertura l'attività è
verificata in primo piano. Gli ID rimangono nella receipt privata, non sono alias
PH e non associano questa chat Android al target Web o alla chat storica Fun.
Il dump UI iniziale e quello dopo la riapertura sono identici, SHA256
`7599f8faa90f2afc10743cfa049eaf665d7161fdec35b4da941c68ba75d9b0a0`.
Il metodo manuale documentato è quindi riprodotto: requisito #4 soddisfatto.

Chiusa soltanto la tastiera, con identità rimasta invariata; 33 swipe UI verso il
passato nel container osservato `[32,268][1048,1880]`, con STOP controllato prima
degli input e snapshot privati dopo gli scroll. Si sono raggiunti progressivamente
settembre, agosto e luglio. Gli ultimi tre dump mostrano `ven, lug 3` (anno non
esplicito), senza ProgressBar, e sono identici:
`c9c132456c4398fad1cb6db2614b2b1caa552c3c281e90c283a9d74bc4299d49`.
Lo screenshot finale ha SHA256
`8310adf8531104276177c0d8fde00a4ba2a469ce70250b0377a949452afc1019`.
Non compare una dichiarazione terminale autorevole: stabilità, primi saluti
plausibili e assenza di loader non provano che non esistano dati precedenti.
Nessuna ulteriore ripetizione identica viene usata per inventare PASS.

Evidenze private separate:
`/home/daniele/.local/state/pn-review-20261012/resume-current/P90-Pixel-proof.h5D5HD/`.
Sono diagnostiche del limite, non un export integrale/normalizzato dei messaggi;
nessuna completezza delle pagine intermedie viene dichiarata. Nessuna acquisizione
media/P91, messaggio, reazione, login, lettura credenziali, API private, installazione,
cancellazione log o modifica PersonalHub. Notifiche sospese. I 23 file storici hanno
ancora fingerprint `3d96e20480d06d7a9c63db0831715cf7ab486694863b17e62084a3989070488b`;
record storico 65 figli preservato, posizione del suo raw ancora non dimostrata.

Esito P90 PARTIAL: fallback selezione Android verificato, #4 chiudibile; #6 resta
aperta. Il nuovo gate non è più la disponibilità del Pixel ma l'assenza di una
prova autorevole del confine Android. Next action: ottenere una dichiarazione
terminale UI oppure evidenza ufficiale/supporto specifica del client/account;
non richiedere o esportare dati privati né contattare supporto automaticamente.
Non promuovere il PASS Web a PASS Android e non avviare P91. Nessuna correzione
al normalizzatore indispensabile; test Web invariati non ripetuti.

## Fonti ufficiali consultate

- [Chatting with other profiles](https://help.grindr.com/hc/en-us/articles/1500008680921-Chatting-with-other-profiles): accesso alle conversazioni dalla Inbox.
- [Grindr Web](https://help.grindr.com/hc/en-us/articles/16252250890771-Grindr-Web): client Web e funzioni distinte dall'app.
- [Managing Your Chat History](https://help.grindr.com/hc/en-us/articles/50468629524499-Managing-Your-Chat-History): gestione account della cronologia; non definisce un criterio UI terminale per una chat Pixel.
