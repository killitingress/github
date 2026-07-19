# `mtext-actions`

Dieses Repository enthält die zentrale M/Text-Lieferautomation. Sie stellt
vier CLI-Kommandos für die wiederverwendbaren GitHub-Workflows bereit:

- `validate-config`
- `sync-resources`
- `build-release`
- `publish-mainframe`

Die Anwendung benötigt nur die Python-Standardbibliothek.

## Aufbau

- `cli.py`: Kommandozeile, Ausgabe und Exitcodes
- `config.py`: Mandanten- und Releaselinienkonfiguration
- `git.py`: Commit-, Branch-, Tag- und Diff-Abfragen
- `sync.py`: Staging, `serverSync` und M/Text-Adapter
- `release.py`: FULL, DELTA, Archive und Informationsdateien
- `manifest.py`: Manifest und Artefaktprüfung vor der Übergabe
- `mainframe.py`: JCL-Rendering und FTP-/JES-Übergabe
- `errors.py`: Status- und Fehlervertrag
- `src/workflow_configuration.py`: interne Vorbereitung der zentralen und
  mandantenseitigen Workflowdateien

## Lokale Prüfung

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m lbs_delivery --help
```

## Workflowdateien über GitHub einrichten

Der manuell gestartete Workflow **Configure workflow files** setzt das
bestätigte FI-Runner-Kennzeichen in den zentralen Fach- und Testjobs und bindet
Workflowaufruf sowie Python-Checkout eines Mandanten-Repositories gemeinsam an
den daraus entstehenden vollständigen Commit-SHA von `mtext-actions`.

Vor dem ersten Lauf werden in GitHub eingerichtet:

- der abgenommene FI-Runner,
- die Repositoryvariable `FI_RUNNER_LABEL` in `mtext-actions`,
- das Environment `Einrichtung` mit dem Secret
  `WORKFLOW_CONFIGURATION_TOKEN`.

Das technische Token ist auf `mtext-actions` und die vorgesehenen
Mandanten-Repositories begrenzt. Es benötigt dort die Berechtigung, geschützte
Workflowdateien auf den ausgewählten Branches festzuschreiben.

Unter **Actions** wird **Configure workflow files** mit dem vollständigen
Mandanten-Repository und dem Zielbranch gestartet. Der Lauf validiert beide
Dateisätze, erzeugt zunächst den zentralen Commit und bindet danach den
Mandanten-Commit an dessen vollständige SHA. Erst wenn die abschließende Prüfung
keine Änderung mehr ermittelt, werden beide Commits in dieser Reihenfolge
gepusht. Die vorgenommenen Änderungen bleiben als Diffs im Workflow-Log
sichtbar. Ein erneuter Lauf erzeugt keine weiteren Commits. Für jedes weitere
Repository oder jeden weiteren Zielbranch wird der Ablauf wiederholt.

Die technische Umsetzung liegt außerhalb der Lieferlogik unter
`src/workflow_configuration.py`. Der Workflow führt keinen Code aus dem
Mandanten-Repository aus.

Rulesets, weitere Environments, Team-Zuordnungen und Actions-Zugriffe werden
erst über den noch offenen API-Teil der Einrichtungsautomation angewendet, wenn
die dafür benötigten Rollen und IDs bestätigt sind.
