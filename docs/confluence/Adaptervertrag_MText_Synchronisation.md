# Idee für den Adaptervertrag der M/Text-Synchronisation

Diese Seite beschreibt den möglichen HTTPS-Upload als Transportmöglichkeit.
Die Auswahl des Transportwegs ist noch offen.

## Zweck der Variante

GitHub Actions überträgt die Projektpakete eines Synchronisationsauftrags per
HTTPS an den M/Text-Adapter. Der Adapter verarbeitet die Aufträge
nacheinander, startet die M/Text-Synchronisierung und stellt deren Ergebnis
bereit.

## Ziel

`mtext_actions` bestimmt den Adapter aus Releaselinie und Zielstufe:

```text
https://<Umgebungskennung>.ltoma.intern/vMtextAdapter/sync
```

Die Umgebungskennung legt die technische Linie und die Zielstufe fest.

## Ablauf

1. Der Workflow legt einen Auftrag an.
2. Der Adapter erzeugt die Auftrags-ID.
3. Der Workflow lädt die Dateien der angekündigten Projekte hoch.
4. Der Workflow schließt den Auftrag ab.
5. Der Adapter entpackt die Projektarchive in ein Auftragsverzeichnis unter
   dem gemeinsamen Pfad `serverSync/`.
6. Der Adapter synchronisiert dieses Verzeichnis nach M/Text.
7. Der Workflow fragt den Status bis zum Ergebnis ab und löscht danach den
   Auftrag.

Erfolgreiche Antworten enthalten ein JSON-Objekt. Anlage, Projektupload,
Abschluss und Statusabfrage liefern `auftrag_id` und `status`.

## Auftrag anlegen

Der Workflow sendet `POST /vMtextAdapter/sync`:

```http
Idempotency-Key: github-run-123456-Entwicklung
Content-Type: application/json
```

```json
{
  "kuerzel": "FI",
  "projekte": ["ProjektA", "ProjektB"]
}
```

Der `Idempotency-Key` besteht aus GitHub-Lauf und Zielstufe. Er bleibt bei einer
Wiederholung desselben Anlege-Requests gleich. Der Adapter gibt dann denselben
Auftrag mit seiner ursprünglichen Auftrags-ID und seinem aktuellen Status
zurück. Er setzt einen vorhandenen Auftrag nicht auf `uploading` zurück. Der
Workflow lädt deshalb nur dann Projektdateien hoch, wenn die Antwort
`uploading` enthält.

Der Adapter antwortet mit der Auftrags-ID:

```http
HTTP/1.1 201 Created
Location: /vMtextAdapter/sync/8f73c1
```

```json
{
  "auftrag_id": "8f73c1",
  "status": "uploading"
}
```

## Projektdateien hochladen

Der Workflow lädt jedes angekündigte Projekt mit einem eigenen Request hoch:

```http
PUT /vMtextAdapter/sync/8f73c1/projekte/ProjektA
Content-Type: multipart/form-data
```

Der Request enthält:

- `informationsdatei`: die JSON-Informationsdatei des Projekts
- `f_archiv`: das F-Archiv eines FULL, bei einem DELTA entfällt dieses Feld
- `d_archiv`: das D-Archiv

Das Projekt im URL-Pfad muss in der Projektliste des Auftrags enthalten sein.
Das Feld `projekt` der Informationsdatei muss mit diesem Pfad übereinstimmen.
Der Adapter nimmt den Request im Status `uploading` an. Er speichert die
Informationsdatei und die Archive zunächst als Upload dieses Projekts und
prüft die SHA-256-Prüfsummen aus der Informationsdatei. Fehlt dort
`stand.von`, handelt es sich um ein FULL und F- und D-Archiv müssen vorhanden
sein. Mit `stand.von` handelt es sich um ein DELTA und das D-Archiv muss
vorhanden sein. Erst ein vollständiger und geprüfter Upload ersetzt einen
bereits vorhandenen Upload desselben Projekts.

Der Adapter antwortet mit dem unveränderten Auftragsstatus:

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "auftrag_id": "8f73c1",
  "status": "uploading"
}
```

Der PUT-Request speichert das Projektpaket. Er startet weder das Entpacken noch
die M/Text-Synchronisation.

## Auftrag abschließen

Nach den Uploads sendet der Workflow:

```http
POST /vMtextAdapter/sync/8f73c1/complete
```

Der Adapter prüft, ob alle angekündigten Projekte und die zugehörigen Dateien
vorhanden und geprüft sind. Ein vollständiger Auftrag erhält den Status
`queued` und wird einmal in die Warteschlange aufgenommen. Eine wiederholte
Abschlussanfrage gibt den aktuellen Auftrag zurück und reiht ihn nicht erneut
ein. Fehlen Projektdateien, bleibt der Status `uploading` und der Adapter
antwortet mit HTTP 409.

Bei erfolgreichem Abschluss antwortet der Adapter:

```http
HTTP/1.1 200 OK
Content-Type: application/json
```

```json
{
  "auftrag_id": "8f73c1",
  "status": "queued"
}
```

## Reihenfolge

Der Adapter reiht abgeschlossene Aufträge in der Reihenfolge ihres Abschlusses
ein und verarbeitet pro M/Text-Ziel einen Auftrag zurzeit. Alle Projektuploads
eines Auftrags werden gemeinsam verarbeitet.

## Status

Der Workflow fragt den Auftrag alle fünf Sekunden ab:

```http
GET /vMtextAdapter/sync/8f73c1
```

| Status | Bedeutung |
|---|---|
| `uploading` | Der Auftrag nimmt Projektdateien entgegen |
| `queued` | Der vollständige Auftrag wartet auf seine Verarbeitung |
| `processing` | Die M/Text-Synchronisierung läuft |
| `succeeded` | M/Text hat den Auftrag erfolgreich verarbeitet |
| `failed` | Der Auftrag konnte nicht verarbeitet werden |

```json
{
  "auftrag_id": "8f73c1",
  "status": "queued"
}
```

Bei einem Fehler enthält die Antwort zusätzlich `meldung`. Der Workflow endet
bei `succeeded` erfolgreich und bei `failed` mit dieser Meldung.

## Aufräumen

Der Adapter löscht Upload- und Workspace-Dateien nach der Verarbeitung und
setzt anschließend `succeeded` oder `failed`. Auftragsstatus und
Idempotency-Key bleiben im Arbeitsspeicher, damit ein Wiederanlauf das Ergebnis
noch lesen kann.

Nachdem der Workflow den Endstatus gelesen hat, sendet er:

```http
DELETE /vMtextAdapter/sync/8f73c1
```

Der Adapter entfernt den Auftragsstatus und die Zuordnung des
Idempotency-Keys und bestätigt das Löschen:

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"ok": true}
```

DELETE ist für die Endzustände `succeeded` und `failed` vorgesehen. Bei einem
noch laufenden Auftrag antwortet der Adapter mit HTTP 409. Nach dem Löschen
liefert die Statusabfrage für diese Auftrags-ID HTTP 404. Derselbe
Idempotency-Key kann danach einen neuen Auftrag anlegen.

Kann der Workflow den Endstatus nicht lesen, bleibt der Auftrag bis zu einem
Wiederanlauf mit demselben `Idempotency-Key` oder bis zum nächsten
Adapter-Neustart erhalten.

## Fehlerantworten

Fehlerantworten enthalten eine kurze Meldung:

```json
{
  "meldung": "Projektdateien fehlen"
}
```

| HTTP-Status | Bedeutung |
|---|---|
| 400 | Request oder Projektpaket ist ungültig |
| 404 | Auftrag ist unbekannt |
| 409 | Request passt nicht zum aktuellen Auftragsstatus |

## Änderungen im Adapter

Die vorhandene M/Text-Anbindung kann für die Verarbeitung eines Auftrags
weiterverwendet werden. Der Adapter benötigt davor eine Auftragsverwaltung und
eine Warteschlange. Die vorhandenen Klassen übernehmen dabei folgende Aufgaben:

| Klasse oder Komponente | Aufgabe |
|---|---|
| `SynchronisationController` | Anlage, Upload, Abschluss, Status und Löschen eines Auftrags bereitstellen |
| `SynchronisationsAuftraege` | Auftrags-ID, Idempotency-Key, Projekte, Status, Meldung, Uploads und Workspace verwalten |
| `SynchronisationProcessor` | Abgeschlossene Aufträge nacheinander verarbeiten und ihren Status setzen |
| `MtextRessourceSynchronisationService` | Den vorbereiteten Workspace eines Auftrags mit M/Text synchronisieren |

Die folgenden Java-Ausschnitte zeigen eine mögliche Umsetzung. Klassen- und
Methodennamen können an die vorhandene Anwendung angepasst werden. Die
HTTP-Pfade, Feldnamen und Statuswerte richten sich nach dem Vertrag dieser
Seite.

### Auftragszustand

Ein Auftrag benötigt mindestens diese Angaben:

```java
public class SynchronisationsAuftrag {
    private String auftragId;
    private String idempotencyKey;
    private String kuerzel;
    private Set<String> projekte;
    private Map<String, ProjektUpload> uploads;
    private SynchronisationsStatus status;
    private String meldung;
    private Path auftragsverzeichnis;
}

public enum SynchronisationsStatus {
    UPLOADING,
    QUEUED,
    PROCESSING,
    SUCCEEDED,
    FAILED
}
```

Die JSON-Ausgabe der Statuswerte muss in Kleinbuchstaben erfolgen. Die
Auftragsverwaltung ordnet einen `Idempotency-Key` einem Auftrag zu. Bei einem
erneuten Anlege-Request mit demselben Schlüssel gibt sie diesen Auftrag zurück.
Statuswechsel und die Zuordnung des Schlüssels müssen auch bei parallelen
Requests konsistent bleiben. Auftragsdaten und Idempotency-Keys werden im
Arbeitsspeicher gehalten. Nach einem Adapter-Neustart überträgt ein erneut
gestarteter Workflow die Projektdateien als neuen Auftrag.

### Controller

Der Controller führt die M/Text-Synchronisation nicht im HTTP-Request aus. Er
übergibt Anlage, Upload und Statuswechsel an die Auftragsverwaltung:

```java
@RestController
@RequestMapping("sync")
public class SynchronisationController {
    private final SynchronisationsAuftraege auftraege;
    private final SynchronisationProcessor processor;

    @PostMapping(produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<AuftragResponse> create(
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @RequestBody AuftragAnlegenRequest request) {
        SynchronisationsAuftrag auftrag =
                auftraege.createOrFind(idempotencyKey, request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .header(HttpHeaders.LOCATION, "/vMtextAdapter/sync/" + auftrag.getAuftragId())
                .body(AuftragResponse.from(auftrag));
    }

    @PutMapping(
            path = "/{auftragId}/projekte/{projekt}",
            consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragResponse uploadProject(
            @PathVariable String auftragId,
            @PathVariable String projekt,
            @RequestPart("informationsdatei") MultipartFile informationsdatei,
            @RequestPart(value = "f_archiv", required = false) MultipartFile fArchiv,
            @RequestPart("d_archiv") MultipartFile dArchiv) {
        return AuftragResponse.from(
                auftraege.saveProject(
                        auftragId, projekt, informationsdatei, fArchiv, dArchiv));
    }

    @PostMapping(path = "/{auftragId}/complete", produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragResponse complete(@PathVariable String auftragId) {
        boolean neuAbgeschlossen = auftraege.complete(auftragId);
        if (neuAbgeschlossen) {
            processor.enqueue(auftragId);
        }
        return AuftragResponse.from(auftraege.get(auftragId));
    }

    @GetMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public AuftragResponse status(@PathVariable String auftragId) {
        return AuftragResponse.from(auftraege.get(auftragId));
    }

    @DeleteMapping(path = "/{auftragId}", produces = MediaType.APPLICATION_JSON_VALUE)
    public Map<String, Boolean> delete(@PathVariable String auftragId) {
        auftraege.deleteCompleted(auftragId);
        return Map.of("ok", true);
    }
}
```

`saveProject` akzeptiert angekündigte Projekte im Status `uploading`.
Die Methode speichert die Multipart-Dateien zunächst getrennt vom bisherigen
Upload des Projekts, prüft die SHA-256-Prüfsummen und ersetzt danach den
bisherigen Upload. `complete` prüft die angekündigten Projekte und setzt
den Status auf `queued`. Der Statuswechsel erfolgt einmalig, damit eine
wiederholte Anfrage denselben Auftrag nicht erneut einreiht.
`deleteCompleted` akzeptiert die Endzustände `succeeded` und
`failed` und entfernt Auftrag und Idempotency-Key.

### Workspace vorbereiten

Die gespeicherten Multipart-Dateien sind noch kein M/Text-Workspace. Vor der
Synchronisation erzeugt der Adapter für den Auftrag ein leeres
Workspace-Verzeichnis unter `serverSync/` und entpackt die Archive aller
Projekte dort hinein. Bei einem FULL wird zuerst das F-Archiv und anschließend
das D-Archiv entpackt. Bei einem DELTA wird das D-Archiv entpackt. Die
Informationsdatei wird nicht in den Workspace kopiert.

`serverSync/` liegt auf einem NFS-Share, das auf dem gemeinsamen Server von
Adapter und M/Text eingehängt ist. Beide Anwendungen greifen dadurch unter
demselben Pfad auf den Workspace zu.

Eine mögliche Aufteilung in der Auftragsverwaltung ist:

```java
public Path createWorkspace(String auftragId) throws IOException {
    SynchronisationsAuftrag auftrag = get(auftragId);
    Path workspace = createWorkspaceDirectory(auftrag);

    for (String projekt : auftrag.getProjekte()) {
        ProjektUpload upload = auftrag.getUpload(projekt);
        if (upload.getFArchiv() != null) {
            unpackArchive(upload.getFArchiv(), workspace);
        }
        unpackArchive(upload.getDArchiv(), workspace);
    }
    return workspace;
}
```

Die Archive enthalten bereits die projektbezogenen Verzeichnisse und beim
D-Archiv die zugehörige Löschliste. Alle angekündigten Projekte landen dadurch
in demselben Workspace, den ein M/Text-Aufruf verarbeitet.

### Warteschlange und Verarbeitung

Ein Executor mit einem Worker stellt die Reihenfolge pro Adapter und damit pro
M/Text-Ziel sicher:

```java
@Bean("mtextSyncExecutor")
public Executor mtextSyncExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(1);
    executor.setMaxPoolSize(1);
    executor.initialize();
    return executor;
}
```

Der Processor setzt den Status vor und nach dem vorhandenen blockierenden
M/Text-Aufruf:

```java
@Component
public class SynchronisationProcessor {
    private final Executor executor;
    private final SynchronisationsAuftraege auftraege;
    private final MtextRessourceSynchronisationService synchronisationService;

    public void enqueue(String auftragId) {
        executor.execute(() -> process(auftragId));
    }

    private void process(String auftragId) {
        auftraege.processing(auftragId);
        String meldung = null;
        try {
            Path workspace = auftraege.createWorkspace(auftragId);
            synchronisationService.synchronize(workspace);
        } catch (Exception exception) {
            meldung = exception.getMessage();
        }

        auftraege.deleteFiles(auftragId);
        if (meldung == null) {
            auftraege.succeeded(auftragId);
        } else {
            auftraege.failed(auftragId, meldung);
        }
    }
}
```

Der für `executor` verwendete Bean ist der einreihige `mtextSyncExecutor`. Das
Einreihen darf den HTTP-Request nicht bis zum Ende der M/Text-Synchronisation
blockieren.

### Vorhandenen M/Text-Aufruf verwenden

Der M/Text-Service erhält das vorbereitete Workspace-Verzeichnis als Parameter.
Die konfigurierte URL zeigt dadurch auf dessen entpackten Inhalt:

```java
public void synchronize(Path workspaceVerzeichnis)
        throws MTextException, IOException {
    MTextActivationServer server = MTextFactory.connect(
            mtextConfig.getTechnicalUser(),
            mtextConfig.getTechnicalUserPassword(),
            null);

    ActivationConfigurationFactory factory =
            (ActivationConfigurationFactory) server.getConfigurationFactory();
    Configuration configuration = factory.newSynchronizationConfiguration();
    configuration.put("url", workspaceVerzeichnis.toUri().toString());
    configuration.put("testRun", false);
    configuration.put("completePackageMode", false);
    configuration.put("mirrorProjectDeletions", true);

    server.writeRepositorySynchronisationScript(
            new ClassPathResource("mtextserverconfig/sync_local.xml").getInputStream());
    server.synchroniseRepositoryBlocking(configuration);
    server.refreshServerCache(MTextActivationServer.ServerCacheType.RESOURCES);
}
```

`sync_local.xml` setzt die Property `workspaceDir` auf den Wert der
Property `repositoryUrl`. M/Text stellt dafür den mit
`configuration.put("url", ...)` gesetzten Synchronisationsparameter bereit.
Dieser verweist in der vorhandenen Implementierung auf das Verzeichnis
`serverSync/`. Für einen Auftrag verweist er auf dessen entpackten Workspace
unter diesem gemeinsamen Pfad.

Der Auftrag erhält `succeeded`, wenn `synchroniseRepositoryBlocking` und die
anschließende Cache-Aktualisierung ohne Exception beendet werden. Die von
M/Text zurückgegebenen Dokumentzustände werden nicht ausgewertet. Eine
Exception setzt den Auftrag auf `failed` und wird als `meldung` bereitgestellt.
