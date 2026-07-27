# `mtext-actions`

Das Repository stellt vier CLI-Kommandos für die wiederverwendbaren
GitHub-Workflows bereit:

- `validate-config`
- `sync-resources`
- `build-release`
- `publish-mainframe`

Die Anwendung benötigt nur die Python-Standardbibliothek.

## Aufbau

- `cli.py`: Kommandozeile, Ausgabe und Exitcodes
- `config.py`: Mandanten- und Releaselinienkonfiguration
- `config/mandanten.json`: vollständige GitHub-Namen, Mandantenkürzel und
  Mainframe-Subsysteme
- `config/releaselinien.json`: aktive Releaselinien, ETAPS-Linien und
  Hostprofile
- `git.py`: Commit-, Branch-, Tag- und Diff-Abfragen
- `sync.py`: Staging, `serverSync` und M/Text-Adapter
- `release.py`: FULL, DELTA, Archive und Informationsdateien
- `manifest.py`: Manifestvertrag und Artefaktprüfung vor der Übergabe
- `mainframe.py`: JCL-Rendering und FTP-/JES-Übergabe
- `errors.py`: Status- und Fehlervertrag
- `src/workflow_configuration.py`: interne Vorbereitung der zentralen und
  mandantenseitigen Workflowdateien

## Lokale Prüfung

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m lbs_delivery --help
```

Die vier Lieferkommandos laufen im festen Aufbau der wiederverwendbaren
Workflows. `GITHUB_WORKSPACE/source` enthält den Mandantenstand,
`GITHUB_REPOSITORY` dessen vollständigen Namen und `RUNNER_TEMP` die
kurzlebigen Arbeitsverzeichnisse. Zentrale Konfiguration und JCL-Vorlage
werden aus derselben `mtext-actions`-Version wie der Python-Code gelesen.
Die CLI nimmt deshalb nur Commit oder Tag entgegen, wenn das jeweilige
Kommando diese Laufdaten benötigt. Der Sync-Branch stammt aus
`GITHUB_REF_NAME`.

## Mandanten-Workflows im Batch aktualisieren

Der manuell gestartete Workflow **Update mandant workflows** setzt das von der
FI festgelegte Runner-Kennzeichen in den zentralen Fach- und Testjobs und bindet
Workflowaufruf sowie Python-Checkout aller vorgesehenen Mandantenbranches an
dieselbe vollständige Commit-SHA von `mtext-actions`.

Vor dem ersten Lauf werden in GitHub eingerichtet:

- der abgenommene Runner der FI,
- die Repositoryvariable `FI_RUNNER_LABEL` in `mtext-actions`,
- das Environment `Einrichtung` mit dem Secret
  `WORKFLOW_CONFIGURATION_TOKEN`.

Das technische Token ist auf `mtext-actions` und die vorgesehenen
Mandanten-Repositories begrenzt. Es benötigt dort die Berechtigung, geschützte
Workflowdateien auf den ausgewählten Branches festzuschreiben.

Unter **Actions** wird **Update mandant workflows** mit der vollständigen
SHA des `mtext-actions`-Commits gestartet.

Der Vorbereitungsjob checkt den angegebenen Commit aus und vergleicht seine
SHA mit der Eingabe. Bei der erstmaligen Aktualisierung kann die
Finalisierung des Runner-Kennzeichens noch einen zentralen Commit erzeugen.
Dessen SHA ist anschließend die gemeinsame Rollout-Version. Spätere Versionen
enthalten bereits das feste Runner-Kennzeichen und verändern das zentrale
Repository nicht mehr.

Die Matrix kombiniert alle Repositories aus `config/mandanten.json`, alle
aktiven Releaselinien aus `config/releaselinien.json` und die Branchstufen
`Entwicklung`, `Abnahme` und `Bereitstellung`. Jeder Matrixjob bindet
Workflowaufruf und Python-Checkout seines Mandantenbranches gemeinsam an die
Rollout-Version. Erst wenn die abschließende Prüfung keine Änderung mehr
ermittelt, wird der Commit gepusht. Die vorgenommenen Änderungen bleiben als
Diffs im Workflow-Log sichtbar. Ein erneuter Lauf mit derselben SHA erzeugt
keine weiteren Commits.

Die technische Ablaufsteuerung liegt unter `src/workflow_configuration.py`.
Sie nutzt `lbs_delivery.config` gemeinsam mit den Lieferkommandos als
verbindliche Konfigurationsschicht. Der Workflow führt keinen Code aus dem
Mandanten-Repository aus.
