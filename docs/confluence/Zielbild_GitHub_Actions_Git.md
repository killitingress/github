# Zielbild für die Ablösung von Jenkins und SVN

**Dokumenttyp:** Zielbild für Fachlichkeit und Technik

**Geltungsbereich:** Verteilung von M/Text-Ressourcen und Bereitstellung von
Mainframe-Lieferungen

Dieses Dokument beschreibt den künftigen Prozess mit Git und GitHub Actions.
Den Arbeitsstand zeigt [Nächste Schritte](./Naechste_Schritte.md), die
Bedienung die [Benutzeranleitung](./Benutzeranleitung.md).

Die
[Soll-Grafik GitHub Actions/Git](../../Architektur_Soll_GitHub_Actions_Git.drawio)
zeigt den Ablauf von einer Änderung bis zur M/Text-Verteilung oder
Mainframe-Übergabe. Die
[Ist-Grafik Jenkins/SVN](../../Architektur_Ist_Jenkins_SVN.drawio) dokumentiert
den bisherigen Prozess.

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in einer nichtproduktiven GitHub-Umgebung erprobt. Während
dieser Testphase bleibt der bisherige Prozess produktiv. Unmittelbar vor der
für Januar 2027 geplanten Produktivsetzung wird der dann freigegebene
SVN-Endstand nach Git übertragen. Danach sind Git und GitHub Actions für diesen
Prozess führend. Eine dauerhafte Synchronisation mit SVN gibt es nicht.

Jeder Mandant erhält ein eigenes Repository mit seinen M/Text-Ressourcen und
seiner Konfiguration. Die gemeinsame Automatisierung liegt in einem zentralen
Repository. So bleiben die Mandantendaten getrennt, während alle Mandanten
dieselben geprüften Abläufe verwenden.

Eine Änderung durchläuft weiterhin die drei Prozess-Stages Entwicklung,
Abnahme und Bereitstellung. Als Stage wird in diesem Dokument ein Abschnitt
des Freigabe- und Lieferprozesses bezeichnet. Der später genannte
JCL-Stage-Code wie `FKTE` oder `JURP` bezeichnet dagegen das
CodePipeline-`LEVEL` und ist davon unabhängig.

Der Ablauf ist:

1. Ein Push nach `Rnnn/Entwicklung` verteilt den Stand an das
   M/Text-Entwicklungssystem.
2. Nach fachlicher Prüfung wird derselbe Stand nach `Rnnn/Abnahme` übernommen
   und an das M/Text-Abnahmesystem verteilt.
3. Freigegebene Änderungen werden nach `Rnnn/Bereitstellung` übernommen. Der
   Push allein erzeugt noch keine Mainframe-Lieferung.
4. Erst ein Release-Tag wie `R261.108` baut die Lieferung. Vor der technischen
   Übergabe an den Mainframe ist eine manuelle Freigabe erforderlich.

Der M/Text-Adapter bleibt die zentrale Schnittstelle. Der Weg nach
`serverSync` wird vor dem Integrationslauf festgelegt. Die Mainframe-Übergabe
erfolgt weiterhin per FTP und JES.

## 2. Verbindliche Rahmenbedingungen

- Der Wechsel von SVN/Jenkins zu Git/GitHub Actions findet zu einem festen
  Zeitpunkt statt. Danach gibt es keinen parallelen produktiven Lieferbetrieb.
- Das bisherige Jenkins-Skript wird nicht weiterentwickelt oder technisch
  portiert. Nur die weiterhin benötigten Regeln, Zuordnungen und
  Übergabeverfahren werden übernommen.
- Jeder Mandant erhält ein eigenes privates GitHub-Repository. Namen und
  grundsätzlicher Aufbau orientieren sich an den bisherigen
  Mandantenstrukturen.
- Die gemeinsame Automatisierung wird zentral durch die FI verwaltet und von
  den Mandanten-Repositories in einer ausdrücklich festgelegten Version
  verwendet.
- `mtext-actions` ist ein privates Repository. Direkten Zugriff erhalten nur
  die zentralen Automatisierungsverantwortlichen. Text-Entwickler der
  Mandanten werden dort nicht als Repositorymitglieder berechtigt.
- Jeder Lauf verarbeitet genau einen Git-Stand, den die Commit-SHA kennzeichnet.
- Der Mandant ergibt sich aus dem Repository und seiner Konfiguration. Er kann
  beim Start eines Laufs nicht frei gewählt werden.
- Die Releaselinien `R260`, `R261` und `R270` erhalten getrennte Branches für
  Entwicklung, Abnahme und Bereitstellung.
- Geheimnisse und Zugangsdaten liegen in den GitHub-Einstellungen, nicht in Git.
- Eine weitergehende Statusabfrage bei M/Text oder auf dem Mainframe wird in
  der ersten Ausbaustufe nicht eingeführt.

## 3. Was aus dem bisherigen Verfahren übernommen wird

Das Jenkins-Skript erledigt heute unter anderem die M/Text-Verteilung, den Bau
von FULL- und DELTA-Paketen, die Erstellung von Inhalts- und Löschlisten sowie
die Übergabe an den Mainframe. Diese fachlichen Ergebnisse werden weiterhin
benötigt.

Nicht übernommen werden die technischen Altlasten des bisherigen Verfahrens.
Dazu gehören langlebige SVN-Arbeitskopien auf Netzlaufwerken,
Reparaturkommandos für blockierte Arbeitsverzeichnisse und zur Laufzeit
erzeugte Skripte mit Zugangsdaten. Die neue Lösung arbeitet stattdessen je Lauf
mit einem frisch ausgecheckten, eindeutig bestimmten Git-Stand.

Die bisherigen Lieferdateien geben folgende Kompatibilitätsregeln vor:

- FULL- und DELTA-Pakete behalten ihre historisch festgelegten Dateinamen. Die
  dafür benötigte Projektkennung wird zentral aus dem freigegebenen
  Projektnamen abgeleitet und kann nicht im Mandanten-Repository geändert
  werden.
- Ein DELTA-Paket enthält eine Löschliste mit dem Namen
  entsprechend der bisherigen Namensregel.
- Ressourcen behalten ihre fachlichen Projektpfade. Bei Fragmentprojekten
  gehört das Mandantenkürzel in eckigen Klammern zum Projektnamen, zum Beispiel
  `LOMS_Autonom[BY]`.
- Zu jedem Paket wird eine Informationsdatei erzeugt. Sie beschreibt den
  Inhalt und den Vergleich zum vorherigen Release, bestimmt aber nicht den
  Inhalt des DELTA-Pakets.
- Die vorhandenen Unterschiede in den Pfaden von FULL- und DELTA-Archiven
  bleiben zunächst erhalten, damit bestehende Empfänger die Dateien weiterhin
  verarbeiten können.
- Archive werden reproduzierbar erzeugt: Derselbe Quellstand und dieselbe
  Konfiguration ergeben denselben Inhalt.

## 4. Zielarchitektur und Verantwortlichkeiten

Die Lösung besteht aus vier Bereichen:

| Bereich | Verantwortung |
|---|---|
| Mandanten-Repository | M/Text-Ressourcen, Projektzuordnungen, mandantenspezifische technische Übergabewerte und schlanke Workflows |
| Zentrales Repository `mtext-actions` | Gemeinsame Prüfungen, Synchronisation, Paketbau und Mainframe-Übergabe |
| GitHub Actions | Ausführung der Abläufe, Freigaben und Protokollierung |
| Self-hosted Runner | Ausführung innerhalb des internen Netzes und, abhängig vom noch festzulegenden M/Text-Transportweg, Zugriff auf Adapter oder Netzlaufwerk sowie auf den Mainframe |

Ein Mandanten-Repository enthält ausschließlich die Ressourcen und Angaben
des jeweiligen Mandanten. Das zentrale Repository enthält keine
Mandantenressourcen, sondern nur die gemeinsam verwendete Automatisierung.

Mandanten-Repositories dürfen die freigegebenen wiederverwendbaren Workflows
über die GitHub-Actions-Zugriffsrichtlinie aufrufen. Diese technische Freigabe
erteilt ihren Benutzern keinen direkten Zugriff auf `mtext-actions`. Die
Ausgaben der aufgerufenen Jobs erscheinen jedoch in den Workflow-Logs des
Mandanten-Repositories. Deshalb werden Logs grundsätzlich als
mandantensichtbar behandelt und enthalten weder Secrets noch unnötige interne
Details.

Damit die technische Freigabe nicht über veränderte aufrufende Workflows
zweckentfremdet werden kann, dürfen Text-Entwickler der Mandanten keine Dateien
unter `.github/workflows/` ändern oder neu anlegen. Ein Push-Ruleset schützt
diesen Pfad auf allen Branches. Nur die zentralen
Automatisierungsverantwortlichen erhalten einen kontrollierten Bypass.
`.config.json` wird ebenfalls von der normalen Ressourcenpflege
getrennt und darf nur durch den benannten technischen Verantwortlichenkreis
geändert werden.

Die Text-Entwickler bearbeiten Briefressourcen in der M/Text Workbench und
nutzen ihren Git-Client für Commit und Push. GitHub im Browser dient für
Laufkontrolle, Wiederholungen, Freigaben und Release-Tags. Für die tägliche
Arbeit ist keine Git-Kommandozeile nötig.

Für die gezielte Übernahme einzelner Änderungen zwischen den Stages erhalten
die dafür berechtigten Text-Entwickler zusätzlich einen geeigneten Git-Client.
Das konkrete Produkt, seine Bereitstellung und der verbindliche Bedienweg
werden vor dem Pilotbetrieb festgelegt und abgenommen.

Die Berechtigungen werden je Mandanten-Repository vergeben. Jeder Mandant
benennt ein Release-Team, das als einzige reguläre Gruppe direkt nach
`Rnnn/Bereitstellung` pushen und neue Release-Tags anlegen darf. So können die
Verantwortlichen je Mandant unterschiedlich sein, ohne die gemeinsame
Automation zu verzweigen. Force-Pushes und das Löschen der Branches dieser
Stages bleiben verboten. Bereits angelegte Release-Tags dürfen auch vom
Release-Team nicht verändert oder gelöscht werden.

Für jeden Lauf checkt GitHub Actions sowohl den ausgewählten Stand des
Mandanten-Repositories als auch eine festgelegte Version der zentralen
Automatisierung aus. Dadurch ist später nachvollziehbar, welche Quellen und
welche Automatisierung verwendet wurden.

Die Verteilung nach Entwicklung oder Abnahme überträgt alle nicht
ausgeschlossenen Projektverzeichnisse des ausgewählten Commits. FULL und DELTA
gelten nur für die spätere Mainframe-Lieferung.

Auf `serverSync` müssen dieselben Pfade und Dateien liegen wie im bisherigen
Verfahren. Der Transportweg und der Adaptervertrag stehen vor dem
nichtproduktiven Integrationslauf fest.

Der bestehende Prozess auf dem Mainframe-Zielsystem IZE9 bleibt unverändert.

## 5. Repositories und aktueller Entwicklungsstand

Ein Mandanten-Repository folgt diesem Grundaufbau:

```text
mtext-<mandant>/
  .github/workflows/
    validate-config.yml
    sync-resources.yml
    release.yml
  .config.json
  <M/Text-Projekte>
```

Das zentrale Repository enthält die wiederverwendbaren Workflows, die
gemeinsame Python-Anwendung, die zentrale Releaselinienzuordnung, das
JCL-Template und die automatisierten Akzeptanztests:

```text
mtext-actions/
  .github/workflows/
  config/
  src/lbs_delivery/
    cli.py
    config.py
    errors.py
    git.py
    mainframe.py
    manifest.py
    release.py
    sync.py
  templates/
  tests/
```

Die Module folgen den fachlichen Abläufen. `sync.py` enthält Staging,
`serverSync` und Adapteraufruf; `mainframe.py` enthält JCL und FTP/JES.
Pfad- und Wertprüfungen stehen direkt an der jeweils zuständigen Eingangs-
oder Systemgrenze. Intern erzeugte Werte werden nicht in weiteren Schichten
erneut validiert.

`mtext-fi` dient als Muster für die Mandanten-Repositories. Alle sichtbaren
Verzeichnisse in der Repositorywurzel werden synchronisiert und in
Releasepakete aufgenommen. `LOMS_Testdaten` soll ebenfalls in das Repository
übernommen werden, ist aber über `excluded_projects` in `.config.json` von der
Synchronisation und den Releasepaketen ausgeschlossen.

Die Workflows im Mandanten-Repository legen nur Auslöser und explizite
Ziel-Environments fest. Die Verarbeitung erfolgt durch die zentralen Workflows aus
`mtext-actions`. Im aktuellen Entwicklungsstand enthalten die Verweise auf
diese zentralen Workflows noch eine nicht lauffähige Folge aus Nullen als
Platzhalter.

Im gemeinsamen Workspace liegt der zur Übernahme vorgesehene Inhalt des
zentralen Repositorys unter `mtext-actions/mtext-actions-next`. Im Zielbetrieb
werden Mandanten und zentrale Automation als eigenständige GitHub-Repositories
unter `j517120/mtext-fi` und `j520730/mtext-actions` geführt. Nach fachlicher
Bestandsaufnahme und Freigabe werden auch
`mtext-autonom`, `mtext-by`, `mtext-lh`, `mtext-nw`, `mtext-os` und
`mtext-sa` nach diesem Muster eingerichtet.

Vor dem ersten Integrationslauf wird der Platzhalter in allen
Mandanten-Workflows durch die vollständige Kennung einer freigegebenen Version
von `mtext-actions` ersetzt. GitHub Enterprise muss den
Mandanten-Repositories außerdem den Zugriff auf die zentralen Workflows
erlauben, ohne deren Benutzer direkt am zentralen Repository zu berechtigen.
Beides wird mit einem nichtproduktiven Lauf geprüft.

## 6. Branches, Weitergabe und Auslöser

Jede aktive Releaselinie besitzt drei Branches, zum Beispiel:

```text
R260/Entwicklung
R260/Abnahme
R260/Bereitstellung
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
Weitergegeben wird dieselbe Änderung, nicht derselbe Commit. Die
vollständige Quell-SHA wird nach einer verbindlichen Konvention im neuen
Ziel-Commit dokumentiert. Ob die Releaselinie fachlich eingerichtet ist,
entscheidet die zentrale Releaselinienzuordnung.

Ein Push nach `Rnnn/Bereitstellung` erzeugt noch keine Lieferung. Erst ein Tag
im Format `Rnnn.nnn` startet den Paketbau. Dabei wird geprüft, ob der Tag zur
angegebenen Releaselinie gehört und vom Bereitstellungsbranch erreichbar ist.
Der Tag ist danach die unveränderliche Identität dieser Lieferung und wird
durch Tag-Rulesets gegen Änderung, Force-Push und Löschung geschützt.

Der zusätzliche Git-Client für die Auswahl und Übernahme einzelner Änderungen
nach Abnahme und Bereitstellung wird vor dem Pilotbetrieb ausgewählt,
bereitgestellt und praktisch abgenommen. Ein direkter Cherry-Pick ist über die
GitHub-Weboberfläche allein nicht verfügbar.

Die Mandanten-Repositories erhalten keinen zusätzlichen `main`-Branch. Als
Default Branch dient der Entwicklungsbranch der aktuell führenden Linie,
zunächst `R261/Entwicklung`. Beim Wechsel der führenden Linie wird diese
Einstellung manuell angepasst.

Manuelle Wiederholungen sind möglich, müssen aber denselben Commit verwenden.
Vor einer erneuten M/Text-Verteilung prüft der Workflow, ob dieser Commit zum
ausgewählten Branch gehört.

### Neue Releaselinie einrichten

Eine neue Linie erhält drei Branches, je einen für Entwicklung, Abnahme und
Bereitstellung, sowie einen Eintrag in
`config/releaselinien.json`. Der Eintrag enthält nur die fachliche
Releaselinie, die technische M/Text-Linie und den Namen eines in
`.config.json` vorhandenen Hostprofils. Hosts, Stage-Suffixe,
serverSync-Pfad, JCL-Parameter und
Tagformat werden unverändert zentral abgeleitet.

Ausgangspunkt der neuen Branches ist der fachlich bestätigte letzte
Release-Tag der bisherigen Linie. Dessen vollständiger Projektstand wird über
den manuellen Sync-Workflow einmal nach Entwicklung und einmal nach Abnahme
übertragen und anschließend in M/Text fachlich geprüft.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Die verwendeten
GitHub-Actions-Bausteine und der interne Runner müssen vor der Aktivierung auf
dieser konkreten Version geprüft werden.

## 7. Workflows, Trigger und Abhängigkeiten

Die Mandanten-Repositories enthalten nur die fachlichen Auslöser. Sie rufen
fest gepinnte wiederverwendbare Workflows aus `mtext-actions` auf. Die
eigentliche Fachlogik liegt in Python.

### Gesamtzusammenhang

| Prozessschritt | Auslöser im Mandanten-Repository | Mandanten-Workflow | Zentraler Workflow | Python-Kommando | Ergebnis |
|---|---|---|---|---|---|
| Mandantenkonfiguration prüfen | Push mit Änderung an `.config.json` auf einen Branch | `validate-config.yml` | `reusable-validate-config.yml` | `validate-config` | Konfiguration geprüft |
| Entwicklung synchronisieren | Push nach `Rnnn/Entwicklung` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync-resources` | Vollständiger Projektstand des Ziel-Commits nach M/Text-Entwicklung synchronisiert |
| Abnahme synchronisieren | Push eines per Cherry-Pick übernommenen Commits nach `Rnnn/Abnahme` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync-resources` | Vollständiger Projektstand des Ziel-Commits nach M/Text-Abnahme synchronisiert |
| Bereitstellungsstand fortschreiben | Cherry-Pick und Push nach `Rnnn/Bereitstellung` | keiner | keiner | keines | Nur Git-Branch fortgeschrieben. Noch keine Lieferung |
| Release bauen und übergeben | Push eines Tags `Rnnn.nnn` oder manueller Start mit vorhandenem Tag | `release.yml` | `reusable-release.yml` | `build-release`, danach `publish-mainframe` | FULL/DELTA gebaut, geprüft und nach Freigabe per FTP/JES übergeben |
| Zentrale Automation testen | Pull Request in `mtext-actions` oder Push auf dessen `main` | entfällt | `ci.yml` | `unittest discover` | Zentrale Testfälle und Workflowverträge geprüft |

Die Actions verarbeiten den Stand, den die Benutzer auf dem jeweiligen Branch
hergestellt haben. Sie schreiben keine Commits, Branches oder Tags.

### Trigger in den Mandanten-Repositories

| Ereignis | Konfigurationsprüfung | Sync Entwicklung | Sync Abnahme | Release |
|---|---:|---:|---:|---:|
| Push auf einen Branch ohne Änderung an `.config.json` | nein | nur nach `Rnnn/Entwicklung` | nur nach `Rnnn/Abnahme` | nein |
| Push auf einen Branch mit Änderung an `.config.json` | ja | nur nach `Rnnn/Entwicklung` | nur nach `Rnnn/Abnahme` | nein |
| Push eines Tags `Rnnn.nnn` | nein | nein | nein | ja |
| Manueller Sync eines Ziel-Commits aus `Rnnn/Entwicklung` | nein | ja | nein | nein |
| Manueller Sync eines Ziel-Commits aus `Rnnn/Abnahme` | nein | nein | ja | nein |
| Manueller Release-Start mit vorhandenem Tag `Rnnn.nnn` | nein | nein | nein | ja |
| Pull Request im Mandanten-Repository | nein | nein | nein | nein |

Der Sync-Workflow besitzt keinen Pfadfilter. Jeder Push nach Entwicklung oder
Abnahme startet daher den vollständigen Ressourcensync. Dabei werden die
sichtbaren, nicht unter `excluded_projects` genannten Projektverzeichnisse
übertragen.

Die Synchronisation wartet nicht auf den Abschluss der separaten
Konfigurationsprüfung. Wenn ein Push nach Entwicklung oder Abnahme zugleich
`.config.json` ändert, können beide Abläufe unabhängig voneinander laufen.
Synchronisation und Release-Erstellung prüfen die verwendete Konfiguration vor
dem Zugriff auf externe Systeme erneut.

### Mandantenseitige YAML-Workflows

| Datei | Automatischer Trigger | Manueller Trigger | Abhängigkeit und Zweck |
|---|---|---|---|
| [`validate-config.yml`](../../mtext-fi/.github/workflows/validate-config.yml) | Push mit Änderung an `.config.json` auf einen Branch | keiner | Ruft `reusable-validate-config.yml` zur Prüfung der Mandantenkonfiguration auf |
| [`sync-resources.yml`](../../mtext-fi/.github/workflows/sync-resources.yml) | Push nach `Rnnn/Entwicklung` oder `Rnnn/Abnahme` | `workflow_dispatch` mit vollständiger `commit_sha` und zugehörigem `source_branch` | Ruft abhängig von der Branchendung `reusable-sync-resources.yml` mit festem Ziel-Environment `Entwicklung` oder `Abnahme` auf |
| [`release.yml`](../../mtext-fi/.github/workflows/release.yml) | Push eines Tags `Rnnn.nnn` | `workflow_dispatch` mit vorhandenem `release_tag` | Ruft `reusable-release.yml` auf. Ein Push nach Bereitstellung allein ist kein Auslöser |

### Zentrale YAML-Workflows

| Datei | Trigger | Jobs und Abhängigkeiten | Implementierung und Wirkung |
|---|---|---|---|
| [`reusable-validate-config.yml`](../../mtext-actions/mtext-actions-next/.github/workflows/reusable-validate-config.yml) | `workflow_call` | Mandanten-Commit auschecken → Automation auschecken → Laufzeit vorbereiten → prüfen | `validate-config` |
| [`reusable-sync-resources.yml`](../../mtext-actions/mtext-actions-next/.github/workflows/reusable-sync-resources.yml) | `workflow_call` | Exakten Mandanten-Commit mit vollständiger Historie auschecken → Automation auschecken → Laufzeit vorbereiten → synchronisieren | `sync-resources --execute`. Schreibt nach `serverSync` und ruft den M/Text-Adapter per HTTPS auf |
| [`reusable-release.yml`](../../mtext-actions/mtext-actions-next/.github/workflows/reusable-release.yml) | `workflow_call` | Job `build` erzeugt das Artefakt. Job `publish` hat `needs: build`, lädt genau dieses Artefakt und bindet das Environment `Bereitstellung` | `build-release`, danach `publish-mainframe --execute`. Übergabe per FTP/JES nach Freigabe |
| [`ci.yml`](../../mtext-actions/mtext-actions-next/.github/workflows/ci.yml) | Pull Request oder Push auf `main` in `mtext-actions` | Automation auschecken → Laufzeit vorbereiten → Akzeptanztests ausführen | `python -m unittest discover -s tests -v` |

Die wiederverwendbaren Workflows sind nur über `workflow_call` erreichbar.
Alle zentralen Jobs verwenden Self-hosted Runner mit den Labels `self-hosted`,
`linux` und standardmäßig `mtext-delivery`.

### Python-Kommandos

| Kommando | Aufgerufen durch | Wesentliche Prüfungen und Abhängigkeiten | Ergebnis |
|---|---|---|---|
| `validate-config` | `reusable-validate-config.yml` | Bekanntes Mandantenkürzel, Repositoryidentität, Hostprofil-Stages, eindeutige Projektcodes und vorhandene Hostprofile der Releaselinien | Status `CONFIG_VALIDATED` |
| `sync-resources` | `reusable-sync-resources.yml` | Branch und Environment stimmen überein. Vollständige SHA. Checkout entspricht SHA. Commit ist aus dem Remote-Branch erreichbar. Projektbäume enthalten keine Symlinks | Vollständiger Projektstand nach `serverSync`, HTTPS-Aufruf des Adapters, Status `ADAPTER_ACCEPTED` |
| `build-release` | Job `build` in `reusable-release.yml` | Tagformat und konfigurierte Releaselinie. Tag aus Bereitstellungsbranch erreichbar. Checkout entspricht Tag-SHA. DELTA-Basis `.100`. Projektbäume enthalten keine Symlinks | Reproduzierbare FULL-/DELTA-Archive, Informationsdateien und `manifest.json` mit SHA-256. Status `ARTIFACT_READY` |
| `publish-mainframe` | Job `publish` in `reusable-release.yml` | Artefaktpfade, Dateigrößen und SHA-256 aus dem Manifest; JCL-Werte beim Rendern; FTP-Secrets vor der Übergabe | JCL je Paket, FTP-Übertragung und Übergabe an JES. Status `MAINFRAME_SUBMITTED` |

Der Einstieg erfolgt über
[`__main__.py`](../../mtext-actions/mtext-actions-next/src/lbs_delivery/__main__.py)
und
[`cli.py`](../../mtext-actions/mtext-actions-next/src/lbs_delivery/cli.py). Die CLI übersetzt
fachliche Fehler in stabile Statuswerte und Prozess-Exitcodes. Ein von null
verschiedener Exitcode lässt den jeweiligen GitHub-Job fehlschlagen.

### Environments, Secrets und Serialisierung

| Bereich | Umsetzung |
|---|---|
| Entwicklung und Abnahme | Der Sync-Job bindet das fest gewählte Environment. Derzeit werden dort keine Secrets gelesen. |
| Bereitstellung | Nur der Publish-Job bindet dieses Environment. Die manuelle Freigabe wird in GitHub konfiguriert. |
| Mainframe-Secrets | Ausschließlich `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD` im Publish-Job |
| Sync-Serialisierung | Concurrency-Gruppe je Repository und Branch. Ein laufender Sync wird nicht aktiv abgebrochen. |
| Release-Serialisierung | Je Repository und Tag. Die Mainframe-Übergabe wird zusätzlich je Mandanten-Repository serialisiert. |
| Build-Publish-Grenze | Publish lädt genau das vom Build benannte Artefakt und vergleicht unmittelbar vor der externen Wirkung Pfad, Größe und SHA-256 jeder manifestierten Datei. |

## 8. Konfiguration

Jedes Mandanten-Repository enthält seine eigene Konfiguration. Sie beschreibt
unter anderem:

- den Mandanten und das zugehörige Repository,
- optionale Projektausschlüsse,
- die für den Mandanten variablen technischen Übergabewerte.

Diese `.config.json` liegt in der Repositorywurzel und ist ein versionierter
Bestandteil des Lieferstands. Alle sichtbaren Verzeichnisse direkt unter der
Wurzel werden als Projekte synchronisiert und paketiert. Versteckte
Verzeichnisse werden ignoriert. Zusätzliche Ausnahmen stehen unter
`excluded_projects`.

Zu den mandantenspezifischen Übergabewerten gehören das Subsystem sowie je
Hostprofil Assignment und JCL-Stage-Code. Die bestehende JCL verwendet
diesen Stage-Code als CodePipeline-`LEVEL`. Ein zusätzlicher Levelwert wird
nicht eingeführt. Diese Werte dürfen bei einer fachlich bestätigten Änderung
der Mandantenzuordnung versioniert in `.config.json` angepasst werden. Der
zentral verwaltete Test-/Produktionswert und Zugangsdaten gehören nicht in
diese Datei.

Die zentrale Datei `config/releaselinien.json` enthält die wachsende Zuordnung
der fachlichen zu den technischen Linien sowie das Übergabeprofil. Die beiden
Felder heißen `mtext_linie` und `uebergabeprofil`. Aktuell gilt:

| Releaselinie | Technische M/Text-Linie |
|---|---|
| `R260` | `en03` |
| `R261` | `en01` |
| `R270` | `en02` |

Vor einer Verteilung oder Lieferung wird die gesamte benötigte Konfiguration
geprüft. Unbekannte Mandanten, Releaselinien, Zielumgebungen oder zusätzliche
Konfigurationsfelder führen zu einem Fehler. Es gibt keine stillschweigende
Rückfallregel auf FI-Werte.

Jede Änderung an `.config.json` startet beim Push einen Config-Check.

FI ist für die unfragmentierten Basisprojekte maßgeblich, `mtext-autonom` für
`LOMS_Autonom`. Die übrigen Mandanten enthalten Fragmentprojekte mit dem
Mandantenkürzel in eckigen Klammern. Testdatenprojekte werden zwar nach Git
übernommen, aber über `excluded_projects` nicht ausgeliefert.

## 9. FULL- und DELTA-Lieferungen

Ein Tag mit der Endung `.100`, zum Beispiel `R261.100`, erzeugt eine
vollständige Lieferung aller Projekte der Mandantenkonfiguration.

Jeder andere gültige Release-Tag derselben Releaselinie erzeugt ein
kumulatives DELTA gegen den `.100`-Tag. Ein Tag `R261.108` enthält somit alle
neuen, geänderten und gelöschten Dateien seit `R261.100`. Frühere
DELTA-Lieferungen müssen nicht lückenlos eingespielt worden sein.

Zu jeder Lieferung wird ein Manifest erzeugt. Die Begleitdatei nennt
Repository, Mandant, Release-Tag, Lieferart, Basis- und Vorgänger-Tag,
Ziel-SHA, JCL-Werte sowie alle Paket- und Informationsdateien mit Pfad, Größe
und SHA-256. Paketartefakte nennen zusätzlich ihren Mainframe-Member. Vor der
Mainframe-Übergabe werden genau diese Dateien mit den manifestierten Angaben
verglichen. So wird sichergestellt, dass das zuvor gebaute und freigegebene
Paket übergeben wird.

Ein fehlgeschlagener Übergabeversuch kann innerhalb desselben GitHub-Laufs mit
dem unveränderten Paket wiederholt werden. Das Paket wird dabei nicht neu
gebaut.

## 10. Mainframe-Übergabe und JCL

Die JCL liegt als eigene versionierte Template-Datei vor. Änderungen
an der Mainframe-Ansteuerung sind dadurch sichtbar und können unabhängig vom
Programmcode geprüft werden.

Für jede Übergabe werden ausschließlich die fachlich festgelegten Werte in das
Template eingesetzt. Historisch feste Werte bleiben fest. Nur tatsächlich
mandantenspezifische Zuordnungen werden aus der Mandantenkonfiguration
übernommen. Die Werte für ISPW, CodePipeline-Stage, Subsystem, Assignment und
Mainframe-Member werden beim Rendern geprüft. Unbekannte Template-Marker führen
vor der Übergabe zu einem Fehler. Zugangsdaten werden weder in die JCL noch in
die Protokolle geschrieben.

Der Release-Workflow trennt den Paketbau von der Mainframe-Übergabe. Der
Paketbau benötigt keinen Zugriff auf das Zielsystem. Erst der Übergabeschritt
erhält Zugriff auf die geschützte Umgebung `Bereitstellung` und wartet dort
auf eine manuelle Freigabe.

Übergaben desselben Mandanten werden nacheinander ausgeführt. Verschiedene
Mandanten können gleichzeitig liefern.

## 11. Status und Fehler

Die Lösung meldet nur den Status, den sie selbst sicher feststellen kann:

| Status | Bedeutung |
|---|---|
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinienzuordnung wurden technisch geprüft. |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig. |
| `SOURCE_FAILED` | Der angegebene Commit, Branch oder Tag konnte nicht eindeutig aufgelöst werden. |
| `RESOURCE_TRANSFER_FAILED` | Die Ressourcen konnten nicht in den Übergabebereich für M/Text geschrieben werden. |
| `ADAPTER_FAILED` | Der M/Text-Adapter war nicht erreichbar oder hat die Anfrage abgelehnt. |
| `ADAPTER_ACCEPTED` | Der M/Text-Adapter hat die Anfrage unmittelbar angenommen. Dies ist noch kein fachlicher Endstatus. |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder Manifest konnten nicht korrekt erstellt werden. |
| `ARTIFACT_READY` | Das Releasepaket wurde vollständig erstellt und geprüft. |
| `MAINFRAME_TRANSFER_FAILED` | Die unmittelbare FTP-/JES-Übergabe ist fehlgeschlagen. |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden technisch übergeben. Der spätere Mainframe-Job kann trotzdem noch fehlschlagen. |

Ein HTTP-Fehler des M/Text-Adapters gilt immer als fehlgeschlagener Lauf. Ein
Status zwischen 200 und 299 bestätigt nur die unmittelbare Annahme der
Anfrage.

Die Automation fragt weder bei M/Text noch auf dem Mainframe nach dem späteren
fachlichen Endstatus.
