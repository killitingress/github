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
Konfigurationsdatei. Die zentral genutzte CI/CD-Automatisierung wird im
Folgenden `mtext_actions` genannt. Sie führt Validierungen, Synchronisierung,
Paketbau und Übergabe an den Mainframe (IZE9) durch. Der aktuelle Entwurf
verwendet dafür `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Die
endgültige Organization und der Repositoryname sind noch mit den GitHub-Admins
zu klären.

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
Request muss dazu im 4-Augenprinzip geprüft und freigegeben werden. Wenn das
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
Ein zweiter manueller Workflow bestätigt diesen Stand und startet Tag-Erzeugung,
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
Lieferumfang prüfen
    │ Lieferung mit demselben geplanten Liefer-Tag ausführen
    ▼
Liefer-Tag, Paketbau und Mainframe-Übergabe durch mtext_actions
```

### Entscheidungen und Nutzen

| Entscheidung | Nutzen |
|---|---|
| Branches nach dem organisationsweiten Leitfaden | `main`, Release- und Feature-Branches bilden Entwicklung und Wartung gut ab. Pull Requests bedeuten natives 4-Augenprinzip. |
| Feature-Push nach M/Text-Entwicklung | Eine Änderung kann vor dem Pull Request vom Entwickler getestet werden. Parallelentwicklungen mehrerer Entwickler werden unterstützt. |
| Pull Request mit Squash Merge | Jeder Pull Request wird als ein fachlicher Commit in den Zielbranch übernommen. Review und Arbeitscommits bleiben im Pull Request sichtbar. |
| GitHub Actions statt Jenkins | Natives Git-Feeling mit modernen Workflows in einem zentralen Tool. |
| Gemeinsames Lieferpaket-Format | Synchronisation und Mainframe-Lieferung verwenden das gleiche Paketformat auf unterschiedlichen Transportwegen. |
| Zweistufige Lieferbestätigung | Die Vorbereitung zeigt den festgehaltenen Stand vor der Lieferung. Eine andere Person erfüllt das empfohlene Vier-Augenprinzip. Dieselbe Person muss eine Direktlieferung als Abweichung bewusst bestätigen. |
| Freigegebene CI/CD-Version | `main` in `mtext_actions` enthält die freigegebene Version. Alle Mandanten verwenden diesen Stand bei ihren nächsten Workflow-Läufen. |
| Zentrale Mainframe-Zugangsdaten | Mandanten-Repositories benötigen keine Mainframe-Zugangsdaten. |

## 2. Branch- und Pull-Request-Modell

Wir orientieren uns am FI-Leitfaden zu Branches und Tags in Git:

- `main` ist der geschützte, dauerhafte Branch der produktiven Releaselinie
- `release/nnn` enthält eine parallel gepflegte vorherige oder kommende
  Releaselinie, zum Beispiel `release/260` oder `release/270`
- Jede Änderung entsteht in einem Branch `feature/nnn/<Bezeichnung>`
- Änderungen an `main` und `release/nnn` erfolgen ausschließlich über Pull Requests
- Pull Requests werden nach Freigabe im 4-Augenprinzip mit Squash Merge zusammengeführt
- Liefer-Tags folgen dem Muster `rnnn.nnn`

### Branches

| Branch | Zweck | Schutz und Lebensdauer |
|---|---|---|
| `main` | Produktive Releaselinie und ihr Abnahmestand | Dauerhaft, Default Branch, geschützt, Änderung über Pull Request |
| `release/nnn` | Parallel gepflegte vorherige oder kommende Releaselinie und ihr Abnahmestand | Geschützt, Änderung über Pull Request, nach Ende der Pflege löschbar |
| `feature/nnn/<Bezeichnung>` | Eine fachlich zusammengehörige Änderung für die genannte Releaselinie | Temporär, nach dem Merge löschbar |
| `bereitstellung/nnn.nnn` | Ausgewählte Squash-Commits für eine Teillieferung | Temporär, nach der Tag-Erzeugung löschbar |

Beispiele für Feature-Branches sind:

```text
feature/261/issue-5678
feature/270/neuer-brief
```

Der Bezeichnungsteil eines Feature-Branches darf weitere Pfadsegmente
enthalten, beispielsweise `feature/270/briefe/anschreiben`.

Ein Feature-Branch beginnt auf dem geschützten Branch, in dem seine
Releaselinie gepflegt wird:

- Für die produktive Releaselinie ist `main` der Zielbranch
- Für die vorherige und die kommende Releaselinie ist `release/nnn` der
  Zielbranch

Damit können Änderungen für die kommende Releaselinie bereits zusammengeführt
und in M/Text-Funktionstest abgenommen werden.

### Pull Requests und Squash Merge

Wenn eine Änderung fertig entwickelt und in M/Text-Entwicklung geprüft ist,
erstellt der Entwickler einen Pull Request auf `main` oder den passenden
Release-Branch. Eine zweite Person prüft die Änderung und gibt sie idealer
Weise frei. Danach wird der Pull Request mittels Squash Merge im Zielbranch
zusammengeführt.

In den Repository-Einstellungen ist `Allow squash merging` aktiviert. Die
anderen Mergeverfahren sind deaktiviert, damit alle Beteiligten denselben
Bedienweg verwenden.

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

Die Zielpräfixe und Releaselinien sind gemeinsam versioniert.
M/Text-Entwicklung verwendet das Präfix `en`, M/Text-Funktionstest das Präfix
`fu`. Das Feld `etaps_linie` enthält den Zahlenteil der technischen Linie.
Präfix und Zahlenteil bilden die Umgebungskennung, beispielsweise `en` und
`01` die Kennung `en01`.

M/Text ist unter `<Umgebungskennung>.ltoms.intern` erreichbar. Der
Synchronisationsadapter derselben Umgebung wird unter
`<Umgebungskennung>.ltoma.intern/vMtextAdapter/sync` aufgerufen.

Die Zuordnung wird zentral in `mtext_actions/config/releaselinien.json`
gepflegt. Die derzeit vorgesehene rollierende Zuordnung lautet:

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

### Projektpakete und Lieferarten

Synchronisation und Mainframe-Lieferung verwenden dasselbe Paketformat. Wie im bisherigen
Jenkins-Ablauf gibt es zwei Archivtypen. Ein F-Archiv enthält den vollständigen
Projektbaum eines Tonic-(Fragment-)Projekts. Ein D-Archiv enthält neue und
geänderte Dateien sowie eine Löschliste. Beide sind gzip-komprimierte
TAR-Dateien mit der Endung `.tgz`.

| Lieferart | Inhalt | Vergleichsstand und Verwendung |
|---|---|---|
| FULL | F-Archiv mit dem vollständigen Projektbaum und leeres D-Archiv | Ohne Vergleichsstand. Für die initiale Synchronisation eines dauerhaften Branchs, den Wechsel der produktiven Releaselinie, den manuellen Vollabgleich und Lieferungen mit der Versionsnummer `100` |
| DELTA | D-Archiv mit neuen und geänderten Dateien sowie einer Löschliste | Bei einem Feature-Push zwischen Ausgangsstand und Feature-Commit, danach zwischen vorherigem und neuem Commit des Feature-Branches. Bei der Mainframe-Lieferung kumulativ zwischen dem `.100`-Tag und dem Liefer-Tag |

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

Eine Voll-Lieferung (FULL) besteht aus dem F-Archiv und einem leeren D-Archiv.
Bei der Übernahme wird zuerst das F-Archiv und anschließend das leere D-Archiv
verarbeitet. Bei der Mainframe-Übergabe ersetzt das leere D-Archiv das
gleichnamige D-Archiv einer früheren Lieferung. Dadurch kann ein vorheriges
DELTA den neuen FULL-Stand nicht wieder verändern. Eine Delta-Lieferung (DELTA)
besteht aus dem D-Archiv.

Der Archivname besteht aus Mandantenkürzel, Projektcode und `F` oder `D`. Bei
der Mainframe-Lieferung ist der Name ohne `.tgz` zugleich das Mainframe-Member
(siehe Kapitel "CodePipeline-Elemente").

Neben den Archiven liegt für jedes Projekt eine JSON-Informationsdatei
`_INFO_<Mandantenkürzel>-<Projekt>.json`, zum Beispiel
`_INFO_FI-LOMS_Basis.json`. Sie entspricht inhaltlich den bisherigen
Info-Dateien in trans/, ist aber technisch verarbeitbar und einheitlich
aufgebaut:

```json
{
  "projekt": "LOMS_Basis",
  "stand": {
    "von": {
      "referenz": "r261.100",
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
  "sha256": {
    "D": "..."
  }
}
```

`von` entfällt bei FULL und bezeichnet bei DELTA den Vergleichsstand. `bis`
bezeichnet den paketierten Zielstand. `elemente` enthält Git-Status und
projektbezogenen Pfad mit den Statuswerten `A` (hinzugefügt), `M` (geändert),
`D` (gelöscht) und `T` (Typ geändert). Bei einem FULL werden die enthaltenen
Dateien mit `A` aufgeführt. Die Schlüssel `F` und `D` unter `sha256` bezeichnen
die vorhandenen Archive.

Mandant und Repository ergeben sich aus dem Mandanten-Repository und dem
Übergabeauftrag. Sie werden in der projektbezogenen Informationsdatei nicht
wiederholt. Die Informationsdatei liegt neben den Archiven, damit sie deren
SHA-256-Prüfsummen enthalten kann.

### Transport nach `serverSync`

Der Transportweg auf das bisher per NFS angesprochene Verzeichnis für die
Synchronisation von M/Text (`serverSync`) ist noch zu klären. Verschiedene
Möglichkeiten kommen infrage. In jedem Fall würden zuvor zusammengestellte
Projektpakete und Informationsdateien übergeben:

- NFS- oder CIFS-Share, der im Runner eingebunden ist und direkt beschrieben
  werden kann
- Upload per POST-Request an LTOMA
- Download eines passenden GitHub-Actions-Artefakts durch LTOMA
- weitere noch zu klärende Möglichkeit

Die weitere Verarbeitung bleibt im Idealfall wie bisher: Der `/sync`-Endpunkt
des Adapters wird aufgerufen und startet intern den
M/Text-Synchronisierungsprozess.

## 4. Mainframe-Lieferung

Die Mainframe-Lieferung verwendet dasselbe Paketformat wie die
M/Text-Synchronisierung, aber einen anderen Transportweg über CodePipeline der
IZE9, MT91 und letztlich im Batch via LXT90#SV, Travic-Link und dem Folgejob
`ressourcen_aktualisieren.sh`. Sie ist kein Release im Sinne des
organisationsweiten Git-Leitfadens.

### Liefer-Tags und Lieferstand

Liefer-Tags folgen dem Muster `rnnn.nnn`, beispielsweise `r261.100` oder
`r261.108`. Die Versionsnummer `.100` bezeichnet das FULL einer Releaselinie.
Der Tag entsteht auf dem vollständigen Stand von `main` oder `release/nnn`.
Jede spätere Version derselben Releaselinie erzeugt wie im bisherigen
Lieferprinzip ein kumulatives DELTA gegen `.100`.

Entspricht der gewünschte Lieferstand dem aktuellen Stand von `main` oder
`release/nnn`, wird dieser Branch vorbereitet. Für eine Teillieferung entsteht
`bereitstellung/nnn.nnn` aus dem vorherigen Liefer-Tag. Die vorgesehenen
Squash-Commits werden mit EGit auf diesen Arbeitsbranch cherry-gepickt. Der
Arbeitsbranch wird nicht nach M/Text-Funktionstest synchronisiert.

Der Workflow **Lieferung vorbereiten** hält Branch, Commit-SHA, Liefer-Tag und
Lieferumfang in einem 30 Tage aufbewahrten Laufartefakt fest. Die
Branchspitze wird danach nicht erneut als Lieferstand aufgelöst. Das Artefakt
heißt beispielsweise `r261.108-lieferungsartefakt`. Bestehen mehrere
Vorbereitungen desselben Liefer-Tags, verwendet die Ausführung die neueste noch
verfügbare Vorbereitung.

Nach der Prüfung startet eine Person **Lieferung ausführen** mit dem geplanten
Liefer-Tag. Der Mandantenlauf lädt die neueste Vorbereitung und bestimmt den
Lieferweg. Ist es die vorbereitende Person, handelt es sich um eine
Direktlieferung, die als Abweichung vom empfohlenen Vier-Augenprinzip bewusst
bestätigt werden muss. Ist es eine abweichende Person, ist dadurch das
Vier-Augenprinzip erfüllt. Der zentrale Workflow erzeugt danach den Liefer-Tag
auf der festgehaltenen SHA und startet Paketbau sowie Mainframe-Übergabe.

Die Liefer-Tags unterliegen bewusst nicht den Regeln für Release-Tags aus dem
Git-Leitfaden, da es sich um projektspezifische Tags handelt die nichts mit
OSP-E Releases zu tun haben. Ein fehlerhaft angelegter Tag kann somit gelöscht
und anschließend unter demselben geplanten Liefer-Tag korrekt vorbereitet
werden. Bei `.100` ist zu beachten, dass spätere DELTA-Lieferungen diesen
Stand als Bezugsstand verwenden. Anders als im bisherigen SVN Ablauf startet
ein Tag-Push keine Übertragung - es muss der dafür vorgesehene Workflow benutzt
werden.

### Lieferung bauen und übertragen

Der zentrale Workflow checkt den markierten Commit aus, erzeugt je Projekt die
in Kapitel 3 beschriebenen Projektpakete und überträgt sie an den Mainframe.
Die JSON-Informationsdatei bleibt beim GitHub-Artefakt und wird nicht als
Mainframe-Member übertragen.

Wird **Lieferung ausführen** mit einem vorhandenen Liefer-Tag gestartet, beginnt
die Paketbildung und Mainframe-Übergabe für diesen Stand erneut. Derselbe
Git-Stand darf mehrfach übertragen werden. Eine neue Bestätigung ist dabei
nicht erforderlich.

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
Archive, die zugehörigen JCL-Dateien und die projektbezogenen
JSON-Informationsdateien. Es wird 30 Tage aufbewahrt. Der Übergabejob überträgt
die Archive unter ihren Membernamen und reicht die zugehörige JCL ein. Die
Informationsdateien werden nicht an den Mainframe übertragen.

Schlägt die Übergabe fehl, kann derselbe Liefer-Tag erneut ausgeführt werden.
Der Paketbau und die Mainframe-Übergabe werden dabei erneut gestartet.

Nach der Mainframe-Übergabe erstellt der zentrale Workflow im
Mandanten-Repository ein GitHub Release zum vorhandenen Liefer-Tag. Die
Beschreibung nennt Liefer-Tag, Lieferart und Commit-SHA. Sie
bestätigt die technische Übergabe und enthält die JSON-Informationsdateien.
Diese dienen als Lieferbeleg. Die Bestätigung ist zuvor im
Mandanten-Repository erfolgt.

### Mainframe-Übergabe

Für die technische Vorbereitung wird angenommen, dass die IZE9 explizites FTPS
anbietet. Unter dieser Annahme werden die erzeugten F- und D-Archive zunächst
unter ihrem jeweiligen Membernamen in `IEA.LOMS.TONICZ` übertragen. Der Client
prüft das Mainframe-Zertifikat mit dem System-Vertrauensspeicher des Runners
und schützt Steuerungs- und passive Datenverbindungen mit TLS. Anschließend
kopiert die beim Paketbau aus `templates/mainframe-upload.jcl` erzeugte JCL das
Member nach `IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ` und registriert es in
CodePipeline. Dabei gelten `STRMNAME=BOAS`, `MTYPE=TONICZ` und
`MNAME=<Membername>`.

Der Paketbau ist von der Mainframe-Übergabe getrennt. Übergaben desselben
Mandanten werden nacheinander ausgeführt. Verschiedene Mandanten können
gleichzeitig liefern.

### Mainframe-Zugangsdaten

Die Mainframe-Zugangsdaten liegen im Repository `mtext_actions`:

| Name | Ablage |
|---|---|
| `MAINFRAME_FTPS_HOST` | Repositoryvariable |
| `MAINFRAME_FTPS_PORT` | Repositoryvariable |
| `MAINFRAME_FTPS_USER` | Repositoryvariable |
| `MAINFRAME_FTPS_PASSWORD` | Repository-Secret |

Der technische FTPS-Benutzer wird für die Übergaben aller Mandanten verwendet.

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
der Repositorywurzel. Sie werden synchronisiert und in Releasepakete
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

### Zentrales CI/CD-Repository `mtext_actions`

Im Mandanten-Repository stehen nur kleine Trigger-Workflows. Die eigentlichen
Arbeitsschritte liegen in `mtext_actions`. Die Trigger-Workflows verweisen auf
`main`. Dieser Branch enthält die freigegebene zentrale CI/CD-Version.

`mtext_actions` enthält die Shared Workflows, die gemeinsame Python-Anwendung,
die zentrale Releaselinien- und Mandantenzuordnung, das JCL-Template und die
Tests:

```text
mtext-actions/
  .github/
    workflows/
      ci.yml
      lieferung.yml
      release.yml
      shared-check-resources.yml
      shared-dispatch.yml
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
      config.py
      git.py
      github.py
      mainframe_release.py
      process.py
      project_package.py
      lieferung.py
      resource_check.py
      sync.py
    mtext.py
  templates/
    mainframe-upload.jcl
  tests/
    <automatisierte Tests>
```

#### Noch zu bestätigende GitHub-Vorgaben

Der aktuelle Implementierungsstand beruht auf Arbeitsannahmen, die vor dem
produktiven Rollout bestätigt oder angepasst werden müssen:

| Arbeitsannahme | Mögliche abweichende Vorgabe | Konsequenz |
|---|---|---|
| `mtext_actions` liegt unter `FinanzInformatik` | Shared Workflows müssen in einer anderen Organization liegen | Vollständige Repositoryverweise, Zugriffsfreigaben und die GitHub-Actions-Richtlinien der beteiligten Organizations müssen angepasst werden. |
| Shared Workflows, Python-Anwendung, Konfiguration und zentrale Lieferworkflows liegen gemeinsam in `mtext_actions` | In der Ziel-Organization soll ein eigenständiges Repository ausschließlich für Shared Workflows entstehen | Die Aufteilung und die gemeinsame Versionierung der Workflow- und Python-Implementierung müssen festgelegt werden. |
| Zugriffe zwischen `mtext_actions` und Mandanten-Repositories erfolgen mit PATs | Die GitHub-Admins stellen eine andere technische Identität bereit | Secret-Verträge und die Erzeugung der Zugriffstoken in den Workflows müssen angepasst werden. |

Ein Umzug des gesamten Repositorys würde die heutige gemeinsame Versionierung
beibehalten und erfordert daher voraussichtlich weniger technische Änderungen
als eine Aufteilung. Der Umzug stellt jedoch noch keine technische Identität
für die Zugriffe auf die Mandanten-Repositories bereit. Hierfür ist gesondert
zu klären, ob eine von den zuständigen Organizations verwaltete GitHub App
vorgesehen ist und in welchen Repositories sie installiert werden darf.

## 6. Workflows

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Trigger-Workflow | Zentraler Workflow | Python-Skript | Ergebnis |
|---|---|---|---|---|---|
| Mandantenkonfiguration und JSON- oder XML-Ressourcen prüfen | Pull Request oder manueller Start | `check-resources.yml` | `shared-check-resources.yml` | `mtext.py validate-config` und `mtext.py check-resources` | Konfiguration geprüft, geänderte konfigurierte Ressourcen oder gewählter Vollstand geprüft und Syntaxbefunde als nicht blockierende Warnungen angezeigt |
| M/Text-Entwicklung synchronisieren | Push auf `feature/nnn/<Bezeichnung>` oder manueller Start | `sync-resources.yml` | `shared-sync-resources.yml` | `mtext.py sync-resources` | Projekte aus dem Commit mit der M/Text-Entwicklungsumgebung synchronisieren |
| M/Text-Funktionstest synchronisieren | Push oder Merge auf `main` oder `release/nnn` sowie manueller Start | `sync-resources.yml` | `shared-sync-resources.yml` | `mtext.py sync-resources` | Projekte aus dem Commit mit der M/Text-Funktionstestumgebung synchronisieren |
| Lieferung vorbereiten | Manueller Start auf `main`, `release/nnn` oder `bereitstellung/nnn.nnn` | `lieferung-vorbereiten.yml` | `shared-lieferung-check.yml` | `mtext.py lieferung check` | SHA und Lieferumfang unter dem geplanten Liefer-Tag festgehalten |
| Lieferung ausführen | Manueller Start mit einem geplanten oder vorhandenen Liefer-Tag | `lieferung-ausfuehren.yml` | `shared-lieferung-ausfuehren.yml` → `shared-dispatch.yml` → `lieferung.yml` → `release.yml` | `mtext.py lieferung aufloesen`, bei einer Vorbereitung `mtext.py lieferung ausfuehren` und `mtext.py lieferung tag` | Vorbereitung bestätigt und erstmalige Übergabe gestartet oder vorhandener Lieferstand erneut übergeben |
| Lieferung bauen und übertragen | Aufruf durch den zentralen Lieferworkflow | `lieferung-ausfuehren.yml` | `lieferung.yml` → `release.yml` | `mtext.py build-release`, `publish-mainframe`, danach `publish-github-release` | FULL oder DELTA an den Mainframe übertragen, GitHub Release mit Lieferinformationen erstellt |
| `mtext_actions` testen | Pull Request oder Push auf `main` in `mtext_actions` | keiner | `ci.yml` | `python -m unittest discover` | Zentrale Tests ausgeführt |

### Trigger-Workflows in den Mandanten-Repositories

Die Trigger-Workflows reagieren auf Änderungen und starten die
Verarbeitung in `mtext_actions`:

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `check-resources.yml` | Pull Request oder manueller Start | Mandantenkonfiguration und geänderte konfigurierte Ressourcen oder den gewählten Vollstand prüfen, Syntaxbefunde als Warnungen anzeigen |
| `lieferung-vorbereiten.yml` | Manueller Start auf dem ausgewählten Branch | SHA und Lieferumfang unter dem geplanten Liefer-Tag festhalten |
| `lieferung-ausfuehren.yml` | Manueller Start mit einem geplanten oder vorhandenen Liefer-Tag | Neueste Vorbereitung bestätigen und die zentrale Lieferung starten oder vorhandenen Lieferstand erneut übergeben |
| `sync-resources.yml` | Push auf einen Feature-, `main`- oder Release-Branch sowie manueller Start | Projekte nach M/Text-Entwicklung oder -Funktionstest übertragen |

Syntaxbefunde aus `check-resources.yml` dienen als Hinweise und verhindern den
Merge nicht.

### Shared Workflows und zentrale Workflows

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `shared-check-resources.yml` | Aufruf durch `check-resources.yml` | Mandantenkonfiguration sowie JSON- und XML-Ressourcen ohne Zugriff auf Zielsysteme prüfen |
| `shared-dispatch.yml` | Aufruf durch einen Mandanten-Workflow | Benannten zentralen Workflow mit seinen Eingaben starten |
| `shared-sync-resources.yml` | Aufruf durch `sync-resources.yml` | Projekte nach M/Text übertragen |
| `shared-lieferung-check.yml` | Aufruf durch `lieferung-vorbereiten.yml` | Liefer-Tag und Branchstand prüfen, Lieferumfang anzeigen und Vorbereitung festhalten |
| `shared-lieferung-ausfuehren.yml` | Aufruf durch `lieferung-ausfuehren.yml` | Liefer-Tag auflösen, eine Vorbereitung bestätigen und `lieferung.yml` starten |
| `lieferung.yml` | Start durch `shared-dispatch.yml` | Bei einer erstmaligen Lieferung den Tag erstellen und `release.yml` aufrufen |
| `release.yml` | Aufruf durch `lieferung.yml` oder manueller Start | FULL- und DELTA-Pakete erstellen, an den Mainframe übertragen und die Lieferinformationen im Mandanten-Repository bereitstellen |
| `ci.yml` | Pull Request oder Push auf `main` in `mtext_actions` | Tests ausführen |

Die als `shared-*.yml` abgelegten Shared Workflows werden direkt in einen
Mandantenlauf eingebunden. Sie erhalten die benötigten Secrets aus dem
Mandanten-Repository und verwenden `main` aus `mtext_actions`. Tag-Erzeugung
und Paketbau benötigen dagegen die in `mtext_actions` hinterlegten technischen
Zugänge. `shared-dispatch.yml` startet sie deshalb über die GitHub-API als
eigenen Lauf auf `main` in `mtext_actions`. Workflowdefinition und
Python-Implementierung stammen in diesem Lauf aus demselben Commit. Die
zentralen Secrets werden nicht an den Mandantenlauf übergeben.

### Protokolle und Rückmeldung

GitHub Actions übernimmt `stdout` und `stderr` der Workflows in das Protokoll.
Die Python-Skripte schreiben ein erfolgreiches Ergebnis als JSON nach `stdout`
und Warnungen oder Fehler nach `stderr`. Bei der Konfigurationsprüfung und der
M/Text-Synchronisation sind diese Ausgaben im Mandanten-Repository sichtbar.

Die Lieferung läuft danach als eigener Workflow in `mtext_actions`.
Ihr Ergebnis und die Informationen zum Paket werden deshalb nach Abschluss im
GitHub Release des Mandanten-Repositories angezeigt.

### Zentrale CI/CD-Version

Änderungen werden nach erfolgreicher zentraler Testsuite über einen Pull
Request in `mtext_actions/main` zusammengeführt. Dieser Stand ist freigegeben.
Die Mandanten-Workflows verweisen auf `mtext_actions@main` und verwenden ihn
bei ihrem nächsten Lauf. Eine separate Aktualisierung der Mandantenbranches ist
dafür nicht erforderlich.

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
| `RESOURCE_TRANSFER_FAILED` | Die Projektpakete konnten nicht für den Adapter bereitgestellt werden | `5` |
| `ADAPTER_FAILED` | Der M/Text-Adapter war nicht erreichbar oder hat den Synchronisationsauftrag abgelehnt | `6` |
| `ADAPTER_ACCEPTED` | Der M/Text-Adapter hat den Synchronisationsauftrag angenommen | – |
| `PACKAGE_FAILED` | Projektpaket, Informationsdatei oder JCL konnten nicht erstellt oder verwendet werden | `4` |
| `ARTIFACT_READY` | Projektpakete, Informationsdateien und JCL wurden erstellt | – |
| `MAINFRAME_TRANSFER_FAILED` | Die FTPS- oder JES-Übergabe ist fehlgeschlagen | `7` |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden per FTPS und JES übergeben | – |
| `GITHUB_RELEASE_FAILED` | Das GitHub Release oder seine Informationsdateien konnten nicht bereitgestellt werden | `8` |
| `GITHUB_RELEASE_PUBLISHED` | Zusammenfassung und Informationsdateien stehen im Mandanten-Repository bereit | – |

## 7. Konfiguration

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

### Zentrale Zuordnungen

`config/mandanten.json` ordnet Mandantenkürzel und Repository eindeutig
einander zu. `config/releaselinien.json` ordnet den M/Text-Zielen ihre Präfixe
und jeder aktiven Releaselinie den Zahlenteil ihrer technischen ETAPS-Linie
sowie ein Hostprofil zu.

`config/ressourcenformate.json` ordnet Dateiendungen dem technischen Format
`json` oder `xml` zu. Die Ressourcenprüfung wählt daraus den Parser. Die
Zuordnung umfasst derzeit:

| Format | Dateiendungen |
|---|---|
| JSON | `.json`, `.formio` |
| XML | `.xml`, `.model`, `.datamodel`, `.conf` |

Das Feld `stage` eines Hostprofils enthält eine der CodePipeline-Stages `FKTE`,
`FKTF`, `JURJ`, `JURP`, `SVTS` oder `VPTV`.

## 8. Schutz und Berechtigungen

| Gegenstand | Regel |
|---|---|
| `main` | Geschützt, keine Löschung oder Umbenennung, fachliche Änderung über Pull Request im Vier-Augenprinzip |
| `release/nnn` | Geschützt, fachliche Änderung über Pull Request im Vier-Augenprinzip |
| `mtext_actions/main` | Geschützt, Änderung nach erfolgreicher zentraler Testsuite über Pull Request |
| `feature/nnn/<Bezeichnung>` | Keine zusätzliche Schutzregel |
| `bereitstellung/nnn.nnn` | Keine zusätzliche Schutzregel, nach der Lieferung löschbar |
| Liefer-Tags `rnnn.nnn` | Der zentrale Lieferworkflow erstellt den Tag auf der bestätigten SHA. Ein fehlerhafter Tag darf gelöscht werden. |
| Workflowdateien und Mandantenkonfiguration | Änderungen erfolgen über Pull Request und Review. Die Trigger-Workflows verweisen auf `mtext_actions@main`. |
| GitHub Release | Der zentrale Workflow darf zum vorhandenen Tag ein GitHub Release im auslösenden Mandanten-Repository erstellen und die Informationsdateien anhängen |
| Mainframe-Zugang | Repositoryvariablen und Repository-Secret in `mtext_actions` |

Der aktuelle Implementierungsstand erwartet in den Mandanten-Repositories
`MTEXT_ACTIONS_TOKEN` mit `Actions: read and write` sowie `Contents: read` für
`mtext_actions`. Damit laden die Workflows die freigegebene CI/CD-Version aus
`main` und starten bei einer Lieferung den zentralen Workflow.

Für den Zugriff in Gegenrichtung erwartet `mtext_actions` derzeit
`WORKFLOW_CONFIGURATION_TOKEN` mit `Contents: read and write` für die
zugeordneten Mandanten-Repositories. Der Zugriff wird für Liefer-Tags und
GitHub Releases mit den Informationsdateien benötigt.

Für den produktiven Rollout fehlt eine vom persönlichen Benutzer unabhängige
technische Identität. Ob die beiden PAT-Verträge durch eine GitHub App oder
eine andere Vorgabe der GitHub-Admins ersetzt werden, ist offen. Die
erforderlichen Repositoryberechtigungen bleiben dabei fachlich bestehen.

## 9. Mögliche Phase 2

Die erste Ausbaustufe bleibt bewusst auf die sichere Ablösung des bestehenden
Lieferwegs begrenzt. Nach einem stabilen Produktivbetrieb können insbesondere
folgende Erweiterungen bewertet werden:

- den nachgelagerten fachlichen Status in M/Text und auf dem Mainframe abfragen
  und im Workflow anzeigen (Polling)
- Betriebsmetriken und kompakte Laufzusammenfassungen ergänzen, ohne
  mandantenübergreifende oder vertrauliche Details offenzulegen
- zusätzliche E-Mail-Benachrichtigungen für relevante Workflow-Ergebnisse
  ergänzen, ohne den fachlichen Laufstatus von der Benachrichtigung abhängig zu
  machen
- Aktualisierungen gepinnter Actions sowie ergänzende Workflow-, Shell-, Typ-
  und Abdeckungsprüfungen automatisieren
