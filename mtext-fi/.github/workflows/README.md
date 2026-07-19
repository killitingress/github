# GitHub-Actions-Vertrag für `mtext-fi`

Die drei YAML-Dateien in diesem Verzeichnis sind bewusst schlanke aufrufende
Workflows. Fachlogik, Zielauflösung, Paketbau und Integrationen gehören in das
zentrale Repository `mtext-actions`.

Die [Benutzeranleitung](../../../docs/confluence/Benutzeranleitung.md)
beschreibt die Bedienung.

## Zentrale Workflowversion

Alle `uses:`-Aufrufe zeigen auf `j520730/mtext-actions`. Bis zur Freigabe der
ersten zentralen Version steht dort der technische Platzhalter
`0000000000000000000000000000000000000000`.

Der zentrale Einrichtungsworkflow in `mtext-actions` trägt nach Bestätigung des
Runner-Kennzeichens durch die FI den vollständigen Commit-SHA in allen
`uses:`-Aufrufen und `automation_ref`-Werten ein. Text-Entwickler und
Release-Verantwortliche pflegen diese technische Referenz nicht.

Bei einer später freigegebenen Version startet das zentrale
Automatisierungsteam denselben Workflow mit deren vollständiger Commit-SHA für
jeden betroffenen Mandantenbranch. Der technische Commit aktualisiert beide
Referenzen gemeinsam. Andere Branches und bereits laufende Workflow-Läufe
bleiben bis zu ihrer eigenen Umstellung auf der bisherigen Version.

Der Lauf validiert alle betroffenen Workflowdateien vor dem ersten
Schreibzugriff. Ein Vertragsfehler verhindert jeden Commit. Ist der
Zielzustand bereits erreicht, endet ein erneuter Lauf ohne weitere Commits.

Ein Branchname wie `main` oder ein beweglicher Tag ist als Referenz nicht
zulässig. Der zusätzliche Input `automation_ref` bezeichnet den Checkout der
zentralen Python-Implementierung. Auf GHES 3.20 gehört der Kontext des
wiederverwendbaren Workflows zum aufrufenden Workflow; die zentrale
Codeversion kann daher nicht zuverlässig aus dem Aufruf selbst abgeleitet
werden.

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
Projektverzeichnisse in der Repositorywurzel. Für M/Text gibt es keinen
DELTA-Modus. Versteckte Verzeichnisse werden ignoriert. Weitere Ausschlüsse
stehen in `excluded_projects` der `.github/config.json`.

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

Ein Push nach `Rnnn/Bereitstellung` startet keine Lieferung. Eine Änderung an
`.github/config.json` startet den Config-Check; auf Entwicklung oder Abnahme
läuft wegen des Branch-Triggers zusätzlich der vollständige Ressourcensync.
Erst der Release-Tag prüft Konfiguration und Branchzuordnung und startet den
Paketbau.

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
- `automation_ref` als zentral gepflegte technische Referenz für den Checkout
  der freigegebenen Implementierung. Die Einrichtungsautomation hält sie mit
  der Version des aufgerufenen Workflows identisch. Das Repository
  `j520730/mtext-actions` ist fest vorgegeben.

Secrets werden nicht als frei wählbare Inputs aus diesen schlanken Workflows
weitergereicht. Die Sync-Jobs binden das zur Stufe gehörende GitHub Environment,
benötigen daraus aber keine Secrets. Nur der Publish-Job bindet das Environment
`Bereitstellung` und liest dort die Mainframe-Secrets. Davon getrennt ist die
fest vorgegebene technische Leseberechtigung für den zentralen Codebezug. Die
Einrichtung ist unter
[Nächste Schritte](../../../docs/confluence/Naechste_Schritte.md) beschrieben.
Für den Aufruf aus `j517120/mtext-fi` wird die GitHub-Enterprise-Actions-Freigabe
des zentralen Repositories eingerichtet. Der Checkout der Python-Implementierung
aus dem privaten zentralen Repository benötigt zusätzlich eine zentral
verwaltete technische Leseberechtigung, weil das `GITHUB_TOKEN` des Laufs auf
das aufrufende Mandanten-Repository begrenzt ist. Die konkrete Berechtigung und
ihre Bereitstellung werden vor dem Integrationslauf festgelegt. Benutzer von
`mtext-fi` benötigen keine Repositorymitgliedschaft in `mtext-actions`.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Der zentrale
Release-Workflow verwendet daher die offiziellen Node-20-v3-Varianten der
Artefakt-Actions statt der auf GHES nicht unterstützten v4-Varianten. Die
Verfügbarkeit der fest gepinnten Action-SHAs und die Node-20-Unterstützung des
von der FI bereitgestellten Runners werden vor dem ersten Integrationslauf
praktisch geprüft.

## Außerhalb der Dateien zu konfigurierende GitHub-Einstellungen

Folgende Schutzmaßnahmen werden als Repository- oder Organisationsregeln in
GitHub konfiguriert und können nicht durch diese Workflow-Dateien allein
erzwungen werden:

Die zentrale Einrichtungsautomation wendet diese Regeln über die
GitHub-Enterprise-API an und prüft ihren Zustand. Die Liste beschreibt den
Zielzustand und ist keine manuelle Klickanleitung.

- direkte Pushes nach `Rnnn/Entwicklung` und `Rnnn/Abnahme` für die jeweils
  berechtigten Mitarbeiter zulassen
- direkte Pushes nach `Rnnn/Bereitstellung` auf das je Mandant benannte
  Release-Team begrenzen. Force-Pushes und Löschen bleiben verboten
- `.github/workflows/**/*` per Push-Ruleset auf allen Branches gegen Änderungen
  durch Mandantenmitarbeiter schützen. Bypass nur für die zentralen
  Automatisierungsverantwortlichen
- `.github/config.json` von normalen Ressourcen-Pushes ausschließen und nur
  dem benannten technischen Verantwortlichenkreis zur Änderung erlauben
- Es werden ausschließlich Git-Tags und keine GitHub Releases verwendet.
  Erstellen und Löschen von Tags `Rnnn.nnn` auf das Release-Team begrenzen.
  Vor dem Löschen eines irrtümlichen Tags den dadurch gestarteten
  Workflow-Lauf abbrechen
- die manuelle Freigabe im Environment `Bereitstellung` ausschließlich auf die
  Mainframe-Übergabe beziehen. Das Löschen eines Tags nimmt eine bereits
  erfolgte Lieferung nicht zurück
- freigegebene Actions und wiederverwendbare Workflows ausschließlich über
  vollständige Commit-SHAs referenzieren
- die drei gemeinsamen GitHub Environments `Entwicklung`, `Abnahme` und
  `Bereitstellung`. Nur `Bereitstellung` verlangt eine manuelle Freigabe
- minimale Berechtigungen des `GITHUB_TOKEN` auf Repository-Ebene.

`R261/Entwicklung` wird zunächst als Default Branch eingestellt. Workflow- und
Konfigurationsänderungen werden je aktiver Linie direkt nach
`Rnnn/Entwicklung` eingebracht und anschließend regulär nach Abnahme und
Bereitstellung übernommen. Beim Linienwechsel setzt die Einrichtungsautomation
den Default Branch auf den Entwicklungsbranch der neuen führenden Linie.
