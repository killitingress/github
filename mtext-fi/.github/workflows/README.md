# GitHub-Actions-Vertrag für `mtext-fi`

Die beiden YAML-Dateien in diesem Verzeichnis sind bewusst dünne aufrufende
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

Vor dem ersten Integrationslauf wird der Null-SHA in beiden Workflow-Dateien durch
den vollständigen 40-stelligen Commit-SHA einer freigegebenen Version von
`mtext-actions` ersetzt.

Ein Branchname wie `main` oder ein beweglicher Tag ist als Referenz nicht
zulässig. `uses:` und der Input `automation_ref` müssen auf denselben Commit
zeigen.

## Workflow-Übersicht

### `sync-resources.yml`

Ein Push auf einen Branch `Rxxx/Entwicklung` oder `Rxxx/Abnahme` ruft die zentrale
Ressourcensynchronisation für genau die zugehörige M/Text-Umgebung auf. Die
manuelle Wiederholung verlangt einen exakten Commit-SHA und einen expliziten
Stufenbranch. Die zentrale Implementierung leitet Releaselinie und Zielumgebung
aus diesem Branch ab und weist den Lauf zurück, wenn der Commit nicht aus dem
gewählten Branch erreichbar ist. Zwei Schreibvorgänge auf dasselbe
Mandanten-/Linien-/Stufen-Ziel werden durch Concurrency serialisiert.

Die zentrale Automatisierung muss den Commit erneut auflösen, die
Repository-Identität gegen `config/mandant.json` prüfen und die Zielumgebung aus
der gemeinsamen Konfiguration bestimmen. Frei eingegebene URLs oder Mandanten
sind nicht vorgesehen.

### `release.yml`

Der Workflow reagiert ausschließlich auf Tags im Format `Rnnn.nnn` oder auf
eine manuelle Wiederholung mit einem bereits vorhandenen Tag. Die zentrale
Automatisierung leitet aus `Rnnn.nnn` den Branch `Rnnn/Bereitstellung` ab und
prüft, dass der Tag von dort erreichbar ist. `.100` erzeugt FULL; andere dreistellige Endungen erzeugen DELTA
gegen den `.100`-Tag derselben Linie.

Direkte Pushes nach `Rnnn/Bereitstellung` lösen keinen Workflow und keine
Lieferung aus. Erst der Release-Tag lädt und validiert die Konfiguration,
prüft die Branchzuordnung und startet den Paketbau.

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
weitergereicht. Jobs im
zentralen wiederverwendbaren Workflow binden das freigegebene GitHub
Environment und lesen ausschließlich dessen Secrets. Die Namen dieser
Environments und der benötigten Secrets sind in diesem Dokument festgelegt;
ihre Werte werden vor dem Integrationslauf durch den Betrieb eingerichtet und
abgenommen. Für den Zugriff von `j517120/mtext-fi` auf
`j520730/mtext-actions` muss außerdem die GitHub-Enterprise-Actions-Freigabe
des zentralen Repositories eingerichtet und praktisch geprüft werden.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Der zentrale
Release-Workflow verwendet daher die offiziellen Node-20-v3-Varianten der
Artefakt-Actions statt der auf GHES nicht unterstützten v4-Varianten. Die
Verfügbarkeit der fest gepinnten Action-SHAs und die Node-20-Unterstützung des
self-hosted Runners werden vor dem ersten Integrationslauf praktisch geprüft.

## Außerhalb der Dateien zu konfigurierende GitHub-Einstellungen

Folgende Schutzmaßnahmen werden als Repository- oder Organisationsregeln in
GitHub konfiguriert und können nicht durch diese Workflow-Dateien allein
erzwungen werden:

- direkte Pushes nach `Rxxx/Entwicklung`, `Rxxx/Abnahme` und
  `Rxxx/Bereitstellung` zulassen;
- freigegebene Actions und wiederverwendbare Workflows;
- die drei gemeinsamen GitHub Environments `Entwicklung`, `Abnahme` und
  `Bereitstellung`; nur `Bereitstellung` verlangt eine manuelle Freigabe;
- minimale Berechtigungen des `GITHUB_TOKEN` auf Repository-Ebene.

`R261/Entwicklung` wird zunächst als Default Branch eingestellt. Workflow- und
Konfigurationsänderungen werden je aktiver Linie direkt nach
`Rxxx/Entwicklung` eingebracht und anschließend über den normalen
Promotionsweg weitergeführt. Beim Linienwechsel wird der Default Branch manuell
auf den Entwicklungsbranch der neuen führenden Linie geändert.
