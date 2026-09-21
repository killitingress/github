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
| `GET` | `/sync2/{auftrag_id}` | vollständigen Auftrag lesen |
| `GET` | `/sync2/{auftrag_id}/execution` | Ausführung mit Status und Ergebnis lesen |
| `DELETE` | `/sync2/{auftrag_id}` | unvollständigen Auftrag abbrechen oder abgeschlossenen Auftrag aufräumen |

Für `/sync2` gelten folgende Anforderungen des Clients:

- POST überträgt JSON in UTF-8 mit `Content-Type: application/json`.
- PUT überträgt unveränderte `.tgz`-Bytes als Datenstrom mit
  `Content-Type: application/gzip` und `Content-Length`.
- `auftrag_id` und `name` werden jeweils als ein URL-Pfadsegment kodiert.
- Ein erfolgreicher POST antwortet mit HTTP 201 und `Location` auf den
  angelegten Auftrag. GET, PUT und DELETE antworten bei Erfolg mit HTTP 200.
- Auftrags- und Ausführungsantworten haben feste Felder. Ein derzeit nicht
  vorhandener Wert wird als `null` ausgegeben und nicht weggelassen.
- Das Socket-Timeout beträgt 30 Sekunden. Die Auftragsverarbeitung muss
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

Vor dem Archivbau fragt der Client mit `GET /sync2/{auftrag_id}/execution` nach einem
bestehenden Auftrag. Die Auftrags-ID bleibt beim Wiederholen desselben
GitHub-Laufs erhalten. Die Anfrage hat keinen Body.

Der Adapter liefert bei bekannter Auftrags-ID HTTP 200 mit der Ausführungsantwort.
Bei unbekannter Auftrags-ID liefert er HTTP 404 mit `message`.
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
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    }
  ]
}
```

Commit und Prüfsumme im Beispiel sind Platzhalter. Das Zielbild beschreibt
die Informationsdaten der Synchronisierung.

| Feld | Typ und Bedeutung |
|---|---|
| `archive` | nicht leeres Array, ein Eintrag je zu synchronisierendem Projekt |
| `archive[].name` | String, Archivdateiname und Schlüssel für den PUT |
| `archive[].information` | Objekt mit den folgenden Projektinformationen |
| `information.projekt` | String, Name des Projektverzeichnisses |
| `information.lieferart` | String, `FULL` oder `DELTA`, für alle Archive des Auftrags gleich |
| `information.scope.bis` | Objekt mit `referenz` und `commit` als Strings für den Zielcommit |
| `information.scope.von` | entsprechendes Objekt für den Ausgangscommit, bei DELTA vorhanden, bei FULL weggelassen |
| `information.sha256` | String, SHA-256 der übertragenen Archivbytes als 64 hexadezimale Zeichen |

Alle aufgeführten Felder außer `scope.von` bei FULL sind vorhanden. Der
Archivname endet bei FULL auf `F.tgz`, bei DELTA auf `D.tgz`.

Ein neuer Auftrag antwortet mit HTTP 201, dem Header
`Location: /vMtextAdapter/sync2/123456-FI` und der vollständigen
Auftragsrepräsentation. Das Mandantenkürzel am Ende der Auftrags-ID bestimmt
den Mandanten des Auftrags.

```json
{
  "auftrag_id": "123456-FI",
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
        "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    }
  ],
  "execution": {
    "status": "ready",
    "message": null,
    "result": null
  }
}
```

`GET /sync2/{auftrag_id}` liefert dieselbe vollständige Repräsentation mit
der dann aktuellen Ausführung.

## Archive hochladen und verarbeiten

Der Client lädt die angekündigten Archive nacheinander hoch:

```http
PUT /vMtextAdapter/sync2/123456-FI/archive/FIBASISF.tgz
Content-Type: application/gzip
Content-Length: 12345
```

Die Ausführungsantwort enthält den aktuellen `status` sowie die Felder
`message` und `result`.
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
Sie kann leer sein. Die Elementliste für den Archivbau verbleibt beim Client
und gehört nicht zum POST-Request.

`serverSync/` enthält die Projektverzeichnisse. Uploads und Löschlisten gehören
nicht in diesen Bestand. Bei der Übernahme dürfen Archiv- und Löschlistenpfade
das jeweilige Projektverzeichnis nicht verlassen.

Gemäß Zielbild umfasst ein Lock je Mandantenkürzel und M/Text-Umgebung die
Übernahme aller Projektarchive und den anschließenden M/Text-Aufruf zur
Aktualisierung des Ressourcen-Caches. Danach wird der Lock freigegeben.
`serverSync/` ist die gemeinsame Synchronisierungsbasis.

## Ausführung, Ergebnis und Aufräumen

Für die Requests des Clients gelten folgende Reaktionen:

| Request | Reaktion | Bedeutung für den Client |
|---|---|---|
| `GET /sync2/{auftrag_id}` | HTTP 200 mit vollständiger Auftragsrepräsentation | Auftrag einschließlich Anmeldung und aktueller Ausführung lesen |
| `GET /sync2/{auftrag_id}/execution` | HTTP 404 mit `message` | kein Auftrag vorhanden, neuen Auftrag beginnen |
| `GET /sync2/{auftrag_id}/execution` | HTTP 200 mit `ready` oder `uploading` | unvollständigen Auftrag löschen und neu beginnen |
| `GET /sync2/{auftrag_id}/execution` | HTTP 200 mit `processing` | Verarbeitung läuft, weiter abfragen |
| `GET /sync2/{auftrag_id}/execution` | HTTP 200 mit `succeeded` | Verarbeitung erfolgreich beendet |
| `GET /sync2/{auftrag_id}/execution` | HTTP 200 mit `failed` und `message` | bei der Suche Auftrag löschen und neu beginnen, nach `processing` mit Fehler beenden |
| `POST /sync2/{auftrag_id}` | HTTP 201 mit `Location` und `ready` | neuer Auftrag ist angelegt und erwartet Uploads |
| `PUT /sync2/{auftrag_id}/archive/{name}` | HTTP 200 mit `uploading` | Archiv angenommen, weitere Archive fehlen |
| `PUT /sync2/{auftrag_id}/archive/{name}` | HTTP 200 mit `processing` | letztes Archiv angenommen, Verarbeitung beginnt |
| `PUT /sync2/{auftrag_id}/archive/{name}` | HTTP 200 mit `failed` und `message` | vollständig empfangenes Archiv hat seine Prüfung nicht bestanden |
| `DELETE /sync2/{auftrag_id}` | HTTP 200 mit `{"status": "succeeded"}` | unvollständiger oder beendeter Auftrag ist entfernt |

HTTP-Fehler liefern ein JSON-Objekt mit `message` und dem oben beschriebenen
Statuscode. Der Auftragsstatus `failed` ist dagegen eine erfolgreiche
HTTP-Antwort auf einen bekannten Auftrag.

Die Auftragsrepräsentation für POST und `GET /sync2/{auftrag_id}` hat
folgende Felder:

| Feld | Typ und Bedeutung |
|---|---|
| `auftrag_id` | nicht leerer String, ID des Auftrags |
| `archive` | beim POST übermittelte Liste der Archive und Projektinformationen |
| `execution` | Objekt mit der aktuellen Ausführung des Auftrags |

Die Ausführungsantwort für PUT und `GET /sync2/{auftrag_id}/execution`
enthält folgende Felder:

| Feld | Typ und Bedeutung |
|---|---|
| `status` | einer der unten aufgeführten Strings |
| `message` | nicht leerer String bei `failed`, sonst `null` |
| `result` | M/Text-Ausgabe als String bei `succeeded` oder `null`, sonst `null` |

Alle genannten Felder sind vorhanden. Die Auftrags-ID steht bereits im
Ressourcenpfad und wird in der Ausführungsantwort nicht wiederholt.
DELETE bestätigt den Löschvorgang mit `status: "succeeded"` ohne
Auftrags-ID. Diese Antwort ist eine Löschbestätigung und kein Auftragsstatus.
Ein erfolgreich abgeschlossener Auftrag darf `result: null` liefern, wenn
M/Text keine Ausgabe bereitstellt.

| Status | Bedeutung |
|---|---|
| `ready` | Auftrag angelegt, wartet auf Uploads |
| `uploading` | Uploads noch nicht abgeschlossen |
| `processing` | Auftrag wird geprüft, wartet auf den Lock oder wird verarbeitet |
| `succeeded` | Verarbeitung erfolgreich beendet |
| `failed` | Prüfung oder Verarbeitung fehlgeschlagen |

```json
{"status": "succeeded", "message": null, "result": "M/Text-Ausgabe"}
```

```json
{"status": "failed", "message": "M/Text-Synchronisierung ist fehlgeschlagen", "result": null}
```

Der Client fragt mit `GET /sync2/{auftrag_id}/execution` bis zu einem Endstatus ab.
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
    private String result;
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
        return auftragAntwort(auftrag);
    }

    public synchronized AuftragAntwort auftrag(String auftragId) {
        return auftragAntwort(lesen(auftragId));
    }

    public synchronized ExecutionAntwort execution(String auftragId) {
        return executionAntwort(lesen(auftragId));
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
    public ResponseEntity<ExecutionAntwort> upload(
            @PathVariable("auftragId") String auftragId,
            @PathVariable("name") String name,
            HttpServletRequest request) throws IOException {
        ...
    }

    @GetMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragAntwort auftrag(@PathVariable("auftragId") String auftragId) {
        return auftraege.auftrag(auftragId);
    }

    @GetMapping(path = "/{auftragId}/execution", produces = MediaType.APPLICATION_JSON_VALUE)
    public ExecutionAntwort execution(@PathVariable("auftragId") String auftragId) {
        return auftraege.execution(auftragId);
    }

    @DeleteMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, String> delete(@PathVariable("auftragId") String auftragId) {
        // Auftrag vor Verarbeitungsbeginn oder nach seinem Endstatus entfernen.
        auftraege.auftragLoeschen(auftragId);
        return Map.of("status", "succeeded");
    }
}
```
