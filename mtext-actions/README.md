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

## Lokale Prüfung

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m lbs_delivery --help
```

## Workflowdateien für die Einrichtung finalisieren

Das Einrichtungskommando setzt das bestätigte FI-Runner-Kennzeichen in allen
zentralen Jobs und bindet Workflowaufruf sowie Python-Checkout aller angegebenen
Mandanten-Repositories gemeinsam an eine freigegebene Commit-SHA. Ohne
`--apply` verändert es keine Datei und liefert einen Prüfbericht:

```bash
python3 scripts/configure-workflows.py \
  --automation-sha <vollständige-commit-sha> \
  --runner-label <fi-runner-kennzeichen> \
  --mandant-root ../mtext-fi
```

Der Plan weist bestehende Abweichungen zwischen `uses:` und `automation_ref`
als `pin_mismatches` und notwendige Änderungen als `changed_files` aus. Vor dem
ersten Schreibzugriff prüft das Kommando alle betroffenen Workflowdateien.
`--apply` ersetzt anschließend jede Datei atomar. Der Gesamtvorgang über mehrere
Repositoryverzeichnisse ist keine gemeinsame Dateisystemtransaktion; nach einem
Schreibfehler setzt ein erneuter idempotenter Lauf die noch ausstehenden
Dateien. Weitere `--mandant-root`-Argumente nehmen zusätzliche
Mandanten-Repositories auf.

Nach `--apply` werden die Änderungen in jedem betroffenen Repository geprüft
und über den vorgesehenen technischen Freigabeweg als Commit festgeschrieben.
Ein abschließender Planlauf mit denselben Eingaben muss sowohl für
`changed_files` als auch für `pin_mismatches` eine leere Liste liefern.

Das Kommando verändert keine GitHub-Einstellungen und liest keine Secrets.
Rulesets, Environments, Team-Zuordnungen und Actions-Zugriffe werden erst über
die GitHub-Enterprise-API angewendet, wenn die dafür benötigten Rollen und IDs
bestätigt sind.
