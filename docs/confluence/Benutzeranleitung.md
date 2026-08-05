# Benutzeranleitung für die M/Text-Lieferung mit GitHub Actions

## 1. Zweck

Diese Anleitung begleitet Text-Entwickler und Administratoren durch den
vollständigen Bedienablauf. Alle Angaben, die sie für ihre jeweilige Aufgabe
benötigen, stehen in diesem Dokument.

Die Lösung führt M/Text-Ressourcen über die drei Stages `Entwicklung`,
`Abnahme` und `Bereitstellung`. Pushes nach Entwicklung und Abnahme lösen die
Synchronisation mit dem jeweiligen M/Text-Server aus. Ein Push nach
Bereitstellung liefert noch nichts aus. Erst ein Release-Tag startet eine
FULL- oder DELTA-Lieferung mit anschließender Mainframe-Übergabe an die IZE9.

### Abgrenzung

Die technische Ersteinrichtung und der Cutover gehören nicht zur normalen
Bedienung. Für die dafür verantwortlichen Teams sind sie zusätzlich in
[Nächste Schritte](./Naechste_Schritte.md) beschrieben.

Die konkrete Benutzerverwaltung erfolgt je Mandanten-Repository. Für die
`Bereitstellung` benennt jeder Mandant ein Mandanten-Release-Team mit wenigen
berechtigten Personen.

## 2. Begriffe und Namensregeln

Eine **Stage** ist in dieser Anleitung ein Abschnitt des Freigabe- und
Lieferprozesses – bei uns wie gewohnt `Entwicklung`, `Abnahme` und
`Bereitstellung`. Jede Releaselinie besitzt einen eigenen Branch für jede
dieser Stages.

| Element | Verbindliches Format | Beispiel |
|---|---|---|
| Branch einer Stage | `Rnnn/Entwicklung`, `Rnnn/Abnahme`, `Rnnn/Bereitstellung` | `R270/Entwicklung` |
| Optionaler Feature-Branch | `feature/Rnnn/<Issue>-<kurzname>` | `feature/R270/0711-komplizierte-Arbeiten` |
| Release-Tag | `Rnnn.nnn` | `R261.100`, `R261.108` |

Die Groß- und Kleinschreibung der Stage-Namen ist verbindlich. Die zentrale
Konfiguration enthält derzeit die Releaselinien `R260`, `R261` und `R270`.

## 3. Grundlagen zu Git

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

Für die tägliche Arbeit bedeutet das unter anderem: **Committen und Pushen sind in
Git zwei getrennte Schritte.** Ein lokaler Commit sichert den eigenen
Arbeitsstand, verändert aber noch nichts auf GitHub und löst keine
Synchronisation aus. Erst der Push auf den Branch einer Stage veröffentlicht
den Stand und startet – bei Entwicklung oder Abnahme – den zugehörigen
Workflow.

Git und GitHub sind dabei nicht dasselbe: **Git** ist die
Versionsverwaltung. **GitHub** stellt das gemeinsame Repository, die
Oberfläche, Berechtigungen und die GitHub-Actions-Automation bereit.

### Commit und SHA einfach erklärt

Ein **Commit** ist ein gespeicherter Stand im Git-Repository. Jeder Commit hat
eine eindeutige technische Kennung, den **Commit-SHA**. Sie besteht aus 40
Zeichen, zum Beispiel
`8f3a1c2d4e5f67890123456789abcdef01234567`. Meist genügt in der Oberfläche
eine verkürzte Darstellung. Für einen manuellen Wiederanlauf verlangt die
Automation jedoch die vollständige Kennung.

Ein Branch-Name wie `R261/Entwicklung` bezeichnet dagegen keinen dauerhaft
festen Stand. Er zeigt auf den jeweils neuesten Commit des Branches und bewegt
sich mit jedem weiteren Push.

### SVN-Pfad und Git-Branch unterscheiden

Im bisherigen SVN-Aufbau sind Stage und Releaselinie Bestandteile des Pfads.
Bei der Migration werden diese Informationen auf Git-Branches abgebildet:

```text
SVN: branches/Entwicklung/R260.100_MText/<Projekt>
Git: Branch R260/Entwicklung, darin Pfad <Projekt>
```

Releaselinie und Stage stehen im Branch-Namen. Im Arbeitsbereich beginnt der
Pfad direkt mit dem Projektverzeichnis.

### Lokales Repository vor der Arbeit aktualisieren

Vor einer Bearbeitung, einem Cherry-Pick oder dem Anlegen eines Release-Tags
muss der lokale Branch auf dem aktuellen GitHub-Stand sein. In der M/Text
Workbench wird dafür das Eclipse-Plugin EGit verwendet.

Git unterscheidet das Abrufen neuer GitHub-Stände vom Aktualisieren des
ausgecheckten Branches:

| Git-Vorgang | Wirkung auf den lokalen Stand |
|---|---|
| `fetch` | Lädt neue Commits und Branchstände von GitHub, verändert aber weder den ausgecheckten lokalen Branch noch dessen Dateien |
| `pull` | Ruft den GitHub-Stand ab und aktualisiert den ausgecheckten Branch |

Welche EGit-Bedienfunktion diese Vorgänge in der M/Text Workbench und im
zusätzlichen Git-Client ausführt und wie sie dort heißt, wird erst bei der
praktischen Abnahme festgelegt. Die freigegebene Funktion muss den lokalen
Branch ohne automatischen Merge auf den aktuellen GitHub-Stand bringen.

Der Standardablauf in der Workbench ist:

1. Das richtige Mandanten-Repository und den vorgesehenen Branch auswählen.
2. Prüfen, dass keine noch nicht abgeschlossene Git-Operation und keine
   ungesicherte lokale Bearbeitung vorliegt.
3. Den lokalen Branch mit der dafür abgenommenen Bedienfunktion auf den
   aktuellen GitHub-Stand bringen. Ein reiner `fetch` genügt dafür noch nicht.
4. Kontrollieren, dass lokaler Branch und GitHub-Branch anschließend auf
   denselben Commit zeigen.
5. Erst danach mit Bearbeitung, Cherry-Pick oder Tag-Erzeugung beginnen.

Lehnt die Aktualisierung wegen eigener lokaler Commits ab, wird weder ein Merge
noch ein Force-Push erzwungen. Dann gilt der Abschnitt
[Push-Ablehnung mit Rebase statt Merge beheben](#push-ablehnung-mit-rebase-statt-merge-beheben).

### Feature-Branch einfach erklärt

Ein **Feature-Branch** ist ein eigener Arbeitsbereich für eine einzelne
Änderung. Damit kann ein noch unfertiger Stand gespeichert und nach GitHub
gepusht werden, ohne
bereits das M/Text-Entwicklungssystem zu aktualisieren. Das ist besonders
nützlich, wenn eine Änderung mehrere Tage dauert oder mehrere Personen daran
arbeiten.

Für eine kleine, fertig vorbereitete Änderung ist kein Feature-Branch nötig.
Sie kann direkt auf dem passenden Entwicklungsbranch bearbeitet und gepusht
werden. Ist die Arbeit auf einem Feature-Branch abgeschlossen, wird der
gewünschte Commit nach `<Releaselinie>/Entwicklung` übernommen. Erst der Push
dieses Entwicklungsbranches startet die M/Text-Synchronisation. Der
Feature-Branch selbst bezeichnet keine Stage des Lieferprozesses und löst
weder eine M/Text-Synchronisation noch einen Release aus. Nur wenn
`.github/config.json` geändert wird, läuft dort der Config-Check.

### Cherry-Pick einfach erklärt

Ein **Cherry-Pick** übernimmt die Änderung eines gezielt ausgewählten Commits
auf einen anderen Branch. Anders als bei der Zusammenführung eines ganzen
Branches werden dadurch nicht automatisch alle dort vorhandenen Änderungen
weitergegeben. Das ist für den vorgesehenen Ablauf zwischen den Stages
wichtig: Nach Abnahme und Bereitstellung sollen nur fachlich ausgewählte
Änderungen übernommen werden.

Der Cherry-Pick erzeugt auf dem Zielbranch einen **neuen Commit mit einer
neuen SHA**. Es wird also dieselbe Änderung weitergegeben, nicht derselbe
Commit.

Mehrere freigegebene Commits können in ihrer ursprünglichen Reihenfolge
nacheinander per Cherry-Pick übernommen und anschließend gemeinsam mit einem
einzigen Push übertragen werden. Jeder dabei neu erzeugte Commit dokumentiert
die vollständige SHA seines jeweiligen Quell-Commits.

Das folgende Beispiel zeigt die selektive Weitergabe. Auf Entwicklung liegen
die unabhängigen Änderungen A, B und C. Nach Abnahme soll zunächst nur B:

```text
Entwicklung:  Basis ─ A ─ B ─ C
Abnahme:      Basis ─ B'
```

`B'` enthält dieselbe fachliche Änderung wie B, ist aber wegen des anderen
Eltern-Commits und der neuen Metadaten ein eigener Commit mit neuer SHA. A und
C werden nicht automatisch übernommen. Beim nächsten Übergang wird der in
Abnahme geprüfte Commit `B'` weitergegeben:

```text
Entwicklung:     Basis ─ A ─ B ─ C
Abnahme:         Basis ─ B'
Bereitstellung:  Basis ─ B''
```

### Push-Ablehnung mit Rebase statt Merge beheben

Wenn zwei Personen vom selben GitHub-Stand aus arbeiten und eine Person zuerst
pusht, baut der lokale Commit der zweiten Person noch auf dem vorherigen Stand
auf. Git lehnt deren Push deshalb üblicherweise als `non-fast-forward` ab. Das
kann auch geschehen, wenn beide Personen unterschiedliche Dateien geändert
haben.

Diese Ablehnung ist noch kein inhaltlicher Konflikt. Sie bedeutet zunächst nur,
dass der lokale Branch nicht mehr aktuell ist. Der neue GitHub-Stand muss
zuerst übernommen werden. Sind die Änderungen unabhängig, kann Git sie
automatisch kombinieren. Überschneiden oder widersprechen sie sich, entsteht
dabei ein Konflikt.

Ein **Rebase** ist dann hilfreich, wenn der GitHub-Branch inzwischen
fortgeschritten ist und zusätzlich eigene, noch nicht gepushte Commits
vorliegen. Nach `fetch` setzt der Rebase diese eigenen Commits auf den aktuellen
Remote-Branch. Überschneidungen werden dabei Commit für Commit aufgelöst. Ein
Rebase ist ausschließlich für eigene, noch nicht veröffentlichte Commits
zulässig, weil er neue Commit-SHAs erzeugt.

Ein **Merge** verbindet zwei Entwicklungsverläufe, ohne vorhandene Commits
umzuschreiben, und kann dabei einen zusätzlichen Merge-Commit erzeugen. Er ist
in diesem Prozess weder zur Behebung einer Push-Ablehnung noch zur Weitergabe
zwischen den Stage-Branches vorgesehen. Eigene noch nicht gepushte Commits
werden per Rebase auf den aktuellen Stand gesetzt. Freigegebene Änderungen
werden per Cherry-Pick in die nächste Stage übernommen.

| Situation | Geeignetes Vorgehen | Ergebnis |
|---|---|---|
| Push wird abgelehnt, weil GitHub fortgeschritten ist, und die eigenen Commits sind noch nicht gepusht | `fetch`, danach `rebase` auf den Remote-Branch | Eigene Commits werden auf dem aktuellen GitHub-Stand neu erzeugt |
| Cherry-Pick in die nächste Stage meldet einen Konflikt | Konflikt innerhalb des laufenden Cherry-Picks auflösen oder den Cherry-Pick vollständig abbrechen | Nur die ausgewählte Änderung wird in den Zielbranch übernommen |
| Fehlerhafter Commit ist bereits gepusht | Gegen-Commit nach dem beschriebenen Rücknahmeverfahren | Gemeinsame Historie bleibt unverändert nachvollziehbar |

### Konflikt bei Rebase oder Cherry-Pick auflösen

Ein Konflikt bedeutet, dass Git den gewünschten Dateiinhalt nicht eindeutig
bestimmen kann. Er wird im freigegebenen Git-Client wie folgt bearbeitet:

1. Nicht pushen und zunächst prüfen, ob gerade ein Rebase oder ein Cherry-Pick
   läuft und welche Dateien betroffen sind.
2. Für jede Konfliktstelle den bisherigen Inhalt des Zielbranches, die zu
   übernehmende Änderung und den gemeinsamen Ausgangsstand vergleichen. Nicht
   pauschal eine komplette Dateiversion auswählen, wenn dadurch fachliche
   Änderungen der anderen Seite verloren gehen.
3. Den fachlich richtigen Zielinhalt herstellen, alle Konfliktmarkierungen
   entfernen und die aufgelösten Dateien zur Fortsetzung auswählen.
4. Die laufende Operation fortsetzen. Treten weitere Konflikte auf, werden
   dieselben Schritte für den nächsten Commit wiederholt.
5. Nach Abschluss Arbeitsstand, Änderungen und Commit-Historie prüfen. Erst
   danach darf der Branch ohne Force-Push übertragen werden.

| Laufende Operation | Nach geprüfter Auflösung fortsetzen | Vollständig abbrechen |
|---|---|---|
| Rebase | Dateien mit `add` als aufgelöst markieren, danach `rebase --continue` | `rebase --abort` |
| Cherry-Pick | Dateien mit `add` als aufgelöst markieren, danach `cherry-pick --continue` | `cherry-pick --abort` |

Ist die fachlich richtige Auflösung nicht eindeutig, wird die Operation
abgebrochen und die Abweichung mit den Verantwortlichen der betroffenen
Änderungen geklärt. Die normale Aktualisierungsfunktion benötigt keinen solchen
Auflösungsablauf: Kann sie den lokalen Branch nicht direkt auf den GitHub-Stand
setzen, bricht sie ohne automatischen Merge ab.

## 4. Git-Anwendungen bedienen

Für den Gesamtprozess werden zwei Anwendungen mit klar getrennten Aufgaben
verwendet:

| Anwendung | Aufgabe | Benutzerkreis |
|---|---|---|
| M/Text Workbench mit integriertem Git-Client (EGit-Plugin) | Briefressourcen bearbeiten, Änderungen prüfen, committen und nach Entwicklung pushen | Text-Entwickler |
| GitHub im Browser | Commits, Release-Tags und Läufe prüfen sowie manuelle Läufe starten | Text-Entwickler sowie die jeweils berechtigten Verantwortlichen |

### Benötigte Git-Funktionen

| Anwendungsfall | Git-Funktion beziehungsweise Befehlsentsprechung | Nächstliegende SVN-Funktion |
|---|---|---|
| Arbeitsstand und ausgewählte Änderungen prüfen | `status` und `diff` | `svn status` und `svn diff` |
| GitHub-Stand abrufen und lokalen Branch ohne zusätzlichen Merge aktualisieren | `fetch` und anschließend `pull` beziehungsweise die freigegebene Aktualisierungsfunktion des Clients | `svn update` |
| Stage-Branch auswählen | `switch` beziehungsweise die Branchauswahl des Clients | `svn switch <URL>` |
| Dateien auswählen, Commit erzeugen und übertragen | `add`, `commit` und `push` | `svn add` und `svn commit`. Der Commit überträgt die Änderung zugleich |
| Commit-Historie, vollständige SHA und konkrete Änderungen prüfen | `log` und `show` | `svn log` und `svn diff -c <Revision>` |
| Letzten lokalen, noch nicht gepushten Commit ergänzen oder seine Nachricht korrigieren | `commit --amend`, nur vor dem Push, da dabei eine neue Commit-SHA entsteht | Keine direkte Entsprechung, weil ein SVN-Commit bereits veröffentlicht ist |
| Ausgewählten Commit in die nächste Stage übernehmen und Konflikte behandeln | `cherry-pick`, nach der geprüften Auflösung `cherry-pick --continue` oder zum vollständigen Abbruch `cherry-pick --abort` | `svn merge -c <Revision> <URL>`. Konflikte werden vor dem anschließenden `svn commit` in der Arbeitskopie aufgelöst |
| Release-Tag auf einem bestätigten Commit anlegen, einzeln pushen und bei Bedarf wieder löschen | `tag` sowie gezielter Push oder Löschung der betreffenden Tag-Referenz. Die konkrete Bedienung wird mit dem zusätzlichen Git-Client abgenommen | `svn copy <Quell-URL> <Tag-URL>` beziehungsweise `svn delete <Tag-URL>`. Ein SVN-Tag ist ein Repositorypfad |
| Inzwischen fortgeschrittenen Remote-Branch mit eigenen, noch nicht gepushten Commits zusammenführen | `fetch`, danach kontrolliertes `rebase` auf den Remote-Branch. Konflikte auflösen und mit `rebase --continue` fortfahren oder mit `rebase --abort` abbrechen | `svn update` integriert lokale, noch nicht committete Änderungen. Lokale SVN-Commits gibt es nicht |
| Noch nicht committete Arbeit vor einem Branchwechsel vorübergehend beiseitelegen | `stash push` und später `stash pop`. Danach die wiederhergestellten Änderungen vollständig prüfen | Keine direkte, durchgängig verfügbare Standardentsprechung |
| Lokale Änderung, lokalen Commit oder gepushten Commit zurücknehmen | je nach Zustand `restore`, `reset` oder `revert` wie im Abschnitt [Änderung oder Commit zurücknehmen](#änderung-oder-commit-zurücknehmen) beschrieben | Lokal `svn revert`. Eine veröffentlichte Änderung wird durch umgekehrten Merge und anschließenden `svn commit` korrigiert |

Die Weitergabe zwischen den Stages erfolgt per Cherry-Pick und nicht durch
einen Merge ganzer Branches. `stash` ist nur eine vorübergehende lokale Ablage
und kein Ersatz für einen geprüften Commit. `clean` gehört nicht zum normalen
Bedienweg, weil es nicht versionierte und damit möglicherweise noch nicht
gesicherte Ressourcendateien unwiederbringlich entfernen kann. Release-Tags
werden ausschließlich durch das Mandanten-Release-Team nach dem beschriebenen
Verfahren in GitHub verwaltet.

Als herstellerseitige Vertiefung dienen die offiziellen Git-Anleitungen
[Git-Grundlagen: Änderungen nachverfolgen und speichern](https://git-scm.com/book/de/v2/Git-Grundlagen-%C3%84nderungen-nachverfolgen-und-im-Repository-speichern)
und
[Ungewollte Änderungen rückgängig machen](https://git-scm.com/book/de/v2/Git-Grundlagen-Ungewollte-%C3%84nderungen-r%C3%BCckg%C3%A4ngig-machen.html)
sowie das
[EGit-Benutzerhandbuch](https://help.eclipse.org/latest/topic/org.eclipse.egit.doc/help/EGit/User_Guide/User-Guide.html)
für die Bedienung in der Eclipse-basierten M/Text Workbench.

### Zusätzlicher Git-Client

Das Eclipse-Plugin EGit wird für die Ressourcenarbeit und die gezielte
Weitergabe zwischen den Branches verwendet. Der Standardablauf ist:

1. Das Mandanten-Repository öffnen und die neuesten GitHub-Stände abrufen.
2. Den Zielbranch auschecken und nach dem Abschnitt
   [Lokales Repository vor der Arbeit aktualisieren](#lokales-repository-vor-der-arbeit-aktualisieren)
   auf den aktuellen GitHub-Stand bringen.
3. Die fachlich freigegebenen Quell-Commits auswählen und, falls Abhängigkeiten
   bestehen, ihre Reihenfolge festlegen.
4. Alle ausgewählten Commits einzeln und in der gewünschten Reihenfolge per
   Cherry-Pick übernehmen.
5. Bei einem Konflikt nicht pushen. Den Cherry-Pick entweder vollständig
   abbrechen oder nach dem Abschnitt
   [Konflikt bei Rebase oder Cherry-Pick auflösen](#konflikt-bei-rebase-oder-cherry-pick-auflösen)
   kontrolliert abschließen.
6. Geänderte Dateien und neu entstandene Ziel-Commits kontrollieren.
7. Die übernommenen Commits gemeinsam mit einem einzigen Push ohne Force-Push
   nach GitHub übertragen und dort den erreichten Ziel-Commit prüfen.

### Änderung oder Commit zurücknehmen

Solange eine Änderung noch nicht gepusht wurde, kann sie lokal verworfen
beziehungsweise ein lokaler Commit kontrolliert zurückgenommen werden. Es ist
zu prüfen, dass dabei keine weiteren noch benötigten lokalen Änderungen
verloren gehen.

Nach einem Push wird der Commit nicht aus dem Stage-Branch entfernt. Ein
Force-Push oder das Zurücksetzen des gemeinsamen Branches ist verboten, weil
die Commit-SHA bereits in GitHub-Läufen und gegebenenfalls in einer
M/Text-Verteilung verwendet wurde. Stattdessen wird mit der Revert-Funktion in
EGit ein neuer Commit erzeugt, der genau die Änderungen des fehlerhaften
Commits umkehrt. Dieser Gegen-Commit wird wie jede andere Änderung geprüft und
gepusht.

Die Git-Begriffe unterscheiden diese Fälle: `restore` verwirft noch nicht
committete Änderungen an Dateien, `reset` nimmt einen noch nicht gepushten
lokalen Commit zurück und `revert` erzeugt den Gegen-Commit für einen bereits
gepushten Commit. Die konkreten Schaltflächen hängen vom freigegebenen
Git-Client ab. Eine Git-Kommandozeile ist dafür nicht vorgeschrieben.
Ein `reset`, `rebase` oder `commit --amend` auf einem bereits gepushten
Stage-Branch würden dessen gemeinsame Historie umschreiben und sind deshalb
nicht zulässig.

| Situation | Vorgehen |
|---|---|
| Lokale Änderung ohne Commit | Nur die nicht mehr benötigten Dateien oder Änderungen verwerfen und den verbleibenden Stand prüfen |
| Lokaler Commit ohne Push | Commit zurücknehmen. Anschließend lokalen Branch und geänderte Dateien prüfen |
| Commit auf Entwicklung oder Abnahme gepusht | Gegen-Commit auf demselben Branch erstellen und pushen. Der dadurch gestartete Sync verteilt den vollständigen korrigierten Stand |
| Commit nach Bereitstellung gepusht, aber noch nicht getaggt | Das Mandanten-Release-Team erstellt und pusht den Gegen-Commit. Ein Push nach Bereitstellung allein erzeugt keine Lieferung |
| Commit bereits in eine weitere Stage übernommen | Den betroffenen Commit in jeder Stage, in die er übernommen wurde, mit den dort geltenden Berechtigungen durch einen eigenen Gegen-Commit zurücknehmen. Ein Gegen-Commit auf Entwicklung ändert Abnahme oder Bereitstellung nicht automatisch |
| Release-Tag falsch angelegt | Einen noch laufenden Ablauf abbrechen und den Tag nach dem Verfahren in Kapitel 10 zurücknehmen. Den Bereitstellungsbranch bei Bedarf mit einem neuen Commit korrigieren und anschließend den korrekten Tag anlegen |
| Mainframe-Übergabe bereits erfolgt | Das Löschen des Tags nimmt die Lieferung nicht zurück. Eine fachliche Korrektur erfolgt mit einem neuen Commit und einem neuen Release-Tag nach dem regulären Verfahren |

Ist der Commit fachlich richtig und nur der Workflow technisch fehlgeschlagen,
wird kein Gegen-Commit erzeugt. In diesem Fall wird derselbe Commit nach der
Fehlerbehebung kontrolliert wiederholt.

### GitHub im Browser

GitHub im Browser dient der Kontrolle und den Prozessschritten, die nicht in
der lokalen Workbench stattfinden.

#### Commit und Workflow-Lauf prüfen

1. Das Mandanten-Repository und dort **Actions** öffnen.
2. Den zum Prozessschritt gehörenden Workflow und den ausgelösten Lauf
   auswählen.
3. Branch oder Tag, Commit-SHA und Auslöser mit dem erwarteten Stand
   vergleichen.
4. Die Jobs und ihre Protokolle öffnen und den abschließenden Status prüfen.
5. Bei einem Fehler zuerst die früheste fachliche Fehlermeldung auswerten und
   keine Zugangsdaten oder andere vertrauliche Werte in Kommentare übernehmen.

#### Lauf abbrechen, wiederholen oder manuell starten

- Ein offensichtlich falscher Lauf wird vor einer externen Wirkung
  abgebrochen.
- **Re-run jobs** wiederholt einen vorhandenen Lauf mit demselben Commit und
  derselben Git-Referenz.
- **Run workflow** startet einen neuen kontrollierten Lauf mit den in Kapitel
  11 beschriebenen Eingaben.
- Vor jeder Wiederholung wird geprüft, ob das Zielsystem den vorherigen Lauf
  bereits angenommen hat.

#### Mainframe-Übergabe freigeben

1. Im Release-Lauf prüfen, dass Tag, Ziel-Commit und Paketbau zum vorgesehenen
   Stand gehören.
2. Den automatisch gestarteten Publish-Job bis zum Abschluss kontrollieren.
3. Anschließend den Status auf dem Host kontrollieren.

Für diese Freigabe ist kein verpflichtendes Vier-Augen-Prinzip vorgesehen.
Eine dafür berechtigte Person darf sowohl den Tag anlegen als auch den
Publish-Job freigeben. Die inhaltlichen Prüfungen vor der Freigabe bleiben
vollständig erforderlich.

Das Anlegen und die kontrollierte Rücknahme eines Release-Tags sind in Kapitel
10 beschrieben. Änderungen an Repositoryrechten, Rulesets, Environments oder
Secrets gehören nicht zur normalen Benutzerarbeit. Einrichtung und Abnahme
sind in [Nächste Schritte](./Naechste_Schritte.md) beschrieben.

## 5. Mandantenkonfiguration in `.github/config.json`

Die Datei `.github/config.json` liegt im Verzeichnis `.github` des
Mandanten-Repositorys und gehört wie die M/Text-Ressourcen zum versionierten
Lieferstand. Sie beantwortet drei Fragen:

1. Zu welchem Mandanten gehört der Stand?
2. Welche Projektverzeichnisse werden ausdrücklich ausgeschlossen?
3. Welche mandantenspezifischen CodePipeline-Zuordnungen gelten für die
   nachgelagerte Übergabe?

### Projektverzeichnisse und Ausschlüsse

Jedes sichtbare Verzeichnis direkt unter der Repositorywurzel ist ein
Lieferprojekt. Es wird bei jedem passenden Entwicklung- oder Abnahmelauf
synchronisiert und bei einem Release als FULL- oder DELTA-Paket gebaut.
Verzeichnisse, deren Name mit einem Punkt beginnt, werden automatisch
ignoriert. Deshalb wird beispielsweise `.github` nicht als Projekt behandelt.

Die optionale Liste `excluded_projects` enthält ausschließlich Verzeichnisse,
die trotz ihrer Lage in der Repositorywurzel nicht verarbeitet werden sollen.
Das Beispiel der FI schließt die Testdaten aus:

```json
"excluded_projects": [
  "LOMS_Testdaten"
]
```

Die technischen Namen der daraus erzeugten Paketdateien und Mainframe-Member
werden aus dem Projektnamen abgeleitet. Dafür entfallen das Präfix `LOMS_` und
ein Mandantensuffix in eckigen Klammern. Von dem verbleibenden Namen werden
höchstens die ersten fünf Zeichen in Großschreibung verwendet. So entstehen
beispielsweise `CONFI`, `FRAME`, `BASIS`, `PKA` und `AUTON`. Zwei Projekte eines
Repositorys dürfen dabei nicht denselben Projektcode ergeben.

Als aktueller fachlicher Referenzstand gelten folgende Projekte:

| Repository | Mandantenkürzel | Projekte | CodePipeline-Subsystem |
|---|---|---|---|
| `mtext-fi` | `FI` | `Configuration`, `Fonts`, `LOMS_Framework`, `LOMS_Basis`, `LOMS_PKA` | `LOMS` |
| `mtext-autonom` | `IT` | `LOMS_Autonom` | `ITMT` |
| `mtext-by` | `BY` | `LOMS_Basis[BY]`, `LOMS_Autonom[BY]` | `BYMT` |
| `mtext-lh` | `LH` | `LOMS_Basis[LH]`, `LOMS_Autonom[LH]` | `LHMT` |
| `mtext-nw` | `NW` | `LOMS_Basis[NW]`, `LOMS_Autonom[NW]` | `NWMT` |
| `mtext-os` | `OS` | `LOMS_Basis[OS]`, `LOMS_Autonom[OS]` | `OSMT` |
| `mtext-sa` | `SA` | `LOMS_Basis[SA]`, `LOMS_Autonom[SA]` | `SAMT` |

Die Matrix schreibt den Lieferumfang technisch nicht fest. Eine fachlich
abgestimmte Änderung der Projektstruktur bleibt möglich. Der Config-Check gibt
gegenüber diesem Referenzstand fehlende oder zusätzliche Projekte im
Workflow-Protokoll mit dem Präfix `WARNUNG:` aus. Einen ansonsten gültigen Stand
verarbeitet er weiter.

### Mandantenspezifische Werte für die technische Übergabe

Die technische Übergabe an die IZE9 benötigt die
ISPW/CodePipeline-Instanz `P` für Produktion oder `T` für Test, das Assignment
und die CodePipeline-Stage. Diese Werte werden in `.github/config.json`
versioniert und können aufgrund besonderer Erfordernisse angepasst werden. Da
die Konfiguration Bestandteil eines Branches ist, sind zum Beispiel
unterschiedliche Assignments je Release möglich.

Beispiel:

```json
"ispw": "P",
"hostprofile": {
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

CodePipeline-Elemente werden gemäß Mandantenkürzel, einem höchstens
fünfstelligen Projektcode aus dem Projektverzeichnisnamen und dem Suffix `F`
für FULL oder `D` für DELTA benannt.
So wird beispielsweise aus `LOMS_Autonom[BY]` das Element `BYAUTONF` oder
`BYAUTOND`. Die zugehörige Archivdatei erhält zusätzlich die Endung `.tgz`.
Ein F-Element enthält den vollständigen Projektbaum. Ein reguläres D-Element
enthält die kumulativ seit dem `.100`-Release neuen und geänderten Dateien sowie
die Löschliste. Bei einem `.100`-Release entsteht zusätzlich zum F-Element ein
leeres D-Element mit leerem Projektverzeichnis und leerer Löschliste. Die
Informationsdatei `_INFO_...txt` gehört zum Releasebeleg und wird nicht als
CodePipeline-Element registriert.

Ein Push mit einer Änderung an `.github/config.json` startet automatisch
**Validate mandant configuration**. Dieser Check prüft die Datei technisch und
liefert frühzeitig eine verständliche
Fehlermeldung. Er erkennt ein unbekanntes Mandantenkürzel, ein unpassendes
Repository, fehlende oder ungültige Hostprofile und mehrdeutige abgeleitete
Projektcodes.

## 6. Neue Releaselinie einrichten

Für jedes neue Release `Rnnn` werden die drei Branches `Rnnn/Entwicklung`,
`Rnnn/Abnahme` und `Rnnn/Bereitstellung` von den
Repository-Verantwortlichen angelegt. Ausgangspunkt ist normalerweise der
zuletzt gelieferte Release-Tag der bisherigen Linie.

Für das neue Release wird der älteste Eintrag in
[`config/releaselinien.json`](../../mtext-actions/config/releaselinien.json)
mit der neuen Zuordnung aus Releaselinie, ETAPS-Linie und Hostprofil
aktualisiert. Beispiel:

```json
{
  "R260": {"etaps_linie": "en03", "hostprofil": "JUR"},
  "R261": {"etaps_linie": "en01", "hostprofil": "FKT"},
  "R270": {"etaps_linie": "en02", "hostprofil": "JUR"}
}
```

Bei Änderungen an den Releaselinien, die zentral durch die FI durchgeführt
werden, müssen die Mandanten-Workflows anschließend einmal aktualisiert werden.
Damit zeigen sie auf eine Version der zentralen Workflows, die die
aktualisierten Releaselinien enthält. Bereitstellungen bleiben dadurch
nachvollziehbar. Die verwendete Mandantenkonfiguration, die gesamte
Tonic-Projektstruktur und die zum Releasezeitpunkt gültigen zentralen Elemente
wie Releaselinien-Konfiguration und verwendete Workflows bilden eine
zusammengehörige und unveränderliche Version.

## 7. Änderung nach Entwicklung bringen

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
Releaselinie und Stage zentral ermittelten M/Text-Ziel. Für `R261` sind dies
beispielsweise `en01e` in Entwicklung und `en01a` in Abnahme. Ein erfolgreicher
Lauf endet mit `ADAPTER_ACCEPTED`.

Nach mehreren kurz aufeinanderfolgenden Pushes ist in GitHub zu prüfen, dass
der letzte erfolgreiche Sync-Lauf den aktuellen Commit des Stage-Branches
verarbeitet hat. Maßgeblich ist der gewünschte vollständige Zielstand, nicht
die erfolgreiche Verarbeitung jedes zwischenzeitlichen Commits.

## 8. Stand zur Abnahme weitergeben

1. Die in Entwicklung erfolgreich geprüften Commits ermitteln.
2. Den aktuellen Zielbranch `<Releaselinie>/Abnahme` auschecken und
   aktualisieren.
3. Die freigegebenen Commits per Cherry-Pick aus
   `<Releaselinie>/Entwicklung` übernehmen.
4. Die neu entstandenen Commits und ihre Änderungen kontrollieren und den
   Abnahmebranch einmal pushen.
5. Unter **Actions → Sync M/Text resources** den Abnahmelauf kontrollieren.
6. Die fachliche Abnahme außerhalb des Workflows nach dem vereinbarten
   Verfahren dokumentieren.

Der Push nach Abnahme verteilt den vollständigen Projektstand des erreichten
Ziel-Commits. Er baut noch kein Mainframe-Paket.

## 9. Ausgewählte Änderungen bereitstellen

1. In GitHub die fachlich freigegebenen Commits aus Abnahme bestimmen und,
   falls Abhängigkeiten bestehen, ihre Reihenfolge festhalten.
2. Den aktuellen Zielbranch `<Releaselinie>/Bereitstellung` auschecken und
   aktualisieren.
3. Das Mandanten-Release-Team übernimmt diese Commits per Cherry-Pick aus
   `<Releaselinie>/Abnahme`.
4. Den resultierenden Stand und die neu entstandenen Commits kontrollieren und
   den Bereitstellungsbranch ohne Force-Push pushen.
5. Den exakten Ziel-Commit in GitHub prüfen und notieren. Der Push startet
   weder Paketbau noch Mainframe-Übergabe.

Nur das für den jeweiligen Mandanten benannte Mandanten-Release-Team darf hier
pushen.

## 10. FULL- oder DELTA-Lieferung auslösen

Vor dem Taggen müssen Releaselinie, Mandant, gewünschter Lieferungstyp und der
exakte Commit auf `<Releaselinie>/Bereitstellung` fachlich bestätigt sein.

- `Rnnn.100` erzeugt je nicht ausgeschlossenem Projekt ein F-Paket mit dem
  vollständigen Stand und zusätzlich ein leeres D-Paket mit leerem
  Projektverzeichnis und leerer Löschliste.
- Jede andere gültige dreistellige Endung, zum Beispiel `R261.108`, erzeugt
  ein kumulatives DELTA von `R261.100` bis zum Zieltag.
- Ein DELTA setzt voraus, dass der `.100`-Tag derselben Linie vorhanden und
  in der Git-Historie ein Vorgänger des Ziel-Tags ist.
- Nur das benannte Mandanten-Release-Team darf einen Release-Tag setzen oder löschen.

Der Release-Tag wird vom Mandanten-Release-Team als reiner Git-Tag angelegt.
GitHub Releases mit Titel, Release Notes oder zusätzlichen Dateien werden
nicht verwendet:

1. Den aktuellen Branch `<Releaselinie>/Bereitstellung` im zusätzlichen
   Git-Client auschecken und den neuesten GitHub-Stand abrufen.
2. Die vollständige SHA des bestätigten Ziel-Commits erneut vergleichen.
3. Den neuen Tag, beispielsweise `R261.108`, genau auf diesem Commit anlegen.
4. Ausschließlich diesen Tag nach GitHub pushen.
5. In GitHub prüfen, dass der Tag auf die bestätigte Commit-SHA zeigt und
   einen Lauf von **Build and publish release** gestartet hat.

Das Pushen des Git-Tags ist die fachliche Freigabe. Es startet den Paketbau und
nach erfolgreicher Prüfung automatisch die Übergabe an die IZE9.

Danach unter **Actions → Build and publish release** prüfen:

1. `Build FULL or DELTA artifact` validiert Konfiguration, Tag und
   Branchzuordnung, baut die Pakete und erzeugt `manifest.json` mit
   SHA-256-Prüfsummen. Bei `.100` müssen je Projekt sowohl das F-Paket als auch
   das zusätzliche leere D-Paket enthalten sein.
2. Das Artefakt heißt `<Repository>-<Release-Tag>` und wird standardmäßig
   30 Tage aufbewahrt.
3. `Verify and hand over artifact to Mainframe` startet nach erfolgreichem
   Build automatisch und bindet das Environment `Bereitstellung`.
4. Vor der Übergabe werden Pfad, Größe und SHA-256 jeder manifestierten Datei
   geprüft. Danach werden die JCL-Werte validiert und in das Template
   gerendert. Dann werden Paket und JCL per FTP/JES an die IZE9 übergeben.

### Irrtümlichen Tag zurücknehmen

Wurde der Tag auf dem falschen Commit oder mit dem falschen Namen angelegt,
bricht das Mandanten-Release-Team einen noch laufenden Ablauf ab. Anschließend
löscht es den irrtümlichen Git-Tag lokal und auf GitHub und legt bei Bedarf den
richtigen Tag an. Der neu angelegte Tag startet einen neuen Lauf.

Eine bereits erfolgte Mainframe-Übergabe wird durch das Löschen eines Tags
nicht rückgängig gemacht. Der korrigierte Lauf überschreibt die betreffenden
Member und CodePipeline versioniert den neuen Stand.

`MAINFRAME_SUBMITTED` bedeutet ausschließlich, dass die unmittelbare
FTP-/JES-Übergabe akzeptiert wurde. Der fachliche Abschluss des Mainframe-Jobs
wird in Ausbaustufe 1 nicht abgefragt. Das Mandanten-Release-Team prüft den weiteren
Status selbst auf dem Host nach dem dafür festgelegten Betriebsverfahren.

## 11. Einen Lauf kontrolliert wiederholen

Ein noch verfügbarer Workflow-Lauf kann in GitHub über **Actions**, den
betroffenen Lauf und **Re-run jobs** mit demselben Commit und derselben
Git-Referenz wiederholt werden. Die folgenden manuellen Durchführungen der
Workflows sind für Fälle gedacht, in denen ein neuer kontrollierter Lauf mit
ausdrücklich angegebenem Commit oder Tag erforderlich ist.

### M/Text-Vollsynchronisation initial starten oder wiederholen

Unter **Actions → Sync M/Text resources → Run workflow** angeben:

- `commit_sha`: vollständiger 40-stelliger SHA des bereits geprüften Commits
- `source_branch`: der passende Branch `Rnnn/Entwicklung` oder `Rnnn/Abnahme`

Die Automation weist den Lauf zurück, wenn der Commit nicht aus dem gewählten
Branch erreichbar ist. Das Zielsystem wird aus dem Branch abgeleitet.

Ein Wiederanlauf eines älteren Sync-Laufs kann einen inzwischen neueren
M/Text-Zielstand wieder durch den vollständigen Stand des älteren Commits
ersetzen. Vor **Re-run jobs** oder **Run workflow** müssen deshalb der
angegebene Commit, der aktuelle Branch-Commit und der gewünschte Zielstand
verglichen werden. Ist der Branch inzwischen weitergelaufen, wird nicht der
alte Lauf wiederholt, sondern ausschließlich der aktuell gewünschte Commit
kontrolliert synchronisiert.

### Release-Lauf wiederholen

Unter **Actions → Build and publish release → Run workflow** den bereits
existierenden `release_tag` angeben. Keinen neuen Tag nur für einen technischen
Wiederanlauf erzeugen. Die Automation löst den Tag erneut auf und prüft seine
Erreichbarkeit aus `<Releaselinie>/Bereitstellung`.

Vor jedem Wiederanlauf klären, ob das Zielsystem die vorherige Übergabe bereits
angenommen hat. GitHub Actions kennt ohne Status-Polling keinen nachgelagerten
fachlichen Endstatus.

## 12. Status und Fehlerbilder verstehen

| Status oder sichtbares Symptom | Bedeutung | Nächste Prüfung |
|---|---|---|
| Workflow kann die `mtext-actions`-Version nicht laden | Technische Einrichtung ist unvollständig oder der Zugriff auf `mtext-actions` fehlt | Zentrale Automatisierungsverantwortliche informieren. Anwender ändern die Workflowdateien nicht selbst |
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinienzuordnung sind technisch konsistent | Fachliche Abstimmung fortsetzen. Der Status ist keine automatische Freigabe für die nächste Stage |
| `VALIDATION_FAILED` | Eingabe, Konfiguration, Branchrichtung oder JCL ungültig | Erste Fehlermeldung lesen. Branch- oder Tagformat und Konfiguration prüfen |
| `SOURCE_FAILED` | Commit oder Tag/Basisreferenz nicht auflösbar | SHA, Tag, `.100`-Basis und Branch-Erreichbarkeit prüfen |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder manifestiertes Artefakt konnte nicht erstellt beziehungsweise geprüft werden | Fehlende Projekte, Symlinks, vorhandenes Ausgabeverzeichnis sowie Pfad, Größe und SHA-256 der Artefakte prüfen |
| `RESOURCE_TRANSFER_FAILED` | Staging oder Veröffentlichung nach `serverSync` fehlgeschlagen | Runner-Dateisystem und Share-/NFS-Ziel einschließlich vorhandener temporärer Verzeichnisse prüfen |
| `ADAPTER_FAILED` | Transportfehler oder Nicht-2xx vom Adapter | HTTP-Status und gekürzten Antworttext im Protokoll prüfen |
| `ADAPTER_ACCEPTED` | Unmittelbare Adapterannahme erfolgreich | Kein Beleg für einen nachgelagerten M/Text-Endstatus. Ist die fachliche Wirkung unklar, wird die Anwendungsbetreuung eingeschaltet. Anwender benötigen keinen direkten Zugriff auf technische Anwendungsprotokolle |
| `ARTIFACT_READY` | Releaseartefakt lokal gebaut und geprüft | Automatisch gestarteten Publish-Job prüfen |
| `MAINFRAME_TRANSFER_FAILED` | FTP-Upload oder JES-Übergabe unmittelbar fehlgeschlagen | Zugangsdaten, Dataset, JES-Ziel, Netzwerk und FTP-Antwort prüfen |
| `MAINFRAME_SUBMITTED` | Unmittelbare FTP-/JES-Übergabe akzeptiert | Das Mandanten-Release-Team prüft den weiteren Status selbst auf dem Host nach dem festgelegten Betriebsverfahren |

Protokolle dürfen keine Zugangsdaten enthalten. Zugangsdaten niemals in
Konfigurationsdateien, Workflow-Eingaben, GitHub-Kommentare oder Support-Tickets
kopieren.
