# GitHub-Actions-Vertrag

Die drei YAML-Dateien in diesem Verzeichnis sind Trigger-Workflows. Fachlogik,
Zielauflösung, Paketbau und Integrationen befinden sich im zentrale Repository.

Der Ablauf ist immer wie folgt:

- Ein Ereignis startet den entsprechenden kleinen Trigger-Workflow
- GitHub lädt die referenzierte Workflowdatei aus mtext-actions@SHA
- Die Jobs dieses zentralen Workflows laufen auf dem Runner des Mandanten-Workflows
- Der Runner checkt den Mandantenstand nach source/ aus.
- Der Runner checkt zusätzlich mtext-actions@automation_ref nach automation/ aus.
- Anschließend führt der Runner den dort liegenden Python-Code aus, beispielsweise:

```shell
python -m lbs_delivery build-release
```

## Workflow-Übersicht

### `validate-config.yml`

Jeder Push, der `.github/config.json` ändert, ruft eine reine
Konfigurationsprüfung auf. Sie validiert die Datei gegen das zentrale Schema,
prüft Repository-Identität und Eindeutigkeit sowie die gemeinsame
Deploymentkonfiguration. Der Check besitzt keinen `--execute`-Pfad, bindet kein
Environment und liest keine Secrets. Sync und Release validieren die
verwendete Konfiguration erneut.

### `sync-resources.yml`

Ein Push auf `Rnnn/Entwicklung` oder `Rnnn/Abnahme` startet die zentrale
Synchronisation für die passende M/Text-Umgebung. Der manuelle Start verlangt
einen Commit-SHA und den zugehörigen Branch. Die zentrale Umsetzung prüft beides
und leitet daraus Releaselinie und Zielumgebung ab.

Jede Synchronisation überträgt den vollständigen Stand aller sichtbaren
Projektverzeichnisse in der Repositorywurzel. Der frühere Jenkins-Parameter
`UMFANG=DELTA` aktualisierte normalerweise vorhandene SVN-Arbeitskopien.
`UMFANG=FULL` legte sie für eine initiale Vollsynchronisation neu an. Da die
GitHub-Automatisierung keine langlebigen Arbeitskopien verwendet, veröffentlicht
sie bei jedem Lauf vollständige Projektstände. Das ist unabhängig von den
FULL- und DELTA-Releasepaketen für den Mainframe. Versteckte Verzeichnisse
werden ignoriert. Weitere Ausschlüsse stehen in `excluded_projects` der
`.github/config.json`.

Zwei Schreibvorgänge auf dasselbe
Mandanten-/Linien-/Stufen-Ziel werden durch Concurrency serialisiert.

Die zentrale Automatisierung prüft den Commit und die Repository-Identität.
URL und Mandant lassen sich nicht frei eingeben.

### `release.yml`

Der Workflow reagiert auf Tags der Form `Rnnn.nnn` oder auf
eine manuelle Wiederholung mit einem bereits vorhandenen Tag. Die zentrale
Automatisierung leitet daraus den Branch `Rnnn/Bereitstellung` ab und
prüft, dass der Tag von dort erreichbar ist. `.100` erzeugt FULL. Andere
dreistellige Endungen erzeugen DELTA gegen den `.100`-Tag derselben Linie.
Ein FULL erzeugt je Projekt das vollständige F-Paket und zusätzlich ein leeres
D-Paket mit leerem Projektverzeichnis und leerer Löschliste.

Ein Push nach `Rnnn/Bereitstellung` startet keine Lieferung. Erst der
Release-Tag prüft Konfiguration und Branchzuordnung und startet den
Paketbau.

Paketbau und Mainframe-Übergabe sind zwei getrennte Jobs desselben zentralen
Release-Workflows. Der zweite Job verwendet den Namen des im ersten Job
einmalig hochgeladenen und durch Manifest-Prüfsummen gesicherten
GitHub-Artefakts.

## Erwarteter Vertrag der zentralen Workflows

Der zentrale Workflow verwendet die folgenden mandantenseitigen Angaben:

- `repository_name`: Repository-Identität des Auslösers
- `commit_sha` beziehungsweise `release_tag` und optional `trigger_sha`
- `target_environment` als feste fachliche Zielstufe Entwicklung oder Abnahme
- `source_branch`, aus dem Releaselinie und Stufe validiert abgeleitet werden
- `automation_ref` als zentral gepflegte technische Referenz für den Checkout
  der freigegebenen Implementierung. Die Einrichtungsautomation hält sie mit
  der Version des aufgerufenen Workflows identisch.

Die Sync-Jobs binden kein GitHub Environment. Nur der Publish-Job bindet das
Environment `Bereitstellung` und liest dort die Mainframe-Secrets.

