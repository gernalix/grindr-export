# Pixel: selezione chat e limite della cronologia

P90, project 106. Le issue #4 e #6 restano aperte fino alla verifica fisica.
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

## Fonti ufficiali consultate

- [Chatting with other profiles](https://help.grindr.com/hc/en-us/articles/1500008680921-Chatting-with-other-profiles): accesso alle conversazioni dalla Inbox.
- [Grindr Web](https://help.grindr.com/hc/en-us/articles/16252250890771-Grindr-Web): client Web e funzioni distinte dall'app.
- [Managing Your Chat History](https://help.grindr.com/hc/en-us/articles/50468629524499-Managing-Your-Chat-History): gestione account della cronologia; non definisce un criterio UI terminale per una chat Pixel.
