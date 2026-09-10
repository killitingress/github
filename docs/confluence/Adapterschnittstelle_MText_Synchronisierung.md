# Adaptervertrag für die M/Text-Synchronisierung

Diese Spezifikation beschreibt die Erweiterung des Adapters für den vorhandenen
HTTP-Client.

## HTTP-Schnittstelle

Der neue Ablauf verwendet `/sync2`. Der bestehende Endpunkt `/sync` bleibt
aus Kompatibilitätsgründen unverändert.

Basis-URL: `http://<Umgebungskennung>.ltoma.intern/vMtextAdapter`

| Methode | Pfad relativ zur Basis-URL | Zweck |
|---|---|---|
| `POST` | `/sync2/{auftrag_id}` | Auftrag anlegen |
| `PUT` | `/sync2/{auftrag_id}/archive/{name}` | angekündigtes Archiv übertragen |
| `GET` | `/sync2/{auftrag_id}` | Auftrag suchen sowie Status und Ergebnis lesen |
| `DELETE` | `/sync2/{auftrag_id}` | unvollständigen Auftrag abbrechen oder abgeschlossenen Auftrag aufräumen |

Für `/sync2` gelten folgende Anforderungen des Clients:

- POST überträgt JSON in UTF-8 mit `Content-Type: application/json`.
- PUT überträgt unveränderte `.tgz`-Bytes als Datenstrom mit
  `Content-Type: application/gzip` und `Content-Length`.
- `auftrag_id` und `name` werden jeweils als ein URL-Pfadsegment kodiert.
- Erfolgreiche Antworten haben HTTP-Status 200 und ein JSON-Objekt als Body.
- Das Socket-Timeout beträgt 15 Sekunden. Die Auftragsverarbeitung muss
  unabhängig vom HTTP-Request laufen und per GET abfragbar bleiben.

Der Client sendet keinen anwendungsspezifischen Authentifizierungsheader.
Zugriffsschutz ist ggf. noch zu klären.

Idee:
Der Adapter darf `/sync2` einschließlich seiner Unterpfade nur für `en01`,
`en02`, `en03`, `fu01`, `fu02` und `fu03` bereitstellen. 
Außerhalb dieser Umgebungen bleibt `/sync2` deaktiviert.

### HTTP-Fehlerantworten

Fehlerhafte Requests beantwortet der Adapter mit einem JSON-Objekt mit
`message`, etwa `{"message": "Archiv ist nicht im Auftrag angekündigt"}`.
Ein ungültiger Request führt zu HTTP 400, eine unbekannte oder bereits
gelöschte Auftrags-ID zu HTTP 404. Ein POST unter einer vorhandenen
Auftrags-ID oder ein abweichender PUT für ein bereits angenommenes Archiv
führt zu HTTP 409 und verändert den Auftrag nicht. Ein unpassender
`Content-Type` führt zu HTTP 415 und ein unerwarteter Adapterfehler bei der
Bearbeitung des HTTP-Requests zu HTTP 500.

Prüfsummen-, Archivinhalts- und Verarbeitungsfehler eines bekannten Auftrags
werden dagegen mit HTTP 200, Auftragsstatus `failed` und `message`
übermittelt.

## Auftrag beim Start suchen

Der Client bildet die Auftrags-ID als
`<GITHUB_RUN_ID>-<Mandantenkürzel>`, beispielsweise `123456-FI`. Das
Mandantenkürzel ordnet jedes Mandanten-Repository eindeutig zu. Jeder Adapter
verwaltet die Aufträge genau einer M/Text-Umgebung, daher gehört die
Umgebungskennung nicht zur Auftrags-ID.

Vor dem Archivbau fragt der Client mit `GET /sync2/{auftrag_id}` nach einem
bestehenden Auftrag. Die Auftrags-ID bleibt beim Wiederholen desselben
GitHub-Laufs erhalten. Die Anfrage hat keinen Body.

Der Adapter liefert bei bekannter Auftrags-ID HTTP 200 mit der
Auftragsantwort. Bei unbekannter Auftrags-ID liefert er HTTP 404 mit `message`.
Fehlt der Auftrag, baut der Client die Archive und legt ihn an. Einen
vorhandenen Auftrag übernimmt oder entfernt er entsprechend seinem Status.

## Auftrag anlegen

```http
POST /vMtextAdapter/sync2/123456-FI
Content-Type: application/json
```

```json
{
  "archive": [
    {
      "name": "FIBASISF.tgz",
      "information": {
        "projekt": "LOMS_Basis",
        "lieferart": "FULL",
        "scope": {
          "bis": {
            "referenz": "release/261",
            "commit": "0123456789abcdef0123456789abcdef0123456789"
          }
        },
        "elemente": [["A", "beispiel.xml"]],
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    }
  ]
}
```

Commit und Prüfsumme im Beispiel sind Platzhalter. Siehe Zielbild Dokument für
volle Beschreibung der Info-Datei.

| Feld | Typ und Bedeutung |
|---|---|
| `archive` | nicht leeres Array, ein Eintrag je zu synchronisierendem Projekt |
| `archive[].name` | String, Archivdateiname und Schlüssel für den PUT |
| `archive[].information` | Objekt mit den folgenden Projektinformationen |
| `information.projekt` | String, Name des Projektverzeichnisses |
| `information.lieferart` | String, `FULL` oder `DELTA`, für alle Archive des Auftrags gleich |
| `information.scope.bis` | Objekt mit `referenz` und `commit` als Strings für den Zielstand |
| `information.scope.von` | entsprechendes Objekt für den Ausgangsstand, bei DELTA vorhanden, bei FULL weggelassen |
| `information.elemente` | Array aus Paaren `[Status, projektbezogener Pfad]`, darf leer sein |
| `information.sha256` | String, SHA-256 der übertragenen Archivbytes als 64 hexadezimale Zeichen |

Alle Felder außer `scope.von` bei FULL sind vorhanden. Die Statuswerte in
`elemente` sind `A` (hinzugefügt), `M` (geändert), `D` (gelöscht) und `T`
(Typ geändert). Pfade verwenden `/` als Trennzeichen. Der Archivname endet
bei FULL auf `F.tgz`, bei DELTA auf `D.tgz`.

Ein neuer Auftrag antwortet mit `{"auftrag_id": "123456-FI", "status": "ready"}`.
Das Mandantenkürzel am Ende der Auftrags-ID bestimmt den Mandanten des
Auftrags.

## Archive hochladen und verarbeiten

Der Client lädt die angekündigten Archive nacheinander hoch:

```http
PUT /vMtextAdapter/sync2/123456-FI/archive/FIBASISF.tgz
Content-Type: application/gzip
Content-Length: 12345
```

Die Antwort enthält `auftrag_id` und den aktuellen `status`.
Bei einem neuen Auftrag sendet der Client die angekündigten Archive.
Ein PUT mit demselben Archivinhalt darf wiederholt werden und liefert mit
HTTP 200 den aktuellen Auftrag, ohne eine weitere Verarbeitung zu starten.

Der Adapter speichert Uploads außerhalb von `serverSync/` (streamt in eine
temporäre Datei) und checkt die SHA-256-Prüfsumme.
Sobald alle angekündigten Archive korrekt vorliegen, beginnt die weitere
Verarbeitung automatisch. Fehler bei Prüfung oder Verarbeitung werden als
`failed` mit `message` bereitgestellt.

Die Archive sind gzip-komprimierte TAR-Dateien:

| Lieferart | Inhalt und Übernahme |
|---|---|
| `FULL` | Das F-Archiv enthält das Projektverzeichnis. Es ersetzt den bisherigen Bestand dieses Projekts unter `serverSync/`. |
| `DELTA` | Das D-Archiv enthält das Projektverzeichnis mit neuen oder geänderten Dateien und eine Löschliste auf der obersten Archivebene. Die Dateien werden übernommen, die aufgeführten Pfade gelöscht. |

Die Löschliste heißt wie das D-Archiv mit `.txt` statt `.tgz`, ist UTF-8-kodiert
und enthält je Zeile einen repositorybezogenen Pfad einschließlich Projektname.
Sie kann leer sein. `elemente` verwendet dagegen Pfade ohne Projektname.
Bei FULL haben die Elemente Status `A`. Bei DELTA nennt die Löschliste die
`D`-Einträge, die übrigen Elemente beschreiben die übertragenen Dateien.

`serverSync/` enthält die Projektverzeichnisse. Uploads und Löschlisten gehören
nicht in diesen Bestand. Bei der Übernahme dürfen Archiv- und Löschlistenpfade
das jeweilige Projektverzeichnis nicht verlassen.

Gemäß Zielbild umfasst ein Lock je Mandantenkürzel und M/Text-Umgebung die
Übernahme aller Projektarchive und den anschließenden M/Text-Aufruf zur
Aktualisierung des Ressourcen-Caches. Danach wird der Lock freigegeben.
`serverSync/` ist die gemeinsame Synchronisierungsbasis.

## Status, Ergebnis und Aufräumen

Für die Requests des Clients gelten folgende Reaktionen:

| Request | Reaktion | Bedeutung für den Client |
|---|---|---|
| `GET /sync2/{auftrag_id}` | HTTP 404 mit `message` | kein Auftrag vorhanden, neuen Auftrag beginnen |
| `GET /sync2/{auftrag_id}` | HTTP 200 mit `ready` oder `uploading` | unvollständigen Auftrag löschen und neu beginnen |
| `GET /sync2/{auftrag_id}` | HTTP 200 mit `processing` | Verarbeitung läuft, weiter abfragen |
| `GET /sync2/{auftrag_id}` | HTTP 200 mit `succeeded` und optionalem `result` | Verarbeitung erfolgreich beendet |
| `GET /sync2/{auftrag_id}` | HTTP 200 mit `failed` und `message` | bei der Suche Auftrag löschen und neu beginnen, nach `processing` mit Fehler beenden |
| `POST /sync2/{auftrag_id}` | HTTP 200 mit `ready` | neuer Auftrag ist angelegt und erwartet Uploads |
| `PUT /sync2/{auftrag_id}/archive/{name}` | HTTP 200 mit `uploading` | Archiv angenommen, weitere Archive fehlen |
| `PUT /sync2/{auftrag_id}/archive/{name}` | HTTP 200 mit `processing` | letztes Archiv angenommen, Verarbeitung beginnt |
| `PUT /sync2/{auftrag_id}/archive/{name}` | HTTP 200 mit `failed` und `message` | vollständig empfangenes Archiv hat seine Prüfung nicht bestanden |
| `DELETE /sync2/{auftrag_id}` | HTTP 200 mit `{"status": "succeeded"}` | unvollständiger oder beendeter Auftrag ist entfernt |

HTTP-Fehler liefern ein JSON-Objekt mit `message` und dem oben beschriebenen
Statuscode. Der Auftragsstatus `failed` ist dagegen eine erfolgreiche
HTTP-Antwort auf einen bekannten Auftrag.

Die Auftragsantwort für POST, PUT und GET hat folgende Felder:

| Feld | Typ und Bedeutung |
|---|---|
| `auftrag_id` | nicht leerer String, ID des Auftrags |
| `status` | einer der unten aufgeführten Strings |
| `result` | optionaler JSON-Wert bei `succeeded`, wenn eine M/Text-Ausgabe vorliegt |
| `message` | Fehlermeldung als String bei `failed` |

`auftrag_id` und `status` sind erforderlich. Bei `failed` ist zusätzlich
`message` erforderlich.
DELETE bestätigt den Löschvorgang mit `status: "succeeded"` ohne
Auftrags-ID. Diese Antwort ist eine Löschbestätigung und kein Auftragsstatus.
`result` enthält die M/Text-Ausgabe einer erfolgreichen Auftragsantwort.

| Status | Bedeutung |
|---|---|
| `ready` | Auftrag angelegt, wartet auf Uploads |
| `uploading` | Uploads noch nicht abgeschlossen |
| `processing` | Auftrag wird geprüft, wartet auf den Lock oder wird verarbeitet |
| `succeeded` | Verarbeitung erfolgreich beendet |
| `failed` | Prüfung oder Verarbeitung fehlgeschlagen |

```json
{"auftrag_id": "123456-FI", "status": "succeeded", "result": "M/Text-Ausgabe"}
```

```json
{"auftrag_id": "123456-FI", "status": "failed", "message": "M/Text-Synchronisierung ist fehlgeschlagen"}
```

Der Client fragt mit `GET /sync2/{auftrag_id}` bis zu einem Endstatus ab.
Solange der Auftrag aktiv ist, wartet er zwischen Abfragen fünf Sekunden.

Nach `succeeded` liest der Client das Ergebnis, nach `failed` die
Fehlermeldung. Anschließend sendet er
`DELETE /sync2/{auftrag_id}`. Der Adapter entfernt die Auftragsdaten und
zugehörigen temporären Dateien und bestätigt mit `{"status": "succeeded"}`.
Der Projektbestand unter `serverSync/` bleibt erhalten. Laut Zielbild
überleben Auftragsdaten keinen Adapter-Neustart.

DELETE ist auch in `ready` und `uploading` erlaubt. Dabei beendet der Adapter
die zugehörige Uploadannahme und verhindert einen anschließenden
Verarbeitungsstart. In `processing` wartet der Client auf den Endstatus und
sendet kein DELETE.

Andere HTTP-Fehler, Netzwerkfehler und ungültige Antworten beenden
den Clientlauf mit `ADAPTER_FAILED`. Das gilt auch bei fehlgeschlagenem DELETE.
Der Client legt das inhaltliche Format von `result` nicht fest.

## Java-Idee

| Klasse oder Komponente | Aufgabe |
|---|---|
| `SynchronisierungsController` | Anlage, Archivupload, Status und Löschen eines Auftrags bereitstellen |
| `SynchronisierungsAuftraege` | Auftragsdaten, Uploadprüfung, Status und Ergebnis verwalten |
| `SynchronisierungsProcessor` | Projektbestand und M/Text-Aufruf unter dem Lock des Mandanten verarbeiten |
| `MtextRessourceSynchronisierungsService` | M/Text mit `serverSync/` aufrufen und das Ergebnis zurückgeben |

### Auftragsdaten und Antworten

```java
public enum SynchronisierungsStatus {
    // Der angelegte Auftrag wartet auf seinen ersten Upload.
    READY,
    // Angekündigte Archive werden empfangen und geprüft.
    UPLOADING,
    // Umfasst Warten auf den Mandanten-Lock, Projektübernahme und M/Text-Synchronisierung.
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
```

Der interne Auftragszustand kann die angekündigten Archive und ihre geprüften
Upload-Dateien gemeinsam halten:

```java
public class SynchronisierungsAuftrag {
    private String auftragId;
    private AuftragAnlegenRequest request;
    private Map<String, ArchivAnmeldung> archive;
    private Map<String, Path> uploads;
    private SynchronisierungsStatus status = SynchronisierungsStatus.READY;
    private Object result;
    private String message;

    // Enthält die Dateien dieses Auftrags außerhalb von serverSync/.
    private Path uploadVerzeichnis;
}
```

### Auftragsverwaltung und Nebenläufigkeit

Der Adapter speichert jeden Auftrag unter seiner Auftrags-ID. Im Beispiel
verhindert `synchronized`, dass mehrere HTTP-Anfragen gleichzeitig diese Daten
lesen oder ändern.
So kann eine Anfrage den Auftrag erst lesen, wenn eine andere ihre Änderungen
einschließlich des Status abgeschlossen hat.

```java
public class SynchronisierungsAuftraege {
    private final Map<String, SynchronisierungsAuftrag> nachId = new HashMap<>();

    public synchronized AuftragAntwort anlegen(
            String auftragId,
            AuftragAnlegenRequest request) {
        if (nachId.containsKey(auftragId)) {
            throw new KonfliktException("Auftrags-ID ist bereits vorhanden");
        }

        requestValidieren(auftragId, request);
        SynchronisierungsAuftrag auftrag =
                SynchronisierungsAuftrag.anlegen(
                        auftragId, request, uploadBasis);
        nachId.put(auftragId, auftrag);
        return antwort(auftrag);
    }

    public synchronized AuftragAntwort status(String auftragId) {
        return antwort(lesen(auftragId));
    }
}
```

### Freigabe von `/sync2` nach Zielumgebung

Vorschlag: Eine Spring-Bedingung (`@Conditional`) prüft den lokalen Hostnamen
gegen die sechs freigegebenen `<Umgebung>.ltoma.intern`-Namen und registriert
bei Übereinstimmung den `/sync2`-Controller. Maßgeblich ist der Hostname des
Servers, nicht der vom Client gesendete HTTP-Host-Header.

### Controller

Beispiel:

```java
@RestController
@RequestMapping("sync2")
public class SynchronisierungsController {
    private final SynchronisierungsAuftraege auftraege;
    private final SynchronisierungsProcessor processor;

    @PostMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AuftragAntwort> create(
            @PathVariable("auftragId") String auftragId,
            @RequestBody AuftragAnlegenRequest request) {
        ...
    }

    @PutMapping(path = "/{auftragId}/archive/{name}", consumes = "application/gzip", produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AuftragAntwort> upload(
            @PathVariable("auftragId") String auftragId,
            @PathVariable("name") String name,
            HttpServletRequest request) throws IOException {
        ...
    }

    @GetMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragAntwort status(@PathVariable("auftragId") String auftragId) {
        return auftraege.status(auftragId);
    }

    @DeleteMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, String> delete(@PathVariable("auftragId") String auftragId) {
        // Auftrag vor Verarbeitungsbeginn oder nach seinem Endstatus entfernen.
        auftraege.auftragLoeschen(auftragId);
        return Map.of("status", "succeeded");
    }
}
```
