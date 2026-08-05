# Benutzeranleitung für M/Text-Ressourcen mit Git

## 1. Zweck und Grundablauf

Diese Anleitung beschreibt die tägliche Arbeit mit M/Text-Ressourcen in Git.
Sie richtet sich an Entwickler und Repository-Verantwortliche, die bisher mit
SVN gearbeitet haben.

Jede Änderung wird in einem eigenen Feature-Branch durchgeführt:

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
zusammengeführten Stand in M/Text-Abnahme prüfen
```

Die Git-Branches heißen:

| Zweck | Name | Beispiel |
|---|---|---|
| Führende Releaselinie | `main` | `main` vertritt R270 |
| Parallel gepflegte Releaselinie | `release/Rnnn` | `release/R261` |
| Einzelne Änderung | `feature/Rnnn/<Bezeichnung>` | `feature/R261/issue-5678` |
| Release-Tag | `v{Release-Version}` | `v261.108` |

Entwicklung und Abnahme sind M/Text-Ziele. Es gibt dafür keine eigenen
Git-Branches.

## 2. Voraussetzungen

Vor der ersten Bearbeitung müssen folgende Voraussetzungen erfüllt sein:

- Der Benutzer besitzt Zugriff auf das Mandanten-Repository.
- Das Repository ist in der M/Text Workbench beziehungsweise im verwendeten
  Eclipse-Arbeitsbereich geklont.
- Benutzername und E-Mail-Adresse sind im Git-Client hinterlegt.
- Die Releaselinie der Änderung ist bekannt.
- Für einen vorhandenen lokalen Klon wurde der aktuelle Stand aus GitHub
  abgerufen.

Ein Git-Arbeitsbaum zeigt zu einem Zeitpunkt einen Branch. Wer gleichzeitig an
mehreren Releaselinien arbeitet, verwendet getrennte lokale Klone und bei
Bedarf getrennte Eclipse-Arbeitsbereiche. Dadurch bleiben Projektbaum,
Releaselinie und lokale Änderungen eindeutig zugeordnet.

Beispiel:

```text
Arbeitsbereich R270  → Klon mit main oder feature/R270/...
Arbeitsbereich R261  → Klon mit release/R261 oder feature/R261/...
Arbeitsbereich R271  → Klon mit feature/R271/...
```

Die genaue Bezeichnung einzelner EGit-Menüpunkte wird im Integrationslauf mit
der eingesetzten Workbench-Version geprüft. Die fachlichen Git-Schritte dieser
Anleitung bleiben dabei unverändert.

## 3. Zielbranch einer Änderung bestimmen

Vor dem Anlegen eines Feature-Branches wird der geschützte Zielbranch
festgelegt:

| Änderung | Ausgangs- und Pull-Request-Zielbranch |
|---|---|
| Änderung für die führende Releaselinie | `main` |
| Wartung oder Fehlerkorrektur für eine ältere gepflegte Linie | `release/Rnnn` |
| Änderung für eine spätere, noch nicht durch einen geschützten Branch vertretene Linie | Ausgangspunkt nach fachlicher Festlegung. Der Feature-Branch bleibt bis zum Linienwechsel ungemergt. |

Der Name des Feature-Branches enthält dieselbe Releaselinie wie die Änderung.

## 4. Feature entwickeln und in Entwicklung testen

### Feature-Branch erstellen

1. Im passenden lokalen Klon den geschützten Ausgangsbranch auswählen.
2. Den aktuellen Stand aus GitHub abrufen.
3. Prüfen, dass keine unbeabsichtigten lokalen Änderungen vorhanden sind.
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
4. Die fachlich zusammengehörigen Dateien zum Commit hinzufügen.
5. Eine verständliche Commit-Nachricht eingeben.
6. Den Commit erstellen.

Auf einem Feature-Branch dürfen mehrere Zwischen-Commits entstehen. Beim
Squash Merge werden sie später zu einem Commit auf dem Zielbranch
zusammengefasst.

### Nach Entwicklung synchronisieren

1. Den Feature-Branch nach GitHub pushen.
2. In GitHub prüfen, dass der Synchronisationslauf für den Branch gestartet
   wurde.
3. Nach erfolgreichem Lauf die Änderung im Entwicklungsziel der Releaselinie
   testen.
4. Bei weiteren Korrekturen erneut committen und pushen.

Jeder Push überträgt den neuen Zielstand automatisch. Unveränderte Ressourcen
werden nicht erneut vom Runner nach `serverSync` übertragen.

Der Entwickler ist dafür verantwortlich, den Feature-Stand in Entwicklung zu
prüfen. Der Entwicklungslauf ist keine technische Pull-Request-Freigabe.

## 5. Pull Request und Abnahme

### Pull Request erstellen

Wenn die Änderung in Entwicklung erfolgreich geprüft wurde:

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

Hat sich der Zielbranch seit dem Erstellen des Feature-Branches geändert,
zeigt GitHub im Pull Request eine Aktualisierungsmöglichkeit an. Die angebotene
Funktion **Update branch** kann verwendet werden. Durch den späteren Squash
Merge erscheinen dadurch keine zusätzlichen Merge-Commits auf dem
Zielbranch.

Entstehen Konflikte, werden sie im Feature-Branch gelöst. Der geschützte
Zielbranch wird dabei nicht direkt bearbeitet. Nach der Konfliktlösung wird der
Feature-Branch erneut gepusht und bei Bedarf nochmals in Entwicklung geprüft.

### Prüfen und zusammenführen

1. Der Prüfer kontrolliert die Änderung nach den geltenden Review-Vorgaben.
2. Offene Rückfragen oder Änderungswünsche werden im Pull Request geklärt.
3. Der Entwickler pusht erforderliche Korrekturen in denselben Feature-Branch.
4. Nach erfolgreichem Review wird **Squash and merge** gewählt.
5. Die endgültige Commit-Nachricht wird kontrolliert.
6. Der Feature-Branch wird nach dem Merge gelöscht.

Der Merge erzeugt einen Commit auf dem geschützten Zielbranch. Dieser Push
startet automatisch die Synchronisation nach M/Text-Abnahme.

### In Abnahme prüfen

1. In GitHub prüfen, dass der Abnahmelauf erfolgreich war.
2. Den zusammengeführten Stand im Abnahmeziel der Releaselinie prüfen.
3. Einen festgestellten Fehler über einen neuen Feature-Branch korrigieren.

Auf `main` oder `release/Rnnn` wird nicht direkt korrigiert.

## 6. Typische parallele Szenarien

### Feature für die führende R270

```text
Ausgangspunkt: main
Arbeit:         feature/R270/neuer-brief
Entwicklung:    ETAPS-Linie von R270, Ziel Entwicklung
Pull Request:   feature/R270/neuer-brief → main
Abnahme:        ETAPS-Linie von R270, Ziel Abnahme
```

### Fehlerkorrektur für die gepflegte R261

```text
Ausgangspunkt: release/R261
Arbeit:         feature/R261/issue-5678
Entwicklung:    ETAPS-Linie von R261, Ziel Entwicklung
Pull Request:   feature/R261/issue-5678 → release/R261
Abnahme:        ETAPS-Linie von R261, Ziel Abnahme
```

### Länger laufendes Feature für R271

```text
Arbeit:         feature/R271/grosses-feature
Entwicklung:    ETAPS-Linie von R271, Ziel Entwicklung
Pull Request:   erst, wenn ein geschützter Zielbranch R271 vertritt
```

Der Branch kann regelmäßig gepusht und in Entwicklung getestet werden. Er wird
nicht vorzeitig nach `main` gemergt, solange `main` noch eine andere
Releaselinie vertritt.

## 7. Änderung auf eine weitere Releaselinie übernehmen

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

## 8. Release erstellen

### Voraussetzungen

Vor dem Erstellen eines Release-Tags müssen folgende Bedingungen erfüllt sein:

- Der vorgesehene Stand liegt auf `main` oder `release/Rnnn`.
- Die Abnahmesynchronisation dieses Stands war erfolgreich.
- Der Benutzer darf nach der organisationsweiten Regel Release-Tags erstellen.
- Der Tagname folgt dem vorgesehenen Releaseformat.

Beispiele:

```text
v261.100   FULL-Basis der Releaselinie R261
v261.108   kumulatives DELTA gegen v261.100
```

### Tag erstellen und pushen

1. Den geschützten Zielbranch im lokalen Git-Client aktualisieren.
2. Den freizugebenden Commit prüfen.
3. Den Release-Tag auf diesem Commit erstellen.
4. Den Tag gezielt nach GitHub pushen.
5. In GitHub prüfen, dass der zentrale Release-Lauf in `mtext-actions`
   gestartet wurde.

Das Pushen des Tags ist die fachliche Entscheidung für die Lieferung. Es gibt
keine zusätzliche Freigabe über ein GitHub Environment.

Ein Release-Tag wird nicht gelöscht. Wurde ein Tag irrtümlich erstellt, erfolgt
die Korrektur mit einem neuen Commit und einem neuen Tag.

### Ergebnis kontrollieren

Der zentrale Lauf:

1. lädt den getaggten Mandantenstand,
2. bestimmt FULL oder DELTA,
3. erstellt Pakete, Lieferbelege und Manifest,
4. prüft Größen und Prüfsummen,
5. übergibt Paket und JCL an den Mainframe.

Bei einem fehlgeschlagenen technischen Übergabeversuch wird derselbe Lauf mit
dem bereits gebauten Artefakt wiederholt. Es wird kein zusätzlicher Tag für
einen technischen Wiederanlauf erzeugt.

## 9. Führende Releaselinie wechseln

Der Wechsel wird zum unternehmensweit vorgegebenen Hauptrelease durch die
Repository-Verantwortlichen durchgeführt.

1. Prüfen, welcher Stand von `main` die bisherige Releaselinie abschließt.
2. Falls weitere Pflege vorgesehen ist, aus diesem geschützten Stand den
   Branch `release/Rnnn` erstellen.
3. Den neuen Release-Branch nach den vorgegebenen Schutzregeln einrichten.
4. In einem Pull Request auf `main` das Feld `releaselinie` in
   `.github/config.json` auf die neue führende Linie setzen.
5. Den Pull Request prüfen und mit Squash Merge zusammenführen.
6. Die initiale Vollsynchronisation der neuen Linie nach Entwicklung und
   Abnahme starten und kontrollieren.
7. Neue Feature-Branches für die neue führende Linie aus `main` erstellen.

Die bisherige Linie wird anschließend über `release/Rnnn` gepflegt. `main`
bleibt der Default Branch.

## 10. Änderungen zurücknehmen

| Situation | Vorgehen |
|---|---|
| Noch nicht committete lokale Änderung | In der Git-Ansicht die betroffenen Dateien zurücksetzen. Vorher prüfen, ob lokale M/Text-Ressourcen dadurch verloren gehen. |
| Commit liegt nur im Feature-Branch | Einen korrigierenden Commit im selben Feature-Branch erstellen oder den lokalen Commit vor dem Push mit der freigegebenen Git-Funktion überarbeiten. |
| Feature-Stand wurde nach Entwicklung synchronisiert | Den Feature-Branch korrigieren und erneut pushen. Der neue Zielstand wird nach Entwicklung synchronisiert. |
| Pull Request wurde bereits gemergt | Einen neuen Feature-Branch anlegen und den Fehler über einen neuen Pull Request korrigieren. |
| Änderung wird auf einer weiteren Releaselinie nicht benötigt | Den dortigen Feature-Branch oder Pull Request nicht weiterführen. Einen bereits erfolgten Merge über einen neuen Gegen-Commit korrigieren. |
| Release-Tag wurde irrtümlich erstellt | Den Tag nicht löschen. Die fachliche Korrektur mit einem neuen Commit und einem neuen Release-Tag liefern. |

Force-Pushes auf geschützte Branches sind nicht zulässig.

## 11. Kontrolle von Workflow-Läufen

Bei einem fehlgeschlagenen Lauf werden zuerst Repository, Branch oder Tag und
Ziel-Commit geprüft. Danach wird die erste fachliche Fehlermeldung im
Workflow-Log gelesen.

| Status | Bedeutung |
|---|---|
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinie wurden geprüft. |
| `VALIDATION_FAILED` | Eingabe oder Konfiguration ist ungültig. |
| `SOURCE_FAILED` | Commit, Branch oder Tag konnte nicht passend aufgelöst werden. |
| `RESOURCE_TRANSFER_FAILED` | Ressourcen konnten nicht nach `serverSync` übertragen werden. |
| `ADAPTER_FAILED` | LTOMA war nicht erreichbar oder hat den Aufruf abgelehnt. |
| `ADAPTER_ACCEPTED` | LTOMA hat den Aufruf angenommen. |
| `PACKAGE_FAILED` | Releasepaket, Lieferbeleg oder Manifest konnte nicht erstellt werden. |
| `ARTIFACT_READY` | Das Releaseartefakt wurde vollständig erstellt und geprüft. |
| `MAINFRAME_TRANSFER_FAILED` | FTP- oder JES-Übergabe ist fehlgeschlagen. |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden technisch übergeben. |

Ein HTTP-Erfolg von LTOMA bestätigt die unmittelbare Annahme des Aufrufs. Die
fachliche Wirkung wird anschließend in M/Text kontrolliert.

## 12. Zuordnung zum bisherigen SVN-Ablauf

| Bisheriger SVN-Schritt | Git-Ablauf |
|---|---|
| Arbeitskopie aktualisieren | Fetch und Aktualisierung des ausgecheckten Branches |
| Änderung committen | Lokal committen und Feature-Branch pushen |
| Entwicklungsstand bereitstellen | Feature-Branch pushen |
| Änderung nach Abnahme übernehmen | Pull Request prüfen und mit Squash Merge zusammenführen |
| Änderung auf weitere Releasepfade übertragen | Squash-Commit in einen Feature-Branch der weiteren Linie übernehmen |
| SVN-Tag erzeugen | Geschützten Git-Tag `v{Release-Version}` auf einem geschützten Stand erstellen |
