# `mtext-actions`

Dieses Repository enthält die zentrale Automation für die Synchronisation von
M/Text-Ressourcen sowie den Bau und die Mainframe-Übergabe von FULL- und
DELTA-Lieferungen. Mandanten-Repositories wie `mtext-fi` rufen die
wiederverwendbaren Workflows mit einer vollständigen Commit-SHA auf.

Das Repository richtet sich an das zentrale Automatisierungsteam. Die tägliche
Arbeit der Text-Entwickler findet im jeweiligen Mandanten-Repository statt.

## Bestandteile

- `.github/workflows/`: zentrale Validierungs-, Synchronisations-, Release- und
  CI-Workflows
- `src/lbs_delivery/`: Python-Implementierung der Lieferabläufe
- `config/releaselinien.json`: Zuordnung von Releaselinien, M/Text-Linien und
  Übergabeprofilen
- `templates/mainframe-upload.jcl`: versioniertes JCL-Template
- `scripts/runner-preflight.sh`: Prüfung der Runner-Laufzeit
- `tests/`: Unit-, Integrations- und Workflowvertragstests

## Lokale Entwicklung

Benötigt wird Python 3.14. Die Anwendung verwendet ausschließlich die
Python-Standardbibliothek.

Tests ausführen:

```bash
cd mtext-actions
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

CLI-Hilfe anzeigen:

```bash
PYTHONPATH=src python3 -m lbs_delivery --help
PYTHONPATH=src python3 -m lbs_delivery <kommando> --help
```

Die vier Kommandos heißen `validate-config`, `sync-resources`, `build-release`
und `publish-mainframe`. Im regulären Betrieb setzen die wiederverwendbaren
Workflows deren Argumente.

## Zentrale Releaselinienzuordnung

[`config/releaselinien.json`](config/releaselinien.json) enthält je
Releaselinie genau `mtext_linie` und `uebergabeprofil`. Der dort genannte Name
muss unter `hostprofile` in der Mandantenkonfiguration vorhanden sein. Neue
Releaselinien werden mit
den zugehörigen drei Branches und dem fachlich bestätigten Ausgangsstand
eingerichtet.

## Runner und GitHub

Die Workflows erwarten einen Self-hosted Linux-Runner mit den Labels
`self-hosted`, `linux` und `mtext-delivery`, Git, Python 3.14 sowie Unterstützung
für Node.js-20-Actions.

In GitHub werden die Environments `Entwicklung`, `Abnahme` und
`Bereitstellung` eingerichtet. Die Mainframe-Übergabe verwendet in
`Bereitstellung` die Secrets `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und
`MAINFRAME_FTP_PASSWORD`. Änderungen am zentralen Workflowvertrag werden über
eine neue Commit-SHA in den Mandanten-Repositories freigegeben.

## Weiterführende Dokumentation

- [Technisches Zielbild](../docs/confluence/Zielbild_GitHub_Actions_Git.md)
- [Benutzeranleitung](../docs/confluence/Benutzeranleitung.md)
- [Migration und Cutover](../docs/confluence/Migration.md)
- [Nächste Schritte](../docs/confluence/Naechste_Schritte.md)
