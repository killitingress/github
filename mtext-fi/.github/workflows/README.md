# GitHub-Actions-Vertrag für `mtext-fi`

Die drei YAML-Dateien in diesem Verzeichnis sind bewusst schlanke aufrufende
Workflows. Fachlogik, Zielauflösung, Paketbau und Integrationen gehören in das
zentrale Repository `mtext-actions`.

Die [Benutzeranleitung](../../../docs/confluence/Benutzeranleitung.md)
beschreibt die Bedienung.

## Technischer Platzhalter im Entwicklungssystem

Alle `uses:`-Aufrufe zeigen auf `j520730/mtext-actions` und derzeit auf den
Null-SHA `0000000000000000000000000000000000`. Unter dieser Referenz gibt es
noch keine zentrale Workflowversion.

Vor dem ersten Integrationslauf wird der Null-SHA in allen Workflow-Dateien
durch den vollständigen 40-stelligen Commit-SHA einer freigegebenen Version
von `mtext-actions` ersetzt.

Ein Branchname wie `main` oder ein beweglicher Tag ist als Referenz nicht
zulässig. `uses:` und der Input `automation_ref` müssen auf denselben Commit
zeigen.

## Workflow-Übersicht

### `validate-config.yml`

Jeder Push, der `.config.json` ändert, ruft eine reine
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
Projektverzeichnisse in der Repositorywurzel. Für M/Text gibt es keinen
DELTA-Modus. Versteckte Verzeichnisse werden ignoriert. Weitere Ausschlüsse
stehen in `excluded_projects` der `.config.json`.

Zwei Schreibvorgänge auf dasselbe
Mandanten-/Linien-/Stufen-Ziel werden durch Concurrency serialisiert.

Die zentrale Automatisierung prüft den Commit und die Repository-Identität.
URL und Mandant lassen sich nicht frei eingeben.

### `release.yml`

Der Workflow reagiert ausschließlich auf Tags im Format `Rnnn.nnn` oder auf
eine manuelle Wiederholung mit einem bereits vorhandenen Tag. Die zentrale
Automatisierung leitet aus `Rnnn.nnn` den Branch `Rnnn/Bereitstellung` ab und
prüft, dass der Tag von dort erreichbar ist. `.100` erzeugt FULL. Andere
dreistellige Endungen erzeugen DELTA gegen den `.100`-Tag derselben Linie.

Ein Push nach `Rnnn/Bereitstellung` startet keine Lieferung. Bei einer
Änderung an `.config.json` läuft nur der Config-Check. Der Release-Tag prüft
Konfiguration und Branchzuordnung und startet den Paketbau.

Paketbau und Mainframe-Übergabe sind zwei getrennte Jobs desselben zentralen
Release-Workflows. Der zweite Job verwendet ausschließlich den Namen des im
ersten Job einmalig hochgeladenen und durch Manifest-Prüfsummen gesicherten
GitHub-Artefakts. Das Mandanten-Repository erzeugt oder verändert keine JCL
und erhält keine FTP-Credentials.

## Erwarteter Vertrag der zentralen Workflows

Der zentrale Workflowvertrag verwendet ausschließlich die folgenden
mandantenseitigen Angaben:

- `repository_name`: Repository-Identität des Auslösers
- `commit_sha` beziehungsweise `release_tag` und optional `trigger_sha`
- `target_environment` für Entwicklung oder Abnahme
- `source_branch`, aus dem Releaselinie und Stufe validiert abgeleitet werden
- `automation_repository` und `automation_ref` für den Checkout der exakt
  gepinnten zentralen Implementierung.

Secrets werden nicht als freie Inputs aus diesen schlanken Workflows
weitergereicht. Die Sync-Jobs binden das zur Stufe gehörende GitHub Environment,
benötigen derzeit aber keine Secrets. Nur der Publish-Job bindet das Environment
`Bereitstellung` und liest dort die Mainframe-Secrets. Deren Namen und die
Einrichtung sind im
[README von `mtext-actions`](../../../mtext-actions/README.md) und unter
[Nächste Schritte](../../../docs/confluence/Naechste_Schritte.md) beschrieben.
Für den Zugriff von `j517120/mtext-fi` auf
`j520730/mtext-actions` muss außerdem die GitHub-Enterprise-Actions-Freigabe
des zentralen Repositories eingerichtet und praktisch geprüft werden. Die
Benutzer von `mtext-fi` benötigen dafür keinen direkten Zugriff auf
`mtext-actions`. Die Freigabe gilt für den Workflowaufruf, nicht für
Repositorymitgliedschaften.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Der zentrale
Release-Workflow verwendet daher die offiziellen Node-20-v3-Varianten der
Artefakt-Actions statt der auf GHES nicht unterstützten v4-Varianten. Die
Verfügbarkeit der fest gepinnten Action-SHAs und die Node-20-Unterstützung des
Self-hosted Runners werden vor dem ersten Integrationslauf praktisch geprüft.

## Außerhalb der Dateien zu konfigurierende GitHub-Einstellungen

Folgende Schutzmaßnahmen werden als Repository- oder Organisationsregeln in
GitHub konfiguriert und können nicht durch diese Workflow-Dateien allein
erzwungen werden:

- direkte Pushes nach `Rnnn/Entwicklung` und `Rnnn/Abnahme` für die jeweils
  berechtigten Mitarbeiter zulassen
- direkte Pushes nach `Rnnn/Bereitstellung` auf das je Mandant benannte
  Release-Team begrenzen. Force-Pushes und Löschen bleiben verboten
- `.github/workflows/**/*` per Push-Ruleset auf allen Branches gegen Änderungen
  durch Mandantenmitarbeiter schützen. Bypass nur für die zentralen
  Automatisierungsverantwortlichen
- `.config.json` von normalen Ressourcen-Pushes ausschließen und nur
  dem benannten technischen Verantwortlichenkreis zur Änderung erlauben
- neue Tags `Rnnn.nnn` nur durch das Release-Team zulassen und bestehende
  Release-Tags gegen Änderung, Force-Push und Löschung schützen
- freigegebene Actions und wiederverwendbare Workflows
- die drei gemeinsamen GitHub Environments `Entwicklung`, `Abnahme` und
  `Bereitstellung`. Nur `Bereitstellung` verlangt eine manuelle Freigabe
- minimale Berechtigungen des `GITHUB_TOKEN` auf Repository-Ebene.

`R261/Entwicklung` wird zunächst als Default Branch eingestellt. Workflow- und
Konfigurationsänderungen werden je aktiver Linie direkt nach
`Rnnn/Entwicklung` eingebracht und anschließend regulär nach Abnahme und
Bereitstellung übernommen. Beim Linienwechsel wird der Default Branch manuell
auf den Entwicklungsbranch der neuen führenden Linie geändert.
