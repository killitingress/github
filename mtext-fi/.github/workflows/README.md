# GitHub-Actions-Vertrag für `mtext-fi`

Die drei YAML-Dateien in diesem Verzeichnis sind bewusst dünne aufrufende
Workflows. Fachlogik, Zielauflösung, Paketbau und Integrationen gehören in das
zentrale Repository `mtext-actions`.

Die Bedienung beschreibt die
[Benutzeranleitung](../../../docs/confluence/Benutzeranleitung.md); die
[Soll-Grafik](../../../Architektur_Soll_GitHub_Actions_Git.drawio) zeigt den
vollständigen Ablauf.

## Technischer Platzhalter im Entwicklungssystem

Alle `uses:`-Aufrufe zeigen auf `j520730/mtext-actions` und derzeit auf den
nicht auflösbaren Null-SHA
`0000000000000000000000000000000000000000`. Dieser Wert ist kein
Sicherheitsmechanismus, sondern nur ein noch zu ersetzender technischer
Platzhalter: Unter dieser Referenz existiert keine zentrale Workflowversion.

Vor dem ersten Integrationslauf wird der Null-SHA in allen Workflow-Dateien
durch den vollständigen 40-stelligen Commit-SHA einer freigegebenen Version
von `mtext-actions` ersetzt.

Ein Branchname wie `main` oder ein beweglicher Tag ist als Referenz nicht
zulässig. `uses:` und der Input `automation_ref` müssen auf denselben Commit
zeigen.

## Workflow-Übersicht

### `validate-config.yml`

Jeder Push, der `config/mandant.json` ändert, ruft eine reine
Konfigurationsprüfung auf. Sie validiert die Datei gegen das zentrale Schema,
prüft Repository-Identität und Eindeutigkeit sowie die gemeinsame
Deploymentkonfiguration. Der Check besitzt keinen `--execute`-Pfad, bindet kein
Environment und liest keine Secrets. Er kann daher weder M/Text noch den
Mainframe verändern und liefert frühes Feedback zu Konfigurationsfehlern. Er
ist kein technisch erzwungenes Gate; Sync und Release validieren die jeweils
verwendete Konfiguration auf ihrem eigenen Ausführungspfad erneut.

### `sync-resources.yml`

Ein Push auf einen Branch `Rnnn/Entwicklung` oder `Rnnn/Abnahme` ruft die
zentrale Ressourcensynchronisation für genau die zugehörige M/Text-Umgebung
auf. Die manuelle Wiederholung verlangt einen exakten Commit-SHA und einen
expliziten Stufenbranch. Die zentrale Implementierung leitet Releaselinie und
Zielumgebung aus diesem Branch ab, gleicht die Releaselinie mit der zentralen
Konfiguration ab und weist den Lauf zurück, wenn Linie oder Commit nicht
zulässig sind. Die Workflow-Trigger enthalten daher keine einzeln gepflegte
Liste aktiver Linien.
Zwei Schreibvorgänge auf dasselbe
Mandanten-/Linien-/Stufen-Ziel werden durch Concurrency serialisiert.

Die zentrale Automatisierung muss den Commit erneut auflösen, die
Repository-Identität gegen `config/mandant.json` prüfen und die Zielumgebung aus
der gemeinsamen Konfiguration bestimmen. Frei eingegebene URLs oder Mandanten
sind nicht vorgesehen.

### `release.yml`

Der Workflow reagiert ausschließlich auf Tags im Format `Rnnn.nnn` oder auf
eine manuelle Wiederholung mit einem bereits vorhandenen Tag. Die zentrale
Automatisierung leitet aus `Rnnn.nnn` den Branch `Rnnn/Bereitstellung` ab und
prüft, dass der Tag von dort erreichbar ist. `.100` erzeugt FULL; andere
dreistellige Endungen erzeugen DELTA gegen den `.100`-Tag derselben Linie.

Direkte Pushes nach `Rnnn/Bereitstellung` lösen keinen Sync- oder
Release-Workflow und keine Lieferung aus. Wird dabei `config/mandant.json`
geändert, läuft lediglich der nebenwirkungsfreie Config-Check. Erst der
Release-Tag prüft die Konfiguration und Branchzuordnung und startet den
Paketbau.

Paketbau und Mainframe-Übergabe sind zwei getrennte Jobs desselben zentralen
Release-Workflows. Der zweite Job verwendet ausschließlich den Namen des im
ersten Job einmalig hochgeladenen und durch Manifest-Prüfsummen gesicherten
GitHub-Artefakts. Das Mandanten-Repository erzeugt oder verändert keine JCL
und erhält keine FTP-Credentials.

## Erwarteter Vertrag der zentralen Workflows

Der zentrale Workflowvertrag verwendet ausschließlich die folgenden
mandantenseitigen Angaben:

- `repository_name`: Repository-Identität des Auslösers;
- `commit_sha` beziehungsweise `release_tag` und optional `trigger_sha`;
- `target_environment` für Entwicklung oder Abnahme;
- `source_branch`, aus dem Releaselinie und Stufe validiert abgeleitet werden;
- `automation_repository` und `automation_ref` für den Checkout der exakt
  gepinnten zentralen Implementierung.

Secrets werden nicht als freie Inputs aus diesen dünnen Workflows
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
`mtext-actions`; die Freigabe gilt für den Workflowaufruf, nicht für
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
  berechtigten Mitarbeiter zulassen;
- direkte Pushes nach `Rnnn/Bereitstellung` auf das je Mandant benannte
  Release-Team begrenzen; Force-Pushes und Löschen bleiben verboten;
- `.github/workflows/**/*` per Push-Ruleset auf allen Branches gegen Änderungen
  durch Mandantenmitarbeiter schützen; Bypass nur für die zentralen
  Automatisierungsverantwortlichen;
- `config/mandant.json` von normalen Ressourcen-Pushes ausschließen und nur
  dem benannten technischen Verantwortlichenkreis zur Änderung erlauben;
- neue Tags `Rnnn.nnn` nur durch das Release-Team zulassen und bestehende
  Release-Tags gegen Änderung, Force-Push und Löschung schützen;
- freigegebene Actions und wiederverwendbare Workflows;
- die drei gemeinsamen GitHub Environments `Entwicklung`, `Abnahme` und
  `Bereitstellung`; nur `Bereitstellung` verlangt eine manuelle Freigabe;
- minimale Berechtigungen des `GITHUB_TOKEN` auf Repository-Ebene.

`R261/Entwicklung` wird zunächst als Default Branch eingestellt. Workflow- und
Konfigurationsänderungen werden je aktiver Linie direkt nach
`Rnnn/Entwicklung` eingebracht und anschließend regulär nach Abnahme und
Bereitstellung übernommen. Beim Linienwechsel wird der Default Branch manuell
auf den Entwicklungsbranch der neuen führenden Linie geändert.
