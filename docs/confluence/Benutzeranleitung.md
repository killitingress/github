# Benutzeranleitung für M/Text-Ressourcen mit Git

## 1. Einstieg von SVN zu Git

Diese Anleitung beschreibt die tägliche Arbeit mit M/Text-Ressourcen in Git.
Sie richtet sich an Entwickler und Repository-Verantwortliche, die bisher mit
SVN gearbeitet haben.

### Kurzfassung

Ausgangsbranch aktualisieren → Feature-Branch erstellen → Änderung committen
und pushen → in M/Text-Entwicklung testen → Pull Request prüfen lassen → mit
Squash Merge zusammenführen → in M/Text-Funktionstest abnehmen.

### Grundprinzipien

In SVN ist ein Commit eine Aktion, durch die Änderungen an das zentrale
Repository übertragen werden. Dabei entsteht eine neue Revision. In Git
hingegen hält ein Commit einen Entwicklungsstand samt Historie zu einem
bestimmten Zeitpunkt fest und entspricht damit am ehesten einer SVN-Revision.
Seine Commit-SHA kennzeichnet ihn eindeutig. Diese besteht aus 40 hexadezimalen
Zeichen, während eine SVN-Revision eine aufsteigende Nummer ist. Git-Commits
werden normalerweise lokal erstellt und erst durch einen Push nach GitHub
übertragen. Technisch ist ein Branch in Git ein Zeiger auf einen Commit. Beim
Push eines Branches nach GitHub werden sämtliche fehlenden Commits dorthin
übertragen und der Branch in GitHub auf den dann aktuellsten Commit
*verschoben*.

Jeder Entwicklungsauftrag wie eine Änderung, Erweiterung oder Korrektur wird
als Feature in einem eigenen temporären Feature-Branch umgesetzt. Wenn ein
Feature fertig entwickelt und getestet wurde, kann ein Pull Request angelegt
werden, um es in `main` oder `release/nnn` zu übernehmen. Der Pull Request muss
dazu im Vier-Augen-Prinzip geprüft und freigegeben werden. Danach werden die
Änderungen des Feature-Branches per Squash Merge in den Zielbranch
übernommen. Dabei entsteht ein neuer Stand und somit auch ein neuer Commit.

Wird ein Feature-Branch nach GitHub gepusht, werden die von ihm geänderten
M/Text-Ressourcen automatisch mit der M/Text-Entwicklungsumgebung
synchronisiert. Dort kann der Entwickler das Feature testen. Ein Merge nach
`main` oder `release/nnn` synchronisiert automatisch die
M/Text-Funktionstestumgebung. Dort soll das Feature von der LBS getestet und
fachlich freigegeben werden.

Eine Mainframe-Lieferung wird aus einem fachlich freigegebenen Stand auf
`main`, `release/nnn` oder `bereitstellung/nnn.nnn` vorbereitet. Die
Vorbereitung hält den gewählten Commit, den Liefer-Tag und den Lieferumfang
fest. Anschließend führt dieselbe oder eine zweite Person die vorbereitete
Lieferung aus. Der zentrale Workflow erzeugt den Liefer-Tag und startet
Paketbau sowie Mainframe-Übergabe.

### Grundablauf einer Änderung

```text
Feature-Branch erstellen und Änderung committen
    │ Push
    ▼
Änderung in M/Text-Entwicklung testen
    │ Pull Request und Review
    ▼
Squash Merge nach main oder release/nnn
    │ automatische Synchronisation
    ▼
Änderung in M/Text-Funktionstest abnehmen
```

### Grundablauf einer Mainframe-Lieferung

```text
Branch und Liefer-Tag auswählen
    │ Lieferung vorbereiten
    ▼
Lieferumfang prüfen und Vorbereitungs-ID kopieren
    │ Vorbereitete Lieferung mit dieser ID ausführen
    ▼
Liefer-Tag, Paketbau und Mainframe-Übergabe
```

### Verwendete Namen

| Gegenstand | Namensschema | Beispiel |
|---|---|---|
| Produktive Releaselinie | `main` | `main` führt 270 |
| Parallel gepflegte Releaselinie | `release/nnn` | `release/261`, `release/271` |
| Einzelne Änderung | `feature/nnn/<Bezeichnung>` | `feature/261/issue-5678` |
| Arbeitsbranch einer Teillieferung | `bereitstellung/nnn.nnn` | `bereitstellung/261.108` |
| Liefer-Tag | `rnnn.nnn` | `r261.108` |

M/Text-Entwicklung und M/Text-Funktionstest sind Zielumgebungen. Sie werden
nicht durch eigene Git-Branches dargestellt.

### Arbeitsmittel und Voraussetzungen

Benötigt werden:

- Zugriff auf das Mandanten-Repository in GitHub
- ein lokaler Klon des Mandanten-Repositorys
- die Einbindung des Klons in die M/Text Workbench beziehungsweise den
  verwendeten Eclipse-Arbeitsbereich
- ein im Git-Client hinterlegter Benutzername und eine E-Mail-Adresse
- die Releaselinie der vorgesehenen Änderung

| Anwendung | Aufgabe |
|---|---|
| M/Text Workbench mit EGit | Ressourcen bearbeiten, Branches verwalten, Änderungen prüfen, committen, cherry-picken und pushen |
| GitHub im Browser | Pull Requests bearbeiten, Workflow-Läufe prüfen, Lieferungen starten, Tags und Lieferinformationen ansehen |

In einem Git-Arbeitsbaum kann ein Branch ausgecheckt sein. Für gleichzeitig
geöffnete Arbeiten an mehreren Releaselinien sind getrennte lokale Klone und
Eclipse-Arbeitsbereiche sinnvoll. So bleiben Projektbaum, Releaselinie und
lokale Änderungen eindeutig zugeordnet.

Beispiel:

```text
Arbeitsbereich 270  → main oder feature/270/...
Arbeitsbereich 261  → release/261 oder feature/261/...
Arbeitsbereich 271  → release/271 oder feature/271/...
```

### Vor jeder Bearbeitung aktualisieren

1. Das richtige Mandanten-Repository und den vorgesehenen Branch auswählen.
2. Prüfen, dass keine ungesicherte Bearbeitung und keine laufende Git-Operation
   offen ist.
3. Die neuen GitHub-Stände mit EGit abrufen.
4. Den ausgecheckten Ausgangsbranch aktualisieren.
5. Kontrollieren, dass der lokale Branch und der GitHub-Branch denselben Stand
   bezeichnen.

## 2. Feature entwickeln und in M/Text-Entwicklung testen

### Kurzfassung

Den Branch der Releaselinie aktualisieren, davon `feature/nnn/<Bezeichnung>`
erstellen, Änderung committen und pushen. Anschließend den eigenen
Synchronisationslauf und den Stand in M/Text-Entwicklung prüfen.

### Ausgangsbranch bestimmen

Die Releaselinie der Änderung bestimmt Ausgangsbranch und späteres
Pull-Request-Ziel:

| Änderung | Ausgangsbranch und Pull-Request-Ziel | Feature-Branch |
|---|---|---|
| Produktive Releaselinie 270 | `main` | `feature/270/<Bezeichnung>` |
| Weiter gepflegte Releaselinie 261 | `release/261` | `feature/261/<Bezeichnung>` |
| Kommende Releaselinie 271 | `release/271` | `feature/271/<Bezeichnung>` |

Die kommende Releaselinie besitzt bereits vor dem Linienwechsel einen
geschützten Release-Branch. Ihre Änderungen können dadurch zusammengeführt und
in M/Text-Funktionstest abgenommen werden.

### Feature-Branch erstellen

1. Im passenden lokalen Klon den Ausgangsbranch auswählen.
2. Den Ausgangsbranch auf den aktuellen GitHub-Stand bringen.
3. Einen neuen Branch `feature/nnn/<Bezeichnung>` erstellen.
4. Den Feature-Branch auschecken.

Die Bezeichnung soll den fachlichen Auftrag erkennen lassen. Beispiele sind:

```text
feature/270/neuer-brief
feature/261/issue-5678
feature/271/adresse-korrigieren
```

### Änderung bearbeiten und committen

1. Die Ressourcen in der M/Text Workbench bearbeiten.
2. In der Git-Ansicht die geänderten, neuen und gelöschten Dateien prüfen.
3. Unbeabsichtigte Dateien von der Übernahme ausschließen oder zurücknehmen.
4. Die fachlich zusammengehörigen Änderungen zum Commit hinzufügen.
5. Eine verständliche Commit-Nachricht eingeben.
6. Den Commit erstellen.

Auf dem Feature-Branch dürfen mehrere Zwischen-Commits entstehen. Sie werden
beim späteren Squash Merge auf dem Zielbranch zusammengefasst.

### Nach M/Text-Entwicklung übertragen

1. Den Feature-Branch nach GitHub pushen.
2. Im Mandanten-Repository unter **Actions** den Lauf **M/Text-Ressourcen
   synchronisieren** öffnen.
3. Kontrollieren, dass der Lauf den eigenen Feature-Branch und dessen aktuellen
   Commit verarbeitet.
4. Nach erfolgreichem Lauf die Änderung in M/Text-Entwicklung testen.
5. Erforderliche Korrekturen erneut committen und pushen.

Der erfolgreiche Workflow bestätigt die technische Übertragung. Die fachliche
Richtigkeit wird anschließend in M/Text geprüft.

### Parallele Feature-Branches koordinieren

Feature-Branches derselben Releaselinie verwenden dieselbe
M/Text-Entwicklungsumgebung. Sie erhalten keine getrennten Testumgebungen. Der
erste Push eines neuen Feature-Branches wird mit dessen Ausgangsbranch
verglichen. Auch dabei werden die durch das Feature geänderten Ressourcen
übertragen. Weitere Pushes verwenden die Änderungen seit dem vorherigen Commit
dieses Feature-Branches.

Unterschiedliche Ressourcen können dadurch parallel entwickelt und getestet
werden. Ändern mehrere Feature-Branches dieselbe Ressource, bestimmt die zuletzt
für diese Ressource synchronisierte Änderung ihren Inhalt in
M/Text-Entwicklung. Dieser seltene Fall wird zwischen den beteiligten
Entwicklern abgestimmt.

## 3. Pull Request und M/Text-Funktionstest

### Kurzfassung

Pull Request vom Feature-Branch zum Branch seiner Releaselinie erstellen →
Prüfer zuordnen → Änderungen und Prüfläufe kontrollieren → **Squash and merge**
→ Synchronisationslauf und Stand in M/Text-Funktionstest prüfen.

### Pull Request erstellen

Wenn die Änderung in M/Text-Entwicklung erfolgreich geprüft wurde:

1. Das Mandanten-Repository in GitHub öffnen.
2. Einen Pull Request vom Feature-Branch auf den zugehörigen Zielbranch
   erstellen.
3. Kontrollieren, dass der Feature-Branch für dieselbe Releaselinie angelegt
   wurde wie der Zielbranch.
4. Die Änderung und das Ergebnis des Entwicklungstests verständlich
   beschreiben.
5. Eine zweite Person für das Review zuordnen.

Beispiele:

```text
feature/270/neuer-brief  → main, wenn main die Releaselinie 270 führt
feature/261/issue-5678   → release/261
feature/271/neuer-brief  → release/271
```

Der Wechsel der produktiven Releaselinie ist ein eigener Ablauf. Dort wird ein
Branch der kommenden Linie bewusst nach `main` übernommen.

### Zielbranchänderungen und Konflikte behandeln

Hat sich der Zielbranch geändert, kann GitHub im Pull Request **Update branch**
anbieten. Diese Funktion übernimmt den neuen Zielbranchstand in den
Feature-Branch. Der spätere Squash Merge hält zusätzliche Arbeitscommits vom
Zielbranch fern.

Entsteht beim Aktualisieren oder bei einem Cherry-Pick ein Konflikt:

1. Nicht pushen und die betroffenen Dateien sowie die laufende Git-Operation
   prüfen.
2. Den bisherigen Inhalt, die neue Änderung und den gemeinsamen Ausgangsstand
   vergleichen.
3. Den fachlich richtigen Inhalt herstellen und Konfliktmarkierungen entfernen.
4. Die aufgelösten Dateien bestätigen und die Git-Operation fortsetzen.
5. Ist die richtige Auflösung unklar, die Operation abbrechen und die
   Abweichung mit den Beteiligten klären.
6. Nach der Auflösung den gesamten Arbeitsstand prüfen, pushen und erneut in
   M/Text-Entwicklung testen.

Wird ein Push abgelehnt, weil der Feature-Branch in GitHub inzwischen
fortgeschritten ist, wird zunächst dessen aktueller Stand abgerufen und in den
lokalen Feature-Branch übernommen. Eine Push-Ablehnung bedeutet nicht
automatisch, dass ein inhaltlicher Konflikt besteht.

### Prüfen und zusammenführen

1. Die zweite Person prüft Änderung, Löschungen und Testbeschreibung.
2. Rückfragen und Änderungswünsche werden im Pull Request geklärt.
3. Korrekturen werden in denselben Feature-Branch gepusht und erneut getestet.
4. Das Ergebnis von **Mandantenkonfiguration und Ressourcen prüfen** wird
   kontrolliert. Fehler in der Konfiguration werden vor dem Merge korrigiert.
   Hinweise zur JSON- oder XML-Syntax werden fachlich bewertet.
5. Nach erfolgreichem Review wird **Squash and merge** gewählt.
6. Die endgültige Commit-Nachricht wird kontrolliert.
7. Der Feature-Branch wird nach dem Merge gelöscht.

Der Squash Merge erzeugt einen Commit auf `main` oder `release/nnn`. Dieser
Push startet die Synchronisation mit M/Text-Funktionstest.

### Stand in M/Text-Funktionstest abnehmen

1. Unter **Actions** den Synchronisationslauf des Zielbranches öffnen.
2. Prüfen, dass der Lauf den Squash-Commit des Pull Requests verarbeitet.
3. Nach erfolgreicher Übertragung den Stand in M/Text-Funktionstest prüfen.
4. Einen festgestellten Fehler über einen neuen Feature-Branch korrigieren.

Auf `main` und `release/nnn` werden fachliche Änderungen nicht direkt
committet.

## 4. Änderung auf eine weitere Releaselinie übernehmen

### Kurzfassung

Squash-Commit der ursprünglichen Änderung ermitteln → neuen Feature-Branch von
der weiteren Releaselinie erstellen → Commit cherry-picken → testen → über
einen eigenen Pull Request zusammenführen.

Soll eine bereits zusammengeführte Änderung auf einer weiteren Releaselinie
verwendet werden, wird ihr Squash-Commit übernommen:

1. Den ursprünglichen Pull Request öffnen.
2. Die Commit-SHA des Squash-Commits feststellen.
3. Den geschützten Ausgangsbranch der weiteren Releaselinie aktualisieren.
4. Von diesem Stand einen neuen Feature-Branch für die weitere Releaselinie
   erstellen.
5. Den Squash-Commit mit EGit per Cherry-Pick übernehmen.
6. Konflikte fachlich auflösen und den vollständigen Stand prüfen.
7. Den Feature-Branch pushen und die Änderung in M/Text-Entwicklung testen.
8. Einen Pull Request auf den Zielbranch dieser Releaselinie erstellen.
9. Review, Squash Merge und M/Text-Funktionstest wie in Kapitel 3 durchführen.

Beispiel:

```text
Squash-Commit aus release/261
    │ Cherry-Pick
    ▼
feature/270/issue-5678
    │ Pull Request
    ▼
main, wenn main die Releaselinie 270 führt
```

Der Cherry-Pick ersetzt weder den Pull Request noch die Prüfung auf der
weiteren Releaselinie.

## 5. Mainframe-Lieferung ausführen

### Kurzfassung

Branch und Liefer-Tag wählen → **Lieferung vorbereiten** → Lieferumfang prüfen
und Vorbereitungs-ID kopieren → **Vorbereitete Lieferung ausführen** →
Mainframe-Übergabe und GitHub Release kontrollieren.

### Lieferstand und Liefer-Tag bestimmen

Liefer-Tags heißen beispielsweise:

```text
r261.100   FULL-Basis der Releaselinie 261
r261.108   kumulatives DELTA gegen r261.100
```

`r261.100` bezeichnet den vollständigen Stand von `main` oder `release/261`.
Eine Teillieferung mit der Versionsnummer `.100` ist nicht vorgesehen.

Entspricht eine spätere Lieferung der aktuellen Branchspitze von `main` oder
`release/nnn`, wird dieser Branch ausgewählt. Sollen ausgewählte, bereits in
M/Text-Funktionstest abgenommene Änderungen geliefert werden, wird ein
Bereitstellungsbranch zusammengestellt.

### Teillieferung zusammenstellen

1. Branches und Tags mit EGit aus GitHub abrufen.
2. Den vorherigen Liefer-Tag auswählen, beispielsweise `r261.107`.
3. Von diesem Tag `bereitstellung/261.108` erstellen und auschecken.
4. Die vorgesehenen Squash-Commits in der gewünschten Reihenfolge per
   Cherry-Pick übernehmen.
5. Konflikte fachlich auflösen und jeden fortgesetzten Cherry-Pick prüfen.
6. Den vollständigen Branchstand und die enthaltenen Commits kontrollieren.
7. Den Bereitstellungsbranch nach GitHub pushen.

Der Bereitstellungsbranch wird nicht nach M/Text synchronisiert. Maßgeblich ist
der in der Liefer-Vorprüfung angezeigte Inhalt. Nach erfolgreicher Lieferung
kann der Bereitstellungsbranch gelöscht werden.

### Lieferung vorbereiten

1. Im Mandanten-Repository **Actions** öffnen.
2. **Lieferung vorbereiten** auswählen.
3. **Run workflow** öffnen.
4. `main`, den passenden `release/nnn` oder den Bereitstellungsbranch
   auswählen.
5. Den Liefer-Tag `rnnn.nnn` eingeben und den Workflow starten.
6. In der Zusammenfassung Branch, Commit, FULL oder DELTA, Bezugsstand und
   projektbezogenen Lieferumfang prüfen.
7. Die angezeigte **Vorbereitungs-ID** kopieren.

Die Commit-SHA wird aus dem ausgewählten Branch ermittelt. Sie wird nicht
eingegeben. Die Vorbereitung hält diesen Stand fest, damit spätere Änderungen
am Branch die vorbereitete Lieferung nicht verändern.

### Vorbereitete Lieferung bestätigen und ausführen

1. Nach der Prüfung unter **Actions** den Workflow **Vorbereitete Lieferung
   ausführen** öffnen.
2. Die Vorbereitungs-ID eingeben.
3. Den Workflow starten.
4. Den angezeigten Lieferweg und den Start des zentralen Lieferlaufs prüfen.

Startet die vorbereitende Person auch den zweiten Workflow, ist es eine
Direktlieferung. Startet eine andere Person den zweiten Workflow, ist es eine
Vier-Augen-Freigabe.

Der zentrale Lauf erstellt den Liefer-Tag auf dem vorbereiteten Commit, baut
die Pakete und startet die Mainframe-Übergabe. Das Pushen eines Tags durch
einen Benutzer startet keine Mainframe-Übergabe.

### Ergebnis kontrollieren

Nach Abschluss wird geprüft:

1. Der zentrale Lieferlauf ist erfolgreich beendet.
2. Paket und JCL wurden an den Mainframe übergeben.
3. Im Mandanten-Repository besteht zum Liefer-Tag ein GitHub Release.
4. Das GitHub Release nennt den gelieferten Commit und enthält die
   JSON-Informationsdateien der Projekte.

Bei `.100` enthält das Lieferartefakt je Projekt ein vollständiges F-Paket und
ein leeres D-Paket. Spätere Liefer-Tags derselben Releaselinie erzeugen ein
kumulatives DELTA gegen den `.100`-Tag.

### Vorhandene Lieferung erneut übergeben

Ein Git-Stand darf mehrfach an CodePipeline übergeben werden:

1. Im Mandanten-Repository **Actions** öffnen.
2. **Lieferung erneut übergeben** auswählen.
3. Den vorhandenen Liefer-Tag eingeben.
4. Den Workflow starten und den zentralen Lieferlauf kontrollieren.

Dabei entstehen keine neue Bestätigung und kein neuer Tag.

Wurde ein Liefer-Tag auf einem falschen Stand erstellt, wird er nicht für einen
anderen Stand wiederverwendet. Der fehlerhafte Tag wird nach dem dafür
festgelegten GitHub-Verfahren gelöscht. Anschließend wird die richtige
Lieferung erneut vorbereitet und ausgeführt.

## 6. Sonderabläufe für Repository-Verantwortliche

### Kurzfassung

Mandantenkonfiguration über einen Pull Request ändern. Einen manuellen
Vollabgleich mit Branch und vollständiger Commit-SHA starten. Beim
Releaselinienwechsel den bisherigen `main` erhalten, die kommende Linie über
einen geprüften Übergangsbranch nach `main` übernehmen und anschließend die
nächste Releaselinie anlegen.

### Mandantenkonfiguration ändern

`.github/config.json` enthält das Mandantenkürzel, die von `main` geführte
Releaselinie, ausgeschlossene Projektverzeichnisse und die Hostprofile für die
Mainframe-Übergabe. Eine Lieferung verändert diese Datei nicht.

Eine normale Änderung der Mandantenkonfiguration wird in einem Feature-Branch
bearbeitet und über einen Pull Request in den Zielbranch übernommen. Das Feld
`releaselinie` von `main` wird im Ablauf zum Wechsel der produktiven
Releaselinie geändert.

Der Workflow **Mandantenkonfiguration und Ressourcen prüfen** kontrolliert die
Konfiguration. Fehler werden vor dem Merge korrigiert. Syntaxbefunde zu
Ressourcen erscheinen als Hinweise und werden geprüft.

Als M/Text-Projekt gilt jedes nicht versteckte Verzeichnis direkt in der
Repositorywurzel, sofern es nicht in `excluded_projects` ausgeschlossen ist.
Vor dem Hinzufügen oder Umbenennen eines Projektverzeichnisses ist zu prüfen,
ob es verarbeitet werden soll und ob der daraus gebildete Projektcode eindeutig
bleibt.

### Manuellen Vollabgleich starten

Ein manueller Vollabgleich ersetzt die einbezogenen Projektstände in der
M/Text-Zielumgebung durch den ausgewählten Git-Stand. Der Lauf wird deshalb mit
anderen Arbeiten auf derselben Releaselinie abgestimmt.

1. Den gewünschten Commit in GitHub öffnen und seine vollständige SHA kopieren.
2. Im Mandanten-Repository **Actions** öffnen.
3. **M/Text-Ressourcen synchronisieren** auswählen.
4. **Run workflow** öffnen.
5. Den Branch auswählen, zu dem der Commit gehört.
6. Die vollständige Commit-SHA eingeben.
7. Den Workflow starten und den Lauf kontrollieren.
8. Den vollständigen Stand im zugeordneten M/Text-Ziel prüfen.

Der ausgewählte Commit muss zum ausgewählten Branch gehören. `main` und
`release/nnn` führen nach M/Text-Funktionstest. Ein Feature-Branch führt nach
M/Text-Entwicklung.

### Die produktive Releaselinie wechseln

Vor dem Wechsel bestehen beispielsweise diese Stände:

```text
release/260   vorherige Releaselinie
main          produktive Releaselinie 261
release/270   kommende Releaselinie
```

#### Bisherige und kommende Linie abschließen

1. Prüfen, dass `release/270` den vollständigen neuen Stand enthält und in
   M/Text-Funktionstest abgenommen wurde.
2. `main` aktualisieren und prüfen, dass dieser Stand die bisher produktive
   Releaselinie 261 abschließt.
3. Falls 261 weiter gepflegt wird, `release/261` auf dem aktuellen
   `main`-Commit erstellen und nach GitHub pushen.
4. Prüfen, dass `release/261` und der bisherige `main` denselben Commit
   bezeichnen.

Beim Erstellen von `release/261` entsteht kein neuer Commit. Die
organisationsweiten Regeln schützen den Branch anhand seines Namens.

#### Kommende Linie nach main übernehmen

1. In EGit die aktuellen Stände von `main` und `release/270` abrufen.
2. Auf Basis des aktuellen `main` den Branch
   `feature/270/releaselinienwechsel` erstellen und auschecken.
3. `release/270` in diesen Branch mergen.
4. Konflikte anhand des vorgesehenen Stands von 270 auflösen und die
   Zusammenführung abschließen.
5. Den gesamten Branch mit `release/270` vergleichen. Ausschließlich auf dem
   bisherigen `main` vorhandene Inhalte entfernen, wenn sie nicht zu 270
   gehören.
6. In `.github/config.json` das Feld `releaselinie` auf `270` setzen.
7. Die Änderung committen und den Branch pushen.
8. Erneut den vollständigen Inhalt mit `release/270` vergleichen. Abgesehen
   von der für `main` benötigten Mandantenkonfiguration dürfen keine
   unbeabsichtigten Unterschiede bestehen.
9. Einen Pull Request von `feature/270/releaselinienwechsel` nach `main`
   erstellen.
10. Den vollständigen Dateiinhalt und insbesondere Löschungen prüfen.
11. Das Review durchführen und den Pull Request mit Squash Merge
    zusammenführen.
12. Prüfen, dass `main` dem vorgesehenen Stand von 270 entspricht und die
    Mandantenkonfiguration `270` nennt.

Der vollständige Vergleich ist erforderlich, weil ein Merge konfliktfreie
Änderungen des bisherigen `main` beibehalten kann.

#### Synchronisation und nächste Linie

1. Den automatisch gestarteten Synchronisationslauf von `main` kontrollieren.
2. Prüfen, dass der vollständige Stand zuerst nach M/Text-Entwicklung und
   anschließend nach M/Text-Funktionstest übertragen wurde.
3. Den Stand in beiden Umgebungen kontrollieren.
4. Neue Features für 270 auf Basis von `main` erstellen.
5. `release/271` auf Basis des neuen `main` erstellen und dort die kommende
   Releaselinie vorbereiten.

Die bisherige Linie 261 wird anschließend über `release/261` gepflegt. `main`
bleibt der Default Branch und führt jetzt 270.

## 7. Fehler beheben und Workflow-Läufe kontrollieren

### Kurzfassung

Erwarteten Branch, Commit oder Liefer-Tag feststellen → erste aussagekräftige
Fehlermeldung prüfen → Ursache im Feature-Branch oder in der technischen
Einrichtung beheben → aktuellen gewünschten Stand erneut verarbeiten. Alte
Synchronisationsläufe nicht unkontrolliert wiederholen.

### Git-Änderungen sicher korrigieren

| Situation | Vorgehen |
|---|---|
| Änderung ist noch nicht committet | Betroffene Dateien nach Prüfung mit **Restore** zurücksetzen. |
| Eigener Commit wurde noch nicht gepusht | Commit im lokalen Feature-Branch korrigieren oder mit **Reset** zurücknehmen. |
| Feature-Branch wurde bereits gepusht | Einen korrigierenden Commit erstellen und erneut pushen. |
| Pull Request wurde bereits zusammengeführt | Einen neuen Feature-Branch und einen neuen Pull Request für die Korrektur erstellen. |
| Änderung wird auf einer weiteren Releaselinie nicht benötigt | Den dortigen Feature-Branch oder Pull Request beenden. Eine bereits zusammengeführte Änderung über einen neuen Korrektur-Commit zurücknehmen. |

**Clean** gehört nicht zum normalen Bedienweg. Die Funktion kann nicht
versionierte M/Text-Ressourcen unwiederbringlich entfernen.

### Workflow-Lauf prüfen

1. Im Mandanten-Repository **Actions** öffnen.
2. Den Workflow und den betroffenen Lauf auswählen.
3. Branch oder Liefer-Tag und verarbeiteten Commit mit dem erwarteten Stand
   vergleichen.
4. Die Jobs öffnen und die erste aussagekräftige Fehlermeldung prüfen.
5. Zugangsdaten nicht in Kommentare, Workflow-Eingaben oder Support-Tickets
   kopieren.

Für Paketbau und Mainframe-Übergabe führt der Mandantenlauf zu einem zentralen
Lauf in `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Das abschließende
GitHub Release steht wieder im Mandanten-Repository.

### Fehlgeschlagene Ressourcenprüfung

- Fehler in `.github/config.json` werden im Feature-Branch korrigiert.
- Hinweise zu JSON- oder XML-Ressourcen werden anhand der genannten Datei und
  Fundstelle geprüft.
- Nach einer Korrektur wird derselbe Feature-Branch erneut gepusht.

### Fehlgeschlagene M/Text-Synchronisation

Ein alter Push-Lauf wird nicht unkontrolliert erneut ausgeführt. Er kann ein
älteres DELTA auf einen inzwischen neueren M/Text-Stand anwenden. Stattdessen
wird zunächst der gewünschte Git-Stand bestimmt.

- Gehört der gewünschte Stand weiterhin zur aktuellen Branchspitze, wird die
  Ursache behoben und der aktuelle Stand erneut synchronisiert.
- Ist ein vollständiger, eindeutig bestimmter Stand erforderlich, startet ein
  Repository-Verantwortlicher den manuellen Vollabgleich.
- Vor jedem Vollabgleich wird die Auswirkung auf parallele Arbeiten derselben
  Releaselinie abgestimmt.

### Fehlgeschlagene Mainframe-Lieferung

Vor einer erneuten Übergabe wird geprüft, ob Mainframe oder CodePipeline den
vorherigen Versuch bereits angenommen haben. Danach wird **Lieferung erneut
übergeben** mit dem vorhandenen Liefer-Tag gestartet. Ein neuer Tag ist nicht
erforderlich.

Ist ausschließlich das Bereitstellen der Lieferinformationen in GitHub
fehlgeschlagen, kann der fehlgeschlagene Rückmeldungsjob erneut ausgeführt
werden. Das Paket wird dabei nicht noch einmal an den Mainframe übertragen.

### Kurzübersicht vom SVN- zum Git-Ablauf

| Bisheriger SVN-Schritt | Git-Ablauf |
|---|---|
| Arbeitskopie aktualisieren | GitHub-Stände abrufen und ausgecheckten Branch aktualisieren |
| Änderung committen | Lokal committen und Feature-Branch pushen |
| Entwicklungsstand bereitstellen | Feature-Branch pushen und M/Text-Entwicklung prüfen |
| Änderung nach M/Text-Funktionstest übernehmen | Pull Request prüfen und mit Squash Merge zusammenführen |
| Änderung auf eine weitere Releaselinie übertragen | Squash-Commit in einen neuen Feature-Branch cherry-picken |
| SVN-Tag für eine Lieferung erzeugen | Lieferung vorbereiten, Lieferumfang prüfen und vorbereitete Lieferung ausführen |
