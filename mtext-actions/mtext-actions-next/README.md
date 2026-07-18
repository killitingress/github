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
