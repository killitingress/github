# Benutzeranleitung für M/Text-Ressourcen mit Git

## 1. Zweck und Grundablauf

Diese Anleitung beschreibt die tägliche Arbeit mit M/Text-Ressourcen in Git.
Sie richtet sich an Entwickler und Repository-Verantwortliche.

Jede Änderung wird in einem eigenen Feature-Branch bearbeitet:

```text
Feature-Branch pushen
    │
    ▼
Änderung in M/Text-Entwicklung testen
    │
    ▼
Pull Request prüfen und mit Squash Merge zusammenführen
    │
    ▼
zusammengeführten Stand in der M/Text-Funktionstestumgebung prüfen
```

Für Branches und Release-Tags gelten folgende Namen:

| Gegenstand | Namensschema | Beispiel |
|---|---|---|
| Führende Releaselinie | `main` | `main` für R270 |
| Parallel gepflegte Releaselinie | `release/Rnnn` | `release/R261` |
| Einzelne Änderung | `feature/Rnnn/<Bezeichnung>` | `feature/R261/issue-5678` |
| Release-Tag | `vnnn.nnn` oder `vnnn.nnnx` | `v261.108`, `v261.108a` |

M/Text-Entwicklung und M/Text-Funktionstest sind die beiden M/Text-Umgebungen.
Es gibt dafür keine eigenen Git-Branches.

## 2. Voraussetzungen

Vor der ersten Bearbeitung müssen folgende Voraussetzungen erfüllt sein:

- Der Benutzer besitzt Zugriff auf das Mandanten-Repository.
- Das Mandanten-Repository ist lokal geklont und in der M/Text Workbench
  beziehungsweise im verwendeten Eclipse-Arbeitsbereich eingebunden.
- Benutzername und E-Mail-Adresse sind im Git-Client hinterlegt.
- Die Releaselinie der Änderung ist bekannt.

In einem Git-Arbeitsbaum kann jeweils ein Branch ausgecheckt sein. Wer
gleichzeitig an mehreren Releaselinien arbeitet, verwendet getrennte lokale
Klone und bei Bedarf getrennte Eclipse-Arbeitsbereiche. Dadurch bleiben
Projektbaum, Releaselinie und lokale Änderungen eindeutig zugeordnet.

Beispiel:

```text
Arbeitsbereich R270  → Klon mit main oder feature/R270/...
Arbeitsbereich R261  → Klon mit release/R261 oder feature/R261/...
Arbeitsbereich R271  → Klon mit feature/R271/...
```

### Wichtige Git-Grundlagen

Git verwaltet die lokalen Versionsstände. GitHub stellt das gemeinsame
Repository, Pull Requests und die GitHub-Actions-Automatisierung bereit.

Für Benutzer, die bisher mit SVN gearbeitet haben, sind vor allem diese
Unterschiede wichtig:

| SVN | Git |
|---|---|
| Der ausgecheckte Arbeitsbereich ist eine Arbeitskopie des zentralen SVN-Repositorys | Jeder lokale Klon ist ein eigenes Git-Repository mit Versionshistorie |
| Ein Commit überträgt die Änderung direkt an den SVN-Server | Ein Commit speichert die Änderung lokal, ein anschließender Push überträgt sie nach GitHub |
| Ein Stand wird mit einer Revisionsnummer wie `r12345` bezeichnet | Ein Stand wird mit seiner Commit-SHA bezeichnet |
| Branches werden meist für länger getrennte Stände verwendet | Ein Feature-Branch dient als vorübergehender Arbeitsbereich für eine Änderung |

| Begriff | Bedeutung |
|---|---|
| Commit | Speichert einen Stand zunächst im lokalen Repository. |
| Push | Überträgt lokale Commits nach GitHub und startet die zum Branch gehörenden Workflows. |
| Commit-SHA | Bezeichnet einen Commit eindeutig. Für einen manuellen Vollabgleich wird sie eingegeben. |
| Fetch | Ruft neue Branchstände und Commits aus GitHub ab, ändert aber weder den ausgecheckten Branch noch dessen Dateien. |
| Aktualisieren | Bringt den ausgecheckten Branch mit der dafür vorgesehenen Funktion des Git-Clients auf den aktuellen GitHub-Stand. |

### Arbeitsmittel

| Anwendung | Aufgabe |
|---|---|
| M/Text Workbench mit EGit | Ressourcen bearbeiten, Änderungen prüfen, Branches sowie Beta-Tags verwenden, committen und pushen |
| GitHub im Browser | Pull Requests bearbeiten, Releases vorbereiten, Commits und Workflow-Läufe prüfen, Tags ansehen und Lieferinformationen öffnen |

Eine Git-Kommandozeile ist für den beschriebenen Ablauf nicht vorgeschrieben.

Die folgenden Git-Funktionen werden im Ablauf benötigt. Wie sie im
verwendeten Client heißen, kann sich unterscheiden:

| Aufgabe | Git-Funktion |
|---|---|
| Arbeitsstand und Änderungen prüfen | Status und Diff |
| GitHub-Stand abrufen und den lokalen Branch aktualisieren | Fetch und anschließend die vorgesehene Aktualisierungsfunktion |
| Branch erstellen oder auswählen | Branch erstellen und Branch wechseln |
| Änderungen speichern und übertragen | Add, Commit und Push |
| Commit-SHA und konkrete Änderungen prüfen | Log und Show |
| Einen Commit auf eine weitere Releaselinie übernehmen | Cherry-Pick |
| Beta-Tag oder ausdrücklich erlaubten direkten Release-Tag anlegen und pushen | Tag und Push des einzelnen Tags |
| Änderungen zurücknehmen | Restore, Reset oder Revert – abhängig davon, ob die Änderung bereits committet oder gepusht wurde |

### Lokalen Branch vor der Arbeit aktualisieren

Vor einer Bearbeitung, einem Cherry-Pick oder dem direkten Erstellen eines Tags:

1. Das richtige Mandanten-Repository und den vorgesehenen Branch auswählen
2. Prüfen, dass keine Git-Operation und keine ungesicherte Bearbeitung offen
   ist
3. Die neuen GitHub-Stände abrufen und den ausgecheckten Branch aktualisieren
4. Kontrollieren, dass der lokale Branch und der GitHub-Branch auf denselben
   Commit zeigen
5. Erst danach mit der vorgesehenen Arbeit beginnen

Ein Fetch allein aktualisiert den ausgecheckten Branch und dessen Dateien
nicht. Schlägt die Aktualisierung wegen lokaler Änderungen oder eigener
Commits fehl, wird kein Force-Push erzwungen. Das weitere Vorgehen richtet sich
nach [Push-Ablehnung und Konflikte behandeln](#push-ablehnung-und-konflikte-behandeln).

## 3. Zielbranch einer Änderung bestimmen

Vor dem Anlegen eines Feature-Branches werden der Ausgangsbranch und das
Pull-Request-Ziel festgelegt. Für eine spätere Releaselinie kann das
Pull-Request-Ziel zu diesem Zeitpunkt noch fehlen:

| Änderung | Ausgangsbranch | Pull-Request-Ziel |
|---|---|---|
| Führende Releaselinie | `main` | `main` |
| Ältere, weiterhin gepflegte Releaselinie | `release/Rnnn` | `release/Rnnn` |
| Spätere Releaselinie ohne geschützten Zielbranch | Nach fachlicher Festlegung | Noch nicht vorhanden |

Der Name des Feature-Branches enthält dieselbe Releaselinie wie die Änderung.

### Typische Szenarien

| Fall | Ausgangsbranch | Feature-Branch | Pull-Request-Ziel |
|---|---|---|---|
| Feature für die führende R270 | `main` | `feature/R270/neuer-brief` | `main` |
| Fehlerkorrektur für die gepflegte R261 | `release/R261` | `feature/R261/issue-5678` | `release/R261` |
| Länger laufendes Feature für R271 | Nach fachlicher Festlegung | `feature/R271/grosses-feature` | Nach dem Linienwechsel `main` |

Ein länger laufendes Feature wird erst zusammengeführt, wenn ein geschützter
Zielbranch seine Releaselinie vertritt. Der Feature-Branch wird regelmäßig mit
Änderungen des festgelegten Ausgangsbranches aktualisiert. Nach dem
Linienwechsel wird er vor dem Pull Request mit dem aktuellen `main` abgeglichen
und erneut in M/Text-Entwicklung getestet.

## 4. Feature entwickeln und in M/Text-Entwicklung testen

### Feature-Branch erstellen

1. Im passenden lokalen Klon den festgelegten Ausgangsbranch auswählen.
2. Prüfen, dass keine unbeabsichtigten lokalen Änderungen und keine noch
   offene Git-Operation vorhanden sind.
3. Den Ausgangsbranch auf den aktuellen GitHub-Stand bringen.
4. Einen neuen Branch `feature/Rnnn/<Bezeichnung>` erstellen.
5. Den Feature-Branch auschecken.

Die Bezeichnung soll die fachliche Änderung erkennen lassen. Geeignete Namen
sind beispielsweise:

```text
feature/R270/neuer-brief
feature/R261/issue-5678
feature/R270/adresse-korrigieren
```

### Änderungen committen

1. Die Ressourcen in der M/Text Workbench bearbeiten.
2. In der Git-Ansicht die geänderten und neuen Dateien kontrollieren.
3. Unbeabsichtigte Dateien von der Übernahme ausschließen oder zurücknehmen.
4. Die fachlich zusammengehörigen Änderungen zum Commit hinzufügen.
5. Eine verständliche Commit-Nachricht eingeben.
6. Den Commit erstellen.

Auf einem Feature-Branch dürfen mehrere Zwischen-Commits entstehen. Beim
Squash Merge werden sie später zu einem Commit auf dem Zielbranch
zusammengefasst.

### Mit M/Text-Entwicklung synchronisieren

1. Den Feature-Branch nach GitHub pushen.
2. In GitHub prüfen, dass der Synchronisationslauf für den Branch gestartet
   wurde.
3. Nach erfolgreichem Lauf die Änderung in der M/Text-Entwicklungsumgebung der
   Releaselinie testen.
4. Bei weiteren Korrekturen erneut committen und pushen.

Jeder Push überträgt den neuen Zielstand automatisch. Ein erfolgreicher Lauf
bestätigt die Übertragung, nicht die fachliche Richtigkeit der Änderung. Diese
prüft der Entwickler anschließend in M/Text.

Nach mehreren kurz aufeinanderfolgenden Pushes ist zu prüfen, dass der letzte
erfolgreiche Synchronisationslauf den aktuellen Commit des Feature-Branches
verarbeitet hat. Erst dieser Stand wird in M/Text getestet.

### Mandantenkonfiguration ändern

Die Datei `.github/config.json` enthält die Angaben, die für die Verarbeitung
dieses Mandanten-Repositories benötigt werden. Dazu gehören die Releaselinie,
das Mandantenkürzel, ausgeschlossene Projektverzeichnisse und die Zuordnung für
die Mainframe-Übergabe. Das Feld `letztes_release` nennt die zuletzt über den
jeweiligen Lieferbranch freigegebene Release-Version. Vor dem ersten Release
steht dort `null`. Beim Release-Freigabe-PR aktualisiert der Workflow dieses
Feld.

Als M/Text-Projekt gilt jedes nicht versteckte Verzeichnis direkt in der
Repositorywurzel, sofern es nicht in `excluded_projects` ausgeschlossen ist.
Vor dem Hinzufügen oder Umbenennen eines Projektverzeichnisses ist deshalb zu
prüfen, ob es verarbeitet werden soll und ob der daraus gebildete Projektcode
eindeutig bleibt.

Eine Änderung an `.github/config.json` folgt demselben Feature- und
Pull-Request-Ablauf wie eine Ressourcenänderung. Im Pull Request prüft der
Workflow **Mandantenkonfiguration und Ressourcen prüfen** die Konfiguration
und die geänderten Ressourcen. Dieser Lauf muss erfolgreich sein, bevor die
Änderung zusammengeführt wird.

Die verbindliche Bedeutung der Konfigurationsfelder und der
Projektverzeichnisse ist im
[Zielbild](./Zielbild_GitHub_Actions_Git.md) beschrieben. Für einen Wechsel der
führenden Releaselinie gilt der Ablauf in Kapitel 9.

## 5. Pull Request und M/Text-Funktionstest

### Pull Request erstellen

Wenn die Änderung in M/Text-Entwicklung erfolgreich geprüft wurde:

1. Das Mandanten-Repository in GitHub öffnen.
2. Einen Pull Request vom Feature-Branch auf den zugehörigen Zielbranch
   erstellen.
3. Kontrollieren, dass Quell- und Zielbranch dieselbe Releaselinie betreffen.
4. Die Änderung und das Ergebnis des Entwicklungstests verständlich
   beschreiben.
5. Den vorgesehenen Prüfer zuordnen.

Beispiele:

```text
feature/R270/neuer-brief  → main
feature/R261/issue-5678   → release/R261
```

### Feature-Branch aktualisieren

Hat sich der Zielbranch seit dem Erstellen des Feature-Branches geändert, kann
der Feature-Branch aktualisiert werden. Falls GitHub im Pull Request die
Funktion **Update branch** anbietet, kann sie dafür verwendet werden. Durch den
späteren Squash Merge erscheinen dabei keine zusätzlichen Merge-Commits auf
dem Zielbranch.

### Push-Ablehnung und Konflikte behandeln

Wird ein Push abgelehnt, weil der Feature-Branch auf GitHub inzwischen
fortgeschritten ist, wird zunächst dessen aktueller Stand abgerufen und in den
lokalen Feature-Branch übernommen. Eine solche Ablehnung bedeutet noch nicht,
dass sich Dateiänderungen widersprechen.

Entsteht beim Aktualisieren oder bei einem Cherry-Pick ein Konflikt:

1. Nicht pushen und die betroffenen Dateien sowie die laufende Git-Operation
   prüfen.
2. Für jede Konfliktstelle den bisherigen Inhalt, die neue Änderung und den
   gemeinsamen Ausgangsstand vergleichen.
3. Den fachlich richtigen Inhalt herstellen und alle Konfliktmarkierungen
   entfernen.
4. Die aufgelösten Dateien bestätigen und die Git-Operation fortsetzen. Ist
   die richtige Auflösung unklar, die Operation abbrechen und die Abweichung
   mit den Beteiligten klären.
5. Nach Abschluss den Arbeitsstand und die Änderungen kontrollieren. Erst dann
   den Feature-Branch pushen und bei Bedarf erneut in M/Text-Entwicklung testen.

### Prüfen und zusammenführen

1. Der Prüfer kontrolliert die Änderung nach den geltenden Review-Vorgaben.
2. Offene Rückfragen oder Änderungswünsche werden im Pull Request geklärt.
3. Der Entwickler pusht erforderliche Korrekturen in denselben Feature-Branch.
4. Nach erfolgreichem Review wird **Squash and merge** gewählt.
5. Die endgültige Commit-Nachricht wird kontrolliert.
6. Der Feature-Branch wird nach dem Merge gelöscht.

Der Merge erzeugt einen Commit auf dem geschützten Zielbranch. Dieser Push
startet automatisch die Synchronisation mit der M/Text-Funktionstestumgebung.

### Stand in M/Text-Funktionstest prüfen

1. In GitHub prüfen, dass der Synchronisationslauf für M/Text-Funktionstest
   erfolgreich war.
2. Den zusammengeführten Stand in der M/Text-Funktionstestumgebung der
   Releaselinie prüfen.
3. Einen festgestellten Fehler über einen neuen Feature-Branch korrigieren.

Auf `main` oder `release/Rnnn` wird nicht direkt korrigiert.

## 6. Änderung auf eine weitere Releaselinie übernehmen

Eine Änderung wird manchmal auf mehreren Releaselinien benötigt. Dafür wird
der Squash-Commit der bereits zusammengeführten Änderung übernommen.

1. Den Pull Request der ursprünglichen Änderung öffnen.
2. Die Commit-SHA des Squash-Commits feststellen.
3. Im lokalen Klon der weiteren Releaselinie den geschützten Ausgangsbranch
   aktualisieren.
4. Einen neuen Feature-Branch für diese Releaselinie erstellen.
5. Den Squash-Commit per Cherry-Pick in den neuen Feature-Branch übernehmen.
6. Konflikte im Feature-Branch lösen.
7. Push, Entwicklungstest und Pull Request wie gewohnt durchführen.

Beispiel:

```text
Fehler zuerst in release/R261 behoben
    │ Squash-Commit übernehmen
    ▼
feature/R270/issue-5678
    │ Pull Request
    ▼
main
```

Der Cherry-Pick ersetzt keinen Pull Request und keine Prüfung auf der weiteren
Releaselinie.

## 7. Release erstellen

### Voraussetzungen

Vor dem Vorbereiten eines Releases müssen folgende Bedingungen erfüllt sein:

- Der aktuelle Stand von `main` oder `release/Rnnn` soll geliefert werden
- Die Synchronisation dieses Branchstands mit der M/Text-Funktionstestumgebung war
  erfolgreich
- Die im Wartungstool vergebene Release-Version ist bekannt

Beispiele:

```text
v261.100   FULL-Basis der Releaselinie R261
v261.108   kumulatives DELTA gegen v261.100
v261.108a  Beta-Lieferstand als kumulatives DELTA gegen v261.100
```

Der optionale letzte Klein- oder Großbuchstabe kennzeichnet einen
Beta-Lieferstand. Mehrere Beta-Lieferungen derselben Release-Version erhalten
unterschiedliche Suffixe, beispielsweise `v261.108a` und `v261.108b`. Bei der
späteren Erzeugung der Lieferung aus den CodePipeline-Elementen wird angegeben,
dass es sich um eine Beta-Lieferung handelt.

### Release über einen Freigabe-PR

Ein Release-Tag ohne Buchstabensuffix wie `v261.108` wird durch den
Freigabeworkflow erstellt:

1. Im Mandanten-Repository **Actions** und den Workflow
   **Release vorbereiten** öffnen.
2. **Run workflow** wählen.
3. `main` oder den passenden `release/Rnnn` als Branch auswählen.
4. Die im Wartungstool vergebene Release-Version eingeben.
5. Den Workflow starten und seinen Abschluss abwarten.
6. Im Repository unter **Branches** den neuen Branch
   `release-approval/<Release-Tag>/<Lauf>` suchen und dort den Pull Request
   eröffnen.
7. Als Ziel des Pull Requests den in Schritt 3 gewählten Lieferbranch
   einstellen. GitHub schlägt `main` vor.

Den Pull Request eröffnet die anfordernde Person selbst. Sie ist damit dessen
Autor und kann ihn nicht selbst genehmigen. So ist sichergestellt, dass die
Freigabe von einer zweiten Person kommt.

Im Diff des Pull Requests steht die neue Release-Version im Feld
`letztes_release` der Datei `.github/config.json`. Der Check **Release
vorprüfen** zeigt Branch und Commit-SHA, FULL oder DELTA, den Bezugsstand, die
betroffenen Projekte sowie die enthaltenen Änderungen und Löschungen. Bei
einer FULL-Lieferung entfällt der Bezugsstand. Der Pull Request kann erst nach
erfolgreicher Vorprüfung zusammengeführt werden. Eine andere Person prüft:

- Der angegebene Branchstand wurde in M/Text-Funktionstest geprüft
- Die Release-Version stimmt mit dem Wartungstool überein
- Die aufgeführten Änderungen und Löschungen sollen geliefert werden

Nach der Freigabe wird der Pull Request zusammengeführt. Der Workflow erstellt
daraufhin den Release-Tag auf dem Merge-Commit des Pull Requests und startet den
zentralen Release-Lauf.

### Beta-Tag erstellen

Ein Beta-Tag mit Buchstabensuffix kann ohne Freigabe-PR erstellt werden:

1. Den aktuellen Stand von `main` oder dem passenden `release/Rnnn` prüfen.
2. Den vorgegebenen Beta-Tagnamen, beispielsweise `v261.108a`, auf diesem
   Commit anlegen.
3. Den Tag nach GitHub pushen.
4. Prüfen, dass der zentrale Release-Lauf gestartet wurde.

Der Tag kann in der M/Text Workbench oder in GitHub erstellt werden. Ein
Beta-Tag kann nicht für eine produktive Lieferung verwendet werden.

### Ergebnis kontrollieren

Nach Abschluss ist in GitHub zu prüfen, dass der zentrale Lauf erfolgreich
beendet wurde. Der Lauf:

1. lädt den getaggten Mandantenstand,
2. bestimmt FULL oder DELTA,
3. erstellt Projektpakete, JSON-Informationsdateien und JCL,
4. übergibt Paket und JCL an den Mainframe,
5. erstellt zum Tag ein GitHub Release im Mandanten-Repository.

Das GitHub Release enthält für jedes Projekt die JSON-Informationsdatei mit
Bezugsstand, Zielstand, Elementen und SHA-256-Prüfsummen. Die
Informationsdateien werden nicht an den Mainframe übertragen.

Bei einem `.100`-Tag enthält das Artefakt für jedes einbezogene Projekt ein
vollständiges F-Paket und ein leeres D-Paket. Jeder weitere Tag derselben
Releaselinie erzeugt ein kumulatives DELTA gegen den `.100`-Tag.

Die Informationsdatei eines DELTAs beschreibt den tatsächlich paketierten
Vergleich vom `.100`-Tag bis zum Release-Tag.

Bei einem fehlgeschlagenen technischen Übergabeversuch wird der
Übergabejob erneut ausgeführt. Er verwendet das bereits gebaute Artefakt. Für
einen technischen Wiederanlauf wird kein zusätzlicher Tag erzeugt.

## 8. Manuellen Vollabgleich starten

Der manuelle Vollabgleich stellt einen ausgewählten Commit vollständig in der
Zielstufe bereit, die sich aus dem ausgewählten Branch ergibt:

| Ausgewählter Branch | Zielstufe |
|---|---|
| `feature/Rnnn/<Bezeichnung>` | M/Text-Entwicklung |
| `main` | M/Text-Funktionstest der in diesem Commit konfigurierten Releaselinie |
| `release/Rnnn` | M/Text-Funktionstest der Releaselinie |

1. Im Mandanten-Repository **Actions** öffnen.
2. Den Workflow **M/Text-Ressourcen synchronisieren** auswählen.
3. **Run workflow** öffnen.
4. Den Branch auswählen, zu dem der Commit gehört. Für die führende
   Releaselinie ist dies `main`.
5. Die Commit-SHA eingeben.
6. Den Workflow starten und den Lauf kontrollieren.
7. Den bereitgestellten Stand im zugeordneten M/Text-Ziel prüfen.

Die Releaselinie wird aus dem ausgewählten Branch und bei `main` aus der
Mandantenkonfiguration des Commits ermittelt. Der Lauf ersetzt die dem
Mandanten zugeordneten Projektstände vollständig. Projektstände anderer
Mandanten bleiben erhalten.

Soll ausnahmsweise ein beliebiger Commit nach M/Text-Entwicklung übertragen
werden, wird ein kurzlebiger Feature-Branch der passenden Releaselinie auf
diesem Commit erstellt und gepusht. Beispielsweise kann
`feature/R271/wiederherstellung` verwendet werden. Der Push synchronisiert den
Commit nach M/Text-Entwicklung. Nach dem erfolgreichen Lauf kann der Hilfsbranch
gelöscht werden.

## 9. Die führende Releaselinie wechseln

Der Wechsel wird zum unternehmensweit vorgegebenen Hauptrelease durch die
Repository-Verantwortlichen durchgeführt.

### Ausgangsstand vorbereiten

1. Prüfen, dass die neue Releaselinie in der zentralen Zuordnung eingerichtet
   ist.
2. In der M/Text Workbench das Mandanten-Repository und `main` auswählen.
3. Prüfen, dass keine lokalen Änderungen und keine Git-Operation offen sind.
4. `main` mit dem GitHub-Stand aktualisieren.
5. Kontrollieren, dass dieser Stand in M/Text-Funktionstest geprüft wurde und
   die bisherige Releaselinie abschließt.

Falls die bisherige Releaselinie weiter gepflegt wird:

1. In der Git-Ansicht `release/Rnnn` auf Basis von `main` erstellen und
   auschecken.
2. `release/Rnnn` nach GitHub pushen.
3. In GitHub kontrollieren, dass `release/Rnnn` und `main` auf denselben Commit
   zeigen.
4. Den automatisch gestarteten Synchronisationslauf kontrollieren.
5. In GitHub kontrollieren, dass Änderungen an `release/Rnnn` einen Pull Request
   und das Vier-Augenprinzip erfordern und Force-Push gesperrt ist.
6. In der M/Text Workbench wieder `main` auswählen.

Beim Erstellen des Release-Branches entsteht kein neuer Commit. Der neue Branch
und `main` bezeichnen zunächst denselben Stand.

### Releaselinie wechseln

1. Einen Feature-Branch der neuen Releaselinie auf Basis von `main` erstellen.
2. In `.github/config.json` ausschließlich das Feld `releaselinie` auf die
   neue führende Linie setzen, die Änderung committen und pushen.
3. Den Synchronisationslauf für M/Text-Entwicklung erfolgreich prüfen.
4. Einen Pull Request auf `main` erstellen. Prüfen, dass
   **Mandantenkonfiguration und Ressourcen prüfen** erfolgreich war, und den
   Pull Request mit Squash Merge zusammenführen.
5. Den automatisch gestarteten Synchronisationslauf kontrollieren. Der
   Squash-Commit wird vollständig mit M/Text-Entwicklung und
   M/Text-Funktionstest synchronisiert.
6. Den Stand in M/Text-Entwicklung und M/Text-Funktionstest kontrollieren.
7. Neue Feature-Branches für die neue führende Linie auf Basis von `main`
   erstellen.

Scheitert die Übertragung nach M/Text-Funktionstest, nachdem die Übertragung
nach M/Text-Entwicklung bereits erfolgreich war, bleibt der Stand in
M/Text-Entwicklung bestehen. Der fehlgeschlagene Lauf wird erneut ausgeführt.
Dabei werden M/Text-Entwicklung und M/Text-Funktionstest vollständig neu
abgeglichen.

Die bisherige Linie wird anschließend über `release/Rnnn` gepflegt. `main`
bleibt der Default Branch.

## 10. Änderungen zurücknehmen

| Situation | Vorgehen |
|---|---|
| Noch nicht committete lokale Änderung | In der Git-Ansicht die betroffenen Dateien zurücksetzen. Vorher prüfen, ob lokale M/Text-Ressourcen dadurch verloren gehen. |
| Commit liegt nur im Feature-Branch | Einen korrigierenden Commit im selben Feature-Branch erstellen oder den lokalen Commit vor dem Push mit der freigegebenen Git-Funktion überarbeiten. |
| Feature-Stand wurde in M/Text-Entwicklung bereitgestellt | Den Feature-Branch korrigieren und erneut pushen. Der neue Zielstand wird in M/Text-Entwicklung bereitgestellt. |
| Pull Request wurde bereits zusammengeführt | Einen neuen Feature-Branch anlegen und den Fehler über einen neuen Pull Request korrigieren. |
| Änderung wird auf einer weiteren Releaselinie nicht benötigt | Den dortigen Feature-Branch oder Pull Request nicht weiterführen. Eine bereits erfolgte Übernahme über einen neuen korrigierenden Commit zurücknehmen. |
| Tag wurde lokal, aber noch nicht nach GitHub gepusht | Den lokalen Tag korrigieren und Tagnamen sowie Commit-SHA erneut prüfen. |

Force-Pushes auf geschützte Branches sind nicht zulässig.

Die Git-Funktionen unterscheiden sich danach, wie weit eine Änderung bereits
veröffentlicht wurde:

| Funktion | Verwendung |
|---|---|
| `Restore` | Noch nicht committete Änderungen an ausgewählten Dateien verwerfen |
| `Reset` | Einen eigenen, noch nicht gepushten Commit lokal zurücknehmen |
| `Revert` | Einen neuen Commit erzeugen, der eine bereits veröffentlichte Änderung zurücknimmt |

`Reset` und `Rebase` sowie das nachträgliche Ändern eines Commits werden nicht
auf bereits veröffentlichte Commits angewendet. `Clean` gehört nicht zum
normalen Bedienweg, weil es nicht versionierte M/Text-Ressourcen
unwiederbringlich entfernen kann.

## 11. Workflow-Läufe kontrollieren

### Lauf prüfen

1. Für Ressourcenprüfung und Synchronisation im Mandanten-Repository
   **Actions** öffnen. Für einen Release den zentralen Lauf in
   `FinanzInformatik/fi_lbs_entw_oms_mtext_actions` öffnen.
2. Den betroffenen Lauf auswählen.
3. Repository, Branch oder Tag, Ziel-Commit und Auslöser mit dem erwarteten
   Stand vergleichen.
4. Die Jobs und ihre Protokolle öffnen und den abschließenden Status prüfen.
5. Bei einem Fehler die erste aussagekräftige Fehlermeldung auswerten.

| Status oder Fehlerbild | Bedeutung | Nächste Prüfung |
|---|---|---|
| Workflow kann die festgelegte CI/CD-Version nicht laden | Zugriff oder technische Einrichtung ist unvollständig | Lauf und verwendete CI/CD-Version festhalten und die Repository-Verantwortlichen informieren. Die Workflowdateien nicht selbst ändern. |
| `RESOURCE_CHECKED` | JSON- und XML-Ressourcen wurden geprüft. Befunde stehen als Warnungen im Laufprotokoll. | Warnungen mit Datei und Fundstelle prüfen. |
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinie wurden geprüft. | Inhaltliche Änderung weiter prüfen. Der Status bestätigt keine fachliche Freigabe. |
| `VALIDATION_FAILED` | Eingabe oder Konfiguration ist ungültig. | Erste Fehlermeldung sowie Branch, Tag und Mandantenkonfiguration prüfen. |
| `RELEASE_APPROVAL_READY` | Der Freigabe-Branch mit der neuen Release-Version wurde veröffentlicht. | Den Pull Request auf den Lieferbranch eröffnen. |
| `RELEASE_APPROVAL_CHECKED` | Release-Version, Branchstand und Lieferumfang wurden geprüft und im Pull Request angezeigt. Der erforderliche Statuscheck ist erfolgreich. | Die Zusammenfassung fachlich prüfen und den Pull Request durch eine zweite Person freigeben lassen. |
| `RELEASE_APPROVAL_VALIDATED` | Merge und eingetragene Release-Version gehören zum Freigabe-Pull-Request. | Die anschließende Tag-Erstellung und den zentralen Release-Lauf prüfen. |
| `SOURCE_FAILED` | Commit, Branch oder Tag konnte nicht passend aufgelöst werden. | Commit-SHA, ausgewählten Branch oder Release-Tag und deren Zuordnung prüfen. |
| `RESOURCE_TRANSFER_FAILED` | Projektpakete oder Informationsdateien konnten nicht auf CIFS bereitgestellt werden. | Fehlermeldung und betroffenes Projekt festhalten und die Repository-Verantwortlichen informieren. |
| `ADAPTER_FAILED` | LTOMA war nicht erreichbar oder hat den Aufruf abgelehnt. | HTTP-Status und Antwort im Protokoll prüfen. Den Lauf erst nach Klärung der Ursache wiederholen. |
| `ADAPTER_ACCEPTED` | LTOMA hat den Aufruf angenommen. | Die fachliche Wirkung anschließend in M/Text kontrollieren. |
| `PACKAGE_FAILED` | Projektpaket, JSON-Informationsdatei oder JCL konnte nicht erstellt oder verwendet werden. | Erste Fehlermeldung, betroffenes Projekt und Releasebasis prüfen. |
| `ARTIFACT_READY` | Projektpakete, JSON-Informationsdateien und JCL wurden erstellt. | Den nachfolgenden Mainframe-Übergabejob kontrollieren. |
| `MAINFRAME_TRANSFER_FAILED` | FTPS- oder JES-Übergabe ist fehlgeschlagen. | Übergabeprotokoll prüfen und vor einem Wiederanlauf klären, ob der vorherige Versuch angenommen wurde. |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden technisch übergeben. | Den nachgelagerten Status auf dem Mainframe nach dem festgelegten Betriebsverfahren kontrollieren. |
| `GITHUB_RELEASE_FAILED` | Die Lieferinformationen konnten im Mandanten-Repository nicht bereitgestellt werden. | Den fehlgeschlagenen Rückmeldungsjob wiederholen. Das Paket wird dabei nicht erneut übertragen. |
| `GITHUB_RELEASE_PUBLISHED` | Zusammenfassung und Informationsdateien stehen beim Release-Tag bereit. | Die Zusammenfassung prüfen und bei Bedarf die Informationsdateien herunterladen. |

### Lauf wiederholen

**Re-run jobs** wiederholt einen vorhandenen Lauf mit demselben Commit und
derselben Git-Referenz. Ein fehlgeschlagener Rückmeldungsjob kann direkt
wiederholt werden. Er aktualisiert das GitHub Release und überträgt das Paket
nicht erneut.

Die Wiederholung eines älteren Synchronisationslaufs kann einen neueren
M/Text-Zielstand durch den Stand des älteren Commits ersetzen. Deshalb werden
vorher die Commit-SHA des Laufs, der aktuelle Branch-Commit und der gewünschte
Zielstand verglichen. Ist der Branch inzwischen weitergelaufen, wird statt des
alten Laufs der gewünschte Commit über den manuellen Vollabgleich aus Kapitel 8
synchronisiert.

Bei einer fehlgeschlagenen Mainframe-Übergabe wird der Übergabejob mit dem
bereits gebauten Artefakt wiederholt. Dafür wird kein neuer Release-Tag
erstellt.

Zugangsdaten werden nicht in Workflow-Eingaben, GitHub-Kommentare oder
Support-Tickets kopiert.

## 12. Zuordnung zum bisherigen SVN-Ablauf

| Bisheriger SVN-Schritt | Git-Ablauf |
|---|---|
| Arbeitskopie aktualisieren | Fetch und Aktualisierung des ausgecheckten Branches |
| Änderung committen | Lokal committen und Feature-Branch pushen |
| Entwicklungsstand bereitstellen | Feature-Branch pushen |
| Änderung nach M/Text-Funktionstest übernehmen | Pull Request prüfen und mit Squash Merge zusammenführen |
| Änderung auf weitere Releasepfade übertragen | Squash-Commit in einen Feature-Branch der weiteren Linie übernehmen |
| SVN-Tag erzeugen | Release über den Freigabe-PR vorbereiten und durch eine zweite Person freigeben lassen |
| Beta-Tag erzeugen | Beta-Tag `vnnn.nnnx` auf dem aktuellen Stand des passenden geschützten Branches erstellen |
