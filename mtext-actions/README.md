# `mtext-actions`

Dieses Dokument richtet sich an Entwickler und technische Verantwortliche der
zentralen M/Text-Automatisierung. Die Bedienung in den Mandanten-Repositories
ist in der [Benutzeranleitung](../docs/confluence/Benutzeranleitung.md)
beschrieben.

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

Der manuell gestartete Workflow **Configure workflow files** setzt das von der
FI bestätigte Runner-Kennzeichen in den zentralen Fach- und Testjobs und bindet
Workflowaufruf sowie Python-Checkout eines Mandanten-Repositories gemeinsam an
den daraus entstehenden vollständigen Commit-SHA von `mtext-actions`.

Vor dem ersten Lauf werden in GitHub eingerichtet:

- der abgenommene Runner der FI,
- die Repositoryvariable `FI_RUNNER_LABEL` in `mtext-actions`,
- das Environment `Einrichtung` mit dem Secret
  `WORKFLOW_CONFIGURATION_TOKEN`.

Das technische Token ist auf `mtext-actions` und die vorgesehenen
Mandanten-Repositories begrenzt. Es benötigt dort die Berechtigung, geschützte
Workflowdateien auf den ausgewählten Branches festzuschreiben.

Unter **Actions** wird **Configure workflow files** mit drei Angaben gestartet:

- vollständige Commit-SHA der freigegebenen `mtext-actions`-Version,
- vollständiger Name des Mandanten-Repositories,
- zu aktualisierender Mandantenbranch.

Der Lauf checkt exakt die angegebene zentrale SHA aus und lehnt einen
abweichenden Stand ab. Bei der erstmaligen Einrichtung kann die Finalisierung
des Runner-Kennzeichens noch einen zentralen Commit erzeugen. Dessen im Log
ausgewiesene SHA ist anschließend die gemeinsame Rollout-Version. Spätere
Versionen enthalten bereits das feste Runner-Kennzeichen und verändern das
zentrale Repository nicht mehr.

Der Mandanten-Commit bindet Workflowaufruf und Python-Checkout gemeinsam an die
Rollout-Version. Erst wenn die abschließende Prüfung keine Änderung mehr
ermittelt, wird er gepusht. Die vorgenommenen Änderungen bleiben als Diffs im
Workflow-Log sichtbar. Ein erneuter Lauf mit derselben SHA erzeugt keine
weiteren Commits. Der Lauf wird für jeden Eintrag der freigegebenen
Rollout-Matrix aus Mandanten-Repository und Branch wiederholt.

Die technische Umsetzung liegt außerhalb der Lieferlogik unter
`src/workflow_configuration.py`. Der Workflow führt keinen Code aus dem
Mandanten-Repository aus.

Rulesets, weitere Environments, Team-Zuordnungen und Actions-Zugriffe gehören
nicht zum derzeitigen Workflow. Ihre Umsetzung und Abnahme sind in
[Nächste Schritte](../docs/confluence/Naechste_Schritte.md) als offener
API-Teil geführt.
