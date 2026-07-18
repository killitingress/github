# Übersicht der GitHub-Actions-Workflows

**Stand:** 18. Juli 2026

Diese Übersicht beschreibt den repräsentativen Mandanten `mtext-fi` und die
zentrale Automation `mtext-actions`. Weitere Mandanten-Repositories sollen
dieselben drei dünnen aufrufenden Workflows enthalten und sich nur durch ihre
Mandantenkonfiguration unterscheiden.

Die drei Prozess-Stages sind `Entwicklung`, `Abnahme` und `Bereitstellung`.
Jede Releaselinie besitzt einen eigenen Branch für jede dieser Stages.

## 1. Gesamtzusammenhang

| Prozessschritt | Auslöser im Mandanten-Repository | Mandanten-Workflow | Zentraler Workflow | Python-Kommando | Ergebnis |
|---|---|---|---|---|---|
| Mandantenkonfiguration prüfen | Push mit Änderung an `config/mandant.json` auf einem beliebigen Branch | `validate-config.yml` | `reusable-validate-config.yml` | `validate-config` | Konfiguration geprüft, kein externer Zugriff |
| Entwicklung synchronisieren | Push nach `Rnnn/Entwicklung` oder manuelle Durchführung des Workflows | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync-resources` | Vollständiger konfigurierter Ressourcenstand in serverSync veröffentlicht und M/Text-Adapter aufgerufen |
| Abnahme synchronisieren | Push nach `Rnnn/Abnahme` oder manuelle Durchführung des Workflows | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync-resources` | Vollständiger konfigurierter Ressourcenstand in serverSync veröffentlicht und M/Text-Adapter aufgerufen |
| Bereitstellungsstand fortschreiben | Manueller Cherry-Pick und Push nach `Rnnn/Bereitstellung` | keiner | keiner | keines | Nur Git-Branch fortgeschrieben; noch keine Lieferung |
| Release bauen und übergeben | Push eines Tags `Rnnn.nnn` oder manuelle Durchführung des Workflows mit vorhandenem Tag | `release.yml` | `reusable-release.yml` | `build-release`, danach `publish-mainframe` | FULL/DELTA-Artefakt gebaut, geprüft und nach Freigabe per FTP/JES übergeben |
| Zentrale Automation testen | Pull Request in `mtext-actions` oder Push auf dessen `main` | entfällt | `ci.yml` | `unittest discover` | Unit-, Integrations- und Workflowvertragstests ausgeführt |

Die GitHub Actions führen derzeit keine Cherry-Picks aus. Die Benutzer stellen
den gewünschten Stand zuerst auf dem Branch der jeweiligen Stage her. Die
Actions verarbeiten anschließend den durch Push oder Tag festgelegten Commit.

## 2. Workflows in einem Mandanten-Repository

| YAML-Datei | GitHub-Anzeigename | Automatischer Trigger | Manueller Trigger | Aufgerufener zentraler Workflow | Zweck und Besonderheiten |
|---|---|---|---|---|---|
| [`validate-config.yml`](../../mtext-fi/.github/workflows/validate-config.yml) | `Validate mandant configuration` | `push` auf jedem Branch, aber nur bei Änderung an `config/mandant.json` | keiner | `reusable-validate-config.yml` | Frühe Feld-, Repository- und Konsistenzprüfung. Keine Secrets, kein Environment und keine externen Schreibzugriffe. Ältere laufende Prüfung derselben Repository-Referenz darf abgebrochen werden. |
| [`sync-resources.yml`](../../mtext-fi/.github/workflows/sync-resources.yml) | `Sync M/Text resources` | Jeder `push` nach `Rnnn/Entwicklung` oder `Rnnn/Abnahme` | `workflow_dispatch` mit vollständiger `commit_sha` und `source_branch` | `reusable-sync-resources.yml` | Wählt abhängig von der Branchendung den fest zugeordneten Job und das Environment `Entwicklung` oder `Abnahme`. Dient auch der initialen Vollsynchronisation und kontrollierten Wiederholung. Gleiches Repository, gleiche Linie und gleicher Branch werden über eine Concurrency-Gruppe gegen parallele Ausführung geschützt. |
| [`release.yml`](../../mtext-fi/.github/workflows/release.yml) | `Build and publish release` | Push eines Tags nach dem Muster `Rnnn.nnn` | `workflow_dispatch` mit einem bereits vorhandenen `release_tag` | `reusable-release.yml` | Startet Build und nachgelagerte Veröffentlichung. Der Push nach `Bereitstellung` allein ist ausdrücklich kein Trigger. Läufe desselben Tags werden nicht parallel ausgeführt. |

Alle drei Mandanten-Workflows besitzen nur `contents: read`. Die Referenzen auf
die zentralen wiederverwendbaren Workflows und der Input `automation_ref`
enthalten derzeit noch die Null-SHA
`0000000000000000000000000000000000000000`. Vor einem Integrationslauf muss
sie durch die vollständige SHA einer freigegebenen Version von
`mtext-actions` ersetzt werden.

## 3. Trigger-Matrix der Mandanten-Repositories

| Ereignis | Konfigurationsprüfung | M/Text-Sync Entwicklung | M/Text-Sync Abnahme | Release |
|---|---:|---:|---:|---:|
| Push einer Ressourcenänderung auf einen Feature-Branch | nein | nein | nein | nein |
| Push mit Änderung an `config/mandant.json` auf einen Feature-Branch | ja | nein | nein | nein |
| Beliebiger Push nach `Rnnn/Entwicklung` | nur wenn `config/mandant.json` geändert wurde | ja | nein | nein |
| Beliebiger Push nach `Rnnn/Abnahme` | nur wenn `config/mandant.json` geändert wurde | nein | ja | nein |
| Beliebiger Push nach `Rnnn/Bereitstellung` | nur wenn `config/mandant.json` geändert wurde | nein | nein | nein |
| Push eines Tags `Rnnn.nnn` | nein | nein | nein | ja |
| Manuelle Durchführung von `Sync M/Text resources` mit Entwicklungsbranch | nein | ja | nein | nein |
| Manuelle Durchführung von `Sync M/Text resources` mit Abnahmebranch | nein | nein | ja | nein |
| Manuelle Durchführung von `Build and publish release` mit vorhandenem Tag | nein | nein | nein | ja |
| Pull Request im Mandanten-Repository | nein | nein | nein | nein |

Wichtig: Der Sync-Workflow besitzt keinen Pfadfilter. Auch ein Push auf einen
Entwicklungs- oder Abnahmebranch, der nur Dokumentation oder technische Dateien
ändert, startet daher den vollständigen Ressourcensync. Dabei werden weiterhin
nur die in `config/mandant.json` erlaubten Projektpfade nach M/Text kopiert.

Der separate Konfigurationscheck ist kein vorgeschaltetes `needs`-Gate für
Sync oder Release. Ändert ein Push nach Entwicklung oder Abnahme zugleich
`config/mandant.json`, können Konfigurationscheck und Sync unabhängig
voneinander laufen. Der Sync validiert die verwendete Konfiguration auf seinem
eigenen Ausführungspfad erneut, bevor er auf ein externes Ziel schreibt. Ebenso
validiert der Releasebau die getaggte Konfiguration selbst.

## 4. Zentrale YAML-Workflows in `mtext-actions`

| YAML-Datei | Trigger | Jobs und Abhängigkeiten | Aufgerufene Implementierung | Externe Wirkung |
|---|---|---|---|---|
| [`reusable-validate-config.yml`](../../mtext-actions/.github/workflows/reusable-validate-config.yml) | ausschließlich `workflow_call` | Ein Job `validate`: Mandanten-Commit auschecken → gepinnte Automation auschecken → Python-Laufzeit vorbereiten → Konfiguration prüfen | `python -m lbs_delivery validate-config` | Keine; liest nur Repository und Konfiguration |
| [`reusable-sync-resources.yml`](../../mtext-actions/.github/workflows/reusable-sync-resources.yml) | ausschließlich `workflow_call` | Ein Job `sync`: exakten Mandanten-Commit mit vollständiger Historie auschecken → Automation auschecken → Laufzeit vorbereiten → Ressourcen synchronisieren. Bindet das übergebene GitHub Environment `Entwicklung` oder `Abnahme`. | `python -m lbs_delivery sync-resources --execute` | Schreibt die konfigurierten Projekte nach serverSync und ruft den M/Text-Adapter synchron per HTTPS auf |
| [`reusable-release.yml`](../../mtext-actions/.github/workflows/reusable-release.yml) | ausschließlich `workflow_call` | Job `build` erzeugt und speichert das Releaseartefakt. Job `publish` hat `needs: build`, lädt genau dieses Artefakt, bindet das Environment `Bereitstellung`, wartet dort auf die eingerichtete Freigabe und veröffentlicht anschließend. | `build-release`, danach `publish-mainframe --execute` | Build zunächst nur innerhalb des Laufs; Publish überträgt Pakete per FTP und reicht JCL bei JES ein |
| [`ci.yml`](../../mtext-actions/.github/workflows/ci.yml) | jeder Pull Request sowie Push auf `main` in `mtext-actions` | Ein Job `test`: Automation auschecken → Laufzeit vorbereiten → alle Tests ausführen | `python -m unittest discover -s tests -v` | Keine vorgesehenen externen Seiteneffekte |

Die wiederverwendbaren Workflows können nicht direkt über die Oberfläche
gestartet werden. Sie benötigen einen `workflow_call` aus dem jeweiligen
Mandanten-Workflow. Alle zentralen Workflows verwenden Self-hosted Runner mit
den Labels `self-hosted`, `linux` und standardmäßig `mtext-delivery`.

## 5. Python-Kommandos als fachliche Workflow-Schicht

Der Einstieg erfolgt immer über
[`__main__.py`](../../mtext-actions/src/lbs_delivery/__main__.py) und
[`cli.py`](../../mtext-actions/src/lbs_delivery/cli.py).

| Python-Kommando | Aufgerufen durch | Wesentliche Eingaben | Prüfungen und Abhängigkeiten | Ergebnis beziehungsweise Nebenwirkung |
|---|---|---|---|---|
| `validate-config` | `reusable-validate-config.yml` | Mandantenkonfiguration, Releaselinienzuordnung und Repositoryname | `config.py`: verwendete Felder und Werte, passende Repository-Identität, eindeutige Projekte und Liefercodes | Status `CONFIG_VALIDATED`; keine externe Nebenwirkung |
| `sync-resources` | `reusable-sync-resources.yml` | exakte Commit-SHA, Quellbranch, Ziel-Environment, Konfigurationen, Stagingpfad | `config.py`: Branch und Environment passen zusammen; `git_refs.py`: vollständige SHA, HEAD entspricht SHA, Commit ist vom Remote-Branch der gewählten Stage erreichbar; `resources.py`: nur erlaubte Projekte, keine unsicheren Pfade oder Symlinks | Kopiert den vollständigen erlaubten Projektstand ins serverSync-Ziel, ruft über `mtext_adapter.py` den HTTPS-Adapter auf und liefert `ADAPTER_ACCEPTED` |
| `build-release` | Job `build` in `reusable-release.yml` | Release-Tag, optional Trigger-SHA, getaggtes Repository, Mandantenkonfiguration und Releaselinienzuordnung | Tagformat und konfigurierte Releaselinie; Tag vom passenden Bereitstellungsbranch erreichbar; Checkout entspricht Tag-SHA; DELTA-Basis `.100`; vorheriger Tag; sichere Projektpfade | Erzeugt reproduzierbare FULL- oder kumulative DELTA-TAR.GZ-Dateien, Informationsdateien und `manifest.json` mit SHA-256-Prüfsummen; Status `ARTIFACT_READY` |
| `publish-mainframe` | Job `publish` in `reusable-release.yml` | Manifest, heruntergeladenes Artefakt, JCL-Template, temporärer JCL-Pfad und FTP-Secrets aus dem Environment | `manifest.py`: verwendete Felder, Querverweise, Pfade, Größen und SHA-256; `mainframe.py`/`jcl.py`: JCL-Werte, Member und Eingabedateien | Rendert je Paket JCL, überträgt das Paket per FTP in das Dataset und reicht die JCL bei JES ein; Status `MAINFRAME_SUBMITTED` |

Die Python-CLI übersetzt fachliche Fehler in stabile Statuswerte und
Prozess-Exitcodes. Ein von null verschiedener Exitcode lässt den jeweiligen
GitHub-Job fehlschlagen.

## 6. Unterstützende Python- und Shell-Komponenten

| Komponente | Verwendet von | Aufgabe |
|---|---|---|
| [`runner-preflight.sh`](../../mtext-actions/scripts/runner-preflight.sh) | allen zentralen YAML-Workflows | Prüft Git und die festgelegte System-Python-Version. Die Delivery-CLI verwendet nur die Standardbibliothek; eine Paketinstallation ist nicht erforderlich. |
| [`config.py`](../../mtext-actions/src/lbs_delivery/config.py) | `validate-config`, Sync und Releasebau | Lädt und validiert Mandantenkonfiguration und Releaselinienzuordnung; Stage-Suffixe, serverSync-Pfad und Adapter-URL sind fest abgeleitet. |
| [`git_refs.py`](../../mtext-actions/src/lbs_delivery/git_refs.py) | Sync und Releasebau | Löst vollständige SHAs und Tags auf, prüft Erreichbarkeit aus Branches, ermittelt vorherige Release-Tags und Git-Diffs. |
| [`resources.py`](../../mtext-actions/src/lbs_delivery/resources.py) | Sync | Staged die erlaubten Ressourcen und ersetzt die Projektverzeichnisse im serverSync-Ziel möglichst atomar. |
| [`mtext_adapter.py`](../../mtext-actions/src/lbs_delivery/mtext_adapter.py) | Sync | Sendet den konfigurierten Payload per HTTPS und akzeptiert unmittelbare HTTP-2xx-Antworten. Kein nachgelagertes Status-Polling. |
| [`release.py`](../../mtext-actions/src/lbs_delivery/release.py) | Releasebau | Bestimmt FULL/DELTA, ermittelt kumulative und direkte Diffs und baut reproduzierbare Archive sowie Informationsdateien. |
| [`manifest.py`](../../mtext-actions/src/lbs_delivery/manifest.py) | Releasebau und Publish | Erzeugt beziehungsweise validiert das Manifest und prüft Dateigrößen sowie SHA-256-Prüfsummen an der Build-Publish-Grenze. |
| [`mainframe.py`](../../mtext-actions/src/lbs_delivery/mainframe.py) | Publish | Liest FTP-Secrets, rendert paketbezogene JCL und führt die FTP-/JES-Übergabe aus. |
| [`jcl.py`](../../mtext-actions/src/lbs_delivery/jcl.py) | Publish über `mainframe.py` | Ersetzt und validiert die Marker des JCL-Templates. |
| [`paths.py`](../../mtext-actions/src/lbs_delivery/paths.py) | Sync, Releasebau und Publish | Verhindert absolute Pfade, Traversal außerhalb erlaubter Wurzeln und unzulässige Symlinks. |
| [`delivery_names.py`](../../mtext-actions/src/lbs_delivery/delivery_names.py) | Konfigurationsprüfung und Releasebau | Leitet die freigegebenen historischen Projektcodes für Paketnamen und Mainframe-Member ab. |
| [`errors.py`](../../mtext-actions/src/lbs_delivery/errors.py) | gesamte Python-Schicht | Definiert stabile Ergebnis- und Fehlerstatus sowie zugehörige Exitcodes. |

## 7. Abhängigkeitsketten

| Einstieg | Abhängigkeitskette |
|---|---|
| Konfigurationsänderung | `mtext-fi/validate-config.yml` → `mtext-actions/reusable-validate-config.yml` → `runner-preflight.sh` → `lbs_delivery validate-config` → `config.py` |
| Push Entwicklung oder Abnahme | `mtext-fi/sync-resources.yml` → `mtext-actions/reusable-sync-resources.yml` → `runner-preflight.sh` → `lbs_delivery sync-resources` → `config.py` + `git_refs.py` + `resources.py` → serverSync → `mtext_adapter.py` → M/Text-Adapter |
| Release-Tag | `mtext-fi/release.yml` → `mtext-actions/reusable-release.yml` → Job `build` → `build-release` → GitHub-Artefakt → Job `publish` → Environment-Freigabe `Bereitstellung` → `publish-mainframe` → FTP-Dataset + JES |
| Änderung an zentraler Automation | `mtext-actions/ci.yml` → `runner-preflight.sh` → `unittest discover` → Unit-, Integrations- und Workflowvertragstests |

## 8. Verwendete externe GitHub Actions

| Action | Verwendet in | Zweck |
|---|---|---|
| `actions/checkout` mit fest gepinnter Commit-SHA | allen zentralen YAML-Workflows | Checkt Mandanten-Repository und/oder zentrale Automation ohne gespeicherte Git-Credentials aus. Sync und Releasebau verwenden für die Branch- und Tagprüfung `fetch-depth: 0`. |
| `actions/upload-artifact` mit fest gepinnter Commit-SHA | Release-Job `build` | Speichert `dist/` als eindeutig benanntes Laufartefakt für den nachfolgenden Publish-Job. |
| `actions/download-artifact` mit fest gepinnter Commit-SHA | Release-Job `publish` | Lädt genau das vom Build-Job benannte Artefakt zur erneuten Prüfung und Übergabe. |

Es werden keine Actions über bewegliche Referenzen wie `main` oder einen
ungepinnten Versionstag eingebunden.

## 9. Environments, Secrets, Rechte und Serialisierung

| Bereich | Umsetzung |
|---|---|
| Repositoryrechte | Alle vorhandenen Workflows deklarieren `contents: read`; aktuell kann kein Workflow Commits, Branches oder Tags schreiben. |
| Environments Entwicklung/Abnahme | Der Sync-Job bindet abhängig vom fest gewählten Mandanten-Job genau eines dieser Environments. Derzeit werden dort keine Secrets gelesen. |
| Environment Bereitstellung | Nur der Publish-Job bindet dieses Environment. Die manuelle Freigabe wird in GitHub konfiguriert, nicht in YAML. |
| Mainframe-Secrets | Ausschließlich `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD` im Publish-Job. |
| Runner-Abhängigkeiten | Self-hosted Linux-Runner, Git, konfigurierte Python-Version sowie Zugriff auf serverSync, Adapter und Mainframe entsprechend dem Job. |
| Sync-Serialisierung | Concurrency-Gruppe je Repository und Branch einer Stage; ein bereits laufender Sync wird nicht aktiv abgebrochen. |
| Release-Serialisierung | Aufrufender Workflow gruppiert je Repository und Tag; Mainframe-Publish wird bei `serialize_publication: true` zusätzlich je Mandanten-Repository serialisiert. |
| Build-Publish-Grenze | Der Build lädt ein benanntes GitHub-Artefakt hoch. Publish lädt genau dieses Artefakt herunter und prüft Manifest, Größen und SHA-256 erneut. |

## 10. Was nicht durch einen Workflow automatisiert ist

| Vorgang | Aktueller Stand |
|---|---|
| Commit und Push in Entwicklung | Benutzeraktion im vorgesehenen Git-Client beziehungsweise in der M/Text Workbench |
| Cherry-Pick Entwicklung → Abnahme | Benutzeraktion; `-x` beziehungsweise Quell-SHA wird nicht technisch erzwungen |
| Cherry-Pick Abnahme → Bereitstellung | Benutzeraktion des berechtigten Release-Teams; Herkunft wird nicht technisch geprüft |
| Konfliktauflösung | Fachlich kontrollierte Benutzeraktion; keine automatische Entscheidung durch GitHub Actions |
| Release-Tag anlegen | Benutzeraktion des Release-Teams; erst der Tag-Push startet den Workflow |
| Branch-, Tag- und Pushschutz | GitHub Rulesets und Repository-/Organisationseinstellungen außerhalb der YAML-Dateien |
| Environment-Freigabe | GitHub-Environment-Konfiguration außerhalb der YAML-Dateien |
