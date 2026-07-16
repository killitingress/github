# Benutzeranleitung für die M/Text-Lieferung mit GitHub Actions

**Bezug:** [Zielbild](./Zielbild_GitHub_Actions_Git.md),
[Soll-Grafik](../../Architektur_Soll_GitHub_Actions_Git.drawio)

## 1. Zweck

Die Lösung führt M/Text-Ressourcen eines Mandanten über die drei Stufen
`Entwicklung`, `Abnahme` und `Bereitstellung`. Pushes nach Entwicklung und
Abnahme lösen die jeweilige M/Text-Synchronisation aus. Der Push nach
Bereitstellung liefert noch nichts aus; erst ein Release-Tag startet eine FULL
oder DELTA Lieferung via der nachgelagerten Mainframe-Übergabe an die IZE9.

### Hinweis zur Einführung

Voraussichtlich ab November/Dezember 2026 steht die neue GitHub-Umgebung auf
Basis eines Abzugs der SVN-Repositories zunächst für Tests zur Verfügung. In
diesem Parallelbetrieb bleibt der bisherige Jenkins-/SVN-Prozess produktiv. Die
Produktivsetzung ist ab Januar 2027 als harter Cutover geplant. Ab dann ist
GitHub für den M/Text Tonic Lieferprozess das führende System.

### Abgrenzung

Zu Themen wie technischer Einrichtung, Aktivierung und Cutover gibt es
[Nächste Schritte](./Naechste_Schritte.md).

Usermigration und Verwaltung, Rollen und Berechtigungsstruktur sind nicht
Bestandteil dieser Dokumentation.

## 2. Begriffe und Namensregeln

| Element | Verbindliches Format | Beispiel |
|---|---|---|
| Stufenbranch | `Rnnn/Entwicklung`, `Rnnn/Abnahme`, `Rnnn/Bereitstellung` | `R271/Entwicklung` |
| Optionaler Feature-Branch | `feature/Rnnn/<Issue>-<kurzname>` | `feature/R270/0711-komplizierte-Arbeiten` |
| Release-Tag | `Rnnn.nnn` | `R261.100`, `R261.108` |

Groß-/Kleinschreibung der Stufen ist verbindlich. Aktive Linien sind derzeit
`R260`, `R261` und `R270`.

### Unterschied zwischen SVN und Git einfach erklärt

SVN und Git erfüllen denselben Grundzweck: Sie speichern Änderungen an Dateien
und machen frühere Stände nachvollziehbar. Der wichtigste Unterschied liegt
darin, wie Änderungen gespeichert und mit anderen geteilt werden.

| SVN | Git |
|---|---|
| Die gemeinsame Versionsverwaltung liegt zentral auf dem SVN-Server. | Jeder ausgecheckte Arbeitsbereich ist ein eigenes lokales Git-Repository mit Versionshistorie. GitHub dient als gemeinsame, zentrale Austauschplattform. |
| Ein Commit überträgt eine Änderung direkt an den SVN-Server. | Ein Commit speichert die Änderung zunächst nur lokal. Erst ein anschließender Push überträgt sie nach GitHub. |
| Neue Stände erhalten fortlaufende Revisionsnummern wie `r12345`. | Jeder Stand erhält eine eindeutige Commit-SHA. |
| Branches werden vergleichsweise selten und eher für länger getrennte Entwicklungslinien verwendet. | Branches lassen sich leicht als vorübergehende Arbeitsbereiche für einzelne Änderungen nutzen. |

Für die tägliche Arbeit bedeutet das vor allem: **Committen und Pushen sind in
Git zwei getrennte Schritte.** Ein lokaler Commit sichert den eigenen
Arbeitsstand, verändert aber noch nichts auf GitHub und löst keine
Synchronisation aus. Erst der Push auf einen Stufenbranch veröffentlicht den
Stand und startet – bei Entwicklung oder Abnahme – den zugehörigen Workflow.

Git und GitHub sind dabei nicht dasselbe: **Git** ist die
Versionsverwaltung. **GitHub** stellt das gemeinsame Repository, die
Oberfläche, Berechtigungen und die GitHub-Actions-Automation bereit.

### Feature-Branch einfach erklärt

Ein **Feature-Branch** ist ein eigener Arbeitsbereich für eine einzelne
Änderung. Dort kann ein noch unfertiger Stand gespeichert und bei Bedarf nach
GitHub gepusht werden, ohne bereits das M/Text-Entwicklungssystem zu
aktualisieren. Das ist besonders nützlich, wenn eine Änderung mehrere Tage
dauert, mehrere Personen daran arbeiten oder der Zwischenstand zunächst
geprüft werden soll.

Für eine kleine, fertig vorbereitete Änderung ist kein Feature-Branch nötig.
Sie kann direkt auf dem passenden Entwicklungsbranch bearbeitet und gepusht
werden. Ist die Arbeit auf einem Feature-Branch abgeschlossen, wird der
gewünschte Commit nach `<Releaselinie>/Entwicklung` übernommen. Erst der Push
dieses Entwicklungsbranches startet die M/Text-Synchronisation. Der
Feature-Branch selbst bezeichnet keine Lieferstufe und löst keine Automation
aus.

### Commit und SHA einfach erklärt

Ein **Commit** ist ein gespeicherter Stand im Git-Repository. Jeder Commit hat
eine eindeutige technische Kennung, den **Commit-SHA**. Sie besteht in diesem
Repository aus 40 Zeichen, zum Beispiel
`8f3a1c2d4e5f67890123456789abcdef01234567`. Meist genügt in der Oberfläche
eine verkürzte Darstellung; für einen manuellen Wiederanlauf verlangt die
Automation jedoch die vollständige Kennung.

Ein Branchname wie `R261/Entwicklung` bezeichnet dagegen keinen dauerhaft
festen Stand. Er zeigt auf den jeweils neuesten Commit des Branches und bewegt
sich mit jedem weiteren Push. Wenn in dieser Anleitung vom „exakten Commit“
die Rede ist, bedeutet das deshalb: Verarbeitet wird genau der Stand, der den
Lauf ausgelöst hat - nicht ein möglicherweise inzwischen neuerer Stand auf
demselben Branch. Bei einem normalen Push übernimmt GitHub diese Kennung
automatisch; Benutzer müssen sie nur bei einer manuellen Wiederholung angeben.

In SVN wird ein Stand üblicherweise über eine fortlaufende Revisionsnummer wie
`r12345` bezeichnet. Git ist nicht an ein zentrales, fortlaufendes
Nummernsystem gebunden und verwendet daher die Commit-SHA als eindeutige
Kennung. Der Zweck ist vergleichbar: Beide Angaben machen einen konkreten
Quellstand nachvollziehbar. Die Git-Kennung ist lediglich technisch anders
aufgebaut und weniger leicht zu merken.

Daneben kommen zwei ähnlich aussehende, aber anders verwendete Kennungen vor:

- Der Commit-SHA von `mtext-actions` legt für Administratoren fest, welche
  freigegebene Version der zentralen Automation verwendet wird.
- Eine SHA-256-Prüfsumme bestätigt, dass eine erzeugte Paketdatei nach dem Bau
  nicht verändert wurde. Sie bezeichnet keinen Git-Commit.

## 3. Änderung nach Entwicklung bringen

1. Den aktuellen `<Releaselinie>/Entwicklung` auschecken; für länger laufende,
   gemeinsam bearbeitete oder zunächst zu prüfende Änderungen optional einen
   Feature-Branch erstellen, zum Beispiel
   `feature/R270/12345-BT0303-viele-Anpassungen-am-Text`.
2. Fachlich vorgesehene Änderungen an den Brief-Ressourcen durchführen.
3. Änderungen committen.
4. Den Commit direkt nach `<Releaselinie>/Entwicklung` pushen.
5. Im GitHub unter **Actions → Sync M/Text resources** den durch den Push
   ausgelösten Lauf kontrollieren.

Der Push startet die Synchronisation des exakten Commits mit dem entsprechenden
Tonic Server (`en01e` für `Entwicklung` und `en01a` für Abnahme). Ein erfolgreicher
Lauf endet mit `ADAPTER_ACCEPTED`.

## 4. Nach Abnahme promoten

1. Den in Entwicklung erfolgreich geprüften Commit ermitteln.
2. Genau diesen Commit direkt nach `<Releaselinie>/Abnahme` pushen.
3. Unter **Actions → Sync M/Text resources** den Abnahmelauf kontrollieren.
4. Die fachliche Abnahme außerhalb des Workflows nach dem vereinbarten
   Verfahren dokumentieren.

Der Push nach Abnahme verteilt den vollständigen konfigurierten Projektstand
des vom Anwender fachlich freigegebenen Commits. Er baut noch kein
Mainframe-Paket. Die Auswahl dieses Commits ist eine fachliche
Verantwortlichkeit. Der Workflow erzwingt keine Gleichheit mit einem früheren
Entwicklungspush.

## 5. Ausgewählte Änderungen bereitstellen

1. Den aktuellen `<Releaselinie>/Bereitstellung` auschecken.
2. Ausschließlich die fachlich freigegebenen Commits aus Abnahme per
   `git cherry-pick` übernehmen. Konflikte fachlich prüfen; keine ungeprüften
   Konfliktauflösungen übernehmen.
3. Den zusammengestellten Stand direkt nach
   `<Releaselinie>/Bereitstellung` pushen.
4. Den Ziel-Commit notieren. Der Push startet weder Paketbau noch
   Mainframe-Übergabe.

Die Auswahl der Commits ist eine fachliche Verantwortung. Die verbindliche
technische Prüfung erfolgt erst, wenn der Release-Tag gesetzt wird.

## 6. FULL oder DELTA Lieferung auslösen

Vor dem Taggen müssen Releaselinie, Mandant, gewünschter Lieferungstyp und der
exakte Commit auf `<Releaselinie>/Bereitstellung` fachlich bestätigt sein.

- `Rnnn.100` erzeugt ein FULL mit dem vollständigen Stand jedes Projekts der
  Delivery-Allowlist.
- Jede andere gültige dreistellige Endung, zum Beispiel `R261.108`, erzeugt
  ein kumulatives DELTA von `R261.100` bis zum Zieltag.
- Ein DELTA setzt voraus, dass der `.100`-Tag derselben Linie vorhanden und
  erreichbar ist.

Zum Auslösen einen einfachen Git-Tag auf dem bestätigten Bereitstellungscommit
setzen und pushen, zum Beispiel:

```bash
git fetch origin R261/Bereitstellung --tags
git tag R261.108 <vollständiger-commit-sha>
git push origin refs/tags/R261.108
```

Danach unter **Actions → Build and publish release** prüfen:

1. `Build FULL or DELTA artifact` validiert Konfiguration, Tag und
   Branchzuordnung, baut die Pakete und erzeugt `manifest.json` mit
   SHA-256-Prüfsummen.
2. Das Artefakt heißt `<Repository>-<Release-Tag>` und wird standardmäßig
   30 Tage aufbewahrt.
3. `Verify and hand over artifact to Mainframe` wartet im Environment
   `Bereitstellung` auf die eingerichtete manuelle Freigabe.
4. Nach der Freigabe werden Manifest und Prüfsummen erneut geprüft, JCL wird
   aus dem versionierten Template gerendert und Paket plus JCL werden per
   FTP/JES übergeben.

`MAINFRAME_SUBMITTED` bedeutet ausschließlich, dass die unmittelbare
FTP-/JES-Übergabe akzeptiert wurde. Der fachliche Abschluss des Mainframe-Jobs
wird in Ausbaustufe 1 nicht abgefragt.

## 7. Einen Lauf kontrolliert wiederholen

### M/Text-Synchronisation wiederholen

Unter **Actions → Sync M/Text resources → Run workflow** angeben:

- `commit_sha`: vollständiger 40-stelliger SHA des bereits geprüften Commits;
- `source_branch`: der passende Branch `Rxxx/Entwicklung` oder
  `Rxxx/Abnahme`.

Die Automation weist den Lauf zurück, wenn der Commit nicht aus dem gewählten
Branch erreichbar ist. Das Zielsystem kann nicht frei eingegeben werden; es
wird aus Branch und zentraler Konfiguration abgeleitet. Eine allgemeine
Erklärung zu Commits und SHAs steht unter „Begriffe und Namensregeln“.

### Release-Lauf wiederholen

Unter **Actions → Build and publish release → Run workflow** den bereits
existierenden `release_tag` angeben. Keinen neuen Tag nur für einen technischen
Wiederanlauf erzeugen. Die Automation löst den Tag erneut auf und prüft seine
Erreichbarkeit aus `<Releaselinie>/Bereitstellung`.

Vor jedem Wiederanlauf klären, ob das Zielsystem die vorherige Übergabe bereits
angenommen hat. GitHub Actions kennt ohne Status-Polling keinen nachgelagerten
fachlichen Endstatus.

## 8. Status und Fehlerbilder verstehen

| Status oder sichtbares Symptom | Bedeutung | Nächste Prüfung |
|---|---|---|
| Workflow kann zentrale Datei am Null-SHA nicht laden | Technischer Platzhalter ist noch eingetragen | Vorgesehenen vollständigen Commit-SHA von `mtext-actions` in beiden Workflows eintragen |
| `VALIDATION_FAILED` | Input, Konfiguration, Schema, Branchrichtung oder JCL ungültig | Erste Fehlermeldung lesen; Branch-/Tagformat und Konfiguration prüfen |
| `SOURCE_FAILED` | Commit oder Tag/Basisreferenz nicht auflösbar | SHA, Tag, `.100`-Basis und Branch-Erreichbarkeit prüfen |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder Manifest konnte nicht sicher gebaut werden | Fehlende Projektpfade, Symlinks, leeres/benutztes Ausgabeverzeichnis prüfen |
| `RESOURCE_TRANSFER_FAILED` | Veröffentlichung nach serverSync/NFS fehlgeschlagen | Mount, Rechte, Zielpfad und Runnerzugriff prüfen; Adapter wurde nicht aufgerufen |
| `ADAPTER_FAILED` | Transportfehler oder Nicht-2xx vom Adapter | HTTP-Status und bereinigten Response-Body im Log prüfen |
| `ADAPTER_ACCEPTED` | Unmittelbare Adapterannahme erfolgreich | Kein Beleg für einen nachgelagerten M/Text-Endstatus |
| `ARTIFACT_READY` | Releaseartefakt lokal gebaut und geprüft | Publish-Freigabe beziehungsweise nächsten Job prüfen |
| `MAINFRAME_TRANSFER_FAILED` | FTP-Upload oder JES-Submit unmittelbar fehlgeschlagen | Credentials, Dataset, JES-Ziel, Netzwerk und FTP-Antwort prüfen |
| `MAINFRAME_SUBMITTED` | Unmittelbare FTP-/JES-Übergabe akzeptiert | Weiteren Status im Betriebsverfahren verfolgen |

Logs dürfen keine Credentials enthalten. Zugangsdaten niemals in Pull
Requests, Konfigurationsdateien, Workflow-Inputs oder Support-Tickets kopieren.
