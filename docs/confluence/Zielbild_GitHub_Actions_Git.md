# Zielbild für die Ablösung von Jenkins und SVN

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in GitHub verprobt. Während
dieser Testphase bleibt der bisherige Prozess produktiv. Unmittelbar vor der
für Januar 2027 geplanten Produktivsetzung wird der dann freigegebene
SVN-Endstand nach Git übertragen. Danach sind Git und GitHub Actions für diesen
Prozess führend und SVN wird zusammen mit der EN4920 abgebaut.

Jeder Mandant erhält ein eigenes Repository mit seinen M/Text-Ressourcen und
seiner Konfiguration. Die gemeinsame Automatisierung liegt im zentralen
Repository `mtext-actions`. So bleiben die Mandantendaten getrennt, während
alle Mandanten dieselben geprüften Abläufe verwenden.

Eine Änderung durchläuft weiterhin die drei Prozess-Stages Entwicklung,
Abnahme und Bereitstellung für die Lieferung.

Der generelle Ablauf ist:

```text
lokale Änderungen committen
    │ Push
    ▼
GitHub Rnnn/Entwicklung ──→ M/Text-Entwicklung synchronisieren
    │                    (z. B. en01e.ltoms.intern)
    │ ausgewählte Commits per Cherry-Pick übernehmen
    ▼
lokaler Rnnn/Abnahme
    │ Push
    ▼
GitHub Rnnn/Abnahme ──→ M/Text-Abnahme synchronisieren
    │                (z. B. en01a.ltoms.intern)
    │ abgenommene Commits per Cherry-Pick übernehmen
    ▼
lokaler Rnnn/Bereitstellung
    │ Push
    ▼
GitHub Rnnn/Bereitstellung ──→ noch keine Lieferung
    │ Release-Tag erstellen und gezielt pushen
    ▼
Paketbau und Mainframe-Übergabe
```

## 2. Zielarchitektur

Die Lösung besteht aus vier Bereichen:

| Bereich | Verantwortung |
|---|---|
| Mandanten-Repository | M/Text-Ressourcen, Mandantenkonfiguration und Workflow-Trigger |
| Automatisierungs-Repository `mtext-actions` | Prüfungen, Synchronisation, Paketbau und Mainframe-Übergabe |
| GitHub Actions | Ausführung der Abläufe, Protokollierung |
| GitHub-Actions-Runner (FI) | Ausführung der Workflows auf dem offiziell verfügbaren Runnerangebot der FI |

Ein Mandanten-Repository enthält seine M/Text-Briefressourcen und die für GitHub
relevante Konfiguration. Das zentrale Automatisierungs-Repository
`mtext-actions` enthält die gemeinsam verwendete Automatisierung.

Mandanten-Repositories dürfen die wiederverwendbaren Workflows über eine
GitHub-Actions-Zugriffsrichtlinie aufrufen. Die Logs der aufgerufenen Jobs sind
im Mandanten-Repository sichtbar und enthalten deshalb weder Secrets noch
unnötige interne Details.

Die Administratoren legen die Berechtigungsregeln für GitHub Actions fest.
GitHub erzeugt für jeden Job ein `GITHUB_TOKEN` mit den daraus resultierenden
Rechten.

Die Text-Entwickler bearbeiten Briefressourcen in der M/Text Workbench und
nutzen den integrierten Git-Client für alle Aktionen, einschließlich
Cherry-Picking und dem Erstellen von Release-Tags. GitHub im Browser dient für
Laufkontrolle, Wiederholungen und die Prüfung von Release-Tags. Für die
tägliche Arbeit ist keine Git-Kommandozeile nötig.

Jeder Mandant benennt ein Mandanten-Release-Team für den
Bereitstellungsbranch und die Release-Tags. Die Verantwortlichen können sich
je Mandant unterscheiden.

Für jeden Lauf checkt GitHub Actions sowohl den ausgewählten Stand des
Mandanten-Repositories als auch eine festgelegte `mtext-actions`-Version aus.
Dadurch ist später nachvollziehbar, welche Quellen und
welche Automatisierung tatsächlich verwendet wurden.

### M/Text-Transport nach `serverSync`

Der heutige Ablauf stellt die zu synchronisierenden Ressourcen zuerst über ein
NFS-Share unter `serverSync` bereit. Danach sendet er einen POST-Request an den
M/Text-Adapter (LTOMA), der die interne Synchronisation mit dem M/Text-Server
(LTOMS) anstößt. Dieser Ablauf ist die Ausgangslage. Der künftige Transportweg
ist noch nicht festgelegt.

Unabhängig vom Transportweg entsteht für jedes synchronisierte Projekt auf
`serverSync` derselbe vollständige Verzeichnisbaum mit denselben relativen
Pfaden, Dateinamen und Dateiinhalten wie im bisherigen Jenkins-/SVN-Verfahren.
Der Workflow bereitet diesen Stand zunächst in einem temporären
Staging-Verzeichnis des Runners vor. Die drei Transportwege verwenden damit
denselben fachlichen Inhalt.

Für die Übertragung per PUT oder über den Artefaktspeicher von GitHub Actions
erzeugt der Workflow aus dem Staging-Verzeichnis ein ZIP-Transportpaket, in
dem direkt die Projektverzeichnisse liegen:

```text
serverSync-R261-Entwicklung-<Commit-SHA>.zip
  LOMS_Basis[BY]/
    <vollständiger Projektbaum>
  LOMS_Autonom[BY]/
    <vollständiger Projektbaum>
```

Dasselbe ZIP-Transportpaket dient als PUT-Nutzlast oder als Inhalt eines
GitHub-Actions-Artefakts. Ein GitHub-Actions-Artefakt speichert Dateien eines
Workflow-Laufs im GitHub-Artefaktspeicher. Der Workflow legt seinen Namen,
seine Aufbewahrungsfrist und die darin gespeicherten Dateien fest. GitHub
vergibt unter anderem die Artefakt-ID und regelt Speicherung, Berechtigung und
Download. Der Download erfolgt über die GitHub-API. LTOMA entpackt die
GitHub-Verpackung und erhält daraus das ursprüngliche ZIP-Transportpaket.

Die Veröffentlichung erfolgt erst, nachdem der gesamte Projektstand erfolgreich
übertragen wurde. Mehrere Mandanten-Repositories teilen sich `serverSync`.

Für die Versorgung von `serverSync` werden drei mögliche Varianten geprüft:

| Variante | Ablauf | Zu klären | Implementierungsaufwand |
|---|---|---|---|
| PUT an den Adapter | Der Workflow erzeugt das ZIP-Transportpaket und sendet diese Datei als Payload eines PUT-Requests an den Adapter. Der Adapter prüft und entpackt es, veröffentlicht die enthaltenen Projektverzeichnisse unter `serverSync` und startet die interne Synchronisation. | HTTP-Vertrag, Authentifizierung, Größenlimits, Prüfsummen, Zeitgrenzen, Wiederholung, Parallelität und Erfolgsstatus | mittel bis hoch |
| Direkter Sharezugriff des Runners | Der Runner stellt den vorbereiteten Verzeichnisbaum direkt auf dem NFS-/Netzlaufwerk des M/Text-Servers bereit und ruft erst danach den Adapter auf. Das ZIP-Transportpaket wird für diesen Weg nicht benötigt. Staging, Veröffentlichung und Wiederanlauf liegen damit in der GitHub-Automatisierung. Diese Variante entspricht dem aktuellen Entwicklungsstand. | Verfügbarkeit und Einbindung des Shares, Pfad, Rechte, Kapazität, atomare Ersetzung, Schutz vor parallelen Schreibvorgängen und Bereinigung nach Fehlern | gering |
| Download aus dem Artefaktspeicher von GitHub Actions | Der Workflow erzeugt dasselbe ZIP-Transportpaket wie in der PUT-Variante und lädt es als Datei in den GitHub-Actions-Artefaktspeicher. LTOMA oder LTOMS lädt diese Datei herunter, prüft und extrahiert sie unter `serverSync` und startet die interne Synchronisation. | Zuständige Zielkomponente, eindeutige Identifikation durch Repository, Workflow-Lauf und Artefakt-ID, technische Identität mit `Actions: read`, Prüfsumme, Erreichbarkeit, Aufbewahrungsfrist, Wiederholung und Bereinigung | mittel |

Vor dem nichtproduktiven Integrationslauf wird genau eine Variante ausgewählt.
Die Entscheidung berücksichtigt Netzwerk- und Sicherheitsvorgaben,
Betriebsverantwortung, Datenmengen und Laufzeiten, atomare Veröffentlichung,
Parallelität, Wiederanlauf und Nachvollziehbarkeit. Implementiert wird nur der
ausgewählte Weg.

## 3. Repositories und aktueller Entwicklungsstand

Ein Mandanten-Repository folgt diesem Grundaufbau:

```text
mtext-<mandant>/
  .github/
    config.json
    workflows/
      validate-config.yml
      sync-resources.yml
      release.yml
  <M/Text-Projekte>
```
`mtext-fi` dient als Muster für die Mandanten-Repositories. Alle sichtbaren
Verzeichnisse in der Repositorywurzel werden synchronisiert und in
Releasepakete aufgenommen. Verzeichnisse wie `LOMS_Testdaten` können über
`.github/config.json` von der Synchronisation und den Releasepaketen
ausgeschlossen werden, aber trotzdem Bestandteil des von Git verwalteten
Repositories sein. Mit `.gitignore` können Dateien generell ausgeschlossen
werden.

Im Mandanten-Repository stehen kleine Trigger-Workflows. Die eigentlichen
Arbeitsschritte liegen in `mtext-actions`. Bei der Einrichtung und bei späteren
Updates informiert der `update-mandant-workflow` die Trigger-Workflows darüber,
welche Version von `mtext-actions` zu verwenden ist.

Das zentrale CI/CD-Repository enthält die wiederverwendbaren Workflows, die
gemeinsame Python-Anwendung, die zentrale Releaselinien- und
Mandantenzuordnung, das JCL-Template und die Tests:

```text
mtext-actions/
  .github/
    workflows/
      ci.yml
      reusable-release.yml
      reusable-sync-resources.yml
      reusable-validate-config.yml
      update-mandant-workflow.yml
  config/
    mandanten.json
    releaselinien.json
  scripts/
    runner-preflight.sh
  src/
    build_release.py
    publish_mainframe.py
    sync_resources.py
    validate_config.py
    workflow_configuration.py
    lbs_delivery/
  templates/
    mainframe-upload.jcl
  tests/
```
Hier ist `lbs_delivery` das zentrale Python-Modul, das diverse Funktionen wie
Fehlercodes, Git-Funktionen und Paketbau kapselt, die von den eigentlichen
Workflow-Skripten benutzt werden.

Vor dem ersten Integrationslauf werden Runner-Kennzeichen und zentrale
Workflowversion finalisiert. Die noch ausstehenden Einrichtungs- und
Abnahmepunkte stehen in [Nächste Schritte](./Naechste_Schritte.md).

## 4. GitHub-Konfiguration

Für Planung und Abnahme ist GitHub Enterprise Server ab Version 3.20.4 als
Zielplattform festgelegt. Die folgenden Einstellungen definieren den
gewünschten Zielzustand.

### Repositories und Zugriffe

| Gegenstand | Zielzugriff |
|---|---|
| Mandanten-Repositories | Für jeden Mandanten besteht ein eigenes Repository. |
| Zentrales Repository | `mtext-actions` ist privat und nur für das zentrale Automatisierungsteam der FI direkt zugänglich. |
| Default Branch | Der Entwicklungsbranch der führenden Releaselinie – zunächst `R261/Entwicklung` – wird beim Wechsel der führenden Linie angepasst. |
| Mandanten-Release-Team | Der benannte Verantwortlichenkreis, der die Mandantenkonfiguration in `.github/config.json` ändern, nach `Rnnn/Bereitstellung` pushen sowie Release-Tags anlegen darf. |

### Schutzregeln für Branches, Pfade und Tags

| Schutzbereich | Regel |
|---|---|
| `Rnnn/Entwicklung` und `Rnnn/Abnahme` | Berechtigte Text-Entwickler dürfen pushen. Force-Pushes und das Löschen der Branches sind gesperrt. |
| `Rnnn/Bereitstellung` | Reguläre Pushes sind auf das Mandanten-Release-Team begrenzt. Force-Pushes und das Löschen des Branches sind gesperrt. |
| `.github/workflows/**/*` | Ein Push-Ruleset schützt die zentral vorgegebenen Aufrufdateien auf allen Branches. |
| `.github/config.json` | Eine Pfadregel trennt Änderungen der Mandantenkonfiguration von der normalen Ressourcenpflege. |
| Tags `Rnnn.nnn` | Nur das Mandanten-Release-Team darf passende Tags erstellen oder löschen. |

### Environments und Secrets

Ein GitHub Environment bildet eine Zielstufe ab und enthält alle dafür
geltenden Schutzregeln, etwa zulässige Branches oder Tags und erforderliche
Freigaben. Seine Secrets stehen Jobs zur Verfügung, die an dieses Environment
gebunden sind und dessen Schutzregeln erfüllen.

| Environment | Verwendung und Schutz |
|---|---|
| `Einrichtung` | Wird ausschließlich vom manuell gestarteten Einrichtungsworkflow in `mtext-actions` gebunden. Es stellt nach Freigabe das auf die vorgesehenen Repositories begrenzte technische Token für die Workflowänderungen bereit. |
| `Bereitstellung` | Wird ausschließlich vom Publish-Job gebunden. Eine berechtigte Person muss die Mainframe-Übergabe manuell freigeben. Ein verpflichtendes Vier-Augen-Prinzip oder eine Sperre der Selbstfreigabe ist nicht vorgesehen. Nur zulässige Release-Tags dürfen dieses Environment verwenden. |

Die Mainframe-Zugangsdaten `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und
`MAINFRAME_FTP_PASSWORD` liegen als Secrets im Environment
`Bereitstellung`. Sie werden weder in Git gespeichert noch an den Build-Job
übergeben.

### GitHub Actions und Ausführung

Nach abgeschlossener Einrichtung gelten für die Ausführung der Workflows die
folgenden technischen Festlegungen:

| Gegenstand | Ergebnis der Einrichtung |
|---|---|
| Zentrale Workflowversion | Jeder Aufruf verwendet die für seinen Rollout festgelegte Version von `mtext-actions`. |
| Aktualisierungsberechtigung | Der Mandanten-Aktualisierungsworkflow erhält über das Environment `Einrichtung` das Secret `WORKFLOW_CONFIGURATION_TOKEN`. |
| Runnerangebot der FI | Die Jobs verwenden einen offiziell von der FI bereitgestellten GitHub-Actions-Runner. Das zugehörige `runs-on`-Kennzeichen wird aus dem Runnerangebot der FI übernommen und in den zentralen Workflows fest eingetragen. |
| Laufzeitvorbereitung | `runner-preflight.sh` ist der gemeinsame Einstieg in die Python-Automatisierung. Es setzt die versionierte Laufzeitvorgabe aus `.python-version` durch. Dadurch laufen alle Workflows mit derselben technischen Voraussetzung. |
| Logs | Ausgaben wiederverwendbarer Workflows sind im Mandanten-Repository sichtbar. |
| Artefakte | Releaseartefakte werden standardmäßig 30 Tage aufbewahrt. Ihre Namen enthalten Repository und Release-Tag. |

### Aktualisierung der Trigger-Workflows

Ein neuer Commit in `mtext-actions`, zum Beispiel weil sich die Releaselinien
ändern, ist nicht automatisch in den Mandanten-Repositories verfügbar, da
deren Trigger-Workflows erst einmal auf eine vorherige Version zeigen. Der
Commit wird deshalb über einen manuell zu startenden Batchlauf **Update
mandant workflows** auf alle in `config/mandanten.json` konfigurierten
Mandanten-Repositories und deren Branches verteilt. Bei der Initialisierung
der Mandanten-Repositories zeigen deren Trigger-Workflows noch auf keine
Version und müssen ebenfalls durch diesen Batch-Workflow eingerichtet werden.

Vor dem ersten Lauf wird im Repository `mtext-actions` das
`runs-on`-Kennzeichen des verwendeten FI-Runners als Repositoryvariable
`FI_RUNNER_LABEL` hinterlegt. Dort wird außerdem das Environment `Einrichtung`
eingerichtet und darin das Secret `WORKFLOW_CONFIGURATION_TOKEN` hinterlegt.
Das Token gehört zu einer technischen Identität, die Workflowdateien in
`mtext-actions` und den Mandanten-Branches festschreiben darf. Anschließend
wird der Batch-Workflow in GitHub manuell gestartet. Als Eingabe wird die SHA
des auszurollenden Commits angegeben.

Der Mandanten-Commit ändert nur `.github/workflows` und löst wegen seiner
Skip-Anweisung keine M/Text-Synchronisation oder Releaseverarbeitung aus.
Fehler in einer Verarbeitung brechen die übrigen Aktualisierungen nicht ab.
Ein erneuter Lauf ist idempotent und erzeugt auf bereits aktuellen Branches
keinen zusätzlichen Commit.

Falls das Runner-Kennzeichen bei der erstmaligen Einrichtung noch
nicht im zentralen Workflowstand enthalten ist, übernimmt der Vorbereitungsjob
es mit einem Commit und verwendet dessen SHA als Rollout-SHA.

## 5. Branches, Weitergabe und Auslöser

Jede aktive Releaselinie besitzt drei Branches, zum Beispiel:

```text
R261/Entwicklung
R261/Abnahme
R261/Bereitstellung
```

Damit ist aus jedem Branchnamen eindeutig erkennbar, zu welcher Releaselinie
und Stage er gehört. Ein gemeinsamer Branch je Stage mit mehreren
Releaseverzeichnissen, wie er in SVN verwendet wurde, wird nicht fortgeführt.

Für größere oder gemeinsam bearbeitete Änderungen kann ein Feature-Branch
verwendet werden. Er löst keine Verteilung aus. Kleine Änderungen dürfen auch
direkt auf dem Entwicklungsbranch entstehen. Ein Feature-Branch ist keine
zusätzliche Stage des Freigabeprozesses.

Ein Push nach `Rnnn/Entwicklung` oder `Rnnn/Abnahme` startet automatisch die
M/Text-Verteilung für die entsprechende Stage. Beim Übergang zur nächsten
Stage wird eine fachlich ausgewählte Änderung per Cherry-Pick übernommen. Der
Cherry-Pick erzeugt auf dem Zielbranch einen neuen Commit mit einer neuen SHA.
Weitergegeben wird dieselbe Änderung, nicht derselbe Commit. Ob die
Releaselinie fachlich eingerichtet ist, entscheidet die zentrale
Releaselinienzuordnung.

Ein Push nach `Rnnn/Bereitstellung` erzeugt noch keine Lieferung. Erst ein Tag
im Format `Rnnn.nnn` startet den Paketbau. Dabei wird geprüft, ob der Tag zur
angegebenen Releaselinie gehört und vom Bereitstellungsbranch erreichbar ist.
Der Tag wird als Git-Tag angelegt und einzeln gepusht. Ein GitHub Release wird
nicht erzeugt. Wurde ein Tag irrtümlich angelegt, wird der dadurch gestartete
Workflow-Lauf vor dem Löschen oder Korrigieren des Tags abgebrochen.

Manuelle Wiederholungen eines Workflows sind möglich, müssen aber denselben
Commit verwenden. Vor einer erneuten M/Text-Verteilung prüft der Workflow, ob
dieser Commit zum ausgewählten Branch gehört.

### Neue Releaselinie einrichten

Eine neue Linie erhält drei Branches, je einen für Entwicklung, Abnahme und
Bereitstellung, sowie einen Eintrag in `config/releaselinien.json`. Der Eintrag
enthält die fachliche Releaselinie, die technische ETAPS-Linie und den Namen
eines in `.github/config.json` vorhandenen Hostprofils. Die JCL-Werte stammen
aus der Mandantenkonfiguration und dem zugeordneten Hostprofil. Die Zuordnung
wird rollierend gepflegt: Beim Aufnehmen einer neuen Releaselinie wird die
ausgeschiedene Zuordnung entfernt, sodass immer drei aktive Releaselinien
enthalten sind.

Ausgangspunkt der neuen Branches ist normalerweise der letzte Release-Tag der
bisherigen Linie. Dessen vollständiger Projektstand wird über den manuellen
Sync-Workflow einmal nach Entwicklung und einmal nach Abnahme übertragen und
anschließend in M/Text fachlich geprüft.

## 6. Workflows, Trigger und Abhängigkeiten

Die Mandanten-Repositories enthalten nur die fachlichen Auslöser. Sie rufen
fest gepinnte wiederverwendbare Workflows aus `mtext-actions` auf. Die
eigentliche Fachlogik liegt in Python.

Ein Ereignis im Mandanten-Repository startet dessen Trigger-Workflow, über den
GitHub die fest gepinnte Workflowdatei aus `mtext-actions` lädt und ihre Jobs auf
dem Runner des Mandanten-Workflows ausführt. Der Runner checkt den festgelegten
Commit des Mandanten-Repositories nach `source/` und
`mtext-actions@automation_ref` nach `automation/` aus und führt anschließend den
Python-Code aus. Weitere Informationen stehen in `workflows/README.md` in den
Mandanten-Repositories.

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Trigger-Workflow | Zentraler Workflow | Python-Kommando | Ergebnis |
|---|---|---|---|---|---|
| Workflowdateien einrichten oder `mtext-actions`-Version ausrollen | Manueller Batchstart in `mtext-actions` mit freigegebener vollständiger SHA | keiner | `update-mandant-workflows.yml` | `python -m workflow_configuration` | Zentrale Runnerwerte und alle Mandanten-Pins auf dieselbe Rollout-SHA geprüft und festgeschrieben |
| Mandantenkonfiguration prüfen | Push mit Änderung an `.github/config.json` auf einen Branch | `validate-config.yml` | `reusable-validate-config.yml` | `validate_config.py` | Konfiguration geprüft |
| Entwicklung synchronisieren | Push nach `Rnnn/Entwicklung` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync_resources.py` | Vollständiger Projektstand des Ziel-Commits nach M/Text-Entwicklung synchronisiert |
| Abnahme synchronisieren | Push eines per Cherry-Pick übernommenen Commits nach `Rnnn/Abnahme` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync_resources.py` | Vollständiger Projektstand des Ziel-Commits nach M/Text-Abnahme synchronisiert |
| Bereitstellungsstand fortschreiben | Cherry-Pick und Push nach `Rnnn/Bereitstellung` | keiner | keiner | keines | Nur Git-Branch fortgeschrieben. Noch keine Lieferung |
| Release bauen und übergeben | Push eines Tags `Rnnn.nnn` oder manueller Start mit vorhandenem Tag | `release.yml` | `reusable-release.yml` | `build_release.py`, danach `publish_mainframe.py` | FULL/DELTA gebaut, geprüft und per FTP/JES übergeben |
| `mtext-actions` testen | Pull Request in `mtext-actions` oder Push auf dessen `main` | entfällt | `ci.yml` | `unittest discover` | Zentrale Testfälle und Workflowverträge geprüft |

### Mandantenseitige Trigger-Workflows

| Datei | Trigger | Aufgabe |
|---|---|---|
| [`validate-config.yml`](../../mtext-fi/.github/workflows/validate-config.yml) | Push mit Änderung an `.github/config.json` | Prüfung der Mandantenkonfiguration starten |
| [`sync-resources.yml`](../../mtext-fi/.github/workflows/sync-resources.yml) | Push nach Entwicklung oder Abnahme sowie manueller Start | Ressourcensynchronisation für die Zielstufe starten |
| [`release.yml`](../../mtext-fi/.github/workflows/release.yml) | Release-Tag sowie manueller Start | Releaseverarbeitung starten |

### Zentrale Workflows

| Datei | Trigger | Aufgabe |
|---|---|---|
| [`update-mandant-workflows.yml`](../../mtext-actions/.github/workflows/update-mandant-workflows.yml) | Manueller Start | Alle vorgesehenen Mandantenbranches auf den `mtext-actions`-Commit aktualisieren |
| [`reusable-validate-config.yml`](../../mtext-actions/.github/workflows/reusable-validate-config.yml) | Aufruf durch `validate-config.yml` | Mandantenkonfiguration prüfen |
| [`reusable-sync-resources.yml`](../../mtext-actions/.github/workflows/reusable-sync-resources.yml) | Aufruf durch `sync-resources.yml` | M/Text-Server synchronisieren |
| [`reusable-release.yml`](../../mtext-actions/.github/workflows/reusable-release.yml) | Aufruf durch `release.yml` | Releasepakete erstellen und an den Mainframe übergeben |
| [`ci.yml`](../../mtext-actions/.github/workflows/ci.yml) | Pull Request oder Push auf `main` in `mtext-actions` | Tests in `mtext-actions` ausführen |

## 7. Konfigurationsdateien

### config.json

Die Datei `.github/config.json` in den Mandanten-Repositories ist ein
versionierter Bestandteil des Lieferstands und enthält einen mandant-Block mit
folgenden Feldern:

| Feld | Bedeutung und Regel |
|---|---|
| `kuerzel` | Bekanntes Mandantenkürzel für Paketnamen und Fragmentprojekte |
| `ispw` | CodePipeline-Instanz `T` für Test oder `P` für Produktion. Standard ist `P` |
| `excluded_projects` | Optionale Liste sichtbarer Projektverzeichnisse, die weder synchronisiert noch paketiert werden |
| `hostprofile` | Ein oder mehrere frei benannte Hostprofile mit `assignment` und `stage` |

#### Beispielhafte .github/config.json

```json
{
  "mandant": {
    "kuerzel": "FI",
    "ispw": "P",
    "excluded_projects": [
      "LOMS_Testdaten"
    ],
    "hostprofile": {
      "FKT": {
        "assignment": "LOMS000066",
        "stage": "FKTE"
      },
      "JUR": {
        "assignment": "LOMS000067",
        "stage": "JURP"
      }
    }
  }
}
```

### mandanten.json

Die folgende Tabelle listet die aktuell bekannten Projekte, die in GitHub
versioniert und paketiert werden. Weitere Projekte können aufgenommen werden,
ohne dass dafür Workflows oder Konfigurationen geändert werden müssen. Eine
Abweichung von diesem Soll-Stand wird aber mit Warnungen im Workflow-Log
gekennzeichnet. Die Zuordnung von Mandant zu Repository wird in `mtext-actions`
unter `config/mandanten.json` zentral gepflegt.

| Repository | Mandantenkürzel | Projekte |
|---|---|---|
| `<oms_team>/mtext-fi` | `FI` | `Configuration`, `Fonts`, `LOMS_Framework`, `LOMS_Basis`, `LOMS_PKA` |
| `<oms_team>/mtext-autonom` | `IT` | `LOMS_Autonom` |
| `<oms_team>/mtext-by` | `BY` | `LOMS_Basis[BY]`, `LOMS_Autonom[BY]` |
| `<oms_team>/mtext-lh` | `LH` | `LOMS_Basis[LH]`, `LOMS_Autonom[LH]` |
| `<oms_team>/mtext-nw` | `NW` | `LOMS_Basis[NW]`, `LOMS_Autonom[NW]` |
| `<oms_team>/mtext-os` | `OS` | `LOMS_Basis[OS]`, `LOMS_Autonom[OS]` |
| `<oms_team>/mtext-sa` | `SA` | `LOMS_Basis[SA]`, `LOMS_Autonom[SA]` |

### releaselinien.json

Die zentrale Datei `config/releaselinien.json` enthält rollierend die Zuordnung
von drei aktiven fachlichen Releaselinien zur jeweiligen technischen
ETAPS-Linie und dem zugehörigen Hostprofil. Ihr aktueller Inhalt ist:

```json
{
  "R260": {"etaps_linie": "en03", "hostprofil": "JUR"},
  "R261": {"etaps_linie": "en01", "hostprofil": "FKT"},
  "R270": {"etaps_linie": "en02", "hostprofil": "JUR"}
}
```

Bei der Synchronisation bestimmt die Releaselinie über `etaps_linie` das
M/Text-Ziel. Bei einer Release-Lieferung bestimmt sie zunächst den Namen des
Hostprofils. `assignment` und CodePipeline-`stage` dieses Profils werden
anschließend aus der Mandantenkonfiguration des getaggten Commits gelesen. So
ergibt beispielsweise `R261` für die FI über `FKT` die Werte
`LOMS000066` und `FKTE`.

Vor einer Verteilung oder Lieferung wird die gesamte benötigte Konfiguration
geprüft. Unbekannte Mandanten, Releaselinien, Zielumgebungen oder zusätzliche
Konfigurationsfelder führen zu einem Fehler.

## 8. Release-Lieferarten FULL und DELTA

Ein Tag mit der Endung `.100`, zum Beispiel `R261.100`, erzeugt für jedes
sichtbare, nicht ausgeschlossene Projekt ein vollständiges F-Paket und ein
zusätzliches leeres D-Paket. Das D-Paket enthält nur das leere
Projektverzeichnis und eine leere Löschliste. Das bisherige Jenkins-Skript
erzeugt und übergibt bei FULL ebenfalls beide Pakete.

Jeder andere gültige Release-Tag derselben Releaselinie erzeugt ein
kumulatives DELTA gegen den `.100`-Tag. Ein Tag `R261.108` enthält somit alle
neuen, geänderten und gelöschten Dateien seit `R261.100`. Frühere
DELTA-Lieferungen müssen nicht lückenlos eingespielt worden sein.
Die `.100`-Basis muss in der Git-Historie ein Vorgänger des Ziel-Tags sein.
Git bestimmt die geänderten, neuen, gelöschten und umbenannten Pfade mit
`git diff`. Python erzeugt daraus das historisch kompatible TAR-Archiv, die
Löschliste und die Informationsdatei mit reproduzierbaren Dateimetadaten.

### CodePipeline-Elemente

Bei einer DELTA-Lieferung entsteht für jedes ausgelieferte Projekt ein
D-Element. Bei einer FULL-Lieferung entstehen ein F-Element mit dem
vollständigen Projektstand und zusätzlich ein leeres D-Element.
Der Elementname ist zugleich der Mainframe-Member und setzt sich aus
Mandantenkürzel, abgeleitetem Projektcode und Elementart zusammen.

```text
<Mandantenkürzel><Projektcode><F|D>
```

Beispielsweise bezeichnet `BYAUTOND` das DELTA-Element für `LOMS_Autonom[BY]`.
Eine FULL-Lieferung von `LOMS_Basis` der FI erzeugt `FIBASISF` mit dem
vollständigen Projektstand sowie ein leeres `FIBASISD`.

| Projekt | "Projektcode" |
|---|---|
| `Configuration` | `CONFI` |
| `Fonts` | `FONTS` |
| `LOMS_Framework` | `FRAME` |
| `LOMS_Basis` | `BASIS` |
| `LOMS_PKA` | `PKA` |
| `LOMS_Autonom` | `AUTON` |

Der "Projektcode" entsteht, indem ein vorhandenes Mandantensuffix und das Präfix
`LOMS_` entfernt und anschließend höchstens die ersten fünf Zeichen in
Großschreibung verwendet werden. Zwei Projekte desselben Repositorys dürfen
nicht denselben Projektcode ergeben. Ein F-Element enthält den vollständigen
Projektbaum. Ein reguläres D-Element enthält die kumulativ seit `.100` neuen und
geänderten Dateien sowie die Löschliste. Das beim FULL zusätzlich erzeugte
D-Element enthält ein leeres Projektverzeichnis und eine leere Löschliste.

### Releaseartefakt und Manifest

Für jeden Release-Lauf speichert GitHub Actions die erzeugten Pakete zusammen
mit Manifest und Prüfsummen als Releaseartefakt. Der Publish-Job verwendet
genau dieses Artefakt für die Mainframe-Übergabe. Das bisherige feste
Verzeichnis `trans` wird für diesen Zweck nicht mehr benötigt. Dateinamen,
fachlicher Inhalt und Archivstruktur der Pakete bleiben unverändert.

Ein DELTA-Artefakt für ein Projekt der FI enthält beispielsweise:

```text
Release-Artefakt/
  FIBASISD.tgz
  _INFO_FI-LOMS_Basis-DELTA-R261.108-R261.107.txt
  manifest.json
```

Ein FULL-Artefakt enthält für dasselbe Projekt beide Mainframe-Pakete:

```text
Release-Artefakt/
  FIBASISF.tgz
  FIBASISD.tgz
  _INFO_FI-LOMS_Basis-FULL-R261.100-<Vorrelease>.txt
  manifest.json
```

Zu jeder Lieferung wird ein Manifest erzeugt. Die Begleitdatei nennt
Repository, Mandant, Release-Tag, Lieferart, Basis- und Vorgänger-Tag,
Ziel-SHA, JCL-Werte sowie alle Paket- und Informationsdateien mit Pfad, Größe
und SHA-256. Paketartefakte nennen zusätzlich ihren Mainframe-Member. Vor der
Mainframe-Übergabe werden genau diese Dateien mit den manifestierten Angaben
verglichen. So wird sichergestellt, dass das zuvor gebaute und geprüfte
Paket übergeben wird.

Der folgende gekürzte Ausschnitt zeigt die Verbindung zwischen Release,
Paket, Mainframe-Member und JCL-Werten. Dateigröße und Prüfsummen stehen
stellvertretend für die im jeweiligen Lauf berechneten Werte:

```json
{
  "artifacts": [
    {
      "kind": "package",
      "member": "FIBASISD",
      "path": "FIBASISD.tgz",
      "project": "LOMS_Basis",
      "sha256": "<SHA-256 des Pakets>",
      "size": 123456
    },
    {
      "kind": "information",
      "path": "_INFO_FI-LOMS_Basis-DELTA-R261.108-R261.107.txt",
      "project": "LOMS_Basis",
      "sha256": "<SHA-256 der Informationsdatei>",
      "size": 1234
    }
  ],
  "base_tag": "R261.100",
  "delivery_type": "DELTA",
  "jcl": {
    "ASSIGNMENT": "LOMS000066",
    "ISPW": "P",
    "LEVEL": "FKTE",
    "SUBSYS": "LOMS"
  },
  "mandant": "FI",
  "previous_tag": "R261.107",
  "release_tag": "R261.108",
  "repository": "mtext-fi",
  "target_sha": "<vollständige Commit-SHA>"
}
```

Ein fehlgeschlagener Übergabeversuch kann innerhalb desselben GitHub-Laufs mit
dem unveränderten Paket wiederholt werden (das Paket wird dabei nicht neu
gebaut).

## 9. Mainframe-Übergabe und JCL

Die JCL liegt als eigene versionierte Template-Datei vor. Änderungen
an der Mainframe-Ansteuerung sind dadurch sichtbar und unabhängig vom
Programmcode prüfbar.

Für jede Übergabe werden ausschließlich die fachlich festgelegten Werte in das
Template eingesetzt. Historisch feste Werte bleiben fest. Nur tatsächlich
mandantenspezifische Zuordnungen werden aus der Mandantenkonfiguration
übernommen. Die Werte für ISPW, CodePipeline-Stage, Assignment und
Mainframe-Member werden beim Rendern geprüft. Unbekannte Template-Marker
führen vor der Übergabe zu einem Fehler. Zugangsdaten werden weder in die JCL
noch in die Protokolle geschrieben.

Das Paket wird zunächst unter seinem Membernamen in
`IEA.LOMS.TONICZ` übertragen. Die JCL kopiert diesen Member nach
`IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ` und registriert ihn anschließend in
CodePipeline. Dabei gelten `STRMNAME=BOAS`, `MTYPE=TONICZ` und
`MNAME=<Membername>`. `APPLID` und `SUBAPPL` erhalten das aus dem
Mandantenkürzel abgeleitete Subsystem, `PROJNO` das Assignment sowie `CLVL` und
`SLVL` den CodePipeline-Stage-Code.

Der Release-Workflow trennt den Paketbau von der Mainframe-Übergabe. Der
Paketbau benötigt keinen Zugriff auf das Zielsystem. Erst der Übergabeschritt
erhält Zugriff auf die geschützte Umgebung `Bereitstellung`.

Übergaben desselben Mandanten werden nacheinander ausgeführt. Verschiedene
Mandanten können gleichzeitig liefern.

## 10. Status und Fehler

Die Lösung meldet nur den Status, den sie selbst sicher feststellen kann:

| Status | Bedeutung |
|---|---|
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinienzuordnung wurden technisch geprüft. |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig. |
| `SOURCE_FAILED` | Der angegebene Commit, Branch oder Tag konnte nicht eindeutig aufgelöst werden. |
| `RESOURCE_TRANSFER_FAILED` | Die Ressourcen konnten nicht in den Übergabebereich für M/Text geschrieben werden. |
| `ADAPTER_FAILED` | Der M/Text-Adapter war nicht erreichbar oder hat die Anfrage abgelehnt. |
| `ADAPTER_ACCEPTED` | Der M/Text-Adapter hat die Anfrage unmittelbar angenommen. Dies ist noch kein fachlicher Endstatus. Bei unklarer Wirkung ermittelt die Anwendungsbetreuung den technischen Anwendungsstatus. |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder Manifest konnten nicht korrekt erstellt werden. |
| `ARTIFACT_READY` | Das Releasepaket wurde vollständig erstellt und geprüft. |
| `MAINFRAME_TRANSFER_FAILED` | Die unmittelbare FTP-/JES-Übergabe ist fehlgeschlagen. |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden technisch übergeben. Der spätere Mainframe-Job kann trotzdem noch fehlschlagen und wird durch das Mandanten-Release-Team auf dem Host kontrolliert. |

Ein HTTP-Fehler des M/Text-Adapters gilt immer als fehlgeschlagener Lauf. Ein
Status zwischen 200 und 299 bestätigt nur die unmittelbare Annahme der
Anfrage.

Die Automatisierung fragt weder bei M/Text noch auf dem Mainframe nach dem
späteren fachlichen Endstatus.

## 11. Qualitätsmerkmale und weitere Ausbaustufe

### Tragende Qualitätsmerkmale

Gemessen an modernen Best Practices für GitHub Actions und automatisierte
Softwarelieferungen besitzt die Lösung eine starke technische Grundlage. Die
Einordnung orientiert sich insbesondere an den GitHub-Empfehlungen zu
[wiederverwendbaren Workflows](https://docs.github.com/en/enterprise-server@3.20/actions/concepts/workflows-and-actions/reusing-workflow-configurations),
zum [sicheren Einsatz von GitHub Actions](https://docs.github.com/en/enterprise-server@3.20/actions/reference/security/secure-use)
und zu [geschützten Environments](https://docs.github.com/en/enterprise-server@3.20/actions/reference/workflows-and-actions/deployments-and-environments).

| Qualitätsmerkmal | Umsetzung und Nutzen |
|---|---|
| Durchgängiger Gesamtablauf | Die fachliche Kette führt von Entwicklung über Abnahme und Bereitstellung zum Release-Tag. Jeder Übergang hat einen eindeutigen Auslöser und ein prüfbares Ergebnis. |
| Zentral gepflegte Automatisierung | Die Mandanten-Workflows enthalten nur Trigger und feste Zielzuordnungen. Die gemeinsame Fachlogik liegt in wiederverwendbaren Workflows und einer Python-Implementierung mit Standardbibliothek in `mtext-actions`. |
| Eindeutige und reproduzierbare Lieferung | Jeder Lauf verarbeitet einen vollständigen Commit-SHA. Das Manifest verbindet Release-Tag, Ziel-Commit und erzeugte Dateien. Gleiche Eingaben erzeugen bytegleiche Archive. Historische Namen, Verzeichnisstrukturen, Löschlisten und JCL-Verträge bleiben erhalten. |
| Getrennte Verantwortlichkeiten | Mandantenressourcen und -konfiguration, gemeinsame Automatisierung, GitHub-Schutzregeln und Runnerbetrieb haben jeweils einen klaren Eigentümer. |
| Geprüfte Build-Publish-Grenze | Der Paketbau ist von der Mainframe-Übergabe getrennt. Das einmal erzeugte Artefakt wird unmittelbar vor der externen Wirkung anhand von Pfad, Größe und SHA-256 geprüft. |
| Automatisiert prüfbarer Vertrag | Tests decken Konfiguration, Git-Bezüge, FULL und DELTA, Manifest, JCL, Ressourcensynchronisation, FTP/JES und Workflowgrenzen ab. Stabile Statuswerte unterscheiden die Fehlerklassen. |

### Mögliche Phase 2

Die erste Ausbaustufe bleibt bewusst auf die sichere Ablösung des bestehenden
Lieferwegs begrenzt. Die in [Nächste Schritte](./Naechste_Schritte.md) geführten
Einrichtungs- und Abnahmepunkte sind Voraussetzungen für die Aktivierung und
keine Phase-2-Themen. Nach einem stabilen Produktivbetrieb können insbesondere
folgende Erweiterungen bewertet werden:

- den nachgelagerten fachlichen Status in M/Text und auf dem Mainframe abfragen
  und im Workflow anzeigen (Polling),
- die FTP-/JES-Übergabe auf einen verschlüsselten Transport umstellen, sobald
  das Zielsystem dafür einen verbindlichen Vertrag bereitstellt,
- Betriebsmetriken und kompakte Laufzusammenfassungen ergänzen, ohne
  mandantenübergreifende oder vertrauliche Details offenzulegen,
- zusätzliche E-Mail-Benachrichtigungen für relevante Workflow-Ergebnisse
  ergänzen, ohne den fachlichen Laufstatus von der Benachrichtigung abhängig zu
  machen,
- Aktualisierungen gepinnter Actions sowie ergänzende Workflow-, Shell-, Typ-
  und Abdeckungsprüfungen automatisieren.
