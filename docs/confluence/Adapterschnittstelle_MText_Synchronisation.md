# Adaptervertrag für die M/Text-Synchronisation

Diese Spezifikation beschreibt die Erweiterung des Adapters für den vorhandenen
HTTP-Client.

## HTTP-Schnittstelle

Der neue Ablauf verwendet `/sync2`. Der bestehende Endpunkt `/sync` bleibt
aus Kompatibilitätsgründen unverändert.

Basis-URL: `http://<Umgebungskennung>.ltoma.intern/vMtextAdapter`

| Methode | Pfad relativ zur Basis-URL | Zweck |
|---|---|---|
| `POST` | `/sync2` | Auftrag anlegen oder wiederaufnehmen |
| `PUT` | `/sync2/{auftrag_id}/archive/{name}` | angekündigtes Archiv übertragen |
| `GET` | `/sync2` mit Header `Idempotency-Key` | Auftrag anhand der Laufkennung suchen |
| `GET` | `/sync2/{auftrag_id}` | Status und Ergebnis lesen |
| `DELETE` | `/sync2/{auftrag_id}` | Auftrag außerhalb von `processing` aufräumen |

Für `/sync2` gelten folgende Anforderungen des Clients:

- POST überträgt JSON in UTF-8 mit `Content-Type: application/json`.
- PUT überträgt unveränderte `.tgz`-Bytes als Datenstrom mit
  `Content-Type: application/gzip` und `Content-Length`.
- `auftrag_id` und `name` werden jeweils als ein URL-Pfadsegment kodiert.
- Erfolgreiche Antworten haben einen 2xx-Status und ein JSON-Objekt als Body.
- Das Socket-Timeout beträgt 15 Sekunden. Die Auftragsverarbeitung muss
  unabhängig vom HTTP-Request laufen und per GET abfragbar bleiben.

Der Client sendet keinen anwendungsspezifischen Authentifizierungsheader.
Zugriffsschutz ist ggf. noch zu klären.

Idee:
Der Adapter darf `/sync2` einschließlich seiner Unterpfade nur für `en01`,
`en02`, `en03`, `fu01`, `fu02` und `fu03` bereitstellen. 
Außerhalb dieser Umgebungen bleibt `/sync2` deaktiviert.

### HTTP-Fehlerantworten

Der Adapter beantwortet fehlerhafte Requests mit folgenden HTTP-Statuscodes
und einem JSON-Objekt mit `message`, etwa
`{"message": "Archiv ist nicht im Auftrag angekündigt"}`:

| HTTP-Status | Auslöser |
|---|---|
| `400 Bad Request` | ungültiger Request, fehlender oder leerer `Idempotency-Key` beim POST oder GET auf `/sync2` oder nicht angekündigter Archivname beim PUT |
| `404 Not Found` | unbekannte oder bereits gelöschte Auftrags-ID oder Idempotenzkennung |
| `409 Conflict` | bekannter `Idempotency-Key` mit abweichendem Requestinhalt oder DELETE eines Auftrags in `processing` |
| `415 Unsupported Media Type` | `Content-Type` passt nicht zum Endpunkt |
| `500 Internal Server Error` | unerwarteter Adapterfehler bei der Bearbeitung des HTTP-Requests |

Prüfsummen-, Archivinhalts- und Verarbeitungsfehler eines bekannten Auftrags
werden dagegen mit Auftragsstatus `failed` und `message` übermittelt.
Der HTTP-Request zum Übermitteln dieses Status erhält eine 2xx-Antwort.

## Auftrag beim Start suchen

Vor dem Archivbau fragt der Client mit `GET /sync2` und dem Header
`Idempotency-Key: github-run-<GITHUB_RUN_ID>-<Umgebungskennung>` nach einem
bestehenden Auftrag. Die Kennung bleibt beim Wiederholen desselben
GitHub-Laufs erhalten. Die Anfrage hat keinen Body.

Der Adapter liefert bei bekanntem Schlüssel HTTP 200 mit der Auftragsantwort.
Bei unbekanntem Schlüssel liefert er HTTP 404 mit `message`.

| Ergebnis der Suche | Ablauf im Client |
|---|---|
| HTTP 404 | Archive bauen, Auftrag anlegen und Uploads starten |
| `processing` | bestehenden Auftrag bis zum Endstatus abfragen |
| `succeeded` | Ergebnis übernehmen, Auftrag aufräumen und erfolgreich enden |
| `ready`, `uploading`, `failed` | Auftrag löschen, Archive bauen und mit demselben Schlüssel neu anlegen |

Lehnt DELETE mit HTTP 409 ab, fragt der Client den Auftrag über seine ID
erneut ab und wartet auf den Abschluss. Meldet diese Abfrage bereits `failed`,
endet der GitHub-Versuch nach dem Aufräumen mit diesem Fehler. Innerhalb
dieses Versuchs wird die Verarbeitung nicht automatisch erneut gestartet.

## Auftrag anlegen

```http
POST /vMtextAdapter/sync2
Idempotency-Key: github-run-123456-en01
Content-Type: application/json
```

```json
{
  "mandant": "FI",
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
| `mandant` | String, Mandantenkürzel |
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

Ein neuer Auftrag antwortet mit `{"auftrag_id": "8f73c1", "status": "ready"}`.
Der Header `Idempotency-Key` identifiziert den Auftrag. Der Client bildet ihn
als `github-run-<GITHUB_RUN_ID>-<Umgebungskennung>`. Ein wiederholter POST mit
diesem Schlüssel liefert die bestehende Auftrags-ID und den aktuellen Status,
ohne die Verarbeitung erneut zu starten.

## Archive hochladen und verarbeiten

Der Client lädt die angekündigten Archive nacheinander hoch:

```http
PUT /vMtextAdapter/sync2/8f73c1/archive/FIBASISF.tgz
Content-Type: application/gzip
Content-Length: 12345
```

Die Antwort enthält `auftrag_id` und den aktuellen `status`.
Bei einem neuen Auftrag sendet der Client die angekündigten Archive.
Wiederholte Uploads lösen keinen zweiten Verarbeitungslauf aus.

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
`serverSync/` ist die gemeinsame Synchronisationsbasis.

## Status, Ergebnis und Aufräumen

Für HTTP-Antworten mit 2xx gilt:

| Request | Antwort |
|---|---|
| POST, neuer Auftrag | Auftragsantwort mit `status: "ready"` |
| POST, bestehender Auftrag | Auftragsantwort mit aktuellem Status, auch `succeeded` oder `failed` |
| PUT | Auftragsantwort mit `uploading`, `processing`, `succeeded` oder `failed` |
| GET über ID oder Idempotenzkennung | Auftragsantwort mit aktuellem Status |
| DELETE | `{"status": "succeeded"}` als Löschbestätigung |

Ein PUT nach Verarbeitungsbeginn liefert den aktuellen Auftrag und startet
keine erneute Verarbeitung. HTTP-Fehler liefern bei allen Request-Typen
`{"message": "…"}` mit dem passenden Code aus der Fehlercodetabelle.

Die Auftragsantwort für POST, PUT und GET hat folgende Felder:

| Feld | Typ und Bedeutung |
|---|---|
| `auftrag_id` | nicht leerer String, ID des Auftrags |
| `status` | einer der unten aufgeführten Strings |
| `result` | optionaler JSON-Wert bei einem Endstatus, wenn eine M/Text-Ausgabe vorliegt |
| `message` | Fehlermeldung als String bei `failed` |

`auftrag_id` und `status` sind erforderlich. Aktive Aufträge liefern diese
beiden Felder, bei `failed` ist zusätzlich `message` erforderlich.
DELETE bestätigt den Löschvorgang mit `status: "succeeded"` ohne
Auftrags-ID. `result` enthält die M/Text-Ausgabe in einer Auftragsantwort.

| Status | Bedeutung |
|---|---|
| `ready` | Auftrag angelegt, wartet auf Uploads |
| `uploading` | Uploads noch nicht abgeschlossen |
| `processing` | Auftrag wird geprüft, wartet auf den Lock oder wird verarbeitet |
| `succeeded` | Verarbeitung erfolgreich beendet |
| `failed` | Prüfung oder Verarbeitung fehlgeschlagen |

```json
{"auftrag_id": "8f73c1", "status": "succeeded", "result": "M/Text-Ausgabe"}
```

```json
{"auftrag_id": "8f73c1", "status": "failed", "message": "M/Text-Synchronisation ist fehlgeschlagen"}
```

Der Client fragt mit `GET /sync2/{auftrag_id}` bis zu einem Endstatus ab.
Solange der Auftrag aktiv ist, wartet er zwischen Abfragen fünf Sekunden.
Liefert ein POST bereits `processing` oder einen Endstatus, entfallen die
Uploads.

Nach `succeeded` oder `failed` liest der Client das Ergebnis und sendet
`DELETE /sync2/{auftrag_id}`. Der Adapter entfernt die Auftragsdaten und
zugehörigen temporären Dateien einschließlich der Zuordnung des
Idempotency-Keys und bestätigt mit `{"status": "succeeded"}`.
Der Projektbestand unter `serverSync/` bleibt erhalten. Laut Zielbild
überleben Auftragsdaten keinen Adapter-Neustart.

DELETE ist auch in `ready` und `uploading` erlaubt. Dabei beendet der Adapter
die zugehörige Uploadannahme und verhindert einen anschließenden
Verarbeitungsstart. Statusprüfung und Löschen werden mit dem Wechsel zu
`processing` abgestimmt. In `processing` antwortet DELETE mit HTTP 409 und
lässt Verarbeitung und Lock bestehen.

HTTP 404 bei der Suche per Idempotenzkennung bedeutet, dass kein Auftrag
besteht. HTTP 409 beim Aufräumen vor einem Neustart führt zur erneuten
Statusabfrage. Andere HTTP-Fehler, Netzwerkfehler und ungültige Antworten beenden
den Clientlauf mit `ADAPTER_FAILED`. Das gilt auch bei fehlgeschlagenem DELETE.
Bei `failed` übernimmt der Client den Wert aus `message`, bei `succeeded` ein vorhandenes
`result`. Der Client legt dessen inhaltliches Format nicht fest.

## Java-Idee

| Klasse oder Komponente | Aufgabe |
|---|---|
| `SynchronisationController` | Anlage, Archivupload, Status und Löschen eines Auftrags bereitstellen |
| `SynchronisationsAuftraege` | Auftragsdaten, Uploadprüfung, Status und Ergebnis verwalten |
| `SynchronisationProcessor` | Projektbestand und M/Text-Aufruf unter dem Lock des Mandanten verarbeiten |
| `MtextRessourceSynchronisationService` | M/Text mit `serverSync/` aufrufen und das Ergebnis zurückgeben |

### Auftragsdaten und Antworten

```java
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
    private Object result;
    private String message;

    // Enthält die Dateien dieses Auftrags außerhalb von serverSync/.
    private Path uploadVerzeichnis;
}
```

### Auftragsverwaltung und Nebenläufigkeit

Der Adapter speichert jeden Auftrag unter seiner Auftrags-ID und merkt sich,
welche ID zu einem Idempotency-Key gehört. Im Beispiel verhindert `synchronized`,
dass mehrere HTTP-Anfragen gleichzeitig diese Daten lesen oder ändern.
So kann eine Anfrage den Auftrag erst lesen, wenn eine andere ihre Änderungen
einschließlich des Status abgeschlossen hat. Bei einem wiederholten POST
vergleicht der Adapter den Requestinhalt mit dem ursprünglich gespeicherten
Inhalt. Der Vergleich mit `equals` setzt voraus, dass die Requestklasse ihre
Feldwerte vergleicht.

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
public class SynchronisationController {
    private final SynchronisationsAuftraege auftraege;
    private final SynchronisationProcessor processor;

    @PostMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AuftragAntwort> create(
            @RequestHeader("Idempotency-Key") String idempotencyKey,
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

    @GetMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragAntwort search(
            @RequestHeader("Idempotency-Key") String idempotencyKey) {
        // Über die gespeicherte Schlüsselzuordnung lesen, bei unbekanntem Schlüssel HTTP 404.
        ...
    }

    @GetMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragAntwort status(@PathVariable("auftragId") String auftragId) {
        return auftraege.status(auftragId);
    }

    @DeleteMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, String> delete(@PathVariable("auftragId") String auftragId) {
        // In PROCESSING mit HTTP 409 ablehnen, sonst Auftrag und Schlüsselzuordnung entfernen.
        auftraege.auftragLoeschen(auftragId);
        return Map.of("status", "succeeded");
    }
}
```
