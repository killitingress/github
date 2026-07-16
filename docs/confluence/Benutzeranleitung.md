# Benutzeranleitung für die M/Text-Lieferung mit GitHub Actions

**Bezug:** [Zielbild](./Zielbild_GitHub_Actions_Git.md),
[Soll-Grafik](../../Architektur_Soll_GitHub_Actions_Git.drawio)

## 1. Zweck

Die Lösung führt M/Text-Ressourcen eines Mandanten über die drei Stufen
`Entwicklung`, `Abnahme` und `Bereitstellung`. Pushes nach Entwicklung und
Abnahme lösen die jeweilige M/Text-Synchronisation aus. Der Push nach
Bereitstellung liefert noch nichts aus; erst ein Release-Tag startet eine
FULL- oder DELTA-Lieferung mit anschließender Mainframe-Übergabe an IZE9.

### Hinweis zur Einführung

Voraussichtlich ab November/Dezember 2026 steht die neue GitHub-Umgebung auf
Basis eines Abzugs der SVN-Repositories zunächst für Tests zur Verfügung. In
diesem Parallelbetrieb bleibt der bisherige Jenkins-/SVN-Prozess produktiv. Die
Produktivsetzung ist ab Januar 2027 als harter Cutover geplant. Ab dann ist
GitHub für den M/Text-Tonic-Lieferprozess das führende System.

### Abgrenzung

Zu Themen wie technischer Einrichtung, Aktivierung und Cutover gibt es
[Nächste Schritte](./Naechste_Schritte.md).

Die konkrete Benutzerverwaltung erfolgt je Mandanten-Repository. Für
`Bereitstellung` und das Setzen von Release-Tags benennt jeder Mandant einen
kleinen Kreis von Release-Verantwortlichen. Andere Text-Entwickler können
diese Schritte nur ausführen, wenn sie diesem Kreis angehören.

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

### M/Text Workbench und GitHub

Die tägliche Bearbeitung findet in der **M/Text Workbench** statt. Ihr
integrierter Git-Client wird verwendet, um geänderte Briefressourcen zu prüfen,
zu committen und auf den vorgesehenen Entwicklungsbranch zu pushen. Für diese
normale Ressourcenarbeit benötigen Text-Entwickler weder die Git-Kommandozeile
noch die erweiterten Verwaltungsfunktionen von GitHub. Einen direkten Zugriff
auf das zentrale Automatisierungs-Repository `mtext-actions` benötigen und
erhalten sie nicht.

Für die gezielte Weitergabe einzelner Änderungen zwischen den Stufen reicht
der integrierte Git-Client der M/Text Workbench nach heutigem Kenntnisstand
nicht aus. Die dafür berechtigten Text-Entwickler erhalten zusätzlich einen
geeigneten Git-Client. Welches Produkt eingesetzt wird und wie Installation,
Authentifizierung und Bedienung erfolgen, wird vor dem Pilotbetrieb festgelegt
und praktisch abgenommen.

**GitHub im Browser** wird für die darüber hinausgehenden Prozessschritte
verwendet. Dazu gehören insbesondere:

- ausgelöste Workflow-Läufe und ihre Protokolle kontrollieren;
- fehlgeschlagene oder ausdrücklich manuell gestartete Läufe wiederholen;
- Freigaben im Environment `Bereitstellung` erteilen;
- durch das Mandanten-Release-Team einen Release-Tag anlegen;
- Branch-, Tag- und Berechtigungsregeln administrieren.

Die Weitergabe ausgewählter Stände nach Abnahme und Bereitstellung ist keine
alltägliche Ressourcenbearbeitung. Der dafür verwendete Bedienweg im
zusätzlichen Git-Client und die berechtigten Verantwortlichen werden vor dem
Pilotbetrieb verbindlich festgelegt.

### Feature-Branch einfach erklärt

Ein **Feature-Branch** ist ein eigener Arbeitsbereich für eine einzelne
Änderung. Sofern der integrierte Git-Client der M/Text Workbench diesen Ablauf
unterstützt und er für den Mandanten freigegeben ist, kann dort ein noch
unfertiger Stand gespeichert und nach GitHub gepusht werden, ohne bereits das
M/Text-Entwicklungssystem zu aktualisieren. Das ist besonders nützlich, wenn
eine Änderung mehrere Tage dauert, mehrere Personen daran arbeiten oder der
Zwischenstand zunächst geprüft werden soll.

Für eine kleine, fertig vorbereitete Änderung ist kein Feature-Branch nötig.
Sie kann direkt auf dem passenden Entwicklungsbranch bearbeitet und gepusht
werden. Ist die Arbeit auf einem Feature-Branch abgeschlossen, wird der
gewünschte Commit nach `<Releaselinie>/Entwicklung` übernommen. Erst der Push
dieses Entwicklungsbranches startet die M/Text-Synchronisation. Der
Feature-Branch selbst bezeichnet keine Lieferstufe und löst weder eine
M/Text-Synchronisation noch einen Release aus. Nur wenn
`config/mandant.json` geändert wird, läuft dort der nebenwirkungsfreie
Config-Check.

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
Lauf ausgelöst hat – nicht ein möglicherweise inzwischen neuerer Stand auf
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
  freigegebene Version der zentralen Automation verwendet wird. Anwender
  müssen diesen Wert weder ermitteln noch ändern.
- Eine SHA-256-Prüfsumme bestätigt, dass eine erzeugte Paketdatei nach dem Bau
  nicht verändert wurde. Sie bezeichnet keinen Git-Commit.

### Cherry-Pick einfach erklärt

Ein **Cherry-Pick** übernimmt die Änderung eines gezielt ausgewählten Commits
auf einen anderen Branch. Anders als bei der Zusammenführung eines ganzen
Branches werden dadurch nicht automatisch alle dort vorhandenen Änderungen
weitergegeben. Das ist für den vorgesehenen Stufenprozess wichtig: Nach
Abnahme und Bereitstellung sollen nur fachlich ausgewählte Änderungen
übernommen werden.

Der Cherry-Pick erzeugt auf dem Zielbranch einen **neuen Commit mit einer
neuen SHA**. Es wird also dieselbe Änderung weitergegeben, nicht derselbe
Commit. Damit die Verbindung trotzdem eindeutig nachvollziehbar bleibt, muss
die vollständige SHA des Quell-Commits nach der für den zusätzlichen
Git-Client festgelegten Konvention in der Nachricht des neuen Ziel-Commits
dokumentiert werden.

Der werkzeugunabhängige Ablauf ist:

1. Den Zielbranch auschecken und auf den aktuellen GitHub-Stand bringen.
2. Den freigegebenen Quell-Commit anhand seiner SHA auswählen.
3. Den Commit per Cherry-Pick auf den Zielbranch übernehmen.
4. Ergebnis, geänderte Dateien und dokumentierte Quell-SHA vor dem Push
   kontrollieren.
5. Den Zielbranch pushen und den dadurch ausgelösten Workflow prüfen.

Bei mehreren voneinander abhängigen Commits werden alle freigegebenen Commits
in ihrer ursprünglichen Reihenfolge übernommen. Meldet der Git-Client einen
Konflikt, wird nicht einfach weitergepusht: Die Abweichung muss fachlich
geklärt, die Konfliktauflösung geprüft und erst danach committed und gepusht
werden. Force-Pushes bleiben verboten.

GitHub bietet in der Weboberfläche keinen allgemeinen direkten Cherry-Pick
zwischen beliebigen Branches an. Die konkreten Schaltflächen können deshalb
erst ergänzt werden, nachdem der zusätzliche Git-Client für den Pilotbetrieb
ausgewählt und abgenommen wurde. Bis dahin beschreibt diese Anleitung den
verbindlichen fachlichen Ablauf, aber noch keine produktspezifische
Klickanleitung.

### Was ist `config/mandant.json`?

Die Datei `config/mandant.json` gehört wie die M/Text-Ressourcen zum
versionierten Lieferstand des Mandanten. Sie beantwortet drei Fragen:

1. Zu welchem Mandanten und Repository gehört der Stand?
2. Welche Projekte werden regulär synchronisiert und als Releasepakete gebaut?
3. Welche mandantenspezifischen technischen Zuordnungen gelten für die
   nachgelagerte Übergabe?

Die Datei enthält keine Passwörter, Ziel-URLs oder frei wählbaren
Release-Einstellungen. Diese Werte werden zentral oder in geschützten
GitHub-Einstellungen verwaltet.

#### Mandantenidentität

```json
"code": "FI",
"repository": "mtext-fi"
```

`code` ist das kurze Mandantenkennzeichen und bildet unter anderem den Anfang
der historischen Lieferdateinamen. `repository` muss exakt dem Namen des
auslösenden GitHub-Repositories entsprechen. Dadurch kann eine Konfiguration nicht
versehentlich in einem anderen Mandanten-Repository verwendet werden. Die
zusätzliche Angabe `"schema_version": 1` am Anfang der vollständigen Datei
bezeichnet nur die technische Formatversion.

#### Reguläre Lieferprojekte unter `projects`

Jeder Eintrag unter `projects` bezeichnet ein reguläres Lieferprojekt. Solche
Projekte werden bei jedem passenden Entwicklung- oder Abnahmelauf
synchronisiert und bei einem Release als FULL- oder DELTA-Paket gebaut. Das
folgende Beispiel zeigt einen einzelnen Eintrag aus der FI-Konfiguration:

```json
"projects": [
  {
    "name": "LOMS_Basis",
    "source_path": "LOMS_Basis"
  }
]
```

| Feld | Bedeutung im Beispiel |
|---|---|
| `name` | Fachlicher Projektname und Name des Zielverzeichnisses unter `serverSync`. Er erscheint außerdem im Manifest und in der Informationsdatei. |
| `source_path` | Verzeichnis im Git-Repository, aus dem die Ressourcen gelesen werden. |

Die technischen Namen der daraus erzeugten Lieferdateien sind historisch
festgelegt und werden zentral aus dem Projektnamen abgeleitet. Sie werden
nicht von Text-Entwicklern in `mandant.json` eingetragen oder geändert.

Ein Verzeichnis wird nicht allein deshalb synchronisiert oder ausgeliefert,
weil es im Repository vorhanden ist. Es muss als reguläres Projekt unter
`projects` stehen. Für linien- oder stufenspezifische Zusatzprojekte gibt es
keine Sonderkonfiguration.

#### Mandantenspezifische Werte für die technische Übergabe

Gemeint sind insbesondere Subsystem, Assignment und der fachliche Stage-Code,
den die bestehende JCL historisch als `LEVEL` bezeichnet.
Diese Werte sind für den Mandanten relevant, werden in `mandant.json`
verständlich beschrieben und können bei einer tatsächlichen Änderung der
Zuordnung angepasst werden. Das FI-Beispiel lautet:

```json
"subsystem": "LOMS",
"handover_profiles": {
  "FKT": {
    "assignment": "LOMS000066",
    "stage": "FKTE"
  },
  "JUR": {
    "assignment": "LOMS000067",
    "stage": "JURP"
  }
}
```

| Feld | Bedeutung | Verwendung in der bestehenden JCL |
|---|---|---|
| `subsystem` | Subsystem des Mandanten, für FI beispielsweise `LOMS` | wird als `SUBSYS` eingesetzt und dort für `APPLID` und `SUBAPPL` verwendet |
| `assignment` | Assignment des Mandanten für das jeweilige Übergabeprofil | wird als `ASSIGNMENT` eingesetzt und dort für `PROJNO` verwendet |
| `stage` | Tatsächlicher fachlicher Stage-Code, beispielsweise `FKTE` oder `JURP` | wird in den historisch `LEVEL` genannten Platzhalter eingesetzt und dort unter anderem für `CLVL` und `SLVL` verwendet |

Die Namen `FKT` und `JUR` unter `handover_profiles` bezeichnen die beiden aus
dem bisherigen Verfahren übernommenen Übergabeprofile. Sie sind nicht selbst
die Stage-Codes. Welche Releaselinie welches Profil verwendet, wird zentral
festgelegt: derzeit `R260 → JUR`, `R261 → FKT` und `R270 → JUR`. Der Mandant
pflegt innerhalb beider Profile seine jeweils gültige Kombination aus
Assignment und Stage-Code.

Als Stage-Codes akzeptiert die Konfiguration derzeit ausschließlich `FKTE`,
`FKTF`, `JURJ`, `JURP`, `SVTS` und `VPTV`. Der getrennte Wert für Test oder
Produktion gehört nicht zur Mandantenkonfiguration; er wird zentral verwaltet
und darf ausschließlich `T` oder `P` sein. Zugangsdaten gehören ebenfalls
nicht in `mandant.json`.

Eine Änderung an `subsystem`, `assignment` oder `stage` verändert die spätere
technische Übergabe. Sie ist deshalb keine gewöhnliche Änderung an einer
Briefressource, aber ausdrücklich zulässig, wenn sich die fachlich bestätigte
Mandantenzuordnung ändert. Die Änderung erfolgt versioniert durch den dafür
berechtigten Verantwortlichenkreis und wird mit den Mandanten- und
Betriebsverantwortlichen abgestimmt. Normale Workbench-Pushes dürfen
`config/mandant.json` nicht verändern; GitHub schützt die Datei mit einer
eigenen Pfadregel.

Ein Push mit einer Änderung an `config/mandant.json` startet automatisch
**Validate mandant configuration**. Dieser Check prüft die Datei ohne Zugriff
auf M/Text oder den Mainframe und liefert frühzeitig eine verständliche
Fehlermeldung. Er erkennt beispielsweise unbekannte Felder, ungültige Formate,
ein unpassendes Repository, doppelte Projektnamen oder nicht freigegebene
Projektzuordnungen.
`CONFIG_VALIDATED` bestätigt jedoch weder, dass alle genannten Verzeichnisse
vorhanden sind, noch dass die technischen Betriebswerte fachlich richtig
gewählt wurden. Der Status ersetzt deshalb keine fachliche Freigabe und ist
kein technisches Gate. Synchronisation und Release validieren die verwendete
Konfiguration auf ihrem tatsächlichen Ausführungspfad erneut.

## 3. Änderung nach Entwicklung bringen

1. In der M/Text Workbench prüfen, dass der aktuelle
   `<Releaselinie>/Entwicklung` geöffnet ist. Für länger laufende oder
   gemeinsam bearbeitete Änderungen kann – nach Freigabe dieses Bedienwegs –
   ein Feature-Branch verwendet werden.
2. Die fachlich vorgesehenen Änderungen an den Briefressourcen durchführen.
3. Im integrierten Git-Client nur die vorgesehenen Änderungen für den Commit
   auswählen und eine aussagekräftige Commit-Nachricht eintragen.
4. Commit und Push auf den vorgesehenen Entwicklungsbranch ausführen.
5. In GitHub unter **Actions → Sync M/Text resources** den durch den Push
   ausgelösten Lauf kontrollieren.

Der Push startet die Synchronisation des exakten Commits mit dem aus
Releaselinie und Stufe zentral ermittelten M/Text-Ziel. Für `R261` sind dies
beispielsweise `en01e` in Entwicklung und `en01a` in Abnahme. Ein erfolgreicher
Lauf endet mit `ADAPTER_ACCEPTED`.

## 4. Stand zur Abnahme weitergeben

1. Den in Entwicklung erfolgreich geprüften Commit ermitteln.
2. Im zusätzlichen Git-Client den aktuellen Zielbranch
   `<Releaselinie>/Abnahme` auschecken und aktualisieren.
3. Die freigegebene Änderung per Cherry-Pick aus
   `<Releaselinie>/Entwicklung` übernehmen.
4. Den neu entstandenen Commit und seine Änderungen kontrollieren und den
   Abnahmebranch ohne Force-Push pushen. Die Commit-Nachricht muss die
   vollständige SHA des Entwicklungs-Commits enthalten.
5. Unter **Actions → Sync M/Text resources** den Abnahmelauf kontrollieren.
6. Die fachliche Abnahme außerhalb des Workflows nach dem vereinbarten
   Verfahren dokumentieren.

Der Push nach Abnahme verteilt den vollständigen konfigurierten Projektstand
des durch den Cherry-Pick neu entstandenen Commits. Er baut noch kein
Mainframe-Paket. Die Auswahl der übernommenen Änderung ist eine fachliche
Verantwortlichkeit. Der Workflow prüft nicht automatisch, aus welchem
Entwicklungs-Commit sie hervorgegangen ist.

## 5. Ausgewählte Änderungen bereitstellen

1. In GitHub die fachlich freigegebenen Commits aus Abnahme bestimmen und ihre
   Reihenfolge festhalten.
2. Im zusätzlichen Git-Client den aktuellen Zielbranch
   `<Releaselinie>/Bereitstellung` auschecken und aktualisieren.
3. Das Mandanten-Release-Team übernimmt ausschließlich diese Änderungen per
   Cherry-Pick aus `<Releaselinie>/Abnahme`. Mehrere abhängige Commits werden
   in ihrer ursprünglichen Reihenfolge übernommen; Konflikte müssen fachlich
   geklärt werden.
4. Den resultierenden Stand und die neu entstandenen Commits kontrollieren und
   den Bereitstellungsbranch ohne Force-Push pushen. Jeder neue Commit muss
   die vollständige SHA seines Quell-Commits aus Abnahme enthalten.
5. Den exakten Ziel-Commit in GitHub prüfen und notieren. Der Push startet
   weder Paketbau noch Mainframe-Übergabe.

Die Auswahl der Commits ist eine fachliche Verantwortung. Die verbindliche
Releaseprüfung erfolgt erst, wenn der Release-Tag gesetzt wird. Pushen darf hier
nur das für den jeweiligen Mandanten benannte Release-Team. In der Pilotphase
wird geprüft, ob dieser direkte Ablauf auch bei parallelen Bereitstellungen
ausreichend übersichtlich bleibt.

## 6. FULL- oder DELTA-Lieferung auslösen

Vor dem Taggen müssen Releaselinie, Mandant, gewünschter Lieferungstyp und der
exakte Commit auf `<Releaselinie>/Bereitstellung` fachlich bestätigt sein.

- `Rnnn.100` erzeugt ein FULL mit dem vollständigen Stand jedes Projekts der
  Projekt-Allowlist.
- Jede andere gültige dreistellige Endung, zum Beispiel `R261.108`, erzeugt
  ein kumulatives DELTA von `R261.100` bis zum Zieltag.
- Ein DELTA setzt voraus, dass der `.100`-Tag derselben Linie vorhanden und
  erreichbar ist.
- Nur das benannte Release-Team darf einen neuen Release-Tag setzen. Ein
  vorhandener Release-Tag ist die unveränderliche Release-Identität und darf
  weder verschoben noch gelöscht werden.

Der Release-Tag wird vom Mandanten-Release-Team in GitHub angelegt:

1. Im Mandanten-Repository **Releases → Draft a new release** öffnen.
2. Unter **Choose a tag** den neuen Namen, beispielsweise `R261.108`, eingeben
   und **Create new tag** wählen.
3. Als Ziel `R261/Bereitstellung` auswählen und nochmals prüfen, dass dessen
   aktueller Commit der bestätigte Release-Stand ist.
4. Den Release veröffentlichen. Dadurch wird der Tag angelegt und der
   Release-Workflow gestartet.

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

Ein noch verfügbarer Workflow-Lauf kann in GitHub über **Actions**, den
betroffenen Lauf und **Re-run jobs** mit demselben Commit und derselben
Git-Referenz wiederholt werden. Die folgenden manuellen Starts sind für Fälle
gedacht, in denen ein neuer kontrollierter Lauf mit ausdrücklich angegebenem
Commit oder Tag erforderlich ist.

### M/Text-Synchronisation wiederholen

Unter **Actions → Sync M/Text resources → Run workflow** angeben:

- `commit_sha`: vollständiger 40-stelliger SHA des bereits geprüften Commits;
- `source_branch`: der passende Branch `Rnnn/Entwicklung` oder
  `Rnnn/Abnahme`.

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
| Workflow kann zentrale Datei am Null-SHA nicht laden | Technischer Platzhalter ist noch eingetragen | Zentrale Automatisierungsverantwortliche informieren; Anwender ändern den SHA nicht selbst |
| `CONFIG_VALIDATED` | Mandanten- und Deploymentkonfiguration sind technisch konsistent | Fachliche Abstimmung fortsetzen; der Status ist keine automatische Freigabe für die nächste Stufe |
| `VALIDATION_FAILED` | Input, Konfiguration, Schema, Branchrichtung oder JCL ungültig | Erste Fehlermeldung lesen; Branch-/Tagformat und Konfiguration prüfen |
| `SOURCE_FAILED` | Commit oder Tag/Basisreferenz nicht auflösbar | SHA, Tag, `.100`-Basis und Branch-Erreichbarkeit prüfen |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder Manifest konnte nicht sicher gebaut werden | Fehlende Projektpfade, Symlinks, leeres/benutztes Ausgabeverzeichnis prüfen |
| `RESOURCE_TRANSFER_FAILED` | Veröffentlichung nach serverSync/NFS fehlgeschlagen | Mount, Rechte, Zielpfad und Runnerzugriff prüfen; Adapter wurde nicht aufgerufen |
| `ADAPTER_FAILED` | Transportfehler oder Nicht-2xx vom Adapter | HTTP-Status und bereinigten Response-Body im Log prüfen |
| `ADAPTER_ACCEPTED` | Unmittelbare Adapterannahme erfolgreich | Kein Beleg für einen nachgelagerten M/Text-Endstatus |
| `ARTIFACT_READY` | Releaseartefakt lokal gebaut und geprüft | Publish-Freigabe beziehungsweise nächsten Job prüfen |
| `MAINFRAME_TRANSFER_FAILED` | FTP-Upload oder JES-Submit unmittelbar fehlgeschlagen | Credentials, Dataset, JES-Ziel, Netzwerk und FTP-Antwort prüfen |
| `MAINFRAME_SUBMITTED` | Unmittelbare FTP-/JES-Übergabe akzeptiert | Weiteren Status im Betriebsverfahren verfolgen |

Logs dürfen keine Credentials enthalten. Zugangsdaten niemals in
Konfigurationsdateien, Workflow-Inputs, GitHub-Kommentare oder Support-Tickets
kopieren.
