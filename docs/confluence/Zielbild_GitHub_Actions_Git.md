# Zielbild für die Ablösung von Jenkins und SVN

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in GitHub verprobt. Während dieser Testphase bleibt der
bisherige Prozess produktiv. Unmittelbar vor der für Januar 2027 geplanten
Produktivsetzung wird der dann gültige SVN-Stand nach Git übertragen.
Danach sind Git und GitHub Actions für den Prozess führend und SVN wird
zusammen mit dem EN4920-Netz abgebaut.

Jeder Mandant erhält ein eigenes Git-Repository in github.intern mit seinen
M/Text-Ressourcen, Trigger-Workflows und einer für diesen Prozess relevanten
Konfigurationsdatei. Die gemeinsam genutzte CI/CD-Automatisierung wird im
Folgenden `mtext_actions` genannt. Sie führt Validierungen, Synchronisierung,
Paketbau und Übergabe an den Mainframe (IZE9) durch. Das Repository
`FI-Actions/fi_lbs_entw_oms_mtext_actions` enthält diese Automatisierung.

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

Die M/Workbench ist das zentrale Arbeitsmittel für die Bearbeitung der
M/Text-Ressourcen und den Git-Abgleich. Über EGit werden lokale Branches und
Commits verwaltet sowie Stände mit GitHub abgeglichen.

Jeder Entwicklungsauftrag (Änderung, Erweiterung, Korrektur, ...) wird als
Feature in einem eigenen temporären Feature-Branch umgesetzt. Wenn ein Feature
fertig entwickelt und getestet wurde, kann ein PR (Pull Request) angelegt
werden, um es in einen Zielbranch wie z.B. `main` zu übernehmen. Der Pull
Request muss dazu nach dem 4-Augenprinzip geprüft und freigegeben werden. Wenn das
passiert ist, werden die Änderungen des Feature-Branches per Squash Merge in
den Zielbranch übernommen. Dabei entsteht ein neuer Stand und somit auch ein
neuer Commit.

Wird ein Feature-Branch nach GitHub gepusht werden seine M/Text-Projekte
automatisch mit der M/Text-Entwicklungsumgebung synchronisiert, damit das
Feature vom Entwickler dort vorab getestet werden kann. Ein Merge nach `main`
oder `release/nnn` synchronisiert in der Folge automatisch die entsprechende
M/Text-Funktionstestumgebung. Dort soll das Feature dann von der LBS getestet
und fachlich freigegeben werden. Danach kann der Feature-Branch wieder gelöscht
werden.

Eine Mainframe-Lieferung kann entweder auf `main` oder `release/nnn`
durchgeführt werden und verwendet dann dessen vollständigen Stand, oder auf
einer in `bereitstellung/nnn.nnn` zusammengestellten Teillieferung. Ein
Vorbereitungs-Workflow hält Commit-SHA, Liefer-Tag und Lieferumfang fest. Der
Freigabe-Workflow bestätigt dann diesen Stand und startet Tag-Erzeugung,
Paketbau und Mainframe-Übergabe.

#### Änderungsablauf

```text
Ressourcen in M/Workbench auf lokalem Feature-Branch bearbeiten
    (feature/nnn/<Bezeichnung>)
    │ Push
    ▼
Synchronisierung mit M/Text-Entwicklung
    │ Entwicklung testen
    ▼
Pull Request nach main (oder release/nnn)
    │ Review und Merge
    ▼
Synchronisierung mit M/Text-Funktionstest
    │ fachlich freigeben lassen
    ▼
Branchstand ist für eine Lieferung bereit
```

#### Lieferablauf

```text
Branch und Liefer-Tag auswählen
    │ Lieferung vorbereiten
    ▼
Vorbereitung prüfen
    │ Lieferung ausführen
    ▼
Liefer-Tag, Paketbau und Mainframe-Übergabe
```

### Entscheidungen und Nutzen

| Entscheidung | Nutzen |
|---|---|
| GitHub Actions statt Jenkins | Natives Git-Feeling mit modernen Workflows in der zentralen Oberfläche in der auch das Repository liegt. |
| Branches nach dem organisationsweiten Leitfaden | `main`, Release- und Feature-Branches bilden Entwicklung und Wartung gut ab. Pull Requests erhöhen Sicherheit und Transparenz und sind Git-native. |
| Feature-Push nach M/Text-Entwicklung | Eine Änderung kann vor dem Pull Request vom Entwickler getestet werden. Parallelentwicklungen mehrerer Entwickler werden unterstützt. |
| Pull Request mit Squash Merge | Jeder Pull Request wird als ein fachlicher Commit in den Zielbranch übernommen und kann später Cherry-Picked werden (entspricht bisherigem Merge-Verfahren). Review und Arbeitscommits bleiben im Pull Request sichtbar. |
| Gemeinsames Format für Archive und Informationen | Synchronisation und Mainframe-Lieferung verwenden dieselben Dateiformate auf unterschiedlichen Transportwegen. |
| Zweistufige Lieferbestätigung | Die Liefer-Workflows unterstützen das 4-Augenprinzip. |

## 2. Branch- und Pull-Request-Modell

Wir orientieren uns am FI-Leitfaden zu Branches und Tags in Git:

- `main` ist der geschützte, dauerhafte Branch der produktiven Releaselinie
- `release/nnn` enthält eine parallel gepflegte vorherige oder kommende
  Releaselinie, zum Beispiel `release/260` oder `release/270`
- Jede Änderung entsteht in einem Branch `feature/nnn/<Bezeichnung>`
- Änderungen an `main` und `release/nnn` erfolgen ausschließlich über Pull Requests
- Pull Requests werden nach Freigabe nach dem 4-Augenprinzip mit Squash Merge zusammengeführt
- Liefer-Tags sind bei uns ungeschützt und folgen dem Muster `rnnn.nnn`

### Branches

* `main`: produktive Releaselinie - dauerhafter, geschützter Default Branch, Änderungen nur via Pull Request
* `release/nnn`: parallel gepflegte vorherige oder kommende Releaselinie - geschützt und nach Ende der Pflege löschbar, Änderungen nur via Pull Request
* `feature/nnn/<Bezeichnung>`: fachlich zusammengehörige Änderung für die Releaselinie - temporär
* `bereitstellung/nnn.nnn`: ausgewählte Squash-Commits für eine Teillieferung - temporär

Beispiele:

```text
release/270
feature/261/issue-5678
feature/270/BT5000/neues-Anschreiben
bereitstellung/261.350
```

### Pull Requests und Squash Merge

Wenn eine Änderung fertig entwickelt und in M/Text-Entwicklung geprüft ist,
erstellt der Entwickler einen Pull Request auf `main` oder den passenden
Release-Branch. Eine zweite Person prüft die Änderung und gibt sie idealer
Weise frei. Danach wird der Pull Request mittels Squash Merge im Zielbranch
zusammengeführt.

In den Repository-Einstellungen soll `Allow squash merging` als einziges
Mergeverfahren aktiviert sein, damit alle Beteiligten denselben Bedienweg
verwenden.

Squash Merge wird aus folgenden Gründen verwendet:

- Aus allen Änderungen eines Pull Requests wird ein fachlich zusammengehöriger
  Commit
- Zwischenstände und Korrektur-Commits aus dem Feature-Branch belasten den
  Verlauf des Zielbranches nicht
- Der lineare Verlauf ist für wenig erfahrene Git-Anwender gut
  nachvollziehbar
- Squash-Commit kann bei Bedarf zurückgenommen oder mittels Cherry-Pick auf
  eine weitere Releaselinie übernommen werden
- Review, Diskussion und ursprüngliche Commits bleiben im Pull Request
  nachvollziehbar

### Wechsel der führenden Releaselinie

Die produktive Releaselinie wechselt mit dem OSPlus-Release, also zweimal im
Jahr. `main` zeigt auf die produktive Releaselinie. Das Feld `releaselinie` der
Mandantenkonfiguration (`.github/config.json`) nennt diese Linie.

Vor dem Wechsel bestehen beispielsweise diese Stände:

```text
release/260   vorherige Releaselinie
main          produktive Releaselinie 261
release/270   kommende Releaselinie
```

Beim Wechsel wird der bisherige `main`-Stand als `release/261` erhalten. Für
die Zusammenführung entsteht `feature/270/releaselinienwechsel` aus dem
aktuellen `main`. `release/270` wird in diesen Branch gemergt. Konflikte und
weitere Abweichungen werden so aufgelöst, dass der fachliche Inhalt dem
vollständigen Stand von `release/270` entspricht.

Im Branch für den Linienwechsel wird außerdem die Mandantenkonfiguration auf
Releaselinie `270` geändert. Der vollständige Stand wird über einen Pull
Request mit Squash Merge nach `main` übernommen. Ein Vergleich mit
`release/270` stellt sicher, dass keine ausschließlich auf dem bisherigen
`main` vorhandenen Inhalte unbeabsichtigt erhalten bleiben.

Release-Branches werden gelöscht, wenn keine Änderungen für die Linie mehr
erwartet werden. Bereits gelieferte Versionen können weiterhin über
Liefer-Tags ausgecheckt werden.

## 3. Synchronisierung

### Zielermittlung

Jede Releaselinie ist einer technischen ETAPS-Linie zugeordnet. Zu jeder
ETAPS-Linie gehören eine M/Text-Entwicklungsumgebung und eine
M/Text-Funktionstestumgebung, jeweils in Stage 0 (Institut 297).

Beispiel:

```text
en01.ltoms.intern   M/Text-Entwicklung
fu01.ltoms.intern   M/Text-Funktionstest
```

Die Zielpräfixe und Releaselinien werden in
`mtext_actions/config/releaselinien.json` gepflegt. Die derzeit vorgesehene
rollierende Zuordnung lautet:

```json
{
  "mtext_ziele": {
    "Entwicklung": "en",
    "Funktionstest": "fu"
  },
  "releaselinien": {
    "260": {"etaps_linie": "03", "hostprofil": "JUR"},
    "261": {"etaps_linie": "01", "hostprofil": "FKT"},
    "270": {"etaps_linie": "02", "hostprofil": "JUR"}
  }
}
```

M/Text-Entwicklung verwendet das Präfix `en`, M/Text-Funktionstest das Präfix
`fu`. Das Feld `etaps_linie` enthält den Zahlenteil der technischen Linie.
Präfix und Zahlenteil bilden die Umgebungskennung, beispielsweise `en` und
`01` die Kennung `en01`. M/Text ist unter `<Umgebungskennung>.ltoms.intern`
erreichbar. Der Sync-Endpunkt des Adapters wird unter
`<Umgebungskennung>.ltoma.intern/vMtextAdapter/sync2` aufgerufen.

### Lieferarten und Projektarchive

Anders als im alten SVN Ablauf verwenden wir nun für Synchronisation und
Mainframe-Lieferung ein einheitliches Archivformat. Es gibt weiterhin die
beiden bekannten Lieferarten:

* `FULL`: Volllieferung mit dem vollständigen Projektbaum je Projekt (F-Archive)
* `DELTA`: Lieferung der neuen und geänderten Dateien sowie einer Löschliste (D-Archive)

Ein Projekt ist hier ein M/Text Tonic (Fragment-)Projektordner mit all seinen
Dateien. Ein Archiv ist hier das gzip-komprimierte TAR-Archiv (`.tgz`) für ein
Projekt.

#### Archive

Der Archivname besteht wie gehabt aus Mandantenkürzel, "Projektcode" und dem
Suffix `F` (FULL) oder `D` (DELTA). Ohne die Dateiendung `.tgz` ist das dann
auch der Name des CodePipeline Members.

```text
<Mandantenkürzel><Projektcode><F|D>(.tgz)
```

Für den Projektcode werden ein ggf. vorhandenes Mandantensuffix und das Präfix
`LOMS_` aus dem Projektnamen entfernt. Vom verbleibenden Namen werden höchstens
die ersten fünf Zeichen in Großschreibung verwendet. Beispielsweise wird aus
`LOMS_Autonom[BY]` der Code `AUTON` und damit für das D-Archiv der Name
`BYAUTOND`.

Ein F-Archiv enthält ein vollständiges Projektverzeichnis. Eine Löschliste ist
daher nicht notwendig. Ein D-Archiv enthält ein Projektverzeichnis mit
ausschließlich den geänderten Dateien und zusätzlich eine Löschliste. Beim
Entpacken ist nicht erkennbar, welche Dateien gegenüber dem Vergleichsstand
entfernt wurden, weil diese Dateien im Archiv gerade nicht mehr vorkommen. Die
Löschliste nennt daher je Zeile einen repositorybezogenen Pfad, der im Ziel
entfernt werden muss - das Format ist gegenüber dem Jenkins-Ablauf unverändert.
Eine Umbenennung in Git erscheint hierbei als Löschung des bisherigen und
Hinzufügen des neuen Pfades.

Aus dem bestehenden Ablauf bleibt bestehen, dass bei der Mainframe-Übergabe bei
FULL zuerst das F-Archiv und anschließend das leere D-Archiv entpackt wird. Der
Travic-Link Folgejob wird an der Stelle zunächst nicht geändert. Der Sinn
dieses Verfahrens und die Ursache ist, dass einmal gelieferte Archive im TL
Upload-Verzeichnis nie gelöscht werden und das leere D-Archiv daher das
gleichnamige D-Archiv einer vorherigen Lieferung ersetzen muss, damit ein
vorheriges DELTA den neuen FULL-Stand nicht verunreinigt.

#### Info-Datei

Neben den Archiven liegt für jedes Projekt auch eine JSON-Informationsdatei
`_INFO_<Mandantenkürzel>-<Projekt>.json`. Inhaltlich orientiert sie sich an
dem, was bisher im `trans/`-Verzeichnis (NFS-Share) abgelegt wurde. Sie ist
jedoch im JSON Format und daher maschinell besser verarbeitbar. Für die
**Mainframe-Lieferung** spielt die Datei technisch keine Rolle, sie wird aber im
GitHub-Release mit abgelegt und kann so bei Bedarf für Kontrollen genutzt
werden. Bei der **Synchronisation** via LTOMA ist sie Teil des initialen
POST-Body und wird verwendet um den Umfang der hochzuladenen Archive
festzulegen. Das folgende Beispiel zeigt eine Mainframe-Lieferung:

```json
{
  "projekt": "LOMS_Basis[BY]",
  "lieferart": "DELTA",
  "scope": {
    "von": {
      "referenz": "r261.128",
      "commit": "..."
    },
    "bis": {
      "referenz": "r261.144",
      "commit": "..."
    }
  },
  "elemente": [
    ["M", "geaendert.model"],
    ["D", "entfernt.js"]
  ],
  "sha256": "..."
}
```

`scope.von` bezeichnet den Ausgangsstand. `scope.bis` gibt den Stand an, der
geliefert oder synchronisiert werden soll. Die Liste `elemente` beschreibt
die Unterschiede zwischen diesen beiden Ständen. Für jeden Stand nennt
`referenz` den Liefer-Tag (bei Lieferungen) oder Branch (bei einer
Synchronisierung) und `commit` die zugehörige Commit-SHA.

`elemente` enthält für jede relevante Datei den Git-Status und ihren
projektbezogenen Pfad mit den Statuswerten `A`
(hinzugefügt), `M` (geändert), `D` (gelöscht) und `T` (Typ geändert). `sha256`
enthält die Prüfsumme des Archivs.

Bei der **Synchronisation** entfällt `scope.von` bei FULL, und alle
Projektdateien stehen mit Status `A` in `elemente`. Bei DELTA stimmen
Elementliste und Archivumfang überein. Die Löschliste enthält die `D`-Einträge
mit vorangestelltem Projektnamen um Kompatibilität mit dem Travic-Link
Folgeskript
zu gewährleisten.

Das folgende Beispiel zeigt einen manuell gestarteten FULL-Abgleich eines
Feature-Branches. Das Beispielprojekt besteht aus zwei Dateien. Beide werden
als Teil des gesamten Projektbestands mit `A` aufgeführt, auch wenn sie bereits
vor dem Abgleich vorhanden waren:

```json
{
  "projekt": "LOMS_Basis",
  "lieferart": "FULL",
  "scope": {
    "bis": {
      "referenz": "feature/261/neues-Anschreiben",
      "commit": "..."
    }
  },
  "elemente": [
    ["A", "Bausteine/integriert/BT0002/neu.model"],
    ["A", "Daten/Modelle/integriert/BT0002/neu.datamodel"]
  ],
  "sha256": "..."
}
```

Bei **Mainframe-Lieferungen** zeigt die Info-Datei die Änderungen seit
dem vorherigen Liefer-Tag. Das entspricht dem bisherigen „DIFF gegenüber
Vorrelease“. Dieser Vergleich wird auch bei einem neuen Hauptrelease gebildet.
DELTA-Archive und ihre Löschlisten beziehen sich hier auf den zugehörigen
`.100`-Tag. Sie enthalten die Änderungen seit diesem Hauptrelease bis zum
aktuellen Liefer-Tag.

Das bedeutet auch, dass sich die Elementliste der Info-Datei und der
Archivumfang bei DELTA-Lieferungen in der Regel unterscheiden. Das spätere
GitHub Release zeigt aber beides: die Änderungen seit dem vorherigen Liefer-Tag
und den tatsächlichen Lieferumfang.

### Transport der Synchronisationsaufträge

Vor dem Archivbau prüft der Workflow die Erreichbarkeit des Adapters über
`GET /vMtextAdapter/version` und gibt die Antwort im Workflow-Log aus.
Schlägt der Aufruf fehl, endet der Lauf mit `ADAPTER_FAILED`. Beim
Linienwechsel werden beide Zieladapter vorab geprüft.

Adapter und M/Text greifen auf den gemeinsamen Pfad `serverSync/` zu. Dieser
enthält die Projektverzeichnisse aller Mandanten und bildet wie im alten Ablauf
die Basis der M/Text-Synchronisation. Der Workflow überträgt die
zusammengestellten Archive und ihre Informationen einzeln per HTTP an LTOMA.
Ein Synchronisationsauftrag umfasst alle Archive, die mit einer M/Text-Umgebung
synchronisiert werden sollen.

Für einen neuen Auftrag gilt folgender Ablauf:

1. Der Workflow initiiert einen Auftrag via POST-Request an LTOMA. Dabei
   kündigt er im POST-Body alle Archive und deren Prüfsummen an, die zum
   Auftrag gehören werden. Der Adapter antwortet mit der Auftrags-ID und dem
   Status `ready`.
2. Der Workflow lädt jedes angekündigte Archiv nacheinander mit einem eigenen
   PUT-Request unter der Auftrags-ID hoch. Der Adapter speichert die
   Upload-Dateien zunächst außerhalb von `serverSync/` und prüft direkt nach
   Empfang eines Archivs dessen Prüfsumme. Während noch nicht alle Uploads des
   Auftrags abgeschlossen sind, antwortet der Adapter auf Statusabfragen via
   GET mit `uploading`.
3. Sobald alle angekündigten Archive vollständig und korrekt vorliegen, setzt
   der Adapter den Auftrag auf `processing`. Ein Lock je Mandantenkürzel und
   M/Text-Umgebung verhindert, dass mehrere Aufträge desselben Mandanten
   gleichzeitig dessen Projektbestand verändern oder eine
   M/Text-Synchronisation ausführen. Andere Mandanten dürfen parallel
   verarbeitet werden. Ist der Lock belegt, bleibt der Auftrag im Status
   `processing`, bis er verarbeitet werden kann.
4. Unter dem Lock übernimmt der Adapter die Inhalte nach `serverSync/`. Bei
   `FULL` ersetzt er die betroffenen Projektverzeichnisse durch den Inhalt der
   F-Archive (löschen und verschieben). Bei `DELTA` wendet er die geänderten
   Dateien und Löschlisten aus den D-Archiven an. Danach ruft der Adapter LTOMS 
   auf, damit dieser den M/Text-Ressourcen-Cache auf Basis von `serverSync`
   aktualisiert. Der Lock wird im Anschluss gelöst.
5. Der Workflow fragt den Auftragsstatus alle 5 Sekunden via GET-Request ab,
   bis der Auftrag `succeeded` oder `failed` erreicht. Die Ausgabe, die durch
   die Ressourcen-Cache Aktualisierung entsteht, wird an den Workflow
   übermittelt und als informative Zusammenfassung angezeigt.
6. Danach sendet der Workflow HTTP-DELETE. Der Adapter entfernt den Auftrag,
   seine Idempotenzkennung, die Upload-Dateien und ein gegebenenfalls
   verwendetes temporäres Arbeitsverzeichnis. Der Projektbestand unter
   `serverSync/` bleibt erhalten.

Vor dem Archivbau sucht der Workflow mit `GET /vMtextAdapter/sync2` nach einem
bestehenden Auftrag. Der Header `Idempotency-Key` enthält
`github-run-<GITHUB_RUN_ID>-<Umgebungskennung>`. Diese Kennung bleibt beim
Wiederholen desselben GitHub-Laufs erhalten. Antwortet der Adapter mit HTTP
404, baut der Workflow die Archive und startet den beschriebenen Ablauf.

Besteht der Auftrag bereits in `processing`, wartet der Workflow auf dessen
Abschluss. Bei `succeeded` übernimmt er das Ergebnis und räumt den Auftrag
auf. In beiden Fällen entfallen Archivbau und Uploads. Einen Auftrag in
`ready`, `uploading` oder `failed` löscht er und startet mit neu gebauten
Archiven unter derselben Kennung erneut.

Ist die Verarbeitung inzwischen gestartet, lehnt der Adapter DELETE mit
HTTP 409 ab und lässt Verarbeitung und Lock bestehen. Der Workflow fragt den
Status erneut ab und wartet auf den Abschluss. Ein dabei gemeldetes `failed`
beendet den Versuch nach dem Aufräumen mit diesem Fehler, ohne erneut zu
starten.

Ein neuer GitHub-Lauf verwendet eine neue Idempotenzkennung und bildet sein
DELTA ab dem letzten erfolgreichen Lauf desselben Branches. Dadurch schließt
er die noch nicht erfolgreich synchronisierten Änderungen ein. Wenn durch
Überholer-Situationen oder Abbrüche und Neustarts korrupte Stände in
`serverSync/` entstehen sollten, ist eine manuelle Volllieferung durchzuführen.
Die Auftragsdaten im Adapter überleben keinen Neustart.

### Erfolg und Reihenfolge aufeinanderfolgender Synchronisationen

Ein DELTA liefert die Änderungen seit dem letzten erfolgreichen Sync-Lauf
desselben Branches. Damit umfassen die D-Archive auch Änderungen
zwischenzeitlich ausgefallener Läufe.  Auf `main` bestimmt ein Push zusätzlich,
ob ein Releaselinienwechsel noch den FULL-Abgleich beider Umgebungen erfordert.

Mehrere Synchronisierungsläufe können gleichzeitig ausgeführt werden.
Fachliche Abhängigkeiten liegen dabei in der Verantwortung der Benutzer. Der
Adapter verarbeitet Aufträge unter dem Lock nacheinander.

## 4. Mainframe-Lieferung

Die Mainframe-Lieferung verwendet dieselben Archiv- und Informationsformate wie
die Synchronisierung, aber einen anderen Transportweg über CodePipeline der
IZE9, MT91 und letztlich im Batch via LXT90#SV, Travic-Link und dessen Folgejob
(`ressourcen_aktualisieren.sh`).

### Liefer-Tags und Lieferstand

Liefer-Tags werden für die Lieferung an CodePipeline genutzt, also nicht für
Releases im Sinne des FI-Leitfadens, daher folgen sie bei uns dem Muster
`rnnn.nnn`, beispielsweise `r261.100` oder `r261.108` und nutzen nicht den
Präfix 'v' für geschützte OSPlus-Releases. Dies erleichtert den Lieferprozess
etwas, da geschützte Tags nur auf geschützten Branches erlaubt sind, was für
Teillieferungen unpraktisch ist.

Für eine Teillieferung zu einem bestimmten Liefer-Tag wird ein ungeschützter
Branch `bereitstellung/nnn.nnn` aus dem vorherigen Liefer-Tag erstellt. Die
relevanten Squash-Commits werden mittels EGit auf diesen Arbeitsbranch
cherry-gepickt.

Der Liefer-Tag `r260.100` kennzeichnet die Volllieferung (FULL) des Hauptreleases
`26.0`. Ein solcher `.100`-Tag entsteht auf `main` oder `release/nnn`.

Bei der Verarbeitung einer Mainframe-Lieferung wird zuerst das F-Archiv und
danach das D-Archiv entpackt. Die Archive bleiben erhalten und werden durch
neue Lieferungen überschrieben. Ein Zwischenrelease ersetzt das D-Archiv,
während das F-Archiv den Stand der `.100`-Lieferung behält. Das DELTA enthält
deshalb kumulativ die Änderungen zwischen `.100` und dem aktuellen Liefer-Tag,
damit FULL und aktuelles DELTA zusammen den Lieferstand ergeben.

Anders als im bisherigen SVN Ablauf startet ein Tag-Push keine Übertragung - es
müssen die vorgesehenen Workflows genutzt werden:

### Lieferung vorbereiten

Der Workflow **Lieferung vorbereiten** wird manuell für den ausgewählten Branch
mit dem geplanten Liefer-Tag gestartet. Er prüft, ob der Tag noch frei ist und
Branch und Tag zur Releaselinie passen.

Die Laufzusammenfassung zeigt den Branch, die Änderungen seit dem vorherigen
Liefer-Tag und den vorgesehenen Lieferumfang. Für die spätere Bestätigung hält
der Workflow Liefer-Tag, Commit-SHA, Repository und vorbereitende Person in
einem 30 Tage aufbewahrten Laufartefakt fest. Das Artefakt heißt z.B.
`r261.108-lieferungsartefakt`.

Sollte auffallen, dass etwas mit der Lieferung fachlich noch nicht stimmt, ist
der Branch zu korrigieren und dann der Workflow erneut mit demselben geplanten
Liefer-Tag zu starten. Dabei entsteht ein neues Laufartefakt.

### Lieferung ausführen

In diesem zweiten Workflow soll eine explizite Vorab-Prüfung durch eine zweite
Person erfolgen, bevor der Tag freigegeben wird. Es kann so sichergestellt
werden, dass das was mit der Lieferung übergeben werden soll auch tatsächlich
das ist was für den Liefer-Tag entwickelt wurde. Falls der gleiche Anwender
**Lieferung ausführen** startet, der auch schon die Vorbereitung getätigt hat,
muss hier explizit die Abweichung vom empfohlenen 4-Augenprinzip angehakt
werden. Technisch das 4-Augenprinzip zu erzwingen wäre umständlich und
organisatorisch bei einigen Mandanten ggf. nicht praktikabel, insofern ist es
auch möglich, dass der gleiche Autor die Lieferung vorbereitet und durchführt.

**Lieferung ausführen** ruft einen Shared Workflow auf, der den Paketbau,
die Mainframe-Übergabe und die Veröffentlichung des Lieferberichts in
aufeinanderfolgenden Jobs ausführt. Der Paketbau stellt die Lieferdateien im
Laufartefakt `release` bereit. Der Übergabejob lädt das Artefakt, überträgt die
Archive an den Mainframe und reicht die JCL ein. Anschließend veröffentlicht
ein weiterer Job den Lieferbericht und die JSON-Informationsdateien im
GitHub Release.

Wird **Lieferung ausführen** mit einem bereits vorhandenen Liefer-Tag
gestartet, beginnt die Paketbildung und Mainframe-Übergabe für diesen Stand
erneut. Derselbe Git-Stand darf mehrfach übertragen werden, das Tag wird aber
nur beim ersten Lauf gesetzt und auch nur dann ist eine Bestätigung
durchzuführen.

#### Lieferartefakt und Lieferbericht

Beim Paketbau in **Lieferung ausführen** entsteht das Laufartefakt `release`.
Es enthält die erzeugten Archive, je Archiv eine eigene JCL-Datei, die
projektbezogenen JSON-Informationsdateien und `lieferbericht.md` und wird
wie das Vorbereitungsartefakt 30 Tage aufbewahrt. Der Übergabejob lädt dieses
Artefakt, überträgt die Archive an den Mainframe und reicht die JCL ein.

Der Lieferbericht nennt Liefer-Tag, Lieferart und Commit-SHA. Er zeigt je
Projekt die Änderungen seit dem vorherigen Liefer-Tag und den Lieferumfang
mit Status und Pfad. Bei DELTA umfasst der Lieferumfang die Änderungen seit
`.100`, bei FULL den gesamten Projektstand. Die Bezugsstände sind im Bericht
angegeben, Löschungen mit `D` gekennzeichnet.

Nach erfolgreicher Mainframe-Übergabe veröffentlicht der Shared Workflow den
Lieferbericht als Beschreibung eines GitHub Releases zum Liefer-Tag im
Mandanten-Repository. Er ergänzt die Bestätigung, dass FTPS und JES die Archive
und JCL angenommen haben, und hängt die JSON-Informationsdateien an.
Ein bereits vorhandenes GitHub Release wird aktualisiert.

#### Mainframe-Übergabe

Für die technische Vorbereitung wird angenommen, dass die IZE9 explizites FTPS
anbietet. Unter dieser Annahme überträgt der Client jedes Archiv zunächst
unter seinem Membernamen in `IEA.LOMS.TONICZ`. Der Client
prüft das Mainframe-Zertifikat gegen die vertrauenswürdigen CA-Zertifikate im
Truststore des Runners und schützt Steuerungs- und passive Datenverbindungen
mit TLS. Nach jedem Archiv-Upload schaltet der Client mit `SITE FILETYPE=JES`
auf die Jobübergabe um und reicht die für dieses Archiv aus
`templates/mainframe-upload.jcl` erzeugte JCL als eigenen Job ein. Dieser
Mainframe-Job kopiert das Member dann nach `IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ`
und registriert es in CodePipeline.

Übergaben desselben Mandanten werden nacheinander ausgeführt. Verschiedene
Mandanten können gleichzeitig liefern.

#### Mainframe-Zugangsdaten

Host, Port und technischer User sind in `mtext_actions` festgelegt. Das
Passwort soll auf Ebene der GitHub-Organisation verwaltet und für die
vorgesehenen Mandanten-Repositories freigegeben werden und steht dann in
Mandanten-Workflows unter `secrets.MAINFRAME_FTPS_PASSWORD` zur Verfügung.

### Kurz zusammengefasst

- **Lieferung vorbereiten**: Prüft den gewählten Branchstand und den geplanten
  Liefer-Tag, zeigt Änderungen und Lieferumfang in der Laufzusammenfassung und
  hält die Vorbereitung mit Commit-SHA im Vorbereitungsartefakt fest.
- **Lieferung ausführen**: Übernimmt die Vorbereitung nach Bestätigung und
  erzeugt den Liefer-Tag auf dem festgehaltenen Commit. Baut die Archive, je
  Archiv eine JCL, die JSON-Informationsdateien und den Lieferbericht und
  speichert sie im Laufartefakt `release`. Der Übergabejob lädt dieses Artefakt,
  überträgt die Archive per FTPS und reicht nach jedem Archiv dessen JCL als
  eigenen Job bei JES ein. Nach erfolgreicher Übergabe werden Lieferbericht
  und JSON-Informationsdateien im GitHub Release veröffentlicht. Bei einem
  vorhandenen Liefer-Tag beginnt der Ablauf erneut beim Paketbau.

## 5. Repositories

### Mandanten-Repositories

Ein Mandanten-Repository folgt diesem Aufbau:

```text
fi_lbs_entw_oms_<kuerzel>/
  .github/
    config.json
    workflows/
      check-resources.yml
      lieferung-ausfuehren.yml
      lieferung-vorbereiten.yml
      sync-resources.yml
  <M/Text-Projekte>
```

`FinanzInformatik/fi_lbs_entw_oms_fi` dient als Muster für die übrigen
Mandanten-Repositories. Die M/Text-Projekte liegen als Verzeichnisse direkt in
der Repositorywurzel. Sie werden synchronisiert und in Lieferpakete
aufgenommen. Einzelne Verzeichnisse wie `LOMS_Testdaten` können in
`.github/config.json` davon ausgeschlossen werden, bleiben aber Teil des
Git-Repositories. Dateien, die gar nicht in Git aufgenommen werden sollen,
werden wie üblich in `.gitignore` eingetragen.

### Repository für Shared Workflows und Action `mtext_actions`

Im Mandanten-Repository stehen nur kleine Trigger-Workflows. Die eigentlichen
Arbeitsschritte liegen in `FI-Actions/fi_lbs_entw_oms_mtext_actions`. Die
Trigger-Workflows nutzen dort den `main` Branch, welcher immer die freigegebene
Version darstellt.

`mtext_actions` enthält die Shared Workflows, die Python-Module, die
Konfigurationsdateien, das JCL-Template und die Tests:

```text
mtext-actions/
  action.yml
  .github/
    workflows/
      ci.yml
      shared-check-resources.yml
      shared-lieferung-ausfuehren.yml
      shared-lieferung-check.yml
      shared-sync-resources.yml
  config/
    mandanten.json
    ressourcenformate.json
    releaselinien.json
  scripts/
    runner-preflight.sh
  src/
    lbs_delivery/
      adapter.py
      config.py
      git.py
      github.py
      mainframe.py
      process.py
      project_archives.py
      lieferung.py
      resource_check.py
      sync.py
    mtext.py
  templates/
    mainframe-upload.jcl
  tests/
```

## 6. Konfiguration

### Mandantenkonfiguration

Die Datei `.github/config.json` liegt im Mandanten-Repository und wird zusammen
mit den M/Text-Projekten versioniert. Der Block `mandant` enthält:

| Feld | Bedeutung |
|---|---|
| `kuerzel` | Mandantenkürzel für Paketnamen und Fragmentprojekte |
| `releaselinie` | Releaselinie von `main` |
| `ispw` | CodePipeline-Instanz `T` oder `P` |
| `excluded_projects` | Projektverzeichnisse, die weder synchronisiert noch paketiert werden |
| `hostprofile` | Assignment und CodePipeline-Stage je Hostprofil |

Beispiel:

```json
{
  "mandant": {
    "kuerzel": "FI",
    "releaselinie": "270",
    "ispw": "P",
    "excluded_projects": ["LOMS_Testdaten"],
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
  }
}
```

Bei Feature- und Release-Branches steht die Releaselinie im Branchnamen. Bei
`main` steht sie im Feld `releaselinie`.

### `mtext_actions`-Konfiguration

`config/mandanten.json` ordnet Mandantenkürzel und Repository einander eindeutig zu:

```
{
  "FI": {"repository": "FinanzInformatik/fi_lbs_entw_oms_fi", "subsystem": "LOMS"},
  "BY": {"repository": "FinanzInformatik/fi_lbs_entw_oms_by", "subsystem": "BYMT"},
  "LH": {"repository": "FinanzInformatik/fi_lbs_entw_oms_lh", "subsystem": "LHMT"},
  "NW": {"repository": "FinanzInformatik/fi_lbs_entw_oms_nw", "subsystem": "NWMT"},
  "OS": {"repository": "FinanzInformatik/fi_lbs_entw_oms_os", "subsystem": "OSMT"},
  "SA": {"repository": "FinanzInformatik/fi_lbs_entw_oms_sa", "subsystem": "SAMT"},
  "IT": {"repository": "FinanzInformatik/fi_lbs_entw_oms_it", "subsystem": "ITMT"}
}
```

`config/releaselinien.json` ist in Kapitel 3 beschrieben.

`config/ressourcenformate.json` wird für die Ressourcenprüfung genutzt um
Dateiendungen einem Prüfverfahren zuzuordnen, da Tonic-Elemente verschiedenste
Endungen haben können, unabhängig von ihrem wahren Dateityp.  Dateien, deren
Endung zu keinem Eintrag oder Glob-Muster in `ressourcenformate.json` passt,
werden nicht geprüft.  Wenn Node.js auf dem Runner verfügbar ist, kann auch
JavaScript geprüft werden. Dies wird dynamisch ermittelt.

## 7. Workflows

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Trigger-Workflow | Shared Workflow | Python-Skript |
|---|---|---|---|---|---|
| Mandantenkonfiguration und Ressourcen prüfen | Pull Request oder manueller Start | `check-resources.yml` | `shared-check-resources.yml` | `mtext.py config validate` und `mtext.py resources check` |
| M/Text-Entwicklung synchronisieren | Push auf `feature/nnn/<Bezeichnung>` oder manueller Start | `sync-resources.yml` | `shared-sync-resources.yml` | `mtext.py resources sync` |
| M/Text-Funktionstest synchronisieren | Push oder Merge auf `main` oder `release/nnn` sowie manueller Start | `sync-resources.yml` | `shared-sync-resources.yml` | `mtext.py resources sync` |
| Lieferung vorbereiten | Manueller Start auf `main`, `release/nnn` oder `bereitstellung/nnn.nnn` | `lieferung-vorbereiten.yml` | `shared-lieferung-check.yml` | `mtext.py delivery check` |
| Lieferung ausführen | Manueller Start mit einem geplanten oder vorhandenen Liefer-Tag | `lieferung-ausfuehren.yml` | `shared-lieferung-ausfuehren.yml` |
| Lieferung bauen und übertragen | Erstellter oder vorhandener Liefer-Tag | `lieferung-ausfuehren.yml` | `shared-lieferung-ausfuehren.yml` | `mtext.py release build`, `release mainframe`, danach `release github` |
| `mtext_actions` testen | Pull Request, Push auf `main` oder manueller Start in `mtext_actions` | keiner | `ci.yml` | `python -m unittest discover` |

### Trigger-Workflows in den Mandanten-Repositories

Die Trigger-Workflows reagieren auf Änderungen und starten die
Verarbeitung in `mtext_actions`:

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `check-resources.yml` | Pull Request oder manueller Start | Mandantenkonfiguration und geänderte konfigurierte Ressourcen oder den gewählten Vollstand prüfen, Syntaxbefunde als Warnungen anzeigen |
| `lieferung-vorbereiten.yml` | Manueller Start auf dem ausgewählten Branch | SHA und Lieferumfang unter dem geplanten Liefer-Tag festhalten |
| `lieferung-ausfuehren.yml` | Manueller Start mit einem geplanten oder vorhandenen Liefer-Tag | Neueste Vorbereitung bestätigen und die Lieferung starten oder vorhandenen Lieferstand erneut übergeben |
| `sync-resources.yml` | Push auf einen Feature-, `main`- oder Release-Branch sowie manueller Start | Projekte nach M/Text-Entwicklung oder -Funktionstest übertragen |

### Shared Workflows

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `shared-check-resources.yml` | Aufruf durch `check-resources.yml` | Mandantenkonfiguration und konfigurierte Ressourcen ohne Zugriff auf Zielsysteme prüfen |
| `shared-sync-resources.yml` | Aufruf durch `sync-resources.yml` | Projekte nach M/Text übertragen |
| `shared-lieferung-check.yml` | Aufruf durch `lieferung-vorbereiten.yml` | Liefer-Tag und Branchstand prüfen, Lieferumfang anzeigen und Vorbereitungs-Artefakt bauen |
| `shared-lieferung-ausfuehren.yml` | Aufruf durch `lieferung-ausfuehren.yml` | Lieferstand ermitteln, eine Vorbereitung bestätigen, bei einer erstmaligen Lieferung den Tag erstellen, Archive und Informationsdateien für FULL oder DELTA erzeugen, die Archive an den Mainframe übertragen und die Lieferinformationen im Mandanten-Repository bereitstellen |
| `ci.yml` | Pull Request oder Push auf `main` oder manueller Start | Tests ausführen |

Die Shared Workflows werden direkt in einen Mandantenlauf eingebunden. Die
Python-Implementierung wird als Action aus `mtext_actions` geladen. Die
Repositoryfreigabe in `FI-Actions` erlaubt GitHub das Laden dieser gemeinsamen
Komponenten ohne eigenes Zugriffstoken.

GitHub stellt jedem Job automatisch einen zeitlich begrenzten Zugangsschlüssel
namens `GITHUB_TOKEN` bereit. Damit kann der Job auf das Mandanten-Repository
zugreifen, etwa um Vorbereitungsartefakte zu lesen oder einen Liefer-Tag und
ein GitHub Release anzulegen. Die erlaubten Aktionen werden über
`permissions` in den Workflow-Dateien festgelegt.

Auch der aufgerufene Shared Workflow arbeitet mit diesem Zugang zum
Mandanten-Repository. Er gehört zum selben Lauf und verwendet die vom
aufrufenden Workflow gewährten Rechte. Tag und GitHub Release entstehen daher
im Mandanten-Repository.

Für den Mainframe-Zugang sind Host, Port und technischer Benutzer in
`mtext_actions` festgelegt. Das Passwort soll als Organisations-Secret
`MAINFRAME_FTPS_PASSWORD` hinterlegt und für die vorgesehenen
Mandanten-Repositories freigegeben werden. Ein Secret ist ein in GitHub
geschützt gespeicherter Wert.

### Protokolle und Rückmeldung

GitHub Actions übernimmt `stdout` und `stderr` der Workflows in das Protokoll.
Die Python-Skripte schreiben ein erfolgreiches Ergebnis als JSON nach `stdout`
und Warnungen oder Fehler nach `stderr`. Bei der Konfigurationsprüfung und der
M/Text-Synchronisation sind diese Ausgaben im Mandanten-Repository sichtbar.

Prüfung, Paketbau, Mainframe-Übergabe und Bereitstellungsbericht sind im
Mandantenlauf sichtbar. **Nach Abschluss stehen das Ergebnis und die
Lieferinformationen außerdem im GitHub Release des Mandanten-Repositories.**

### Status und Fehlercodes

Die Workflows melden mit einem festen Status, was erreicht wurde oder an
welcher Stelle sie abgebrochen sind. Bei Fehlern endet das Programm außerdem
mit dem zugehörigen Exitcode.

| Status | Bedeutung | Exitcode bei Fehlern |
|---|---|---|
| `RESOURCE_CHECKED` | JSON- und XML-Ressourcen wurden geprüft, Befunde stehen als Warnungen bereit | – |
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinienzuordnung wurden geprüft | – |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig | `2` |
| `LIEFERUNG_CHECKED` | SHA, Liefer-Tag und Lieferumfang der Vorbereitung wurden festgehalten | – |
| `LIEFERUNG_BESTAETIGT` | Die vorbereitete Lieferung wurde durch dieselbe oder eine zweite Person bestätigt | – |
| `LIEFERUNG_TAGGED` | Der Liefer-Tag wurde auf der festgehaltenen SHA erstellt | – |
| `SOURCE_FAILED` | Checkout, Commit, Branch oder Tag können nicht als Quelle verwendet werden | `3` |
| `ADAPTER_FAILED` | Adapteraufruf oder M/Text-Synchronisation sind fehlgeschlagen | `6` |
| `ADAPTER_COMPLETED` | Der M/Text-Adapter hat die Synchronisation erfolgreich abgeschlossen | – |
| `PACKAGE_FAILED` | Archiv, Informationsdatei oder JCL konnten nicht erstellt oder verwendet werden | `4` |
| `ARTIFACT_READY` | Archive, Informationsdateien und JCL wurden erstellt | – |
| `MAINFRAME_TRANSFER_FAILED` | Die FTPS- oder JES-Übergabe ist fehlgeschlagen | `7` |
| `MAINFRAME_SUBMITTED` | Archive und JCL wurden per FTPS und JES übergeben | – |
| `GITHUB_RELEASE_FAILED` | Das GitHub Release oder seine Informationsdateien konnten nicht bereitgestellt werden | `8` |
| `GITHUB_RELEASE_PUBLISHED` | Zusammenfassung und Informationsdateien stehen im Mandanten-Repository bereit | – |
