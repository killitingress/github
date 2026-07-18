# Git und SVN: Konflikte, Aktualisierung und Weitergabe zwischen Stages

Diese Arbeitsnotiz enthält kompakte Textbausteine für das Benutzerhandbuch.
Die drei Prozess-Stages sind `Entwicklung`, `Abnahme` und `Bereitstellung`;
jede Releaselinie besitzt einen eigenen Branch für jede Stage.

## SVN und Git im Vergleich

Bei SVN schreibt ein Commit die ausgewählten Änderungen direkt in das zentrale
Repository. Änderungen an unterschiedlichen Briefen lassen sich deshalb im
Alltag meist unabhängig nacheinander committen. Auch SVN kann jedoch bei einem
veralteten Stand zunächst ein Update verlangen; ein Konflikt zeigt sich dann
beim Update oder Merge.

Bei Git sind Commit und Push getrennt. Der Commit speichert die Änderung nur
lokal. Der Push versucht anschließend, den gemeinsamen Branch auf GitHub
weiterzusetzen. Hat seit dem letzten Aktualisieren bereits jemand anderes
gepusht, wird der eigene Push normalerweise als `non-fast-forward` abgelehnt –
auch wenn unterschiedliche Dateien geändert wurden.

Eine solche Push-Ablehnung ist noch kein inhaltlicher Konflikt. Sie bedeutet
nur, dass der lokale Branch veraltet ist. Erst beim Übernehmen des neuen
GitHub-Stands durch Rebase oder Merge kann ein echter Konflikt entstehen.

## Merge, Rebase und Pull

Ein **Merge** verbindet zwei Entwicklungsverläufe und erzeugt gegebenenfalls
einen zusätzlichen Merge-Commit. Die vorhandenen Commits bleiben unverändert,
die Historie kann dadurch aber unübersichtlicher werden.

Ein **Rebase** setzt eigene, noch nicht veröffentlichte Commits auf den neuen
GitHub-Stand. Die Änderungen werden erneut angewendet und erhalten neue SHAs.
Bereits veröffentlichte Commits dürfen in diesem Prozess nicht per Rebase
umgeschrieben werden.

Ein **Pull** holt den GitHub-Stand und integriert ihn anschließend. Je nach
Client geschieht das per Merge oder Rebase. „Pull ausführen“ ist deshalb als
Arbeitsanweisung zu ungenau. Nach Auswahl des Git-Clients muss verbindlich
dokumentiert werden, welche Schaltfläche und welche Variante zu verwenden ist.
Für eigene, noch nicht gepushte Commits auf dem Branch einer Stage ist Rebase
in der Regel übersichtlicher.

## Warum gleiche Änderungen unterschiedliche SHAs haben

Eine Commit-SHA ist nicht nur ein Hash der geänderten Dateien. Sie wird aus dem
gesamten Commit-Objekt gebildet. Dazu gehören insbesondere:

- der vollständige versionierte Repository-Dateistand, also alle in diesem
  Commit erfassten Dateien und Verzeichnisse;
- der vorherige Commit, bei einem Merge mehrere Eltern-Commits;
- Autor, Committer und Zeitpunkte;
- die Commit-Nachricht und gegebenenfalls eine Signatur.

Vereinfacht:

```text
Commit-SHA = Hash(Repository-Dateistand + Eltern-Commit + Metadaten + Nachricht)
```

Dieser Dateistand ist eine Momentaufnahme des gesamten Repositories. Er umfasst
nicht nur die mit dem Commit geänderten Dateien, sondern auch alle unverändert
weitergeltenden versionierten Dateien. Lokale, nicht zum Commit hinzugefügte
oder von Git nicht verfolgte Dateien gehören nicht dazu.

Der vollständige Stand ist einbezogen, weil die SHA nicht nur eine eindeutige
Nummer, sondern auch ein Fingerabdruck des Commits ist. Ein Zeitstempel allein
reicht nicht: Mehrere Rechner können zur selben Zeit Commits erzeugen, ihre
Uhren können abweichen und Zeitangaben lassen sich ändern. Außerdem würde ein
Zeitstempel keine nachträgliche Inhaltsänderung erkennbar machen. Git speichert
dabei nicht jedes Mal alle Dateien neu. Der Commit verweist auf einen
Tree-Hash; unveränderte Dateiobjekte werden wiederverwendet. Ändert sich eine
versionierte Datei oder ein Eltern-Commit, ändert sich über diese Verweise auch
die Commit-SHA.

Ein Cherry-Pick übernimmt dieselbe fachliche Änderung, erzeugt auf dem
Zielbranch aber einen neuen Commit. Dieser hat mindestens einen anderen
Eltern-Commit; meist unterscheiden sich außerdem Commit-Zeitpunkt und Nachricht.
Deshalb haben B und `B'` unterschiedliche SHAs, obwohl dieselben Dateiänderungen
übernommen wurden:

```text
B  = Hash(Repository-Stand nach B  + Eltern-Commit A     + Metadaten von B)
B' = Hash(Repository-Stand nach B' + Eltern-Commit Basis + Metadaten von B')
```

Die SHA identifiziert somit einen konkreten Commit einschließlich seiner
Position in der Historie, nicht nur eine einzelne Dateiänderung. Die hier
verwendete 40-stellige Commit-SHA ist außerdem von der SHA-256-Prüfsumme eines
Lieferartefakts zu unterscheiden.

## Konflikte behandeln

Ein technischer Konflikt kann bei Merge, Rebase oder Cherry-Pick entstehen,
etwa wenn dieselben Zeilen geändert wurden oder eine Datei gleichzeitig
gelöscht und bearbeitet wurde. Git erkennt jedoch keine rein fachlichen
Widersprüche. Auch ein automatisch kombiniertes Ergebnis muss deshalb geprüft
werden.

Der grundsätzliche Ablauf lautet:

1. Quelländerung und aktuellen Zielstand vergleichen.
2. Gewünschtes fachliches Ergebnis klären.
3. Konflikt im Git-Client auflösen oder den Vorgang sicher abbrechen.
4. Alle betroffenen Dateien und den Gesamtstand prüfen.
5. Erst danach erneut pushen und den Workflow kontrollieren.

Force-Push oder ungeprüftes Überschreiben des Zielbranches sind keine
Lösungsstrategien.

## Änderungen zwischen den Stages weitergeben

Ein Feature-Branch kann unfertige Arbeiten voneinander trennen. Spätestens bei
der Übernahme nach Entwicklung muss die Änderung aber mit dem aktuellen Stand
des Entwicklungsbranches kombiniert werden.

Die selektive Weitergabe zwischen den Stages erfolgt zweimal per Cherry-Pick:

```text
Entwicklung -> Cherry-Pick -> Abnahme -> Cherry-Pick -> Bereitstellung
```

Beispiel: Auf Entwicklung liegen die unabhängigen Änderungen A, B und C. Für
die Abnahme wird zunächst nur B ausgewählt:

```text
Entwicklung:  Basis ─ A ─ B ─ C
Abnahme:      Basis ─ B'
```

`B'` ist dieselbe fachliche Änderung wie B, aber ein neuer Commit mit eigener
SHA. A und C werden nicht automatisch übernommen. Sie können später in einer
anderen Reihenfolge folgen, sofern keine Abhängigkeiten bestehen:

```text
Entwicklung:  Basis ─ A ─ B ─ C
Abnahme:      Basis ─ B' ─ C' ─ A'
```

Bereitstellung übernimmt anschließend den tatsächlich geprüften
Abnahme-Commit `B'`, nicht erneut den ursprünglichen Entwicklungs-Commit B:

```text
Entwicklung:     Basis ─ A  ─ B  ─ C
Abnahme:         Basis ─ B' ─ C' ─ A'
Bereitstellung:  Basis ─ B''
```

Die Striche kennzeichnen neue Commits und SHAs, keine fachlich veränderten
Varianten.

Vor jedem Cherry-Pick wird der Zielbranch aktualisiert. Danach werden der
freigegebene Commit aus der unmittelbar vorherigen Stage übernommen, der
resultierende Gesamtstand geprüft und die vollständige SHA des übernommenen
Quell-Commits in die Nachricht des neuen Commits eingetragen. Abhängige Commits
müssen vollständig und in der ursprünglichen Reihenfolge übernommen werden.
Wird der Push zwischenzeitlich abgelehnt, ist der Zielbranch erneut zu
aktualisieren und das Ergebnis nochmals zu prüfen.

Für die Quell-SHA sollte eine einheitliche, auswertbare Konvention gelten. Git
kann sie beim Cherry-Pick mit der Option `-x` in die Commit-Nachricht aufnehmen.
Das sieht beispielsweise so aus:

```text
(cherry picked from commit 8f3a1c2d4e5f67890123456789abcdef01234567)
```

Falls der ausgewählte Client dies nicht unterstützt, ist eine vergleichbare
feste Zeile in der Commit-Nachricht zu definieren. Bei `B'` wird so die SHA von
B aus Entwicklung eingetragen; bei `B''` die SHA von `B'` aus Abnahme. Dadurch
bleibt trotz der jeweils neuen Commit-SHA nachvollziehbar, welcher Commit aus
der unmittelbar vorherigen Stage übernommen wurde. Die Automation wertet diese
Angabe derzeit nicht aus; sie dient zunächst der manuellen Nachvollziehbarkeit.

Ein Pull Request ersetzt den Cherry-Pick nicht. Ein direkter Pull Request von
Entwicklung nach Abnahme würde grundsätzlich alle noch fehlenden Unterschiede
umfassen. Für die Auswahl nur eines Commits wäre weiterhin ein Auswahlbranch
mit Cherry-Pick erforderlich.

## Rolle der GitHub Actions

Die vorhandenen Actions führen keine Cherry-Picks aus. Sie verarbeiten den
Stand, den die Benutzer zuvor auf den Branch der jeweiligen Stage gepusht haben:

```text
Push Entwicklung  -> vollständigen Stand nach M/Text-Entwicklung synchronisieren
Cherry-Pick und Push Abnahme
                  -> vollständigen Stand nach M/Text-Abnahme synchronisieren
Cherry-Pick und Push Bereitstellung
                  -> noch keine Lieferung
Release-Tag       -> FULL oder DELTA bauen und nach Freigabe übergeben
```

Die Sync-Workflows verwenden den exakten Commit, der den Push ausgelöst hat,
und prüfen, dass er zum angegebenen Branch der Stage Entwicklung oder Abnahme
gehört. Der Release-Workflow prüft entsprechend, dass der Tag vom passenden
Bereitstellungsbranch erreichbar ist. Die Actions wählen aber keine fachlichen
Änderungen aus und kontrollieren derzeit auch nicht deren
Cherry-Pick-Herkunft.

Eine Action könnte technisch einen ausgewählten Quell-Commit mit
`git cherry-pick -x` übernehmen und den Zielbranch pushen. Sie müsste dann
jedoch Schreibrechte auf das Repository und eine eng begrenzte Ausnahme von
den Branchschutzregeln erhalten. Außerdem müsste sie Berechtigung,
zulässige Weitergaberichtung, Quell-SHA und den zwischenzeitlich aktuellen
Zielstand prüfen.
Bei einem Konflikt könnte sie nicht selbst fachlich entscheiden, sondern müsste
abbrechen und den Fall an einen Benutzer zurückgeben.

Nur die `-x`-Zeile nachträglich an einen bereits gepushten Commit anzuhängen ist
keine gute Alternative: Jede Änderung der Commit-Nachricht erzeugt eine neue
SHA und würde das Umschreiben des veröffentlichten Branchverlaufs erfordern.
Wenn eine schreibende Promotion-Action eingeführt wird, sollte sie deshalb den
gesamten Cherry-Pick erzeugen. Andernfalls bleibt `-x` Aufgabe des Git-Clients;
eine Action könnte die vorhandene Herkunftsangabe lediglich prüfen und einen
fehlerhaften Lauf ablehnen.

## Noch fehlende Inhalte im Benutzerhandbuch

Das Benutzerhandbuch sollte noch ergänzen:

- Push-Ablehnung im Unterschied zu einem echten Konflikt;
- Merge, Rebase und die verbindliche Pull-Variante;
- Umgang mit uncommitteten lokalen Änderungen;
- Konfliktauflösung, Abbruch und Wiederanlauf im ausgewählten Git-Client;
- Verhalten, wenn der Zielbranch zwischen Cherry-Pick und Push verändert wird;
- verbindliches Format der Quell-SHA und Zuständigkeit bei Konflikten;
- eine praktisch geprüfte, produktspezifische Klickanleitung.

## Bewertung der aktuellen Implementierung

Die vorhandene Implementierung unterstützt den Cherry-Pick-Ablauf bereits.
Pushes nach `Rnnn/Entwicklung` und `Rnnn/Abnahme` synchronisieren den exakten
neuen Commit. Die Automation prüft seine Erreichbarkeit aus dem angegebenen
Branch der angegebenen Stage, verlangt aber keine gemeinsame lineare Historie
der Branches der drei Stages. Neue SHAs aus Cherry-Picks sind daher
unproblematisch.

Auch Bereitstellung funktioniert mit diesem Modell: Erst ein Release-Tag muss
vom passenden Bereitstellungsbranch erreichbar sein. FULL und DELTA werden aus
dem getaggten Dateistand gebildet und sind nicht von identischen SHAs in den
vorherigen Stages abhängig.

Nicht erzwungen wird derzeit die Herkunft. Die Automation prüft weder, ob ein
Abnahme-Commit tatsächlich aus Entwicklung stammt, noch ob ein
Bereitstellungs-Commit aus Abnahme stammt. Die Quell-SHA ist momentan eine
Prozessregel.

Für die Funktionsfähigkeit sind keine Änderungen an Sync- oder Release-Logik
nötig. Vor dem Pilotbetrieb müssen jedoch die Null-SHA-Platzhalter ersetzt,
Rulesets und Berechtigungen eingerichtet, Force-Pushes gesperrt und
Parallel- sowie Konfliktfälle mit dem gewählten Git-Client getestet werden.

Soll die Herkunft technisch erzwungen werden, wäre eine zusätzliche Prüfung
der neu gepushten Commits erforderlich. Sie müsste eine standardisierte
Quell-SHA auswerten und sicherstellen, dass diese aus der unmittelbar
vorherigen Stage erreichbar ist. Für Bereitstellung wäre dafür ein eigener
Prüfworkflow oder eine Prüfung vor dem Tagging notwendig.
