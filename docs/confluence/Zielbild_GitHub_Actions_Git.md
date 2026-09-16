# Zielbild für die Ablösung von Jenkins und SVN

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in GitHub verprobt. Während dieser Testphase bleibt der
bisherige Prozess produktiv. Unmittelbar vor der für Anfang 2027 geplanten
Produktivsetzung wird der dann gültige SVN-Stand nach Git übertragen.
Danach sind Git und GitHub Actions für den Prozess führend und SVN wird
zusammen mit dem EN4920-Netz abgebaut.

Jeder Mandant erhält ein eigenes Git-Repository in github.intern mit seinen
M/Text-Ressourcen, Trigger-Workflows und einer für diesen Prozess relevanten
Konfigurationsdatei. Die gemeinsam genutzte und im Folgenden beschriebene
CI/CD-Automatisierung nennen wir `mtext_actions`. Sie führt Validierungen,
Synchronisierung und Lieferung an CodePipeline zentral durch.

### Grundprinzipien

In SVN ist ein Commit eine Aktion, durch die Änderungen an das zentrale
Repository übertragen werden. Dabei entsteht eine neue Revision als
aufsteigende Nummer. In Git hingegen werden Commits in einer lokalen Kopie
eines Repositories getätigt und per Push an ein zentrales Repository
übertragen. Zu jedem Commit gehört eine 40-stellige Commit-SHA, die den
zugehörigen Entwicklungsstand samt Historie zu einem bestimmten Zeitpunkt
eindeutig identifiziert und damit am ehesten einer SVN-Revision entspricht.
Technisch ist ein Branch in Git ein Zeiger auf einen Commit. Beim Push eines
Branches nach GitHub werden sämtliche fehlenden Commits dorthin übertragen und
der Branch in GitHub auf den dann aktuellsten Commit *verschoben*.

Jeder Entwicklungsauftrag (Änderung, Erweiterung, Korrektur, ...) wird als
Feature in einem eigenen temporären Feature-Branch umgesetzt. Wenn ein Feature
fertig entwickelt und getestet wurde, kann ein PR (Pull Request) angelegt
werden, um es in einen Zielbranch wie z.B. `main` zu übernehmen. Der Pull
Request muss dazu in GitHub nach dem 4-Augenprinzip geprüft und freigegeben
werden, da Release-Branches und main generell geschützte Branches sind. Wenn
das passiert ist, werden die Änderungen des Feature-Branches per Squash Merge
in den Zielbranch übernommen. Dabei entsteht ein neuer Stand und somit auch ein
neuer Commit.

Wird ein Feature-Branch nach GitHub gepusht, werden seine M/Text-Projekte
automatisch mit der M/Text-Entwicklungsumgebung synchronisiert, damit das
Feature vom Entwickler dort vorab getestet werden kann. Ein Merge nach `main`
oder `release/nnn` synchronisiert in der Folge automatisch die entsprechende
M/Text-Funktionstestumgebung. Dort soll das Feature dann von der LBS getestet
und fachlich freigegeben werden. Danach kann der Feature-Branch wieder gelöscht
werden.

Eine Mainframe-Lieferung kann entweder auf `main` oder `release/nnn`
durchgeführt werden und verwendet dann dessen vollständigen Stand, oder auf
einer in `bereitstellung/nnn.nnn` zusammengestellten Teillieferung. Ein
Vorbereitungs-Workflow hält Branch, Commit-SHA und Lieferumfang fest und
zeigt sie in einem Freigabe-Issue. Der Freigabekommentar startet anschließend
Paketbau und Mainframe-Übergabe. Nach erfolgreicher Übergabe entsteht der
Liefer-Tag.

Die **M/Workbench** ist dabei das zentrale Arbeitsmittel für die Bearbeitung
der M/Text-Ressourcen und die Arbeit mit Git über das Eclipse-Plugin `EGit`.
Dieses Plugin erlaubt dem Anwender lokale Branches und Commits zu verwalten und
mit GitHub bzw. M/Text zu synchronisieren.

#### Änderungsablauf

```text
Ressourcen in M/Workbench auf lokalem Feature-Branch bearbeiten (feature/nnn/<Bezeichnung>)
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
Lieferung vorbereiten
    │ Branch auswählen (bereitstellung/nnn.nnn, release/nnn oder main)
    ▼
Freigabe-Issue prüfen
    │ /freigabe
    ▼
Paketbau, Mainframe-Übergabe und Liefer-Tag
```

### Entscheidungen und Nutzen

| Entscheidung | Nutzen |
|---|---|
| GitHub Actions statt Jenkins | Moderne Workflows in der dafür vorgesehenen zentralen Oberfläche, in der auch das Repository liegt. |
| Branches nach dem organisationsweiten Leitfaden | `main`, Release- und Feature-Branches bilden Entwicklung und Wartung gut ab. Pull Requests erhöhen Sicherheit und Transparenz und sind GitHub-native. |
| Feature-Push nach M/Text-Entwicklung | Eine Änderung kann vor dem Pull Request vom Entwickler getestet werden. |
| Pull Request mit Squash Merge | Jeder Pull Request wird als ein fachlicher Commit in den Zielbranch übernommen und kann später Cherry-Picked werden (entspricht bisherigem Merge-Verfahren). Review und Arbeitscommits bleiben im Pull Request sichtbar. |
| Nachvollziehbare Lieferfreigabe | Ein Issue ist der zentrale Henkel für alle Informationen und Schritte, die zu einer Mainframe-Lieferung gehören. |

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
Release-Branch. Eine zweite Person prüft die Änderung und gibt sie idealerweise
frei. Danach wird der Pull Request mittels Squash Merge im Zielbranch
zusammengeführt.

In den Repository-Einstellungen soll `Allow squash merging` als einziges
Mergeverfahren aktiviert sein, damit alle Beteiligten denselben Bedienweg
verwenden.

Squash Merge wird aus folgenden Gründen verwendet:

- Aus allen Änderungen eines Pull Requests wird ein fachlich zusammengehöriger
  Einzel-Commit
- Der lineare Verlauf ist für wenig erfahrene Git-Anwender gut nachvollziehbar
- Squash-Commit kann bei Bedarf zurückgenommen oder mittels Cherry-Pick auf
  eine weitere Releaselinie übernommen werden
- Review, Diskussion und ursprüngliche Commits bleiben im Pull Request
  nachvollziehbar

### Wechsel der führenden Releaselinie

Die produktive Releaselinie wechselt mit jedem OSPlus-Release, also zweimal im
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
en01.ltom[a|s].intern   M/Text-Entwicklung
fu01.ltom[a|s].intern   M/Text-Funktionstest
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

Anders als im alten SVN Ablauf verwenden wir nun für Synchronisierung und
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

#### Informationsdaten der Synchronisierung

Bei der Synchronisierung via LTOMA stehen die Informationsdaten zu jedem
Archiv im initialen POST-Body. Sie legen den Umfang der hochzuladenden
Archive fest. `scope.von` (nur bei DELTA relevant) bezeichnet den Ausgangsstand
und `scope.bis` den zu synchronisierenden Ziel-Stand. `referenz` nennt den
Branch, `commit` die zugehörige Commit-SHA und `sha256` die Prüfsumme des
Archivs.

Bei FULL baut der Workflow das F-Archiv aus dem vollständigen
Projektverzeichnis. Bei DELTA ermittelt
er die geänderten und gelöschten Projektdateien aus dem Git-Vergleich und baut
daraus das D-Archiv samt Löschliste. Die Elementliste dient dem Paketbau. Der
POST-Body enthält sie nicht. Die Löschliste enthält die gelöschten Pfade mit
vorangestelltem Projektnamen, damit das Format mit dem bestehenden
Travic-Link-Folgeskript kompatibel bleibt.

Beispiel:

```json
{
  "projekt": "LOMS_Basis",
  "lieferart": "FULL",
  "scope": {
    "bis": {
      "referenz": "release/270",
      "commit": "..."
    }
  },
  "sha256": "..."
}
```

Bei Mainframe-Lieferungen stehen Abweichungen gegenüber dem vorherigen
Liefer-Tag und der tatsächliche Archivumfang im Freigabe-Issue. DELTA-Archive
und ihre Löschlisten beziehen sich auf den zugehörigen `.100`-Tag. Sie enthalten
die Änderungen seit diesem Hauptrelease bis zum aktuellen Liefer-Tag.

### Transport der Synchronisierungsaufträge

Vor dem Archivbau prüft der Workflow die Erreichbarkeit des Adapters über
`GET /vMtextAdapter/version`. Schlägt der Aufruf fehl, endet der Lauf mit
`ADAPTER_FAILED`. Beim Linienwechsel werden beide Zieladapter vorab geprüft.

Adapter und M/Text teilen sich den gemeinsamen Pfad `serverSync/` (ehemals ein
NFS Share im EN4920). Dieser enthält die Projektverzeichnisse aller Mandanten
und bildet wie im alten Ablauf die Basis der M/Text-Synchronisierung. Der
Workflow überträgt die zusammengestellten Archive und ihre Informationen
einzeln per HTTP PUT an LTOMA. Ein Synchronisierungsauftrag umfasst alle
Archive, die mit einer M/Text-Umgebung synchronisiert werden sollen.

Für einen neuen Auftrag gilt folgender Ablauf:

1. Der Workflow bildet die Auftrags-ID als
   `<GITHUB_RUN_ID>-<Mandantenkürzel>` und initiiert darunter einen Auftrag via
   POST-Request an LTOMA. Im POST-Body kündigt er alle Archive und deren
   Prüfsummen an. Der Adapter antwortet mit der Auftrags-ID und dem Status
   `ready`.
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
   M/Text-Synchronisierung ausführen. Andere Mandanten dürfen parallel
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
   die Ressourcen-Cache-Aktualisierung entsteht, wird an den Workflow
   übermittelt und als Laufartefakt `mtext-ergebnis` bereitgestellt.
   Die Laufzusammenfassung verweist auf das Artefakt.
6. Danach sendet der Workflow HTTP-DELETE. Der Adapter entfernt den Auftrag,
   die Upload-Dateien und ein gegebenenfalls verwendetes temporäres
   Arbeitsverzeichnis.

Vor dem Archivbau sucht der Workflow mit
`GET /vMtextAdapter/sync2/{auftrag_id}` nach einem bestehenden Auftrag. Die
Auftrags-ID bleibt beim Wiederholen desselben GitHub-Laufs erhalten. Antwortet
der Adapter mit HTTP 404, baut der Workflow die Archive und startet den
beschriebenen Ablauf.

Besteht der Auftrag bereits in `processing`, wartet der Workflow auf dessen
Abschluss. Bei `succeeded` übernimmt er das Ergebnis und räumt den Auftrag
auf. In beiden Fällen entfallen Archivbau und Uploads. Einen Auftrag in
`ready`, `uploading` oder `failed` löscht er und startet mit neu gebauten
Archiven unter derselben Auftrags-ID erneut, da bei so einem Status ein
Zustand vorliegt, der nicht einfach repariert werden kann.

Ein neuer GitHub-Lauf verwendet eine neue Auftrags-ID und bildet sein
DELTA ab dem letzten erfolgreichen Lauf desselben Branches. Dadurch schließt
er die noch nicht erfolgreich synchronisierten Änderungen ein. Wenn durch
Überholer-Situationen oder Abbrüche und Neustarts korrupte Stände in
`serverSync/` entstehen sollten, ist eine manuelle Volllieferung durchzuführen.
Die Auftragsdaten im Adapter überleben keinen Neustart.

Die Laufzusammenfassung verlinkt den synchronisierten Git-Stand. Bei DELTA
verlinkt sie auch den Ausgangsstand und den Vergleich beider Commits. Bei FULL
zeigen die Projektverzeichnisse im Zielstand den Archivinhalt. Bei DELTA zeigt
der Vergleich die Änderungen, aus denen die Projektarchive und Löschlisten
entstehen. Er umfasst auch Änderungen außerhalb dieser Projekte. Eine
gesonderte Elementliste wird für Synchronisierungen nicht aufbewahrt. Liegt
eine M/Text-Ausgabe vor, wird sie in das Laufartefakt `mtext-ergebnis`
übernommen.

### Erfolg und Reihenfolge aufeinanderfolgender Synchronisierungen

Ein DELTA liefert die Änderungen seit dem letzten erfolgreichen Sync-Lauf
desselben Branches. Damit umfassen die D-Archive auch Änderungen
zwischenzeitlich ausgefallener Läufe. Auf `main` bestimmt ein Push zusätzlich,
ob ein Releaselinienwechsel noch den FULL-Abgleich beider Umgebungen erfordert.

Mehrere Synchronisierungsläufe können gleichzeitig ausgeführt werden.
Fachliche Abhängigkeiten liegen dabei in der Verantwortung der Benutzer. Der
Adapter verarbeitet Aufträge unter dem Lock nacheinander.

## 4. Mainframe-Lieferung

Die Mainframe-Lieferung verwendet dasselbe Archivformat wie die
Synchronisierung, aber einen anderen Transportweg über CodePipeline der IZE9,
MT91 und letztlich im Batch via LXT90#SV, Travic-Link und dessen Folgejob
(`ressourcen_aktualisieren.sh`).

### Liefer-Tags und Lieferstand

Liefer-Tags werden für die Lieferung an CodePipeline genutzt, also nicht für
Releases im Sinne des FI-Leitfadens, daher folgen sie bei uns dem Muster
`rnnn.nnn`, beispielsweise `r261.100` oder `r261.108` und nutzen nicht den
Präfix 'v' für geschützte OSPlus-Releases. Dies erleichtert den Lieferprozess
etwas, da geschützte Tags nur auf geschützten Branches erlaubt sind, was für
Teillieferungen unpraktisch ist.

Für eine Teillieferung wird ein ungeschützter Branch `bereitstellung/nnn.nnn`
zusammengestellt. Als Ausgangspunkt bietet sich der vorherige Liefer-Tag der
Releaselinie an: Sein Stand enthält die bereits gelieferten Änderungen, weitere
ausgewählte Squash-Commits werden mit EGit cherry-gepickt. Ein Ausgangspunkt
auf `main` oder `release/nnn` ist ebenfalls möglich. Dann gehört dessen
gesamter Stand zur Lieferung. Für ein DELTA muss der `.100`-Tag der
Releaselinie ein Vorfahr des vorbereiteten Commits sein.

Für den Vergleich im Freigabe-Issue ist der vorherige Liefer-Tag der höchste
vorhandene Liefer-Tag mit kleinerer Tag-Nummer. Sein Commit muss kein Vorfahr
des Bereitstellungsbranches sein. Dieser Vergleich bestimmt nicht den
Archivinhalt.

Bei der Verarbeitung einer Mainframe-Lieferung wird (aktuell und wie bisher)
zuerst das F-Archiv und danach das D-Archiv entpackt. Die Archive bleiben
erhalten und werden durch neue Lieferungen überschrieben. Ein Zwischenrelease
ersetzt das D-Archiv, während das F-Archiv den Stand der `.100`-Lieferung
behält. Das DELTA enthält deshalb kumulativ die Änderungen zwischen `.100` und
dem aktuellen Liefer-Tag, damit FULL und aktuelles DELTA zusammen den
Lieferstand ergeben.

Anders als im bisherigen SVN Ablauf startet ein Tag-Push keine Übertragung - es
müssen die vorgesehenen Workflows genutzt werden:

### Lieferung vorbereiten

Der Workflow **Lieferung vorbereiten** wird manuell für den ausgewählten Branch
gestartet. Er leitet den Liefer-Tag aus dem Branch ab und prüft, ob der Tag noch
frei ist. `main` und `release/nnn` ergeben `rnnn.100`.
`bereitstellung/nnn.nnn` ergibt `rnnn.nnn`.

Das dabei entstehende Freigabe-Issue zeigt Branch, Abweichungen gegenüber dem
vorherigen Liefer-Tag und vorgesehenen Lieferumfang. Der Liefer-Tag steht im
Titel, Branch und Commit-SHA im Text. Die Laufzusammenfassung verweist darauf.

Sollte auffallen, dass etwas mit der Lieferung fachlich noch nicht stimmt, ist
der Branch zu korrigieren und der Workflow erneut zu starten. Dabei entsteht
ein neues Freigabe-Issue.

### Lieferung freigeben und ausführen

Das mit `lieferung:vorbereitet` gekennzeichnete Freigabe-Issue zeigt den Stand,
der geliefert werden soll. Eine Person mit Repository-Berechtigung `maintain`
(oder `admin`) startet die Lieferung mit dem Kommentar `/freigabe`. Die
vorbereitende Person darf die Lieferung selbst freigeben. Der Workflow liest
den Liefer-Tag aus dem Titel und die Commit-SHA aus dem Text. Die Commit-Zeile
muss eindeutig sein. Bei der ersten gültigen Freigabe wechselt das Label von
`lieferung:vorbereitet` zu
`lieferung:gestartet`, bevor die Lieferdateien erstellt werden. Nach
erfolgreichem Abschluss ersetzt `lieferung:abgeschlossen` das Label
`lieferung:gestartet`, bevor das Issue geschlossen wird. Danach kann mittels
`/freigabe`-Kommentar aus diesem Issue keine Lieferung mehr erfolgen. Mit
/wiederholung kann die Lieferung allerdings erneut durchgeführt werden.

Durch `/freigabe` wird ein Shared Workflow aus `mtext_actions` aufgerufen, der den
Paketbau, die Mainframe-Übergabe und die Tag-Erzeugung in aufeinanderfolgenden
Jobs ausführt. Der Paketbau verwendet die festgehaltene Commit-SHA und stellt
alle an den Mainframe übergebenen Dateien (.tgz und .jcl) im Laufartefakt
`release` bereit, so dass diese innerhalb der nächsten 30 Tage ggf.
kontrolliert werden können. Der Übergabejob liest das Artefakt, überträgt die
Archive an den Mainframe und reicht die JCL ein. Danach erzeugt der Workflow
den Liefer-Tag. Es wird eine Annotation am Tag erzeugt, um das zugehörige
Freigabe-Issue zu referenzieren. Anschließend wird ein Abschlusskommentar im
Issue erzeugt, der zum Tag verlinkt und die Namen und SHA-256-Prüfsummen der
übertragenen Archivdateien auflistet, und das Issue geschlossen.

#### Mainframe-Übergabe

Die IZE9 unterstützt FTPS ohne Client-Zertifikat. Diesen Betriebsweg verwendet
der Client mit technischem Benutzer und Passwort. Er prüft das
Serverzertifikat nicht und benötigt daher weder ein hinterlegtes
Zertifikat noch den Truststore des Runners. Damit sind Steuerungs- und passive
Datenverbindungen verschlüsselt, auch wenn die Identität der Gegenstelle
nicht bestätigt wird. Der Client überträgt jedes Archiv zunächst unter seinem
Membernamen in `IEA.LOMS.TONICZ`. Nach jedem Archiv-Upload schaltet er mit
`SITE FILETYPE=JES` auf die Jobübergabe um und reicht die für dieses Archiv aus
`templates/mainframe-upload.jcl` erzeugte JCL als eigenen Job ein. Dieser
Mainframe-Job kopiert das Member dann nach `IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ`
und registriert es in CodePipeline.

Übergaben desselben Mandanten werden nacheinander ausgeführt. Verschiedene
Mandanten können gleichzeitig liefern.

#### Mainframe-Zugangsdaten

Host, Port und technischer User sind in `mtext_actions` festgelegt. Das
Passwort soll auf Ebene der GitHub-Organisation verwaltet und für die
vorgesehenen Mandanten-Repositories freigegeben werden und steht dann in
Mandanten-Workflows unter `secrets.IZE9_FTPS_PASSWORD_MTEXT` zur Verfügung.

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
Git-Repositories. Elemente, die gar nicht von Git verwaltet werden sollen,
werden wie üblich in `.gitignore` eingetragen.

### Repository für Shared Workflows und Action `mtext_actions`

Im Mandanten-Repository stehen nur Trigger-Workflows. Die eigentlichen
Arbeitsschritte liegen in `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Die
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
      project_packages.py
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
mit den M/Text-Projekten versioniert. Beispiel für den Block `mandant`:

```json
{
  "mandant": {
    "kuerzel": "FI",
    "releaselinie": "270",
    "ispw": "P",
    "dry_run": true,
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

`ispw` bezeichnet die CodePipeline-Instanz `T` oder `P`. Projektverzeichnisse
in `excluded_projects` bleiben bei Prüfung, Synchronisierung und Paketbau
außen vor. `hostprofile` ordnet jedem Hostprofil ein Assignment und eine
CodePipeline-Stage zu.

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

`config/ressourcenformate.json` wird für die Ressourcenprüfung genutzt, um
Dateiendungen einem Prüfverfahren zuzuordnen, da Tonic-Elemente verschiedenste
Endungen haben können, unabhängig von ihrem wahren Dateityp. Dateien, deren
Endung zu keinem Eintrag oder Glob-Muster in `ressourcenformate.json` passt,
werden nicht geprüft. Wenn Node.js auf dem Runner verfügbar ist, kann auch
JavaScript geprüft werden. Dies wird dynamisch ermittelt.

## 7. Workflows

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Trigger-Workflow | Shared Workflow | Python-Skript |
|---|---|---|---|---|
| Ressourcen prüfen | Manueller Start auf einem ausgewählten Branch | `check-resources.yml` | `shared-check-resources.yml` | `mtext.py resources check` |
| M/Text-Entwicklung synchronisieren | Push auf `feature/nnn/<Bezeichnung>` oder manueller Start | `sync-resources.yml` | `shared-check-resources.yml`, danach `shared-sync-resources.yml` | `mtext.py resources check`, danach `mtext.py resources sync` |
| M/Text-Funktionstest synchronisieren | Push oder Merge auf `main` oder `release/nnn` sowie manueller Start | `sync-resources.yml` | `shared-check-resources.yml`, danach `shared-sync-resources.yml` | `mtext.py resources check`, danach `mtext.py resources sync` |
| Lieferung vorbereiten | Manueller Start auf `main`, `release/nnn` oder `bereitstellung/nnn.nnn` | `lieferung-vorbereiten.yml` | `shared-check-resources.yml`, danach `shared-lieferung-check.yml` | `mtext.py resources check`, danach `mtext.py delivery check` |
| Lieferung freigeben | Kommentar `/freigabe` im offenen Freigabe-Issue durch eine Person mit `maintain` oder `admin` | `lieferung-ausfuehren.yml` | `shared-lieferung-ausfuehren.yml` | `mtext.py delivery resolve` |
| Testlieferung ausführen | Manueller Start mit der Nummer des Freigabe-Issues | `lieferung-testen.yml` | `shared-lieferung-ausfuehren.yml@test` | `mtext.py delivery resolve` |
| Verwendete Freigabe melden | Weiterer Kommentar `/freigabe` in einem Issue mit `lieferung:gestartet` oder `lieferung:abgeschlossen` | `lieferung-ausfuehren.yml`, Job `freigabe-hinweis` | keiner | keiner, Issue-Kommentar per `curl` |
| Lieferung wiederholen | Kommentar `/wiederholung` in einem Issue mit `lieferung:gestartet` oder `lieferung:abgeschlossen` | `lieferung-ausfuehren.yml` | `shared-lieferung-ausfuehren.yml` | `mtext.py delivery resolve` |
| Lieferung bauen und übertragen | Vorbereitete SHA oder vorhandener Liefer-Tag | `lieferung-ausfuehren.yml` oder `lieferung-testen.yml` | `shared-lieferung-ausfuehren.yml` | `mtext.py release build`, `release mainframe`, bei Erstlieferung `delivery tag`, danach `delivery complete` |
| `mtext_actions` testen | Pull Request, Push auf `main` oder manueller Start in `mtext_actions` | keiner | `ci.yml` | `python -m unittest discover` |

### Shared Workflows

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `shared-check-resources.yml` | Aufruf durch `check-resources.yml`, `sync-resources.yml` oder `lieferung-vorbereiten.yml` | Mandantenkonfiguration und konfigurierte Ressourcen ohne Zugriff auf Zielsysteme prüfen |
| `shared-sync-resources.yml` | Aufruf durch `sync-resources.yml` | Projekte nach M/Text übertragen |
| `shared-lieferung-check.yml` | Aufruf durch `lieferung-vorbereiten.yml` | Liefer-Tag aus dem Branch ableiten und Lieferumfang im Freigabe-Issue anzeigen |
| `shared-lieferung-ausfuehren.yml` | Aufruf durch `lieferung-ausfuehren.yml` oder `lieferung-testen.yml` | Freigabe und Lieferstand prüfen, Archive und JCL für FULL oder DELTA erzeugen, an den Mainframe übertragen, den angenommenen Stand taggen und das Ergebnis im Freigabe-Issue festhalten |
| `ci.yml` | Pull Request oder Push auf `main` oder manueller Start | Tests ausführen |

Die Testlieferung ruft den Shared Workflow und dessen Implementierung vom
Branch `test` auf. Alle regulären Lieferungen verwenden `main`.

Die Shared Workflows werden direkt in einen Mandantenlauf eingebunden. Die
Python-Implementierung wird als Action aus `mtext_actions` geladen. Die
Repositoryfreigabe in `FinanzInformatik` erlaubt GitHub das Laden dieser
gemeinsamen Komponenten ohne eigenes Zugriffstoken.

GitHub stellt jedem Job automatisch einen zeitlich begrenzten Zugangsschlüssel
namens `GITHUB_TOKEN` bereit. Damit kann der Job auf das Mandanten-Repository
zugreifen, etwa um Freigabe-Issues zu lesen und anzulegen oder Liefer-Tags zu
erstellen. Die erlaubten Aktionen werden über `permissions` in den
Workflow-Dateien festgelegt.

Auch der aufgerufene Shared Workflow arbeitet mit diesem Zugang zum
Mandanten-Repository. Er gehört zum selben Lauf und verwendet die vom
aufrufenden Workflow gewährten Rechte. Liefer-Tag und Freigabe-Issue entstehen
daher im Mandanten-Repository.

### Status und Fehlercodes

Die Workflows melden mit einem festen Status, was erreicht wurde oder an
welcher Stelle sie abgebrochen sind. Bei Fehlern endet das Programm außerdem
mit dem zugehörigen Exitcode.

| Status | Bedeutung | Exitcode bei Fehlern |
|---|---|---|
| `RESOURCE_CHECKED` | Die konfigurierten Ressourcen wurden geprüft, Befunde stehen als Warnungen bereit | – |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig | `2` |
| `LIEFERSTAND_ERMITTELT` | Der Lieferstand für Freigabe oder Wiederholung wurde ermittelt | – |
| `LIEFERUNG_CHECKED` | Branch, Commit-SHA und Lieferumfang wurden im Freigabe-Issue festgehalten | – |
| `LIEFERUNG_TAGGED` | Der Liefer-Tag wurde auf der festgehaltenen SHA mit Freigabe-Issue-Zuordnung erstellt | – |
| `LIEFERUNG_ABGESCHLOSSEN` | Der erfolgreiche Lauf wurde im geschlossenen Freigabe-Issue festgehalten | – |
| `LIEFERUNG_NICHT_ABGESCHLOSSEN` | Der nicht abgeschlossene Lauf wurde im offenen Freigabe-Issue festgehalten | – |
| `SOURCE_FAILED` | Checkout, Commit, Branch oder Tag können nicht als Quelle verwendet werden | `3` |
| `ADAPTER_FAILED` | Adapteraufruf oder M/Text-Synchronisierung sind fehlgeschlagen | `6` |
| `ADAPTER_COMPLETED` | Der M/Text-Adapter hat die Synchronisierung erfolgreich abgeschlossen | – |
| `ADAPTER_SKIPPED` | Adapterauftrag und Archivübertragung wurden übersprungen und eine erfolgreiche M/Text-Antwort simuliert | – |
| `PACKAGE_FAILED` | Archiv oder JCL konnten nicht erstellt oder verwendet werden | `4` |
| `ARTIFACT_READY` | Archive und JCL wurden erstellt | – |
| `MAINFRAME_TRANSFER_FAILED` | Die FTPS- oder JES-Übergabe ist fehlgeschlagen | `7` |
| `MAINFRAME_SUBMITTED` | Archive und JCL wurden per FTPS und JES übergeben | – |
| `MAINFRAME_SKIPPED` | FTPS- und JES-Übergabe wurden im Dry Run übersprungen | – |
| `FREIGABE_FAILED` | Freigabe-Issue, Label oder Repository-Rolle konnten nicht über GitHub verarbeitet werden | `9` |
