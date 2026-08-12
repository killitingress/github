# Einordnung der mandanteneigenen Python-Werkzeuge

## Einordnung

Die LBS-IT verwendet sechs selbst entwickelte Python-Werkzeuge für Prüfungen
und Arbeiten an den heutigen SVN- und Tonic-Strukturen. Die LBS-IT besitzt den
Quellcode, aus dem die derzeit verwendete Anwendung kompiliert wird, und möchte
die Hoheit über die Anwendungen und ihre fachlichen Regeln behalten.

Die Werkzeuge werden deshalb erstmal nicht als Bestandteil von `mtext_actions`
betrachtet, sondern können mandanteindividuell in einer auf dem Runner
ausführbaren Python-Fassung je Mandante-Repository bereitstellt und dann durch
eigene GitHub-Actions-Workflows aufgerufen werden. Eine Beschränkung auf die
Python-Standardbibliothek erleichtert dabei die Ausführbarkeit auf dem Runner.

| Werkzeug oder Prüfung | Einordnung für GitHub |
|---|---|
| **TargetFiles** | Bleibt beim Mandanten. Das Werkzeug kann bei Bedarf als manueller Workflow im Mandanten-Repository ausgeführt werden. |
| **Branchabgleich** | Wird nicht unverändert übernommen. Zuerst ist zu klären, ob der neue Git- und Releaseablauf den benötigten Nachweis bereits erbringt. |
| **Master-Update** | Ist im derzeitigen Berechtigungsmodell nicht abgebildet, da ein Mandanten-Workflow keinen Zugriff auf das FI-Master-Repository hat. |
| **QS-Checker** | Bleibt zunächst beim Mandanten. Glossar, QS-Regeln und weitere fachliche Prüfungen liegen dort. Eine spätere gemeinsame Lösung kann getrennt entschieden werden. |
| **Fehler-Trace** | Datenquelle, geprüfte Fehler und interaktive Funktionen müssen erläutert werden. Wahrscheinlich keine Aufgabe für GitHub. |
| **WorkspaceSVNHelfer** | Gehört nicht in GitHub Actions. Arbeiten am privaten Arbeitsbereich bleiben eine lokale Aufgabe. |
| **JSON- und XML-Prüfung** | Ist als zentrale technische Prüfung in `mtext_actions` sinnvoll. Ein kleiner Trigger-Workflow startet sie in jedem Mandanten-Repository. |

## Zentrale Prüfung von Ressourcen

Unabhängig vom mandanteneigenen QS-Checker prüft ein erster zentraler Workflow,
ob versionierte Ressourcen technisch wohlgeformt sind (Linting).

Die Python-Standardbibliothek unterstützt die Prüfung der JSON-Syntax und der
XML-Wohlgeformtheit. Die XSD-Validierung benötigt ein zusätzliches, für den
Runner festgelegtes Werkzeug oder eine Bibliothek. Form.io beschreibt Formulare
als Form JSON, ob hier eine zusätzliche Korrektheitsprüfung möglich ist, ist
noch zu klären.

Desweiteren ist ein automatisierter Regressionstest vorgesehen (Lars).

Die Prüfung läuft bei Pull Requests und berücksichtigt die hinzugefügten,
geänderten und umbenannten Ressourcen. Eine zentrale Zuordnungsdatei legt fest,
welche Dateiendungen als JSON oder XML geprüft werden. Dazu gehören auch
Tonic-Ressourcen mit Endungen wie `.model`, `.datamodel` oder `.conf` sowie
Form.io-Dateien mit der Endung `.formio`. Eine Vollprüfung kann manuell gestartet
werden. Befunde erscheinen mit Datei und, soweit verfügbar, Zeile und Spalte.
Ein Befund beendet den Lauf zunächst nicht als Fehler und verhindert damit den
Pull Request nicht. Welche Befunde später verbindlich werden, erfordert eine
eigene fachliche Entscheidung.

Die gemeinsame Prüflogik und der wiederverwendbare Workflow liegen in
`mtext_actions`. Die Mandanten-Repositories enthalten den Trigger-Workflow und
zeigen die Warnungen beim betroffenen Pull Request an.

## Branchabgleich im neuen Ablauf

Der bisherige Branchabgleich verglich die zu einem Objekt gehörenden Dateien
direkt zwischen drei SVN-Branches für Entwicklung, Abnahme und Bereitstellung.
Er sollte nachweisen, dass der entwickelte und abgenommene Inhalt unverändert
bereitgestellt wurde.

Git kann Inhalte zwischen Branches, Tags und Commits vergleichen. Durch einen
Squash Merge entsteht jedoch ein neuer Commit mit einer neuen SHA auch wenn die
übernommenen Dateiinhalte dem Feature-Stand entsprechen. Im neuen Zielbild gibt
es außerdem keine drei entsprechenden Git-Branches. Daher kann der bisherige
Ablauf nicht unverändert weiterverwendet werden. Allerdings wird das Gewünschte
prinzipiell schon durch den neuen Lieferweg sichergestellt:

1. Pull Request nach 4-Augenprinzip
2. Squash Merge erzeugt Commit in geschütztem Zielbranch - kann nachträglich nicht mehr verändert werden
3. Release-Tag auf dem freigegebenen Commit und Paketbau aus diesem Commit
4. GitHub Release mit Commit und Lieferinformationen
