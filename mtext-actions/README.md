# `fi_lbs_entw_oms_mtext_actions`

Das Repository `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, kurz
`mtext_actions`, enthält die zentrale CI/CD-Automatisierung für
Mandantenkonfiguration, M/Text-Synchronisation, Releasebau und
Mainframe-Übergabe.

## Branches und Auslöser

- `main` vertritt die führende Releaselinie eines Mandanten.
- `release/Rnnn` vertritt eine parallel gepflegte Releaselinie.
- `feature/Rnnn/<Bezeichnung>` enthält eine einzelne Änderung.
- Feature-Pushes synchronisieren mit der Umgebung M/Text-Entwicklung.
- Merges nach `main` oder `release/Rnnn` synchronisieren mit der Umgebung
  M/Text-Funktionstest.
- Manuelle Läufe gleichen einen Commit vollständig mit dem Ziel seines Branches
  ab.
- Ein Wechsel der auf `main` konfigurierten Releaselinie gleicht den ersten
  Stand automatisch vollständig mit M/Text-Entwicklung und
  M/Text-Funktionstest ab.
- Reguläre Tags wie `v261.100` und `v261.108` entstehen standardmäßig nach dem
  Merge eines Release-Freigabe-PRs.
- Beta-Tags wie `v261.108a` können direkt erstellt werden.
- Der Push eines zulässigen Tags startet den Release-Workflow.

## Aufbau

- `src/validate_config.py`: Prüfung der Mandantenkonfiguration
- `src/check_resources.py`: warnende Syntaxprüfung für JSON- und XML-Ressourcen
- `src/sync_resources.py`: Einstieg in die Ressourcensynchronisation
- `src/release_approval.py`: Vorbereitung und Prüfung der Release-Freigabe
- `src/build_release.py`: Einstieg in den Releasebau
- `src/publish_mainframe.py`: Einstieg in die Mainframe-Übergabe
- `src/publish_github_release.py`: Rückmeldung im Mandanten-Repository
- `src/workflow_configuration.py`: Workflow-Aktualisierungen
- `src/lbs_delivery/config.py`: Mandanten- und Releaselinienkonfiguration
- `src/lbs_delivery/git.py`: Commit-, Branch-, Tag- und Diff-Abfragen
- `src/lbs_delivery/project_package.py`: gemeinsames Projektpaket für Sync und Release
- `src/lbs_delivery/release_approval.py`: versionierter Freigabenachweis
- `src/lbs_delivery/sync.py`: CIFS-Übergabe und Adapterauftrag
- `src/lbs_delivery/mainframe_release.py`: Releasebau, JCL und FTPS-/JES-Übergabe
- `src/lbs_delivery/github_release.py`: GitHub Release und Informationsdateien
- `src/lbs_delivery/github_api.py`: gemeinsame Anfragen an die GitHub-REST-API
- `config/mandanten.json`: Mandantenkürzel, Repositories und Subsysteme
- `config/ressourcenformate.json`: Dateiendungen und ihr technisches Format
- `config/releaselinien.json`: M/Text-Zielpräfixe, aktive Releaselinien,
  ETAPS-Linien und Hostprofile

## GitHub-Konfiguration

In `mtext_actions` werden eingerichtet:

| Name | Art | Verwendung |
|---|---|---|
| `MAINFRAME_FTPS_HOST` | Repositoryvariable | FTPS-Ziel |
| `MAINFRAME_FTPS_PORT` | Repositoryvariable | Steuerungsport des expliziten FTPS-Zugangs |
| `MAINFRAME_FTPS_USER` | Repositoryvariable | zentraler technischer FTPS-Benutzer |
| `MAINFRAME_FTPS_PASSWORD` | Repository-Secret | FTPS-Passwort für den zentralen Übergabejob |
| `WORKFLOW_CONFIGURATION_TOKEN` | Repository-Secret | Mandanten-Workflows ausrollen, Freigabe-Branches und Release-Tags erstellen sowie Lieferinformationen veröffentlichen |

`WORKFLOW_CONFIGURATION_TOKEN` gilt für die zugeordneten
Mandanten-Repositories. Es benötigt dort `Contents: read and write` und
`Workflows: read and write` sowie `Pull requests: read`. Der
technische Benutzer ist in den Schutzregeln als Ausnahme von der
Pull-Request-Pflicht für den administrativen Rollout hinterlegt. Die geltenden
Tag-Regeln müssen die Erstellung regulärer Release-Tags durch diese Identität
zulassen.

Jedes Mandanten-Repository erhält `MTEXT_ACTIONS_TOKEN` als Repository-Secret.
Der Fine-grained PAT ist auf
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` begrenzt und besitzt dort
`Contents: read` sowie `Actions: write`.

Die Organisationsvariable `MTEXT_CIFS_ROOT` enthält den auf dem Runner
eingehängten CIFS-Basispfad. Sie ist für die Mandanten-Repositories verfügbar,
da deren Workflows die wiederverwendbare Synchronisation aufrufen.

GitHub Environments werden nicht verwendet.

## Workflow-Aktualisierungen

Der manuell gestartete Workflow **Mandanten-Workflows aktualisieren** erhält die
vollständige Commit-SHA der gewünschten CI/CD-Version von `mtext_actions`. Er
wird von den zuständigen Admins gestartet, prüft die angegebene
CI/CD-Version und verarbeitet für jeden Mandanten:

- `main`,
- vorhandene `release/Rnnn`-Branches der aktiven Releaselinien.

Der Lauf aktualisiert unter `.github/workflows` alle `.yml`- und `.yaml`-Dateien,
die einen wiederverwendbaren Workflow aus `mtext_actions` aufrufen. Eigene
Workflows ohne einen solchen Aufruf bleiben unverändert. Anschließend pusht der
Lauf den Rollout-Commit direkt auf den jeweiligen Zielbranch. Nicht vorhandene
Mandanten-Repositories und Branches werden mit einer Warnung übersprungen.
Feature-Branches sind keine Rollout-Ziele. Der Rollout startet keine
M/Text-Synchronisation.

## Automatische Prüfung

Jeder Pull Request in `mtext_actions` und jede Änderung an `main` startet den
GitHub-Workflow **Zentrale Testsuite**. Er führt die Python-Tests auf dem dafür
vorgesehenen Runner aus, ohne M/Text oder den Mainframe anzusprechen. Vor dem
Zusammenführen muss der Testjob **Zentrale CI/CD-Implementierung testen**
erfolgreich abgeschlossen sein.

Die Anwendung benötigt Python ab Version 3.11 sowie Git und `tar`. Der
Python-Code verwendet für seine Produktivlogik die Standardbibliothek.

## Prüfung von JSON- und XML-Ressourcen

Der wiederverwendbare Workflow `reusable-check-resources.yml` prüft bei einem
Pull Request die dort hinzugefügten, geänderten und umbenannten Ressourcen.
Eine manuell gestartete Prüfung umfasst den vollständigen Mandantenstand. Die
zentrale Datei `config/ressourcenformate.json` ordnet jede berücksichtigte
Dateiendung dem Format `json` oder `xml` zu. Damit werden auch XML-Ressourcen
mit Endungen wie `.model`, `.datamodel` oder `.conf` und Form.io-Dateien mit der
Endung `.formio` vom passenden Parser geprüft.

JSON-Ressourcen müssen gültige JSON-Syntax besitzen, XML-Ressourcen müssen
wohlgeformt sein. Befunde erscheinen mit Datei und Fundstelle als Warnungen und
lassen den Prüfschritt erfolgreich enden.

Eine Prüfung der Tonic-XMLs gegen ein XSD wird ergänzt, sobald das verbindliche
XSD, seine Dateizuordnung und das dafür auf dem Runner freigegebene Werkzeug
feststehen.
