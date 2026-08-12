# `fi_lbs_entw_oms_mtext_actions`

Das Repository `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, kurz
`mtext_actions`, enthält die zentrale CI/CD-Automatisierung für
Mandantenkonfiguration, M/Text-Synchronisation, Releasebau und
Mainframe-Übergabe.

## Git-Vertrag

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
- Tags wie `v261.100` und `v261.108` starten den zentralen Releaseweg.

## Aufbau

- `src/validate_config.py`: Prüfung der Mandantenkonfiguration
- `src/check_resources.py`: warnende Syntaxprüfung für JSON- und XML-Ressourcen
- `src/sync_resources.py`: Einstieg in die Ressourcensynchronisation
- `src/build_release.py`: Einstieg in den Releasebau
- `src/publish_mainframe.py`: Einstieg in die Mainframe-Übergabe
- `src/publish_github_release.py`: Rückmeldung im Mandanten-Repository
- `src/workflow_configuration.py`: geprüfte Workflow-Aktualisierungen
- `src/lbs_delivery/config.py`: Mandanten- und Releaselinienkonfiguration
- `src/lbs_delivery/git.py`: Commit-, Branch-, Tag- und Diff-Abfragen
- `src/lbs_delivery/sync.py`: dauerhafter `serverSync`-Stand und LTOMA-Aufruf
- `src/lbs_delivery/release.py`: FULL, DELTA, Archive und Lieferbelege
- `src/lbs_delivery/manifest.py`: Manifest und Artefaktprüfung
- `src/lbs_delivery/mainframe.py`: JCL-Rendering und FTP-/JES-Übergabe
- `src/lbs_delivery/github_release.py`: GitHub Release und Informationsdateien
- `config/mandanten.json`: Mandantenkürzel, Repositories und Subsysteme
- `config/ressourcenformate.json`: Dateiendungen und ihr technisches Format
- `config/releaselinien.json`: M/Text-Zielpräfixe, aktive Releaselinien,
  ETAPS-Linien und Hostprofile

## GitHub-Konfiguration

In `mtext_actions` werden eingerichtet:

| Name | Art | Verwendung |
|---|---|---|
| `MAINFRAME_FTP_HOST` | Repositoryvariable | FTP-Ziel |
| `MAINFRAME_FTP_USER` | Repositoryvariable | zentraler technischer FTP-Benutzer |
| `MAINFRAME_FTP_PASSWORD` | Repository-Secret | FTP-Passwort für den zentralen Übergabejob |
| `WORKFLOW_CONFIGURATION_TOKEN` | Repository-Secret | Mandanten-Workflows administrativ ausrollen und Lieferinformationen veröffentlichen |

`WORKFLOW_CONFIGURATION_TOKEN` gilt für die zugeordneten
Mandanten-Repositories. Es benötigt dort `Contents: read and write` und
`Workflows: read and write`. Der technische Benutzer ist in den Schutzregeln
als Ausnahme von der Pull-Request-Pflicht für den administrativen Rollout
hinterlegt.

Jedes Mandanten-Repository erhält `MTEXT_ACTIONS_TOKEN` als Repository-Secret.
Der Fine-grained PAT ist auf
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` begrenzt und besitzt dort
`Contents: read` sowie `Actions: write`.

GitHub Environments werden nicht verwendet.

## Workflow-Aktualisierungen

Der manuell gestartete Workflow **Mandanten-Workflows aktualisieren** erhält die
vollständige Commit-SHA der gewünschten CI/CD-Version von `mtext_actions`. Er
wird von den zuständigen Admins gestartet, prüft die freigegebene
CI/CD-Version und verarbeitet für jeden Mandanten:

- `main`,
- vorhandene `release/Rnnn`-Branches der aktiven Releaselinien.

Der Lauf trägt diese Commit-SHA in den bestehenden Mandanten-Workflows ein und
pusht den Rollout-Commit direkt auf den jeweiligen Zielbranch. Nicht vorhandene
Release-Branches werden übersprungen. Feature-Branches sind keine
Rollout-Ziele. Der Rollout enthält ausschließlich Änderungen unter
`.github/workflows` und startet keine M/Text-Synchronisation.

## Automatische Prüfung

Jeder Pull Request in `mtext_actions` und jede Änderung an `main` startet den
GitHub-Workflow **Zentrale Testsuite**. Er führt die Python-Tests auf dem dafür
vorgesehenen Runner aus, ohne M/Text oder den Mainframe anzusprechen. Vor dem
Zusammenführen muss der Testjob **Testet Zentrale CI/CD-Implementierung**
erfolgreich abgeschlossen sein.

Die Anwendung benötigt Python ab Version 3.11 und verwendet für ihre
Produktivlogik die Standardbibliothek.

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
