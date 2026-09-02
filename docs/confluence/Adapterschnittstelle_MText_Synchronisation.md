# Technische Schnittstelle des M/Text-Adapters

Diese Seite ist die Implementierungsgrundlage für den HTTP-Client in
`mtext_actions` und den M/Text-Adapter. Sie legt das HTTP-Protokoll, die
Validierung, das Zustandsmodell, die Verarbeitung und das Verhalten bei
Wiederholungen und Fehlern fest.

Die Kapitel bis einschließlich [Client-Ablauf](#client-ablauf) sind für beide
Seiten verbindlich. Die Java-Beispiele zeigen eine dazu passende
Serverimplementierung. Andere interne Strukturen sind zulässig, wenn sie das
beschriebene Verhalten einhalten.

Das Format der Projektinformationen sowie die Bedeutung von `FULL`, `DELTA`,
F-Archiv und D-Archiv sind im
[Zielbild](Zielbild_GitHub_Actions_Git.md#archive-projektinformationen-und-lieferarten)
definiert. Diese Schnittstelle übernimmt die Felder, die der Adapter für Prüfung und
Zuordnung benötigt. Er beschreibt keine Entscheidung darüber, wann ein FULL
oder DELTA erstellt wird.

## Verantwortungsgrenze

Der Client übernimmt folgende Aufgaben:

- alle Archive eines Auftrags vor dem POST erzeugen
- ihre Projektinformationen im POST vollständig ankündigen
- die angekündigten Archivbytes mit je einem PUT übertragen
- den Status bis zu einem Endstatus abfragen
- das Ergebnis lesen und den beendeten Auftrag löschen

Der Adapter übernimmt folgende Aufgaben:

- Idempotency-Key, Auftragsdaten und Uploads einander zuordnen
- Archive streamend empfangen und vor der Verarbeitung prüfen
- die Verarbeitung eines vollständigen Auftrags einmal starten
- Änderungen am Projektbestand und den M/Text-Aufruf je Mandantenkürzel
  serialisieren
- Status, Ergebnis und Fehlermeldung bis zum DELETE bereitstellen

Der Client sendet keinen anwendungsspezifischen Authentifizierungsheader. Der
netzseitige Zugriffsschutz des HTTP-Endpunkts ist noch mit der LTOMA-Umgebung
festzulegen und nicht Bestandteil dieser Anwendungsschnittstelle.

## Basis-URL

```text
http://<Umgebungskennung>.ltoma.intern/vMtextAdapter/sync
```

`mtext_actions` bestimmt die Umgebungskennung aus der M/Text-Umgebung und der
ETAPS-Linie. Eine Adapterinstanz verarbeitet eine M/Text-Umgebung. Der Pfad
`serverSync/` und die M/Text-Verbindung gehören deshalb zur Konfiguration
dieser Instanz und werden nicht im Request übergeben.

## HTTP-Konventionen

- Metadatenrequests verwenden `application/json` mit UTF-8.
- Erfolgreiche Antworten mit Inhalt und Fehlerantworten verwenden
  `application/json` mit UTF-8.
- Archivuploads verwenden `application/gzip` und enthalten die unveränderten
  Bytes der `.tgz`-Datei.
- Der Client sendet beim Upload `Content-Length` und überträgt die Datei als
  Datenstrom.
- `auftrag_id` und `name` werden als jeweils ein URL-Pfadsegment kodiert.
- Der Client verwendet 15 Sekunden als Socket-Timeout für einzelne
  blockierende Netzwerkoperationen. Dies ist kein Gesamtzeitlimit für einen
  HTTP-Request. Ein Archivupload darf länger dauern, solange die Übertragung
  fortschreitet.
- Die Verarbeitung des Auftrags einschließlich der Archivinhaltsprüfung läuft
  außerhalb der HTTP-Requests und unterliegt diesem Socket-Timeout nicht.
- Eine Adapterantwort darf höchstens 1 MiB groß sein. Der Client behandelt
  größere oder unvollständige Antworten als ungültig.
- Die Schnittstelle legt keine feste Obergrenze für Metadaten oder Archivuploads
  fest. Der Server darf Archive deshalb nicht vollständig im Arbeitsspeicher
  puffern. Betriebliche HTTP-Limits müssen die erzeugten Aufträge zulassen.
- Der Client akzeptiert bei erfolgreicher Kommunikation jeden 2xx-Status,
  prüft anschließend aber den beschriebenen JSON-Inhalt.
- Der Server ignoriert unbekannte JSON-Felder in Requests. Der Client ignoriert
  unbekannte JSON-Felder in Antworten. Dadurch können optionale Felder ergänzt
  werden, ohne bestehende Implementierungen zu brechen.

## Ressourcen

| Methode | Pfad | Zweck |
|---|---|---|
| `POST` | `/vMtextAdapter/sync` | Auftrag anlegen oder anhand des Idempotency-Keys wiederaufnehmen |
| `PUT` | `/vMtextAdapter/sync/{auftrag_id}/archive/{name}` | angekündigtes Archiv hochladen |
| `GET` | `/vMtextAdapter/sync/{auftrag_id}` | Status und gegebenenfalls Ergebnis lesen |
| `DELETE` | `/vMtextAdapter/sync/{auftrag_id}` | beendeten Auftrag löschen |

Die nachfolgenden Statuscodes legen das erwartete Serververhalten genauer
fest.

### HTTP-Status

| Methode | Bei erfolgreichem Request | Bei einem Fehler |
|---|---|---|
| `POST` | `HTTP 201 (Created)` für einen neuen Auftrag, `HTTP 200 (OK)` für einen bekannten Idempotency-Key | `HTTP 400 (Bad Request)`, `HTTP 409 (Conflict)`, `HTTP 415 (Unsupported Media Type)`, `HTTP 500 (Internal Server Error)` |
| `PUT` | `HTTP 202 (Accepted)` | `HTTP 400 (Bad Request)`, `HTTP 404 (Not Found)`, `HTTP 415 (Unsupported Media Type)`, `HTTP 500 (Internal Server Error)` |
| `GET` | `HTTP 200 (OK)` | `HTTP 404 (Not Found)`, `HTTP 500 (Internal Server Error)` |
| `DELETE` | `HTTP 200 (OK)` | `HTTP 404 (Not Found)`, `HTTP 409 (Conflict)`, `HTTP 500 (Internal Server Error)` |

Die vollständige JSON-Antwort steht beim jeweiligen Request. POST, PUT und GET
liefern `auftrag_id` und `status`. Abhängig vom Status kommen `ergebnis` oder
`meldung` hinzu. DELETE liefert `{"ok": true}`.

## Auftrag anlegen

```http
POST /vMtextAdapter/sync
Idempotency-Key: github-run-123456-en01
Content-Type: application/json
```

```json
{
  "kuerzel": "FI",
  "auftragsart": "FULL",
  "archive": [
    {
      "name": "FIBASISF.tgz",
      "information": {
        "projekt": "LOMS_Basis",
        "scope": {
          "bis": {
            "referenz": "release/261",
            "commit": "0123456789abcdef0123456789abcdef01234567"
          }
        },
        "elemente": [["A", "beispiel.xml"]],
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    }
  ]
}
```

| Feld | Typ | Bedeutung |
|---|---|---|
| `kuerzel` | String | Mandantenkürzel |
| `auftragsart` | String | `FULL` oder `DELTA` |
| `archive` | Array | angekündigte Archive des Auftrags |
| `archive[].name` | String | Schlüssel des Archivs für den späteren PUT |
| `archive[].information` | Objekt | Projektinformationen gemäß Zielbild |

Jeder Archivname ist innerhalb eines Auftrags eindeutig und bezeichnet das
Archiv im zugehörigen PUT. Die Projektinformationen enthalten dessen
SHA-256-Prüfwert.

Alle genannten Felder sind erforderlich. `archive` enthält mindestens einen
Eintrag. Leere Strings sind für `kuerzel`, `archive[].name`, `projekt`,
`referenz`, `commit` und Prüfsummen nicht zulässig.

`archive[].name` ist ein Dateiname ohne `/`, `\` oder Pfadsegmente. Bei `FULL`
endet er mit `F.tgz`, bei `DELTA` mit `D.tgz`. Der Adapter leitet aus dem Namen
keinen internen Ablagepfad ab.

### Projektinformationen

`archive[].information` hat folgende Struktur:

| Feld | Typ | Vorkommen |
|---|---|---|
| `projekt` | String | immer |
| `scope` | Objekt | immer |
| `scope.von` | Objekt | bei `DELTA` |
| `scope.von.referenz` | String | bei `DELTA` |
| `scope.von.commit` | String | bei `DELTA` |
| `scope.bis` | Objekt | immer |
| `scope.bis.referenz` | String | immer |
| `scope.bis.commit` | String | immer |
| `elemente` | Array | immer, darf leer sein |
| `elemente[]` | Array aus Status und Pfad | je enthaltenem Element |
| `sha256` | String | immer, Prüfsumme des angekündigten Archivs |

Jeder Eintrag in `elemente` besteht aus zwei Strings. Der erste String ist
`A`, `M`, `D` oder `T`. Der zweite ist ein projektbezogener Pfad mit `/` als
Trennzeichen. Absolute Pfade und Pfade mit einem Segment `..` sind ungültig.
Ein projektbezogener Pfad kommt innerhalb der Elementliste höchstens einmal
vor.

Für `FULL` gelten folgende technische Zuordnungen:

- `scope.von` fehlt
- der angekündigte Name bezeichnet das F-Archiv

Für `DELTA` gelten folgende technische Zuordnungen:

- `scope.von` ist vorhanden
- der angekündigte Name bezeichnet das D-Archiv

Die Prüfsumme besteht aus 64 hexadezimalen Zeichen. Groß- und Kleinschreibung
werden beim Vergleich nicht unterschieden.

### Validierung des POST

Der Adapter prüft vor dem Anlegen eines Auftrags:

1. Der Header `Idempotency-Key` ist vorhanden und nicht leer.
2. Der Anfrageinhalt ist ein JSON-Objekt und enthält die erforderlichen Felder
   mit den beschriebenen Typen.
3. `auftragsart` ist `FULL` oder `DELTA`.
4. Die Archivnamen und die Werte von `information.projekt` sind innerhalb des
   Auftrags jeweils eindeutig.
5. Alle Projektinformationen passen zur Auftragsart.

Schlägt eine dieser Prüfungen fehl, antwortet der Adapter mit HTTP 400 (Bad
Request) und legt keinen Auftrag an.

Ein neuer Auftrag liefert:

```http
HTTP/1.1 201 Created
Location: /vMtextAdapter/sync/8f73c1
Content-Type: application/json
```

```json
{
  "auftrag_id": "8f73c1",
  "status": "ready"
}
```

Der `Idempotency-Key` identifiziert den Auftrag. Wiederholte POST-Requests mit
demselben Schlüssel liefern dieselbe `auftrag_id` und den aktuellen Status.
Sie erzeugen keinen weiteren Auftrag und setzen den vorhandenen Auftrag nicht
zurück.

Für einen bereits bekannten Schlüssel vergleicht der Adapter den JSON-Inhalt
mit dem beim ersten POST gespeicherten Inhalt. Bei gleichem Inhalt antwortet er
mit HTTP 200 (OK) und dem aktuellen Auftrag. Bei einer Abweichung antwortet er
mit HTTP 409 (Conflict). Der Idempotency-Key wird als undurchsichtiger String
behandelt. Seine Zusammensetzung wird vom Client bestimmt und vom Adapter nicht
ausgewertet.

Der Vergleich erfolgt auf den deserialisierten, in dieser Schnittstelle definierten
Feldern. Die Reihenfolge von JSON-Objektfeldern ist ohne Bedeutung. Die
Reihenfolge der Einträge in `archive` und `elemente` bleibt Bestandteil des
Requests. Unbekannte Felder gehen nicht in den Vergleich ein.

## Archiv hochladen

```http
PUT /vMtextAdapter/sync/8f73c1/archive/FIBASISF.tgz
Content-Type: application/gzip
Content-Length: 12345
```

Der Anfrageinhalt enthält die unveränderten Archivbytes. `name` muss einem beim
POST angekündigten Archiv entsprechen. Der Adapter nimmt den Upload in
`ready` oder `uploading` entgegen und prüft seine SHA-256-Prüfsumme anhand der
zugehörigen Projektinformationen.

Der Adapter verarbeitet den Anfrageinhalt streamend. Er schreibt ihn zuerst in
eine neue temporäre Datei außerhalb von `serverSync/` und berechnet dabei
SHA-256. Erst nach vollständig empfangenem Inhalt und übereinstimmender Prüfsumme
wird die Datei als Upload dieses Archivnamens gespeichert. Der Adapter
antwortet danach ohne die TAR-Inhaltsprüfung abzuwarten. Ein abgebrochener oder
fehlgeschlagener Upload verändert einen bereits erfolgreich gespeicherten
Upload nicht.

Ein PUT in `ready` setzt den Auftrag auf `uploading`. Ein weiterer PUT in
`uploading` darf einen angekündigten Archivnamen erneut übertragen. Der letzte
erfolgreiche Upload dieses Namens ersetzt dabei den vorherigen Upload atomar.

Ein angenommener Upload liefert den aktuellen Auftrag:

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
```

```json
{
  "auftrag_id": "8f73c1",
  "status": "uploading"
}
```

Nach dem letzten erfolgreich anhand seiner Prüfsumme bestätigten Archiv
wechselt der Auftrag ohne weiteren Request zu `processing`. Die Antwort auf
diesen PUT kann daher bereits `processing` enthalten.

Ein wiederholter PUT startet die Verarbeitung nicht erneut. Hat die
Verarbeitung bereits begonnen oder ist der Auftrag beendet, liefert der
Adapter mit HTTP 202 (Accepted) den aktuellen Auftrag und verändert den
gespeicherten Upload nicht. Dadurch kann der Client einen PUT wiederholen,
dessen Antwort verloren ging.

Eine abweichende SHA-256-Prüfsumme setzt den Auftrag während des PUT auf
`failed`. Die Antwort enthält dann `meldung`. Die nicht angenommene temporäre
Datei wird entfernt.

### Archivinhaltsprüfung

Nach dem Wechsel zu `processing` prüft der Adapter alle Archive außerhalb des
Upload-Requests. Vor Abschluss dieser Prüfung erwirbt er den Lock des Mandanten
nicht und verändert `serverSync/` nicht:

1. Die Datei ist ein lesbares gzip-komprimiertes TAR-Archiv.
2. Archivpfade sind relativ und bleiben nach Normalisierung innerhalb des
   vorgesehenen Projektverzeichnisses. Ein Archiv darf weder durch `..`,
   absolute Pfade noch Verknüpfungsziele außerhalb dieses Bereichs schreiben.
3. Das Archiv enthält das unter `information.projekt` genannte
   Projektverzeichnis.
4. Ein FULL enthält den Projektbestand und keine Löschliste.
5. Ein DELTA enthält die neuen und geänderten Projektdateien. Seine Löschliste
   heißt wie das Archiv ohne `.tgz` mit der Endung `.txt` und liegt auf der
   obersten Archivebene.
6. Jeder Pfad der Löschliste ist relativ zum Repositorybestand, beginnt mit
   dem Namen aus `information.projekt` und bleibt nach Normalisierung in diesem
   Projektverzeichnis.
7. Bei FULL entsprechen die Datei- und Verknüpfungseinträge unter dem
   Projektverzeichnis den Pfaden in `elemente`. Ihre Statuswerte sind `A`.
8. Bei DELTA entsprechen die Datei- und Verknüpfungseinträge unter dem
   Projektverzeichnis den Einträgen mit Status `A`, `M` oder `T`. Die
   Löschliste entspricht den Einträgen mit Status `D`.

Für den Vergleich mit `elemente` wird der vorangestellte Projektname aus den
Archiv- und Löschlistenpfaden entfernt. Verzeichniseinträge werden nicht mit
`elemente` verglichen.

Die Prüfung darf zugleich das temporäre Arbeitsverzeichnis für die spätere
Übernahme vorbereiten. Ein inhaltlich ungültiges Archiv setzt den Auftrag auf
`failed`. Die Meldung wird über die Statusabfrage gelesen.

Ein syntaktisch ungültiger PUT, ein unbekannter Archivname oder ein falscher
Content-Type liefert eine HTTP-Fehlerantwort. Eine abweichende Prüfsumme setzt
den bekannten Auftrag noch im PUT auf `failed`. Andere Archivfehler werden
während `processing` erkannt.

## Status und Ergebnis lesen

```http
GET /vMtextAdapter/sync/8f73c1
```

Ein bekannter Auftrag liefert HTTP 200 (OK) und die nachfolgend beschriebene
JSON-Struktur.

Die JSON-Antwort für einen bekannten Auftrag hat folgende Felder:

| Feld | Typ | Vorkommen |
|---|---|---|
| `auftrag_id` | String | immer |
| `status` | String | immer |
| `ergebnis` | beliebiger JSON-Wert | bei einem Endstatus, wenn ein M/Text-Ergebnis vorliegt |
| `meldung` | String | bei `failed` |

`meldung` fehlt bei allen anderen Statuswerten. `ergebnis` fehlt, solange kein
M/Text-Ergebnis vorliegt. Optionale Felder werden bei fehlendem Wert
weggelassen und nicht mit `null` übertragen.

Während der Verarbeitung besteht die vollständige Antwort aus Auftrags-ID und
Status:

```json
{
  "auftrag_id": "8f73c1",
  "status": "processing"
}
```

Beispiel eines erfolgreichen Endstatus:

```json
{
  "auftrag_id": "8f73c1",
  "status": "succeeded",
  "ergebnis": "M/Text-Ausgabe"
}
```

Beispiel eines fehlgeschlagenen Auftrags:

```json
{
  "auftrag_id": "8f73c1",
  "status": "failed",
  "meldung": "M/Text-Synchronisation ist fehlgeschlagen"
}
```

`ergebnis` wird als JSON-Wert übertragen. Sein Inhalt ist kein Bestandteil
dieser Schnittstelle.

## Statusmodell

| Status | Bedeutung | Möglicher Folgestatus |
|---|---|---|
| `ready` | Der Auftrag ist angelegt und hat noch keinen angenommenen Upload | `uploading`, `failed` |
| `uploading` | Archive werden empfangen oder geprüft | `processing`, `failed` |
| `processing` | Der Adapter verarbeitet den vollständigen Auftrag | `succeeded`, `failed` |
| `succeeded` | Die Verarbeitung ist technisch erfolgreich beendet | – |
| `failed` | Die Prüfung oder Verarbeitung ist fehlgeschlagen | – |

`succeeded` und `failed` sind Endstatus. Ein erfolgreicher GET-Request bestätigt
den Abruf des Auftrags. Für den Erfolg der Verarbeitung ist das Feld `status`
maßgeblich.

### Atomare Statuswechsel

Statuswechsel und die Entscheidung zum Start der Verarbeitung erfolgen unter
derselben Synchronisationsgrenze wie die Auftragsdaten:

1. Jeder vollständig empfangene Upload mit passender Prüfsumme wird beim
   Auftrag eingetragen.
2. Der Request, der den letzten fehlenden Upload einträgt, setzt den Status von
   `uploading` auf `processing`.
3. Dieser Statuswechsel liefert intern einmalig die Entscheidung, die
   Verarbeitung zu starten.
4. Parallele oder wiederholte PUT-Requests sehen danach `processing` und dürfen
   keinen weiteren Verarbeitungslauf starten.

Der Status `processing` umfasst Archivinhaltsprüfung, Warten auf den Lock des
Mandanten und die eigentliche Verarbeitung. Ein zusätzlicher
Status für die Warteschlange ist nicht Teil der Schnittstelle.

## Verarbeitung auf dem Adapter

Die Verarbeitung einschließlich der Archivinhaltsprüfung läuft nach Abschluss
des letzten PUT außerhalb des HTTP-Request-Threads. Ein Executor oder ein
gleichwertiger Mechanismus darf den Start verzögern. Die Statusabfrage bleibt
währenddessen erreichbar.

### Mandantenbezogene Synchronisationsgrenze

Pro Mandantenkürzel und konkreter M/Text-Umgebung darf ein Auftrag gleichzeitig
den Projektbestand verändern oder M/Text aufrufen. Die Synchronisationsgrenze
beginnt vor der ersten Änderung an `serverSync/` und endet nach dem M/Text-Aufruf
einschließlich der Cache-Aktualisierung.

Die Projektverzeichnisse verschiedener Mandanten sind disjunkt. Aufträge mit
unterschiedlichen Mandantenkürzeln dürfen daher innerhalb derselben M/Text-Umgebung
parallel verarbeitet werden. Aufträge desselben Mandanten werden auch dann
nacheinander verarbeitet, wenn sie aus unterschiedlichen Branches stammen.

Eine einzelne Adapterinstanz kann dafür je Mandantenkürzel einen Prozess-Lock
verwenden. Verarbeiten mehrere Adapterinstanzen dieselbe M/Text-Umgebung, müssen
Auftragsdaten, Idempotenzzuordnung und die nach Mandantenkürzel unterschiedenen
Locks zwischen ihnen gemeinsam wirken. Alternativ wird pro M/Text-Umgebung eine
Adapterinstanz betrieben.

### Übernahme nach `serverSync/`

`serverSync/` enthält unmittelbar die Projektverzeichnisse und keine
Auftragsverzeichnisse, Archive, Informationsdateien oder Löschlisten.

Für jedes Archiv führt der Adapter unter der mandantenbezogenen
Synchronisationsgrenze folgende Schritte aus:

- Bei `FULL` ersetzt er das durch `information.projekt` bezeichnete
  Projektverzeichnis durch den vollständigen Inhalt des F-Archivs. Dateien des
  vorherigen Projektstands, die nicht im Archiv vorkommen, bleiben nicht
  erhalten.
- Bei `DELTA` kopiert oder ersetzt er die im D-Archiv enthaltenen
  Projektdateien und entfernt anschließend die in der Löschliste genannten
  Pfade. Fehlende zu löschende Dateien gelten nicht als Fehler.
- Andere Projektverzeichnisse werden nicht verändert.
- Archiv und Löschliste dürfen keine Schreib- oder Löschoperation außerhalb
  des bezeichneten Projektverzeichnisses auslösen.

Ein temporäres Arbeitsverzeichnis darf außerhalb von `serverSync/` vorbereitet
werden. Die Übernahme in den Projektbestand bleibt Teil der mandantenbezogenen
Synchronisationsgrenze.

### M/Text-Aufruf

Nach der erfolgreichen Übernahme aller Archive ruft der Adapter M/Text mit
`serverSync/` als Synchronisationsbasis auf. Der Aufruf ist blockierend. Danach
aktualisiert er den M/Text-Ressourcen-Cache.

Enden Übernahme, M/Text-Synchronisation und Cache-Aktualisierung ohne Exception,
speichert der Adapter die M/Text-Rückgabe als `ergebnis` und setzt den Auftrag
auf `succeeded`. Eine Exception setzt den Auftrag auf `failed` und wird als
technische `meldung` gespeichert. Der Mandanten-Lock wird in beiden Fällen
freigegeben.

Vor `succeeded` prüft der Adapter, ob die serialisierte JSON-Antwort
innerhalb der Antwortgrenze von 1 MiB bleibt. Überschreitet das M/Text-Ergebnis
diese Grenze, setzt er den Auftrag ohne `ergebnis` auf `failed` und verwendet
eine entsprechende technische Meldung.

Die Verarbeitung bietet kein Rollback. Bei `failed` kann der Projektbestand
teilweise verändert sein. Wiederholte HTTP-Requests verarbeiten denselben
Auftrag nicht erneut.

## Auftrag löschen

Ein Auftrag kann in `succeeded` oder `failed` gelöscht werden:

```http
DELETE /vMtextAdapter/sync/8f73c1
```

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "ok": true
}
```

Nach erfolgreichem DELETE sind der Auftrag, sein Ergebnis, seine Uploads und
die Zuordnung des Idempotency-Keys nicht mehr über diese API verfügbar. Ein
anschließender GET mit derselben `auftrag_id` liefert HTTP 404 (Not Found). Ein
DELETE in einem anderen Status liefert HTTP 409 (Conflict).

Der Projektbestand unter `serverSync/` wird durch DELETE nicht verändert. Ein
zweiter DELETE derselben Auftrags-ID liefert HTTP 404 (Not Found).

### Lebensdauer und Adapter-Neustart

Auftragsdaten, Idempotenzzuordnung, Uploads und Ergebnis bleiben bis zum
erfolgreichen DELETE oder bis zu einem Adapter-Neustart erhalten. Eine
Persistenz über den Neustart hinaus ist nicht Bestandteil der Schnittstelle.

Beim Start entfernt der Adapter zurückgebliebene temporäre Upload- und
Arbeitsdateien. Zuvor bekannte Auftrags-IDs liefern danach HTTP 404 (Not Found).
Ein POST mit dem bisherigen Idempotency-Key legt einen neuen Auftrag an.
Änderungen, die ein vor dem Neustart abgebrochener Auftrag bereits an
`serverSync/` vorgenommen hat, werden nicht zurückgesetzt.

## Fehlerantworten

Fehler eines Requests liefern ein JSON-Objekt mit `meldung`:

```json
{
  "meldung": "Archiv ist nicht im Auftrag angekündigt"
}
```

| HTTP-Status | Bedeutung |
|---|---|
| `HTTP 400 (Bad Request)` | Request oder Archivzuordnung ist ungültig |
| `HTTP 404 (Not Found)` | Auftrag ist unbekannt |
| `HTTP 409 (Conflict)` | Request ist im aktuellen Auftragsstatus nicht zulässig |
| `HTTP 415 (Unsupported Media Type)` | `Content-Type` passt nicht zum Endpunkt |
| `HTTP 500 (Internal Server Error)` | Request konnte wegen eines unerwarteten Adapterfehlers nicht beantwortet werden |

Fehler während der Prüfung oder Verarbeitung eines bekannten Auftrags werden
über den Status `failed` gemeldet.

Der Adapter gibt in HTTP-Fehlerantworten keine Stacktraces, lokalen Pfade oder
Zugangsdaten aus. `meldung` beschreibt den Fehler so, dass der Client ihn im
Workflow anzeigen kann.

## Client-Ablauf

Der Client verarbeitet einen Auftrag in dieser Reihenfolge:

1. Er erzeugt die Projektartefakte aus einem gemeinsamen Lieferumfang und
   leitet daraus die Auftragsart `FULL` oder `DELTA` ab.
2. Er liest die Projektinformationen und sendet den POST mit einem über
   Wiederholungen des GitHub-Laufs stabilen Idempotency-Key. Der Schlüssel hat
   das Format `github-run-<GITHUB_RUN_ID>-<Umgebungskennung>`.
3. Liefert der POST `ready` oder `uploading`, sendet er alle angekündigten
   Archive. Bereits vorhandene Uploads dürfen dadurch erneut übertragen
   werden.
4. Liefert der POST bereits `processing`, `succeeded` oder `failed`, beginnt
   der Client nicht erneut mit den Uploads.
5. Nach den Uploads fragt er den Auftrag alle fünf Sekunden per GET ab, bis
   `succeeded` oder `failed` erreicht ist.
6. Er merkt sich `ergebnis` oder `meldung` und sendet DELETE.
7. Bei `failed` meldet er nach dem Löschversuch die gespeicherte Meldung als
   `ADAPTER_FAILED`. Bei `succeeded` gibt er Auftrags-ID und ein vorhandenes
   `ergebnis` zurück.

Der GitHub-Job begrenzt Uploads und Statusabfragen gemeinsam auf 30 Minuten.
Ein Abbruch des Clients beendet die serverseitige Verarbeitung nicht. Ein
erneuter Lauf nimmt einen noch vorhandenen Auftrag über den Idempotency-Key
wieder auf.

Der Client behandelt folgende Antworten als Adapterfehler:

- Netzwerkfehler oder eine länger als 15 Sekunden blockierte Socket-Operation
- HTTP-Status außerhalb von 2xx
- ungültiges JSON oder eine JSON-Antwort, die kein Objekt ist
- fehlende oder leere `auftrag_id`
- fehlender, leerer oder unbekannter `status`
- eine vorhandene `meldung`, die kein String ist

Schlägt DELETE bei einem fehlgeschlagenen Auftrag fehl, enthält die
Clientmeldung sowohl die gespeicherte Adaptermeldung als auch den
Löschfehler. Schlägt DELETE bei einem erfolgreichen Auftrag fehl, gilt der
Clientlauf als fehlgeschlagen, weil der Auftrag nicht vollständig aufgeräumt
wurde.

### Referenzlogik des Clients

Das folgende Pseudocode-Beispiel zeigt die für Wiederaufnahme und Aufräumen
entscheidenden Verzweigungen:

```text
artifacts = alle Archive und Projektinformationen materialisieren
auftragsart = gemeinsame Auftragsart bestimmen

auftrag = POST /sync

wenn auftrag.status in [ready, uploading]:
    für jedes Archiv:
        auftrag = PUT /sync/{auftrag_id}/archive/{name}
        wenn auftrag.status in [succeeded, failed]:
            Uploadschleife beenden

solange auftrag.status nicht in [succeeded, failed]:
    auftrag = GET /sync/{auftrag_id}
    wenn auftrag.status in [ready, uploading, processing]:
        fünf Sekunden warten

meldung = auftrag.meldung oder technische Standardmeldung
DELETE /sync/{auftrag_id}

wenn auftrag.status == failed:
    ADAPTER_FAILED mit meldung auslösen

auftrag_id und vorhandenes ergebnis zurückgeben
```

Der Client liest Archivdateien in Blöcken und setzt `Content-Length` aus der
Dateigröße. Der Dateiname wird mit Prozentkodierung als ein Pfadsegment
übertragen. Dasselbe gilt für die vom Adapter gelieferte Auftrags-ID.

## Java-Beispiele zur Umsetzung

Dieses Kapitel zeigt eine mögliche Umsetzung der Schnittstelle mit Spring und
Jackson. Die Klassen- und Methodennamen sind keine Bestandteile der
Schnittstelle. Imports, Konstruktoren und Getter sind nicht
dargestellt.

Die Serverkonfiguration stellt mindestens folgende Werte bereit:

| Wert | Verwendung |
|---|---|
| Context-Path `/vMtextAdapter` | gemeinsames Präfix der HTTP-Endpunkte |
| Upload-Basis | Auftragsverzeichnisse, temporäre Uploads und Arbeitsverzeichnisse außerhalb von `serverSync/` |
| `serverSync` | gemeinsamer Projektbestand dieser M/Text-Umgebung |
| Executor | Verarbeitung außerhalb des HTTP-Request-Threads |
| M/Text-Verbindungsdaten | technischer Benutzer und Zielverbindung des vorhandenen M/Text-Service |

Upload-Basis und `serverSync` werden aus vertrauenswürdiger
Serverkonfiguration gelesen. Requestfelder dürfen diese Basispfade nicht
ersetzen oder erweitern.

| Klasse oder Komponente | Aufgabe |
|---|---|
| `SynchronisationController` | Anlage, Archivupload, Status und Löschen eines Auftrags bereitstellen |
| `SynchronisationsAuftraege` | Auftragsdaten, Uploadprüfung, Status und Ergebnis verwalten |
| `SynchronisationProcessor` | Projektbestand und M/Text-Aufruf unter dem Lock des Mandanten verarbeiten |
| `MtextRessourceSynchronisationService` | M/Text mit `serverSync/` aufrufen und das Ergebnis zurückgeben |

### Auftragsdaten und Antworten

```java
public record AuftragAnlegenRequest(
        String kuerzel,
        Auftragsart auftragsart,
        List<ArchivAnmeldung> archive) {
}

public record ArchivAnmeldung(String name, JsonNode information) {
}

public enum Auftragsart {
    // Ersetzt die Projekte des Auftrags durch die Stände aus ihren F-Archiven.
    FULL,
    // Übernimmt Änderungen und die zugehörigen Löschungen in vorhandene Projekte.
    DELTA
}

public enum SynchronisationsStatus {
    // Der angelegte Auftrag wartet auf seinen ersten Upload.
    READY,
    // Angekündigte Archive werden empfangen und geprüft.
    UPLOADING,
    // Umfasst Warten auf den Mandanten-Lock, Projektübernahme und M/Text-Synchronisation.
    PROCESSING,
    // Übernahme und M/Text-Aufruf sind ohne technischen Fehler beendet.
    SUCCEEDED,
    // Prüfung oder Verarbeitung des Auftrags sind fehlgeschlagen.
    FAILED;

    @JsonValue
    public String jsonWert() {
        return name().toLowerCase(Locale.ROOT);
    }
}

@JsonInclude(JsonInclude.Include.NON_NULL)
public record AuftragAntwort(
        @JsonProperty("auftrag_id") String auftragId,
        SynchronisationsStatus status,
        Object ergebnis,
        String meldung) {
}

public record AnlageErgebnis(boolean neu, AuftragAntwort antwort) {
}
```

Der interne Auftragszustand kann die angekündigten Archive und ihre geprüften
Upload-Dateien gemeinsam halten:

```java
public class SynchronisationsAuftrag {
    private String auftragId;
    private String idempotencyKey;
    private AuftragAnlegenRequest request;
    private Map<String, ArchivAnmeldung> archive;
    private Map<String, Path> uploads;
    private SynchronisationsStatus status = SynchronisationsStatus.READY;
    private Object ergebnis;
    private String meldung;

    // Enthält die Dateien dieses Auftrags außerhalb von serverSync/.
    private Path uploadVerzeichnis;
}
```

### Auftragsverwaltung und Nebenläufigkeit

Eine einfache Implementierung hält zwei Zuordnungen: Auftrags-ID zu Auftrag
und Idempotency-Key zu Auftrags-ID. Beide Zuordnungen und jeder Statuswechsel
werden gemeinsam synchronisiert. Der Vergleich eines wiederholten POST kann
bei unveränderten DTOs über deren strukturelle Gleichheit erfolgen.

```java
public class SynchronisationsAuftraege {
    private final Map<String, SynchronisationsAuftrag> nachId = new HashMap<>();
    private final Map<String, String> nachIdempotencyKey = new HashMap<>();

    public synchronized AnlageErgebnis anlegenOderLesen(
            String idempotencyKey,
            AuftragAnlegenRequest request) {
        String vorhandeneId = nachIdempotencyKey.get(idempotencyKey);
        if (vorhandeneId != null) {
            SynchronisationsAuftrag vorhanden = nachId.get(vorhandeneId);
            if (!vorhanden.getRequest().equals(request)) {
                throw new KonfliktException(
                        "Idempotency-Key gehört zu einem anderen Request");
            }
            return new AnlageErgebnis(false, antwort(vorhanden));
        }

        requestValidieren(idempotencyKey, request);
        String auftragId = UUID.randomUUID().toString();
        SynchronisationsAuftrag auftrag =
                SynchronisationsAuftrag.anlegen(
                        auftragId, idempotencyKey, request, uploadBasis);
        nachId.put(auftragId, auftrag);
        nachIdempotencyKey.put(idempotencyKey, auftragId);
        return new AnlageErgebnis(true, antwort(auftrag));
    }

    public synchronized AuftragAntwort status(String auftragId) {
        return antwort(lesen(auftragId));
    }
}
```

`requestValidieren` setzt die Regeln aus [Validierung des
POST](#validierung-des-post) um. `antwort` erzeugt eine unveränderliche
Momentaufnahme. Die produktive Implementierung darf keine veränderbaren Maps,
Listen oder internen Pfade aus dem Auftrag an Controller oder Processor
weitergeben.

Für einen Upload wird die langsame I/O nicht unter dem globalen Monitor
ausgeführt. Der Ablauf besteht aus drei Teilen:

1. Unter Synchronisation Auftrag, Status und Archivankündigung prüfen.
2. Außerhalb der Synchronisation in eine neue temporäre Datei streamen,
   SHA-256 berechnen und mit der Ankündigung vergleichen.
3. Unter Synchronisation erneut den Auftrag lesen, die anhand ihrer Prüfsumme
   bestätigte Datei für den Archivnamen eintragen und gegebenenfalls atomar
   nach `processing` wechseln.

Ändert sich der Status während Schritt 2 zu `processing`, `succeeded` oder
`failed`, wird die neue temporäre Datei entfernt und der aktuelle Auftrag
zurückgegeben. Die bereits gestartete Verarbeitung wird nicht beeinflusst.

Die Entscheidung aus Schritt 3 kann als Ergebnisobjekt an den Controller
zurückgegeben werden:

```java
public record UploadErgebnis(
        AuftragAntwort antwort,
        boolean verarbeitungStarten) {
}
```

### Controller und Uploadprüfung

Der Controller liest die Archivbytes während des PUT-Requests. Nach dem letzten
Upload mit passender Prüfsumme stößt er die Archivinhaltsprüfung und weitere
Verarbeitung außerhalb des Requests an:

```java
@RestController
@RequestMapping("sync")
public class SynchronisationController {
    private final SynchronisationsAuftraege auftraege;
    private final SynchronisationProcessor processor;

    @PostMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AuftragAntwort> anlegen(
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @RequestBody AuftragAnlegenRequest request) {
        AnlageErgebnis ergebnis =
                auftraege.anlegenOderLesen(idempotencyKey, request);
        if (!ergebnis.neu()) {
            return ResponseEntity.ok(ergebnis.antwort());
        }

        return ResponseEntity.created(URI.create(
                        "/vMtextAdapter/sync/"
                                + ergebnis.antwort().auftragId()))
                .body(ergebnis.antwort());
    }

    @PutMapping(
            path = "/{auftragId}/archive/{name}",
            consumes = "application/gzip",
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AuftragAntwort> hochladen(
            @PathVariable("auftragId") String auftragId,
            @PathVariable("name") String name,
            HttpServletRequest request) throws IOException {
        // Der Request-Stream muss vor Beginn der asynchronen Verarbeitung gelesen sein.
        UploadErgebnis ergebnis =
                auftraege.archivSpeichernUndPruefsummePruefen(
                auftragId, name, request.getInputStream());
        if (ergebnis.verarbeitungStarten()) {
            processor.starten(auftragId);
        }
        return ResponseEntity.accepted().body(ergebnis.antwort());
    }

    @GetMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragAntwort status(@PathVariable("auftragId") String auftragId) {
        return auftraege.status(auftragId);
    }

    @DeleteMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Boolean> loeschen(@PathVariable("auftragId") String auftragId) {
        auftraege.beendetenAuftragLoeschen(auftragId);
        return Map.of("ok", true);
    }
}
```

Das Beispiel setzt voraus, dass `/vMtextAdapter` als Context-Path der
Anwendung konfiguriert ist. `@RequestMapping("sync")` bildet darunter die in der
Schnittstelle genannten Pfade.

`anlegenOderLesen` ordnet den Idempotency-Key einem neuen Auftrag zu oder
liefert den vorhandenen Auftrag. Die Zuordnung muss bei parallelen Requests
konsistent bleiben.

`archivSpeichernUndPruefsummePruefen` prüft die Archivankündigung, speichert
den Datenstrom außerhalb von `serverSync/` und vergleicht seine Prüfsumme. Sind
alle Archive auf diese Weise bestätigt, setzt die Methode den Auftrag atomar
auf `processing`. Ihr Rückgabewert zeigt an, ob dieser Request die
Verarbeitung starten soll.

Eine abweichende Prüfsumme wird in dieser Methode in den Auftragsstatus
`failed` übersetzt und als `UploadErgebnis` zurückgegeben. Eine syntaktisch
ungültige Anfrage wird dagegen als `UngueltigerRequestException` behandelt und
liefert HTTP 400 (Bad Request). Inhaltsfehler des Archivs entstehen erst in
der asynchronen Verarbeitung.

### Abbildung von HTTP-Fehlern

Domänenspezifische Exceptions verhindern, dass Controller und
Auftragsverwaltung Spring-Typen vermischen. Ein gemeinsamer Handler bildet sie
auf die HTTP-Schnittstelle ab:

```java
public record FehlerAntwort(String meldung) {
}

@RestControllerAdvice
public class SynchronisationFehlerbehandlung {
    @ExceptionHandler(UngueltigerRequestException.class)
    public ResponseEntity<FehlerAntwort> ungueltig(RuntimeException exception) {
        return ResponseEntity.badRequest()
                .body(new FehlerAntwort(exception.getMessage()));
    }

    @ExceptionHandler(UnbekannterAuftragException.class)
    public ResponseEntity<FehlerAntwort> unbekannt(RuntimeException exception) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(new FehlerAntwort(exception.getMessage()));
    }

    @ExceptionHandler(KonfliktException.class)
    public ResponseEntity<FehlerAntwort> konflikt(RuntimeException exception) {
        return ResponseEntity.status(HttpStatus.CONFLICT)
                .body(new FehlerAntwort(exception.getMessage()));
    }
}
```

Spring beantwortet nicht unterstützte Content-Types mit HTTP 415 (Unsupported
Media Type). Für unerwartete Exceptions wird zentral HTTP 500 (Internal Server
Error) mit einer allgemeinen Meldung erzeugt und die vollständige Exception
serverseitig protokolliert.

### Archivverarbeitung

Die Archivverarbeitung kapselt die Grenze zwischen nicht vertrauenswürdigen
Uploadpfaden und lokalen Dateipfaden:

```java
public interface ArchivVerarbeitung {
    void pruefen(
            Path archiv,
            String archivname,
            Auftragsart auftragsart,
            JsonNode information) throws IOException;

    void vollstaendigUebernehmen(
            Path archiv,
            JsonNode information,
            Path serverSync) throws IOException;

    void deltaUebernehmen(
            Path archiv,
            JsonNode information,
            Path serverSync) throws IOException;
}
```

Jeder aus Archiv, Projektinformation oder Löschliste gelesene Pfad wird vor
einer Dateioperation gegen seine erlaubte Basis aufgelöst:

```java
private Path sicherAufloesen(Path basis, String eingabe) {
    Path normalisierteBasis = basis.toAbsolutePath().normalize();
    Path ziel = normalisierteBasis.resolve(eingabe).normalize();
    if (!ziel.startsWith(normalisierteBasis)) {
        throw new UngueltigesArchivException(
                "Archivpfad verlässt das Projektverzeichnis");
    }
    return ziel;
}
```

Zusätzlich prüft die Implementierung symbolische und harte Verknüpfungen, bevor
sie Dateien erzeugt oder löscht. Eine Verknüpfung darf die geprüfte Basis auch
indirekt nicht verlassen.

Für ein FULL wird das Archiv in ein neues Arbeitsverzeichnis entpackt. Nach
vollständiger Prüfung wird das bisherige Projektverzeichnis unter dem
Mandanten-Lock entfernt und das vorbereitete Projektverzeichnis an seine Stelle
verschoben.
Liegt das Arbeitsverzeichnis auf einem anderen Dateisystem, kopiert der Adapter
das vorbereitete Projektverzeichnis stattdessen rekursiv an die Zielposition.
Ein Fehler beim Verschieben oder Kopieren setzt den Auftrag auf `failed`.

Für ein DELTA wird das Archiv ebenfalls in ein Arbeitsverzeichnis entpackt.
Die Projektdateien werden unter dem Mandanten-Lock in das bestehende
Projektverzeichnis kopiert. Danach werden die geprüften Einträge der Löschliste
entfernt. Leere Verzeichnisse dürfen anschließend entfernt werden. Die
Löschliste selbst wird nicht nach `serverSync/` kopiert.

### Übernahme und Synchronisation

Der Executor führt die Verarbeitung außerhalb des Upload-Requests aus. Der
je Mandantenkürzel bestimmte Lock umfasst die Änderungen am Projektbestand und
den M/Text-Aufruf:

```java
@Component
public class SynchronisationProcessor {
    private final Executor executor;
    private final SynchronisationsAuftraege auftraege;
    private final ArchivVerarbeitung archivVerarbeitung;
    private final MtextRessourceSynchronisationService synchronisationService;

    // Gemeinsame Synchronisationsbasis aller Mandanten dieser M/Text-Umgebung.
    private final Path serverSync;

    // Ein Lock je Mandantenkürzel lässt disjunkte Mandanten parallel arbeiten.
    private final ConcurrentMap<String, Lock> mandantenLocks =
            new ConcurrentHashMap<>();

    public void starten(String auftragId) {
        try {
            executor.execute(() -> verarbeiten(auftragId));
        } catch (RejectedExecutionException exception) {
            auftraege.fehlgeschlagen(
                    auftragId, "Verarbeitung konnte nicht gestartet werden");
        }
    }

    private void verarbeiten(String auftragId) {
        SynchronisationsAuftrag auftrag = auftraege.lesen(auftragId);
        try {
            for (Map.Entry<String, Path> upload : auftrag.getUploads().entrySet()) {
                ArchivAnmeldung anmeldung = auftrag.getArchive().get(upload.getKey());
                archivVerarbeitung.pruefen(
                        upload.getValue(),
                        upload.getKey(),
                        auftrag.getRequest().auftragsart(),
                        anmeldung.information());
            }
        } catch (Exception exception) {
            auftraege.fehlgeschlagen(
                    auftragId,
                    "Archivinhaltsprüfung fehlgeschlagen: "
                            + exception.getMessage());
            return;
        }

        Lock mandantenLock = mandantenLocks.computeIfAbsent(
                auftrag.getRequest().kuerzel(), kuerzel -> new ReentrantLock());
        mandantenLock.lock();
        try {
            for (Map.Entry<String, Path> upload : auftrag.getUploads().entrySet()) {
                ArchivAnmeldung anmeldung = auftrag.getArchive().get(upload.getKey());
                if (auftrag.getRequest().auftragsart() == Auftragsart.FULL) {
                    archivVerarbeitung.vollstaendigUebernehmen(
                            upload.getValue(), anmeldung.information(), serverSync);
                } else {
                    archivVerarbeitung.deltaUebernehmen(
                            upload.getValue(), anmeldung.information(), serverSync);
                }
            }

            Object ergebnis = synchronisationService.synchronisieren(serverSync);
            if (!auftraege.ergebnisPasstInAntwort(auftragId, ergebnis)) {
                auftraege.fehlgeschlagen(
                        auftragId, "M/Text-Ergebnis überschreitet 1 MiB");
                return;
            }
            auftraege.abschliessen(
                    auftragId, SynchronisationsStatus.SUCCEEDED, ergebnis, null);
        } catch (Exception exception) {
            auftraege.fehlgeschlagen(
                    auftragId,
                    "Übernahme oder M/Text-Synchronisation fehlgeschlagen: "
                            + exception.getMessage());
        } finally {
            // Auch nach Fehlern muss der nächste Auftrag dieses Mandanten weiterlaufen.
            mandantenLock.unlock();
        }
    }
}
```

Wenn mehrere Adapterinstanzen dieselbe M/Text-Umgebung verarbeiten, muss der
Lock desselben Mandanten auch zwischen diesen Instanzen wirken.

### M/Text-Aufruf und Ergebnis

Der Service übergibt `serverSync/` als Synchronisationsbasis an M/Text:

```java
public Object synchronisieren(Path serverSync)
        throws MTextException, IOException {
    MTextActivationServer server = MTextFactory.connect(
            mtextConfig.getTechnicalUser(),
            mtextConfig.getTechnicalUserPassword(),
            null);

    ActivationConfigurationFactory factory =
            (ActivationConfigurationFactory) server.getConfigurationFactory();
    Configuration configuration = factory.newSynchronizationConfiguration();
    configuration.put("url", serverSync.toUri().toString());
    configuration.put("testRun", false);
    configuration.put("completePackageMode", false);
    configuration.put("mirrorProjectDeletions", true);

    server.writeRepositorySynchronisationScript(
            new ClassPathResource(
                    "mtextserverconfig/sync_local.xml").getInputStream());
    Object ergebnis = server.synchroniseRepositoryBlocking(configuration);
    server.refreshServerCache(MTextActivationServer.ServerCacheType.RESOURCES);
    return ergebnis;
}
```

`sync_local.xml` übernimmt den Synchronisationsparameter `repositoryUrl` als
`workspaceDir`. Die M/Text-Rückgabe wird als `ergebnis` in die Antwort
übernommen.

## Abnahmekriterien

Eine Client- und Serverimplementierung der Schnittstelle wird mindestens mit den
folgenden Fällen geprüft:

| Fall | Erwartetes Ergebnis |
|---|---|
| gültiger erster POST | HTTP 201 (Created), `Location`, neue Auftrags-ID und `ready` |
| gleicher POST mit gleichem Idempotency-Key | HTTP 200 (OK), gleiche Auftrags-ID und unveränderter aktueller Status |
| anderer JSON-Inhalt mit bekanntem Idempotency-Key | HTTP 409 (Conflict) und `meldung` |
| erster gültiger Upload eines unvollständigen Auftrags | HTTP 202 (Accepted) und `uploading` |
| wiederholter gültiger Upload vor Verarbeitungsbeginn | HTTP 202 (Accepted), Upload bleibt verwendbar und Auftrag startet höchstens einmal |
| Upload mit abweichender Prüfsumme | HTTP 202 (Accepted), `failed` und `meldung`, keine Änderung an `serverSync/` |
| letzter gültiger Upload | HTTP 202 (Accepted) und `processing`, Verarbeitung startet einmal |
| parallele letzte Uploads | ein Statuswechsel zu `processing` und ein Verarbeitungsstart |
| parallele Aufträge desselben Mandanten | Projektübernahme und M/Text-Aufruf erfolgen nacheinander unter demselben Lock |
| parallele Aufträge verschiedener Mandanten | Projektübernahme und M/Text-Aufruf dürfen innerhalb derselben Umgebung parallel erfolgen |
| PUT nach Verarbeitungsbeginn | HTTP 202 (Accepted) mit aktuellem Status, kein weiterer Verarbeitungsstart |
| GET eines bekannten Auftrags | HTTP 200 (OK) mit passender Auftrags-ID und aktuellem Status |
| GET eines unbekannten Auftrags | HTTP 404 (Not Found) und `meldung` |
| erfolgreicher M/Text-Aufruf | `succeeded` und vorhandenes Ergebnis wird als `ergebnis` übertragen |
| fehlgeschlagene Übernahme oder M/Text-Aufruf | `failed`, technische `meldung` und freigegebener Mandanten-Lock |
| DELETE eines aktiven Auftrags | HTTP 409 (Conflict), Auftrag bleibt erhalten |
| DELETE eines Endstatus | HTTP 200 (OK) und `{"ok": true}` |
| GET oder zweiter DELETE nach dem Löschen | HTTP 404 (Not Found) |
| Adapter-Neustart | temporäre Auftragsdateien werden entfernt, frühere Auftrags-IDs liefern HTTP 404 (Not Found) |
| Archivpfad außerhalb des Projekts | Auftrag wird `failed`, außerhalb des Projekts erfolgt keine Dateioperation |

Änderungen an Pfaden, erforderlichen Feldern, Statuswerten oder der Bedeutung
eines bestehenden Feldes sind Schnittstellenänderungen. Neue optionale JSON-Felder
sind kompatibel, solange das beschriebene Verhalten unverändert bleibt.
