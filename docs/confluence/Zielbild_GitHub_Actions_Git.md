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
Konfigurationsdatei. Die CI/CD-Automatisierung, die von diesen
Trigger-Workflows zentral genutzt wird, liegt im Repository
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` (im Folgenden `mtext_actions`
genannt). Sie führt Validierungen, Synchronisierung, Paketbau und Übergabe an
den Mainframe (IZE9) durch.

Wir orientieren uns am FI-Leitfaden zu Branches und Tags in Git:

- `main` ist der geschützte, dauerhafte Branch der führenden Releaselinie;uu
- `release/nnn` enthält eine parallel gepflegte Releaselinie (z.B.
  `release/261`)
- Jede Änderung entsteht in einem Branch `feature/nnn/<Bezeichnung>`
- Änderungen an `main` und `release/nnn` erfolgen ausschließlich über Pull Requests
- Pull Requests werden nach Freigabe im 4-Augenprinzip mit Squash Merge zusammengeführt
- Release-Tags folgen dem Muster `vnnn.nnn` (oder `vnnn.nnnx` für
  Beta-Lieferungen)

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

Ein Release wird später aus einem fachlich freigegebenen Branch (`main` oder
`release/nnn`) vorbereitet. Der Release-Freigabeprozess hält Release-Version
und Lieferumfang fest. Eine zweite Person prüft und genehmigt den zugehörigen
Pull Request. Nach dessen Merge erzeugt der Workflow den Release-Tag und
startet Paketbau sowie Mainframe-Übergabe.

#### Änderungsablauf

```text
Entwicklung in lokalem Feature-Branch (feature/nnn/<Bezeichnung>)
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
Branchstand ist für ein Release bereit
```

#### Release-Ablauf

```text
Gewählter Branchstand auf main (oder release/nnn)
    │ Release-Freigabe starten
    ▼
Pull Request vom technischen Freigabe-Branch nach main (oder release/nnn)
    │ Review und Merge
    ▼
Release-Tag, Paketbau und Mainframe-Übergabe durch mtext_actions
```


### Entscheidungen und Nutzen

| Entscheidung | Nutzen |
|---|---|
| Branches nach dem organisationsweiten Leitfaden | `main`, Release- und Feature-Branches bilden Entwicklung und Wartung gut ab. Pull Requests bedeuten natives 4-Augenprinzip. |
| Feature-Push nach M/Text-Entwicklung | Eine Änderung kann vor dem Pull Request vom Entwickler getestet werden. Parallelentwicklungen mehrerer Entwickler werden unterstützt. |
| Pull Request mit Squash Merge | Jeder Pull Request wird als ein fachlicher Commit in den Zielbranch übernommen. Review und Arbeitscommits bleiben im Pull Request sichtbar. |
| GitHub Actions statt Jenkins | Natives Git-Feeling mit modernen Workflows in einem zentralen Tool. |
| Gemeinsames Lieferpaket-Format | Synchronisation und Release verwenden das gleiche Paketformat auf unterschiedlichen Transportwegen. |
| Release-Freigabe-PR | Eine zweite Person bestätigt Release-Version und Lieferumfang. Der Workflow erzeugt danach den Release-Tag auf dem Merge-Commit der Freigabe. |
| Freigegebene CI/CD-Version | Alle Mandanten verwenden dieselbe Version von `mtext_actions`. Die Commit-SHA zeigt, welche Version ausgeführt wurde. |
| Zentrale Mainframe-Zugangsdaten | Mandanten-Repositories benötigen keine Mainframe-Zugangsdaten. |

## 2. Branch- und Pull-Request-Modell

### Branches

| Branch | Zweck | Schutz und Lebensdauer |
|---|---|---|
| `main` | Führende Releaselinie und Ausgangspunkt der regulären Weiterentwicklung | Dauerhaft, Default Branch, geschützt, Änderung über Pull Request |
| `release/nnn` | Parallel gepflegte Releaselinie, insbesondere für Wartung und Fehlerkorrekturen | Geschützt, Änderung über Pull Request, nach Ende der Pflege löschbar |
| `feature/nnn/<Bezeichnung>` | Eine fachlich zusammengehörige Änderung für die genannte Releaselinie | Temporär, nach dem Merge löschbar |
| `release-approval/<Release-Tag>/<Lauf>` | Technischer Branch für den Release-Freigabe-PR | Der Freigabeworkflow erstellt ihn mit der neuen Release-Version, nach dem Merge ist er löschbar |

Beispiele für Feature-Branches sind:

```text
feature/261/issue-5678
feature/270/neuer-brief
```

Der Bezeichnungsteil eines Feature-Branches darf weitere Pfadsegmente
enthalten, beispielsweise `feature/270/briefe/anschreiben`.

Ein Feature-Branch beginnt auf dem geschützten Branch, in dem seine
Releaselinie gepflegt wird:

- Für die führende (aktive) Releaselinie ist `main` der Zielbranch
- Für eine parallel gepflegte Linie ist `release/nnn` der Zielbranch
- Ein Feature für eine spätere Releaselinie bleibt bis zum Linienwechsel im
  Feature-Branch und kann dort entwickelt und in M/Text-Entwicklung getestet
  werden

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

Die führende Releaselinie wechselt mit dem OSPlus-Release, also zweimal im
Jahr. `main` zeigt immer auf die aktuelle Releaselinie, und welche das zu einem
Zeitpunkt ist, wird im Feld `releaselinie` der Mandantenkonfiguration
(`.github/config.json`) festgehalten.

Vor dem Wechsel wird aus einem geeigneten `main`-Commit ein Branch
`release/nnn` für die bisherige Releaselinie erstellt. Danach wird in einem
eigenen Pull Request auf `main` die `releaselinie` hochgezählt. GitHub
Actions erkennt die Änderung und synchronisiert automatisch mit
M/Text-Entwicklung und M/Text-Funktionstest der neuen Linie, so dass in den
Umgebungen automatisch der korrekte neue Stand vorliegt.

Release-Branches werden gelöscht, wenn keine Änderungen für die Linie mehr
erwartet werden, bzw. in der Regel wenn es drei neuere Releases gibt. Bereits
veröffentlichte Versionen können weiterhin über Release-Tags ausgecheckt
werden.

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

Synchronisation und Release verwenden dasselbe Paketformat. Wie im bisherigen
Jenkins-Ablauf gibt es zwei Archivtypen. Ein F-Archiv enthält den vollständigen
Projektbaum eines Tonic-(Fragment-)Projekts. Ein D-Archiv enthält neue und
geänderte Dateien sowie eine Löschliste. Beide sind gzip-komprimierte
TAR-Dateien mit der Endung `.tgz`.

| Lieferart | Inhalt | Vergleichsstand und Verwendung |
|---|---|---|
| FULL | F-Archiv mit dem vollständigen Projektbaum und leeres D-Archiv | Ohne Vergleichsstand. Für die erste Synchronisation, den Wechsel der führenden Releaselinie, den manuellen Vollabgleich und Releases mit der Versionsnummer `100`, auch als Beta |
| DELTA | D-Archiv mit neuen und geänderten Dateien sowie einer Löschliste | Bei der Synchronisation zwischen vorherigem und neuem Commit des Git-Ereignisses. Beim Release kumulativ zwischen dem `.100`-Tag und dem Release-Tag |

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

Ein Voll-Lieferung (FULL) besteht aus dem F-Archiv und einem leeren D-Archiv.
Bei der Übernahme wird zuerst das F-Archiv und anschließend das leere D-Archiv
verarbeitet. Bei der Mainframe-Übergabe ersetzt das leere D-Archiv das
gleichnamige D-Archiv einer früheren Lieferung. Dadurch kann ein vorheriges
DELTA den neuen FULL-Stand nicht wieder verändern. Eine Delta-Lieferung (DELTA)
besteht aus dem D-Archiv.

Der Archivname besteht aus Mandantenkürzel, Projektcode und `F` oder `D`. Beim
Release ist der Name ohne `.tgz` zugleich das Mainframe-Member (siehe Kapitel
"CodePipeline-Elemente").

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
      "referenz": "v261.100",
      "commit": "..."
    },
    "bis": {
      "referenz": "v261.108",
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

### Offene Entscheidung: Transport nach `serverSync`

Für M/Text muss der aus den Projektpaketen erzeugte Stand unter `serverSync`
bereitgestellt und anschließend über den bestehenden Adapter synchronisiert
werden. Der technische Transportweg ist noch festzulegen. Zur Auswahl stehen:

| Variante | Ablauf | Vor der Entscheidung zu klären |
|---|---|---|
| PUT an den Adapter | Der Runner überträgt Projektpakete und Informationsdateien an den Adapter. Dieser prüft und verarbeitet sie unter `serverSync` und startet die Synchronisation. | HTTP-Vertrag, Authentifizierung, Größenlimits, Zeitgrenzen und Rückmeldung |
| GitHub-Actions-Artefakt | Der Workflow speichert Projektpakete und Informationsdateien als Artefakt. Eine Zielkomponente lädt sie herunter, verarbeitet sie unter `serverSync` und startet die Synchronisation. | Zielkomponente, Zugriff auf GitHub Actions, Downloadmeldung und Aufbewahrungsfrist |
| CIFS-Übergabeverzeichnis (entspricht bisherigem NFS Share) | Der Runner schreibt Projektpakete und Informationsdateien in ein auftragsbezogenes CIFS-Verzeichnis und meldet dem Adapter den Pfad. Dieser übernimmt die Verarbeitung unter `serverSync` und startet die Synchronisation. | CIFS-Basispfad und Rechte, Adaptervertrag, Rückmeldung sowie Aufbewahrung und Bereinigung |

## 4. Release

Releases sind im Grunde auch nur Synchronisierungen, jedoch auf einem anderen
Transportweg - über das CodePipeline der IZE9, MT91 und letztlich im Batch via
LXT90#SV, Travic-Link und dem besonderen Folgejob `ressourcen_aktualisieren.sh`.

### Release-Tags

Release-Tags folgen dem Muster `vnnn.nnn` oder `vnnn.nnnx`, beispielsweise
`v261.100`, `v261.108` oder `v261.108a`. Der optionale Buchstabe am Ende
kennzeichnet eine Beta-Lieferung.

Für eine Lieferung startet der Antragsteller den Vorbereitungsworkflow auf
`main` (oder `release/nnn`). Der Workflow übernimmt die
Release-Version (die via Wartungstool festgelegt wurde) und legt den
technischen Freigabe-Branch `release-approval/<Release-Tag>/<Lauf>` an. Dabei
wird das Feld `letztes_release` der Mandantenkonfiguration geändert und eine
Workflow-Zusammenfassung erzeugt, die Informationen zu Commit, Bezugsstand,
Projekten und Lieferumfang enthält und als Basis für die nachfolgende Prüfung
durch eine zweite Person herangezogen wird.

Der Antragsteller eröffnet den Pull Request des Freigabe-Branches nach `main`
(der `release/nnn`). Eine zweite Person prüft den Stand und den Lieferumfang.
Nach erfolgreicher Vorprüfung und dem Merge wird der Release-Tag auf dem
Merge-Commit erstellt und die Lieferung gestartet. Der Release-Tag kann später
nicht mehr geändert oder gelöscht werden per FI-Tag-Rulesets. Ein fälschlicher
Weise angelegter Tag kann nur von den GitHub-Administratoren der FI
zurückgenommen werden, daher ist vorher ausführlich zu prüfen!

Beta-Tags können ohne dieses 4-Augenprinzip erstellt werden und stoßen direkt
die Lieferung an, da sie sowieso nicht für produktive Lieferungen verwendet
werden können.

### Release automatisch bauen und übertragen

Ein zulässiger Release-Tag startet den zentralen Workflow in `mtext_actions`.
Er checkt den markierten Commit aus, erzeugt je Projekt die in Kapitel 3
beschriebenen Projektpakete und überträgt sie an den Mainframe. Die
Versionsnummer `100` erzeugt auch bei einem Beta-Tag ein FULL. Alle anderen
Versionen derselben Releaselinie erzeugen ein kumulatives DELTA gegen den
`.100`-Tag. Die JSON-Informationsdatei bleibt beim GitHub-Artefakt und wird
nicht als Mainframe-Member übertragen.

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

### Releaseartefakt

Das GitHub-Actions-Artefakt, das beim Release entsteht, enthält die erzeugten
Archive, die zugehörigen JCL-Dateien und die projektbezogenen
JSON-Informationsdateien. Es wird 30 Tage aufbewahrt. Der Übergabejob überträgt
die Archive unter ihren Membernamen und reicht die zugehörige JCL ein. Die
Informationsdateien werden nicht an den Mainframe übertragen.

Schlägt die Übergabe fehl, kann dasselbe Artefakt erneut übergeben werden. Die
Pakete müssen dafür nicht neu gebaut werden.

Nach der Mainframe-Übergabe erstellt der zentrale Workflow im
Mandanten-Repository ein GitHub Release zum vorhandenen Release-Tag. Die
Release-Beschreibung nennt Release-Tag, Lieferart und Commit-SHA. Sie
bestätigt die technische Übergabe und enthält die JSON-Informationsdateien.
Diese dienen als Lieferbeleg. Die fachliche Freigabe ist zuvor durch den
Release-Freigabe-PR erfolgt.

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
      release-approval.yml
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
Arbeitsschritte liegen in `mtext_actions`. Bei späteren Änderungen trägt
`update-mandant-workflows.yml` in den Trigger-Workflows ein, welche Version von
`mtext_actions` sie verwenden sollen.

`mtext_actions` ist in diesem Zielbild das Repository
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Es enthält die
wiederverwendbaren Workflows, die gemeinsame Python-Anwendung, die zentrale
Releaselinien- und Mandantenzuordnung, das JCL-Template und die Tests:

```text
mtext-actions/
  .github/
    workflows/
      ci.yml
      release-approval.yml
      release.yml
      reusable-check-resources.yml
      reusable-dispatch.yml
      reusable-release-approval-check.yml
      reusable-sync-resources.yml
      update-mandant-workflows.yml
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
      release_approval.py
      resource_check.py
      rollout.py
      sync.py
    mtext.py
  templates/
    mainframe-upload.jcl
  tests/
    <automatisierte Tests>
```

## 6. Workflows

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Trigger-Workflow | Zentraler Workflow | Python-Skript | Ergebnis |
|---|---|---|---|---|---|
| Mandanten-Workflows aktualisieren | Manueller Start in `mtext_actions` mit der gewünschten Commit-SHA | keiner | `update-mandant-workflows.yml` | `mtext.py rollout` | Verweise auf `mtext_actions` verwenden die neue Version |
| Mandantenkonfiguration und JSON- oder XML-Ressourcen prüfen | Pull Request oder manueller Start | `check-resources.yml` | `reusable-check-resources.yml` | `mtext.py validate-config` und `mtext.py check-resources` | Konfiguration geprüft, geänderte konfigurierte Ressourcen oder gewählter Vollstand geprüft und Syntaxbefunde als nicht blockierende Warnungen angezeigt |
| M/Text-Entwicklung synchronisieren | Push auf `feature/nnn/<Bezeichnung>` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `mtext.py sync-resources` | Projekte aus dem Commit mit der M/Text-Entwicklungsumgebung synchronisieren |
| M/Text-Funktionstest synchronisieren | Push oder Merge auf `main` oder `release/nnn` sowie manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `mtext.py sync-resources` | Projekte aus dem Commit mit der M/Text-Funktionstestumgebung synchronisieren |
| Release freigeben | Manueller Start auf dem Lieferbranch, selbst eröffneter Freigabe-PR und dessen Merge | `release-approval.yml` | `reusable-release-approval-check.yml` sowie `reusable-dispatch.yml` → `release-approval.yml` | `mtext.py release-approval` | Vorprüfung im Pull Request angezeigt und Release-Tag auf dem Merge-Commit erstellt |
| Release bauen und übertragen | Push eines Tags `vnnn.nnn` oder `vnnn.nnnx` | `release-approval.yml` | `reusable-dispatch.yml` → `release.yml` | `mtext.py build-release`, `publish-mainframe`, danach `publish-github-release` | FULL oder DELTA an den Mainframe übertragen, GitHub Release mit Lieferinformationen erstellt |
| `mtext_actions` testen | Pull Request oder Push auf `main` in `mtext_actions` | keiner | `ci.yml` | `python -m unittest discover` | Zentrale Tests ausgeführt |

### Trigger-Workflows in den Mandanten-Repositories

Die Trigger-Workflows reagieren auf Änderungen und starten die
Verarbeitung in `mtext_actions`:

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `check-resources.yml` | Pull Request oder manueller Start | Mandantenkonfiguration und geänderte konfigurierte Ressourcen oder den gewählten Vollstand prüfen, Syntaxbefunde als Warnungen anzeigen |
| `release-approval.yml` | Manueller Start, Release-Freigabe-PR oder Release-Tag | Technischen Freigabe-Branch vorbereiten, Vorprüfung anzeigen, den Release-Tag auf dem Merge-Commit erstellen oder die Release-Erstellung starten |
| `sync-resources.yml` | Push auf einen Feature-, `main`- oder Release-Branch sowie manueller Start | Projekte nach M/Text-Entwicklung oder -Funktionstest übertragen |

Syntaxbefunde aus `check-resources.yml` dienen als Hinweise und verhindern den
Merge nicht.

### Zentrale Workflows

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `reusable-check-resources.yml` | Aufruf durch `check-resources.yml` | Mandantenkonfiguration sowie JSON- und XML-Ressourcen ohne Zugriff auf Zielsysteme prüfen |
| `reusable-dispatch.yml` | Aufruf durch `release-approval.yml` | Benannten zentralen Workflow mit seinen Eingaben starten |
| `reusable-sync-resources.yml` | Aufruf durch `sync-resources.yml` | Projekte nach M/Text übertragen |
| `reusable-release-approval-check.yml` | Aufruf durch `release-approval.yml` | Geplanten Release prüfen und Branchstand sowie Lieferumfang im Pull Request anzeigen |
| `release-approval.yml` | Start durch `reusable-dispatch.yml` mit `phase` `prepare` oder `finalize` | `letztes_release` und Freigabe-Branch vorbereiten oder nach dem Merge den Release-Tag erstellen |
| `release.yml` | Start durch `reusable-dispatch.yml` | FULL- und DELTA-Pakete erstellen, an den Mainframe übertragen und die Lieferinformationen im Mandanten-Repository bereitstellen |
| `ci.yml` | Pull Request oder Push auf `main` in `mtext_actions` | Tests ausführen |
| `update-mandant-workflows.yml` | Manueller Start | Verweise auf `mtext_actions` in den Mandanten-Workflows aktualisieren |

Die mit `reusable-` benannten Workflows werden direkt in einen Mandantenlauf
eingebunden. Sie erhalten die benötigten Secrets aus dem Mandanten-Repository
und verwenden die dort festgelegte CI/CD-Version. Die Vorbereitung und der
Abschluss einer Release-Freigabe sowie der Releasebau benötigen dagegen die in
`mtext_actions` hinterlegten technischen Zugänge. `reusable-dispatch.yml`
startet sie deshalb über die GitHub-API als eigenen Lauf auf `main` in
`mtext_actions`. Workflowdefinition und Python-Implementierung stammen in
diesem Lauf aus demselben Commit. Die zentralen Secrets werden nicht an den
Mandantenlauf übergeben.

### Protokolle und Rückmeldung

GitHub Actions übernimmt `stdout` und `stderr` der Workflows in das Protokoll.
Die Python-Skripte schreiben ein erfolgreiches Ergebnis als JSON nach `stdout`
und Warnungen oder Fehler nach `stderr`. Bei der Konfigurationsprüfung und der
M/Text-Synchronisation sind diese Ausgaben im Mandanten-Repository sichtbar.

Die Release-Erstellung läuft dagegen als eigener Workflow in `mtext_actions`.
Ihr Ergebnis und die Informationen zum Paket werden deshalb nach Abschluss im
GitHub Release des Mandanten-Repositories angezeigt.

### Aktualisierung der Mandanten-Workflows

Wenn die Mandanten-Repositories eine neue Version von `mtext_actions`
verwenden sollen, starten die zuständigen Admins
`update-mandant-workflows.yml` manuell. Der Workflow aktualisiert alle
Workflowdateien, die einen wiederverwendbaren Workflow aus `mtext_actions`
aufrufen. Eigene Workflows ohne einen solchen Aufruf bleiben unverändert. Für
jeden Zielbranch schreibt er einen administrativen Rollout-Commit.

Die Workflowdateien gehören zu den Branches der Mandanten-Repositories. Daher
aktualisiert der Workflow `main` und jeden vorhandenen Release-Branch getrennt.
Nicht vorhandene Mandanten-Repositories und Branches werden mit einer Warnung
übersprungen.
Der technische Rollout-Zugriff darf dafür die Pull-Request-Pflicht der
geschützten Zielbranches umgehen. Fachliche Änderungen verwenden weiterhin den
Pull-Request-Ablauf. Reine Änderungen unter `.github/workflows` lösen keine
M/Text-Synchronisation aus.

### Status und Fehlercodes

Die Workflows melden mit einem festen Status, was erreicht wurde oder an
welcher Stelle sie abgebrochen sind. Bei Fehlern endet das Programm außerdem
mit dem zugehörigen Exitcode.

| Status | Bedeutung | Exitcode bei Fehlern |
|---|---|---|
| `RESOURCE_CHECKED` | JSON- und XML-Ressourcen wurden geprüft, Befunde stehen als Warnungen bereit | – |
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinienzuordnung wurden geprüft | – |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig | `2` |
| `RELEASE_APPROVAL_READY` | Technischer Branch mit der neuen Release-Version wurde veröffentlicht | – |
| `RELEASE_APPROVAL_CHECKED` | Release-Version, Branchstand und Lieferumfang wurden für den Pull Request geprüft | – |
| `RELEASE_APPROVAL_VALIDATED` | Merge und eingetragene Release-Version gehören zum Freigabe-Pull-Request | – |
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
| `letztes_release` | Zuletzt über diesen Lieferbranch freigegebene Release-Version, vor dem ersten Release `null` |
| `excluded_projects` | Projektverzeichnisse, die weder synchronisiert noch paketiert werden |
| `hostprofile` | Assignment und CodePipeline-Stage je Hostprofil |

Beispiel:

```json
{
  "mandant": {
    "kuerzel": "FI",
    "releaselinie": "270",
    "ispw": "P",
    "letztes_release": null,
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
`main` steht sie im Feld `releaselinie`. Der Freigabeworkflow aktualisiert
`letztes_release` auf dem technischen Freigabe-Branch. Die Konfiguration der
fachlichen Projekte und Zielsysteme bleibt dabei unverändert.

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
| `main` | Geschützt, keine Löschung oder Umbenennung, fachliche Änderung über Pull Request im Vier-Augenprinzip, erforderlicher Statuscheck **Release vorprüfen** |
| `release/nnn` | Geschützt, fachliche Änderung über Pull Request im Vier-Augenprinzip, erforderlicher Statuscheck **Release vorprüfen**, Erstellung aus geschütztem Branch oder Release-Tag |
| `feature/nnn/<Bezeichnung>` | Keine zusätzliche Schutzregel |
| Release-Tags ohne Buchstabensuffix `vnnn.nnn` | Der technische Freigabeworkflow erstellt den Tag nach Review und Merge des Freigabe-Pull-Requests. |
| Beta-Tags `vnnn.nnnx` | Dürfen lokal oder in GitHub auf einem Commit des passenden geschützten Branches erstellt werden. |
| Workflowdateien und Mandantenkonfiguration | Mandantenkonfiguration und reguläre Workflowänderungen über Pull Request und Review. Freigegebene CI/CD-Versionen werden über den administrativen Rollout aktualisiert. |
| GitHub Release | Der zentrale Workflow darf zum vorhandenen Tag ein GitHub Release im auslösenden Mandanten-Repository erstellen und die Informationsdateien anhängen |
| Mainframe-Zugang | Repositoryvariablen und Repository-Secret in `mtext_actions` |

Die Trigger-Workflows verwenden das Fine-grained PAT eines technischen
GitHub-Benutzers, um `mtext_actions` aufzurufen. Das Token gilt für das
Repository `FinanzInformatik/fi_lbs_entw_oms_mtext_actions` und besitzt
`Actions: read and write` sowie `Contents: read`. In den
Mandanten-Repositories liegt es als Secret `MTEXT_ACTIONS_TOKEN`. Damit laden
die Workflows die festgelegte CI/CD-Version und starten bei einem Release den
zentralen Workflow.

Für den Zugriff in Gegenrichtung liegt `WORKFLOW_CONFIGURATION_TOKEN` in
`mtext_actions`. Es gilt für die zugeordneten Mandanten-Repositories und
besitzt dort `Contents: read and write`, `Pull requests: read` sowie
`Workflows: read and write`. Der technische Benutzer ist in den Schutzregeln
als Ausnahme von der Pull-Request-Pflicht für den administrativen
Workflow-Rollout hinterlegt. Das Token aktualisiert die Trigger-Workflows,
veröffentlicht die technischen Freigabe-Branches, liest den zusammengeführten Freigabe-PR
und erstellt die freigegebenen Tags sowie die GitHub Releases mit den
Informationsdateien.

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
