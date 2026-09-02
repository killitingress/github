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

Eine Mainframe-Lieferung verwendet den vollständigen Stand von `main` oder
`release/nnn` oder eine auf `bereitstellung/nnn.nnn` zusammengestellte
Teilmenge. Die Vorbereitung hält Commit-SHA, Liefer-Tag und Lieferumfang fest.
Die Freigabe bestätigt diesen Stand und startet Tag-Erzeugung, Paketbau und
Mainframe-Übergabe.

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
| Branches nach dem organisationsweiten Leitfaden | `main`, Release- und Feature-Branches bilden Entwicklung und Wartung gut ab. Pull Requests unterstützen das 4-Augenprinzip direkt. |
| Feature-Push nach M/Text-Entwicklung | Eine Änderung kann vor dem Pull Request vom Entwickler getestet werden. Parallelentwicklungen mehrerer Entwickler werden unterstützt. |
| Pull Request mit Squash Merge | Jeder Pull Request wird als ein fachlicher Commit in den Zielbranch übernommen und kann später Cherry-Picked werden. Review und Arbeitscommits bleiben im Pull Request sichtbar. |
| GitHub Actions statt Jenkins | Natives Git-Feeling mit modernen Workflows in der zentralen Oberfläche in der auch das Repository liegt. |
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

| Branch | Zweck | Schutz und Lebensdauer |
|---|---|---|
| `main` | Produktive Releaselinie und ihr Abnahmestand | Default Branch, geschützt, Änderung über Pull Request, Dauerhaft |
| `release/nnn` | Parallel gepflegte vorherige oder kommende Releaselinie und ihr Abnahmestand | Geschützt, Änderung über Pull Request, nach Ende der Pflege löschbar |
| `feature/nnn/<Bezeichnung>` | Eine fachlich zusammengehörige Änderung für die genannte Releaselinie | Temporär, nach dem Merge löschbar |
| `bereitstellung/nnn.nnn` | Ausgewählte Squash-Commits für eine Teillieferung | Temporär, nach der Tag-Erzeugung löschbar |

Beispiele für Feature-Branches sind:

```text
feature/261/issue-5678
feature/270/BT5000/neues-Anschreiben
```

Ein Feature-Branch basiert immer auf dem geschützten Branch, für den er
entwickelt wird.

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
- Der Squash-Commit kann bei Bedarf zurückgenommen oder mittels Cherry-Pick auf
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
`main` vorhandenen Inhalte unbeabsichtigt erhalten bleiben. Danach beginnt die
Vorbereitung der kommenden Releaselinie auf `release/271`.

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
`<Umgebungskennung>.ltoma.intern/vMtextAdapter/sync` aufgerufen.

### Archive, Projektinformationen und Lieferarten

| Begriff | Bedeutung |
|---|---|
| Projekt | Ein M/Text-Projekt mit seinen Dateien |
| Archiv | Eine gzip-komprimierte TAR-Datei (`.tgz`) für ein Projekt. Ein F-Archiv enthält dessen vollständigen Stand, ein D-Archiv neue und geänderte Dateien sowie eine Löschliste |
| Synchronisationsauftrag, kurz Auftrag | Die beim Adapter gemeinsam zu verarbeitenden Archive und Informationen für eine M/Text-Umgebung |

Anders als im alten SVN Ablauf verwenden wir nun für Synchronisation und Mainframe-Lieferung ein einheitliches Archivformat.
Es gibt weiterhin die beiden bekannten Lieferarten:

| Lieferart | Archive je Projekt |
|---|---|
| FULL | F-Archiv mit dem vollständigen Projektbaum. Bei der Mainframe-Lieferung zusätzlich ein leeres D-Archiv |
| DELTA | D-Archiv mit neuen und geänderten Dateien sowie einer Löschliste |

Das F-Archiv enthält das Projektverzeichnis mit allen Dateien und ersetzt den
im Ziel vorhandenen Stand vollständig. Eine Löschliste ist deshalb nicht
notwendig.

Das D-Archiv enthält das Projektverzeichnis mit den zu übernehmenden Dateien
und die Löschliste `<Mandantenkürzel><Projektcode>D.txt`. Beim Entpacken ist
nicht erkennbar, welche Dateien gegenüber dem Vergleichsstand entfernt wurden,
weil diese Dateien im Archiv gerade nicht mehr vorkommen. Die Löschliste nennt
daher je Zeile einen repositorybezogenen Pfad, der im Ziel entfernt werden
muss - das Format ist gegenüber dem Jenkins-Ablauf unverändert. Eine
Umbenennung erscheint als Löschung des bisherigen und Hinzufügen des neuen
Pfads.

Aus dem bestehenden Ablauf wird übernommen, dass bei der Mainframe-Übergabe bei
FULL zuerst das F-Archiv und anschließend das leere D-Archiv entpackt wird. Der
Travic-Link Folgejob wird an der Stelle erstmal nicht geändert. Der Sinn
dahinter ist, dass einmal gelieferte Archive nie gelöscht werden und das leere
D-Archiv daher das gleichnamige D-Archiv einer früheren Lieferung ersetzt. Es
enthält eine leere Löschliste und keine Projektdateien. Dadurch kann ein
vorheriges DELTA den neuen FULL-Stand nicht wieder verändern. Für die
M/Text-Synchronisation genügt bei FULL das F-Archiv.

Der Archivname besteht wie gehabt aus Mandantenkürzel, Projektcode und `F` oder
`D`. Bei der Mainframe-Lieferung ist der Name ohne `.tgz` zugleich das
Mainframe-Member.

Neben den Archiven liegt für jedes Projekt eine JSON-Informationsdatei
`_INFO_<Mandantenkürzel>-<Projekt>.json`, zum Beispiel
`_INFO_FI-LOMS_Basis.json`. Inhaltlich und namentlich orientiert sie sich an
dem, was bisher im `trans/`-Verzeichnis (NFS-Share) abgelegt wurde. Sie ist
jedoch im JSON Format und daher maschinell besser verarbeitbar. Für die
Mainframe-Lieferung spielt die Datei keine technische Rolle, sie wird aber im
GitHub-Release mit abgelegt und kann so bei Bedarf für Kontrollen oder zur
Revision genutzt werden. Bei der Synchronisation via LTOMA ist sie Teil des
initialen POST-Body und wird verwendet um den Umfang der hochzuladenen Archive
zu beschreiben. Das folgende Beispiel zeigt eine Mainframe-Lieferung:

```json
{
  "projekt": "LOMS_Basis",
  "lieferart": "DELTA",
  "scope": {
    "von": {
      "referenz": "r261.107",
      "commit": "..."
    },
    "bis": {
      "referenz": "r261.108",
      "commit": "..."
    }
  },
  "elemente": [
    ["M", "geaendert.xml"],
    ["D", "entfernt.xml"]
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
enthält als String die Prüfsumme des F-Archivs bei FULL oder des D-Archivs bei
DELTA.

Bei der **Synchronisation** entfällt `scope.von` bei FULL und alle
Projektdateien stehen mit `A` in `elemente`. Bei DELTA stimmen Elementliste und
Archivumfang überein. Die Löschliste enthält die `D`-Einträge mit
vorangestelltem Projektnamen um Kompatibilität mit dem Travic-Link Folgeskript
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
    ["A", "beispiel.xml"],
    ["A", "vorlage.xml"]
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
Schlägt der Aufruf fehl, endet der Lauf mit
`ADAPTER_FAILED`. Beim Linienwechsel werden beide Zieladapter vorab geprüft.

Adapter und M/Text greifen auf den gemeinsamen, per NFS eingebundenen Pfad
`serverSync/` zu. Es enthält unmittelbar die Projektverzeichnisse aller
Mandanten und bildet die Basis der M/Text-Synchronisation. Upload-Dateien und
temporäre Auftragsverzeichnisse liegen außerhalb dieses Pfads. Der Workflow
überträgt die zusammengestellten Archive und ihre Informationen per HTTP an
den M/Text-Adapter. Ein Synchronisationsauftrag umfasst die Archive, die
gemeinsam für eine M/Text-Umgebung verarbeitet werden sollen. Der Ablauf ist:

1. Der Workflow legt den Auftrag beim Adapter an. Er übergibt das
   Mandantenkürzel und die Informationen zu allen Archiven einschließlich ihrer
   Lieferart `FULL` oder `DELTA` und SHA-256-Prüfsummen. Alle Archive eines
   Auftrags haben dieselbe Lieferart. Ein Archiv enthält
   ein komprimiertes Projekt. Bei `FULL` werden F-Archive angekündigt. Ein
   leeres D-Archiv wird nicht übertragen. Bei `DELTA` werden D-Archive
   angekündigt. Der Adapter antwortet mit der Auftragskennung und dem Status
   `ready`.
2. Der Workflow lädt jedes angekündigte Archiv mit einem eigenen PUT unter der
   Auftragskennung hoch. Die URL enthält keine internen Ablagepfade. Der Adapter
   speichert die Upload-Dateien außerhalb von `serverSync/` und antwortet
   während des Uploads mit `uploading`. Nach jedem Upload prüft er die
   SHA-256-Prüfsumme gegen die beim Anlegen übergebene Prüfsumme.
3. Sobald alle angekündigten Archive vollständig und geprüft vorliegen, setzt
   der Adapter den Auftrag auf `processing`. Ein Lock je Mandantenkürzel und
   M/Text-Umgebung verhindert, dass mehrere Aufträge desselben Mandanten
   gleichzeitig dessen Projektbestand verändern oder eine
   M/Text-Synchronisation ausführen. Andere Mandanten dürfen parallel verarbeitet
   werden. Ist der Lock belegt, bleibt der Auftrag im Status `processing`, bis
   er verarbeitet werden kann.
4. Unter dem Lock übernimmt der Adapter die Inhalte in `serverSync/`. Bei
   `FULL` ersetzt er die betroffenen Projektverzeichnisse durch den Inhalt der
   F-Archive. Bei `DELTA` wendet er die geänderten Dateien und Löschlisten aus
   den D-Archiven an. `serverSync/` enthält unmittelbar die
   Projektverzeichnisse aller Mandanten und keine Auftragsverzeichnisse. Danach
   ruft der Adapter M/Text für diesen Bestand auf und aktualisiert den
   M/Text-Ressourcen-Cache. Der Lock wird nach der Cache-Aktualisierung gelöst.
5. Der Workflow fragt den Auftragsstatus ab, bis der Auftrag `succeeded` oder
   `failed` erreicht. Der unveränderte M/Text-Output gehört zum Ergebnis und
   wird im Workflow als informative Zusammenfassung angezeigt. Sein Inhalt
   wird nicht automatisiert ausgewertet.
6. Nach Auswertung des Ergebnisses sendet der Workflow DELETE. Der Adapter
   löscht die Upload-Dateien, ein gegebenenfalls verwendetes temporäres
   Arbeitsverzeichnis und die Auftragsdaten. Der Projektbestand in
   `serverSync/` bleibt erhalten.

Eine aus Workflow-Lauf und M/Text-Umgebung gebildete Idempotenzkennung sorgt dafür,
dass ein wiederholtes Anlegen desselben Auftrags dieselbe Auftragskennung
liefert und die Verarbeitung nicht erneut startet. Nach einem Fehler wird kein
konsistenter Projektbestand automatisch zugesichert. Ein späterer automatischer
Lauf bildet sein DELTA erneut ab dem letzten erfolgreichen Lauf desselben
Branches und schließt dadurch die noch nicht erfolgreich synchronisierten
Änderungen ein. Ein manueller Start gleicht den ausgewählten Branch mit FULL
ab.

Beim Start entfernt der Adapter temporäre Upload-, Arbeits- und Auftragsdaten
früherer Prozesse. Deren Auftragskennungen sind danach unbekannt und liefern
HTTP 404. Der Projektbestand in `serverSync/` bleibt erhalten.

### Erfolg und Reihenfolge aufeinanderfolgender Synchronisationen

Ein DELTA liefert die Änderungen seit dem letzten erfolgreichen Sync-Lauf
desselben Branches. GitHub stellt dessen Commit bereit. Damit umfassen die
D-Archive auch Änderungen zwischenzeitlich ausgefallener Läufe. Ein DELTA ohne
Projektänderungen benötigt keine Übertragung.

Auf `main` bestimmt der letzte erfolgreiche Push zusätzlich, ob ein
Releaselinienwechsel noch den FULL-Abgleich beider Umgebungen erfordert.

Läufe desselben Branches werden nacheinander ausgeführt. Ein neuer Lauf kann
einen wartenden Lauf ersetzen, ohne den aktiven Lauf abzubrechen. Sein
Vergleichsstand wird nach Abschluss des aktiven Laufs gelesen. Ein älterer
Branchstand darf einen inzwischen erfolgreich synchronisierten Stand nicht
zurücksetzen.

Läufe verschiedener Branches können parallel übertragen werden. Ihre fachlichen
Abhängigkeiten bleiben in der Verantwortung der Benutzer. Der Adapter
verarbeitet die Projektübernahme und den M/Text-Aufruf verschiedener Branches
desselben Mandanten unter dessen gemeinsamem Lock nacheinander.

## 4. Mainframe-Lieferung

Die Mainframe-Lieferung verwendet dieselben Archiv- und Informationsformate wie
die M/Text-Synchronisierung, aber einen anderen Transportweg über CodePipeline der
IZE9, MT91 und letztlich im Batch via LXT90#SV, Travic-Link und dem Folgejob
`ressourcen_aktualisieren.sh`. Sie ist kein Release im Sinne des
organisationsweiten Git-Leitfadens.

### Liefer-Tags und Lieferstand

Liefer-Tags werden für die Lieferung an CodePipeline genutzt, also nicht für
Releases im Sinne des FI-Leitfadens, daher folgen sie bei uns dem Muster
`rnnn.nnn`, beispielsweise `r261.100` oder `r261.108` und nutzen nicht den
Präfix 'v' für geschützte OSPlus-Releases. Dies erleichtert den Lieferprozess
etwas, da geschützte Tags nur auf geschützten Branches erlaubt sind, was für
Teillieferungen unpraktisch ist.

Bei `r260.108` steht `260` für das Hauptrelease `26.0` und `108` für das
Zwischenrelease. Das Hauptrelease wird im Repository als dreistellige
Releaselinie angegeben. Zwischenreleases liegen zwischen `100` und `999`.

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

Die M/Text-Synchronisierung schreibt dagegen den vorhandenen Zustand fort.
Ihre aufeinanderfolgenden DELTAs bauen auf den zuvor erfolgreich
synchronisierten Änderungen auf.

Anders als im bisherigen SVN Ablauf startet ein Tag-Push keine Übertragung - es
müssen die vorgesehenen Workflows genutzt werden:

Der Workflow **Lieferung vorbereiten** hält Branch, Commit-SHA, Liefer-Tag und
Informationen zum Lieferumfang in einem 30 Tage aufbewahrten Laufartefakt fest.
Das Artefakt heißt z.B. `r261.108-lieferungsartefakt`.

Es wird empfohlen (aber nicht erzwungen), dass eine **andere** Person dann
**Lieferung ausführen** mit dem geplanten Liefer-Tag startet. Das
4-Augenprinzip zu erzwingen wäre technisch auch umständlich und
organisatorisch bei einigen Mandanten ggf. nicht praktikabel. Es ist dennoch zu
bevorzugen und eine Abweichung davon wird explizit im Laufprotokoll geloggt.

In diesem zweiten Workflows soll eine explizite Vorab-Prüfung, erfolgen bevor
der Tag freigegeben wird. Es kann so sichergestellt werden, dass das was
mit der Lieferung übergeben werden soll auch tatsächlich das ist was für den
Liefer-Tag entwickelt wurde. Erst dann wird das Tag tatsächlichen auf dem Stand
erzeugt und der Paketbau gestartet.

### Lieferung bauen und übertragen

Der Shared Workflow checkt den markierten Commit aus und erzeugt die in
Kapitel 3 beschriebenen Archive und JSON-Informationsdateien. Er überträgt die
Archive per FTPS an den Mainframe. Die Informationsdateien bleiben beim
Lieferbericht.

Wird **Lieferung ausführen** mit einem bereits vorhandenen Liefer-Tag
gestartet, beginnt die Paketbildung und Mainframe-Übergabe für diesen Stand
erneut. Derselbe Git-Stand darf mehrfach übertragen werden, das Tag wird aber
nur beim ersten Lauf gesetzt und auch nur dann ist eine Bestätigung
durchzuführen.

### CodePipeline-Elemente

Der Name eines Elements ist zugleich sein Mainframe-Member. Er setzt sich aus
Mandantenkürzel, Projektcode und Elementart zusammen:

```text
<Mandantenkürzel><Projektcode><F|D>
```

Beispielsweise bezeichnet `BYAUTOND` das DELTA-Element für
`LOMS_Autonom[BY]`. Eine FULL-Lieferung von `LOMS_Basis` der FI erzeugt
`FIBASISF` mit dem vollständigen Projektstand sowie ein leeres `FIBASISD`.

Beispielhafte Projektcodes:

| Projekt | Projektcode |
|---|---|
| `Configuration` | `CONFI` |
| `Fonts` | `FONTS` |
| `LOMS_Framework` | `FRAME` |
| `LOMS_Basis` | `BASIS` |
| `LOMS_PKA` | `PKA` |
| `LOMS_Autonom` | `AUTON` |

Für den Projektcode werden ein vorhandenes Mandantensuffix und das Präfix
`LOMS_` entfernt. Vom verbleibenden Namen werden höchstens die ersten fünf
Zeichen in Großschreibung verwendet. Zwei Projekte desselben Repositories
dürfen dabei nicht denselben Projektcode ergeben.

Der Inhalt der F- und D-Elemente richtet sich nach der in Kapitel 3
beschriebenen Lieferart.

### Lieferartefakt

Das GitHub-Actions-Artefakt, das bei der Lieferung entsteht, enthält die erzeugten
Archive, die zugehörigen JCL-Dateien, die projektbezogenen
JSON-Informationsdateien und `lieferbericht.md`. Der Bericht wird beim Paketbau
aus denselben Vergleichsständen erzeugt. Das Artefakt wird 30 Tage aufbewahrt.
Der Übergabejob überträgt
die Archive unter ihren Membernamen und reicht die zugehörige JCL ein. Die
Informationsdateien werden nicht an den Mainframe übertragen.

Schlägt die Übergabe fehl, kann derselbe Liefer-Tag erneut ausgeführt werden.
Der Paketbau und die Mainframe-Übergabe werden dabei erneut gestartet.

Nach der Mainframe-Übergabe erstellt der Shared Workflow im
Mandanten-Repository ein GitHub Release zum vorhandenen Liefer-Tag. Die
Beschreibung nennt Liefer-Tag, Lieferart und Commit-SHA. Sie zeigt je Projekt
die Änderungen seit dem vorherigen Liefer-Tag und den Lieferumfang mit Status und Pfad.
Der jeweilige Bezugsstand steht am Abschnitt. Bei DELTA ist der Lieferumfang
kumulativ seit `.100`, bei FULL umfasst er den gesamten Projektstand.
Löschungen sind mit `D` gekennzeichnet. Der Anwender kann beide Listen auf der
GitHub-Release-Seite lesen, ohne einen Git-Vergleich auszuführen oder einen Anhang zu
öffnen. Die Beschreibung bestätigt außerdem die technische Übergabe.
Die JSON-Informationsdateien werden als Lieferbeleg angehängt. Die Bestätigung
ist zuvor im Mandanten-Repository erfolgt.

### Mainframe-Übergabe

Für die technische Vorbereitung wird angenommen, dass die IZE9 explizites FTPS
anbietet. Unter dieser Annahme werden die erzeugten F- und D-Archive zunächst
unter ihrem jeweiligen Membernamen in `IEA.LOMS.TONICZ` übertragen. Der Client
prüft das Mainframe-Zertifikat mit dem System-Vertrauensspeicher des Runners
und schützt Steuerungs- und passive Datenverbindungen mit TLS. Anschließend
kopiert die beim Paketbau aus `templates/mainframe-upload.jcl` erzeugte JCL das
Member nach `IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ` und registriert es in
CodePipeline.

Der Paketbau ist von der Mainframe-Übergabe getrennt. Übergaben desselben
Mandanten werden nacheinander ausgeführt. Verschiedene Mandanten können
gleichzeitig liefern.

### Mainframe-Zugangsdaten

Host, Port und technischer User sind in `mtext_actions` festgelegt. Das
Passwort soll auf Ebene der GitHub-Organisation verwaltet und für die
vorgesehenen Mandanten-Repositories freigegeben werden und steht dann in
Mandanten-Workflows unter `secrets.MAINFRAME_FTPS_PASSWORD` zur Verfügung.

## 5. Konfiguration

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
`main` steht sie im Feld `releaselinie`. Eine Lieferung verändert die
Mandantenkonfiguration nicht.

### `mtext_actions`-Konfiguration

`config/mandanten.json` ordnet Mandantenkürzel und Repository einander eindeutig zu.
`config/releaselinien.json` ist in Kapitel 3 beschrieben.

`config/ressourcenformate.json` wird für die Ressourcenprüfung genutzt um
Dateiendungen einem Prüfverfahren zuzuordnen, da Tonic-Elemente verschiedenste
Endungen haben können, unabhängig von ihrem wahren Dateityp.
Dateien, deren Endung zu keinem Eintrag oder Glob-Muster in
`ressourcenformate.json` passt, werden nicht geprüft.
Nur wenn Node.js auf dem Runner verfügbar ist, kann JavaScript geprüft werden. Dies wird dynamisch ermittelt.
Die Zuordnung ist derzeit:

```
{
  "dateiendungen": {
    ".datamodel": "xml",
    ".mapping": "xml",
    ".model": "xml",
    ".pageLayout*": "xml",
    ".outputSettings": "xml",
    ".template": "xml",
    ".xml": "xml",
    ".formio": "json",
    ".json": "json",
    ".js": "js"
  }
}
```

## 6. Repositories

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

Die Mandanten-Repositories sind verbindlich zugeordnet:

| Mandantenkürzel | GitHub-Repository |
|---|---|
| `FI` | `FinanzInformatik/fi_lbs_entw_oms_fi` |
| `IT` | `FinanzInformatik/fi_lbs_entw_oms_it` |
| `BY` | `FinanzInformatik/fi_lbs_entw_oms_by` |
| `LH` | `FinanzInformatik/fi_lbs_entw_oms_lh` |
| `NW` | `FinanzInformatik/fi_lbs_entw_oms_nw` |
| `OS` | `FinanzInformatik/fi_lbs_entw_oms_os` |
| `SA` | `FinanzInformatik/fi_lbs_entw_oms_sa` |

### Repository für Shared Workflows und Action `mtext_actions`

Im Mandanten-Repository stehen nur kleine Trigger-Workflows. Die eigentlichen
Arbeitsschritte liegen in
`FI-Actions/fi_lbs_entw_oms_mtext_actions`. Die Trigger-Workflows nutzen dort
den `main` Branch, welcher immer die freigegebene Version darstellt.

`mtext_actions` enthält die Shared Workflows, die Python-Module,
die Konfigurationsdateien, das JCL-Template und die
Tests:

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

Syntaxbefunde aus `check-resources.yml` dienen als Hinweise und verhindern den
Merge nicht.

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

Der aufgerufene Workflow verwendet das `GITHUB_TOKEN` des
Mandanten-Repositories. Der Trigger-Workflow gewährt die für seinen Ablauf
benötigten Rechte. Dadurch erstellt der Lieferworkflow Tag und GitHub Release
im Mandanten-Repository, ohne einen zweiten Lauf in `mtext_actions` zu starten.
Die organisationsweiten Mainframe-Werte stehen dem Mandantenlauf nach der
Repositoryfreigabe als Actions-Variablen und Actions-Secret zur Verfügung. Der
Trigger-Workflow reicht das Secret ausdrücklich an den aufgerufenen Workflow
weiter.

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
