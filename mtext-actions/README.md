# `fi_lbs_entw_oms_mtext_actions`

Das Repository `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, kurz
`mtext_actions`, enthält die zentrale CI/CD-Automatisierung für
Mandantenkonfiguration, M/Text-Synchronisation, Releasebau und
Mainframe-Übergabe.

## Git-Vertrag

- `main` vertritt die führende Releaselinie eines Mandanten.
- `release/Rnnn` vertritt eine parallel gepflegte Releaselinie.
- `feature/Rnnn/<Bezeichnung>` enthält eine einzelne Änderung.
- Feature-Pushes synchronisieren nach M/Text-Entwicklung.
- Merges nach `main` oder `release/Rnnn` synchronisieren nach M/Text-Abnahme.
- Manuelle Läufe gleichen einen Commit vollständig mit dem Ziel seines Branches
  ab.
- Ein Wechsel der auf `main` konfigurierten Releaselinie gleicht den ersten
  Stand automatisch vollständig mit Entwicklung und Abnahme ab.
- Tags wie `v261.100` und `v261.108` starten den zentralen Releaseweg.

## Aufbau

- `src/validate_config.py`: Prüfung der Mandantenkonfiguration
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
- `config/releaselinien.json`: aktive Releaselinien, ETAPS-Linien und Hostprofile

## GitHub-Konfiguration

In `mtext_actions` werden eingerichtet:

| Name | Art | Verwendung |
|---|---|---|
| `FI_RUNNER_LABEL` | Repositoryvariable | Runner des Aktualisierungsworkflows |
| `MAINFRAME_FTP_HOST` | Repositoryvariable | FTP-Ziel |
| `MAINFRAME_FTP_USER` | Repositoryvariable | zentraler technischer FTP-Benutzer |
| `MAINFRAME_FTP_PASSWORD` | Repository-Secret | FTP-Passwort für den zentralen Übergabejob |
| `WORKFLOW_CONFIGURATION_TOKEN` | Repository-Secret | Mandantenstände lesen, Aktualisierungsbranches und Pull Requests erstellen sowie Lieferinformationen veröffentlichen |

`WORKFLOW_CONFIGURATION_TOKEN` gilt für die zugeordneten
Mandanten-Repositories. Es benötigt dort `Contents: read and write` und
`Pull requests: read and write`.

Jedes Mandanten-Repository erhält `MTEXT_ACTIONS_TOKEN` als Repository-Secret.
Der Fine-grained PAT ist auf
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` begrenzt und besitzt dort
`Contents: read` sowie `Actions: write`.

GitHub Environments werden nicht verwendet.

## Workflow-Aktualisierungen

Der manuell gestartete Workflow **Update mandant workflows** erhält die
vollständige Commit-SHA der gewünschten CI/CD-Version von `mtext_actions`. Er
prüft, dass alle Runnerkennzeichen
festgelegt sind, und verarbeitet für jeden Mandanten:

- `main`,
- vorhandene `release/Rnnn`-Branches der aktiven Releaselinien.

Der Lauf trägt diese Commit-SHA in den bestehenden Mandanten-Workflows ein und
erstellt einen technischen Branch mit Pull Request. Er pusht nicht direkt auf
einen geschützten Branch. Nicht vorhandene Release-Branches werden
übersprungen. Feature-Branches sind keine Rollout-Ziele.

## Automatische Prüfung

Jeder Pull Request startet den GitHub-Workflow **Central tests**. Er führt die
Python-Tests auf dem dafür vorgesehenen Runner aus, ohne M/Text oder den
Mainframe anzusprechen. Vor dem Zusammenführen muss der Testjob
**Test central CI/CD implementation** erfolgreich abgeschlossen sein.

Die Anwendung benötigt Python ab Version 3.11 und verwendet für ihre
Produktivlogik die Standardbibliothek.
