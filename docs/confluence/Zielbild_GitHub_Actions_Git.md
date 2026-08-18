# Zielbild für die Ablösung von Jenkins und SVN

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in GitHub verprobt. Während dieser Testphase bleibt der
bisherige Prozess produktiv. Unmittelbar vor der für Januar 2027 geplanten
Produktivsetzung wird der dann gültige SVN-Stand nach Git übertragen.
Danach sind Git und GitHub Actions für den Prozess führend und SVN wird
zusammen mit dem EN4920-Netz abgebaut.

Jeder Mandant erhält ein eigenes Git-Repository mit seinen M/Text-Ressourcen,
Trigger-Workflows und einer für diesen Prozess relevanten Konfigurationsdatei.
Die CI/CD-Automatisierung, die von diesen Trigger-Workflows genutzt wird, liegt
im Repository `FinanzInformatik/fi_lbs_entw_oms_mtext_actions` (im Folgenden
`mtext_actions`). Sie validiert das Repo, synchronisiert M/Text, erstellt die
FULL- und DELTA-Pakete und übergibt sie an den Mainframe. Nach erfolgreicher
Übergabe erstellt sie außerdem ein GitHub Release im jeweiligen
Mandanten-Repository.

Das Branch-Modell folgt dem FI-Leitfaden:

- `main` ist der geschützte, dauerhafte Branch der führenden Releaselinie
- `release/Rnnn` enthält eine parallel gepflegte Releaselinie
- Jede Änderung entsteht in einem Branch `feature/Rnnn/<Bezeichnung>`
- Änderungen an `main` und `release/Rnnn` erfolgen über Pull Requests im
  Vier-Augenprinzip
- Pull Requests werden mit Squash Merge zusammengeführt
- Release-Tags folgen dem Muster `vnnn.nnn` oder `vnnn.nnnx`
- Reguläre Releases werden standardmäßig über einen Release-Freigabe-PR
  freigegeben

*M/Text-Entwicklung* und *M/Text-Funktionstest* sind keine Git-Branches. Sie
bezeichnen die beiden M/Text-Umgebungen einer Releaselinie.

```text
feature/Rnnn/<Bezeichnung>
    │ Push
    ▼
M/Text-Entwicklung der Releaselinie
    │ fachlich testen
    ▼
Pull Request nach main oder release/Rnnn
    │ Review und Squash Merge
    ▼
M/Text-Funktionstest der Releaselinie
    │ regulärer Release-Freigabe-PR
    │ Review und Merge
    ▼
Release-Tag, Paketbau und Mainframe-Übergabe durch mtext_actions
```

Bei einem Feature-Push werden die M/Text-Projekte automatisch mit der
M/Text-Entwicklungsumgebung synchronisiert. Ein Merge nach `main` oder
`release/Rnnn` synchronisiert sie automatisch mit der
M/Text-Funktionstestumgebung. Ein regulärer Release-Freigabe-PR bestätigt den
zu liefernden Branchstand im Vier-Augenprinzip. Nach dem Merge erzeugt der
Workflow den Release-Tag und startet den Paketbau und die Mainframe-Übergabe.

### Entscheidungen und Nutzen

| Entscheidung | Nutzen |
|---|---|
| Branches nach dem organisationsweiten Leitfaden | `main`, Release- und Feature-Branches reichen für Entwicklung und Wartung aus. Zusätzliche Prozess-Branches oder Cherry-Picks zwischen M/Text-Entwicklung und M/Text-Funktionstest sind nicht nötig. |
| Feature-Push nach M/Text-Entwicklung | Eine Änderung kann vor dem Pull Request im passenden M/Text-Ziel geprüft werden. |
| Pull Request mit Squash Merge | Jeder Pull Request wird als ein fachlicher Commit in den Zielbranch übernommen. Review und Arbeitscommits bleiben im Pull Request sichtbar. |
| Gemeinsames M/Text-Projektpaket | Synchronisation und Release verwenden dasselbe `.tgz`-Format und dieselbe JSON-Informationsdatei. Sie unterscheiden sich durch Bezugsstand und Transportweg. |
| Adapter verantwortet die Übernahme nach `serverSync` | Der Workflow übergibt projektweise einen Vollstand oder die Änderungen eines Git-Ereignisses. Der Adapter aktualisiert daraus `serverSync` und startet die M/Text-Synchronisation. |
| Release-Freigabe-PR für reguläre Releases | Eine zweite Person bestätigt Branchstand, Release-Version und Lieferumfang. Der Workflow erzeugt danach den Release-Tag auf dem Merge-Commit der Freigabe. |
| Freigegebene CI/CD-Version | Alle Mandanten verwenden dieselbe geprüfte Version von `mtext_actions`. Die vollständige Commit-SHA zeigt, welche Version ausgeführt wurde. |
| Zentrale Mainframe-Zugangsdaten | Mandanten-Repositories benötigen keine Mainframe-Zugangsdaten. |

## 2. Branch- und Pull-Request-Modell

### Branches

| Branch | Zweck | Schutz und Lebensdauer |
|---|---|---|
| `main` | Führende Releaselinie und Ausgangspunkt der regulären Weiterentwicklung | Dauerhaft, Default Branch, geschützt, Änderung über Pull Request |
| `release/Rnnn` | Parallel gepflegte Releaselinie, insbesondere für Wartung und Fehlerkorrekturen | Geschützt, Änderung über Pull Request, nach Ende der Pflege löschbar |
| `feature/Rnnn/<Bezeichnung>` | Eine fachlich zusammengehörige Änderung für die genannte Releaselinie | Temporär, nach dem Merge löschbar |

Beispiele für Feature-Branches sind:

```text
feature/R260/issue-1234
feature/R261/issue-5678
feature/R270/neuer-brief
```

Der Bezeichnungsteil eines Feature-Branches darf weitere Pfadsegmente
enthalten, beispielsweise `feature/R270/briefe/anschreiben`.

Ein Feature-Branch beginnt auf dem geschützten Branch, in dem seine
Releaselinie gepflegt wird:

- Für die führende (aktive) Releaselinie ist `main` der Zielbranch
- Für eine parallel gepflegte Linie ist `release/Rnnn` der Zielbranch
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
Jahr.

Vor dem Wechsel wird aus einem geeigneten `main`-Commit ein Branch
`release/Rnnn` für die bisherige Releaselinie erstellt. Danach wird in einem
eigenen Pull Request auf `main` nur das Feld `releaselinie` in der
Mandantenkonfiguration (`.github/config.json`) geändert. Die M/Text-Ressourcen
bleiben dabei unverändert. Nach dem Merge steht `main` für die neue
Releaselinie.

GitHub Actions erkennt dabei die geänderte `releaselinie` und synchronisiert die
M/Text-Projekte aus `main` automatisch mit M/Text-Entwicklung und
M/Text-Funktionstest der neuen Linie. Die Verantwortlichen des Repositories
führen den Wechsel durch und kontrollieren beide Ziele. Für `mtext_actions` und
`fi_lbs_entw_oms_fi` sind dies die FI-Fachverantwortlichen. Für die weiteren
Mandanten-Repositories sind es die jeweiligen Mandantenverantwortlichen.

Release-Branches werden gelöscht, wenn keine Änderungen für die Linie mehr
erwartet werden, bzw. in der Regel spätestens wenn es drei neuere Releases
gibt. Bereits veröffentlichte Versionen können weiterhin über ihre geschützten
Release-Tags ausgecheckt werden.

## 3. M/Text-Projektpaket und Synchronisation

### Zielermittlung

Jede Releaselinie ist einer technischen ETAPS-Linie zugeordnet. Zu jeder
ETAPS-Linie gehören eine M/Text-Entwicklungsumgebung und eine
M/Text-Funktionstestumgebung, jeweils in Stage 0.

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
    "R260": {"etaps_linie": "03", "hostprofil": "JUR"},
    "R261": {"etaps_linie": "01", "hostprofil": "FKT"},
    "R270": {"etaps_linie": "02", "hostprofil": "JUR"}
  }
}
```

Für die Zielermittlung gelten folgende Regeln:

| Git-Ereignis | Releaselinie | M/Text-Ziel |
|---|---|---|
| Push nach `feature/Rnnn/<Bezeichnung>` | `Rnnn` aus dem Feature-Branch | M/Text-Entwicklung |
| Merge nach `release/Rnnn` | `Rnnn` aus dem Release-Branch | M/Text-Funktionstest |
| Merge nach `main` | `releaselinie` aus der Mandantenkonfiguration | M/Text-Funktionstest |
| Wechsel der `releaselinie` auf `main` | neue `releaselinie` aus der Mandantenkonfiguration | M/Text-Entwicklung und M/Text-Funktionstest |
| Manueller Vollabgleich eines Feature-Branches | `Rnnn` aus dem Feature-Branch | M/Text-Entwicklung |
| Manueller Vollabgleich von `main` | `releaselinie` aus dem ausgewählten Commit | M/Text-Funktionstest |
| Manueller Vollabgleich eines Release-Branches | `Rnnn` aus dem Release-Branch | M/Text-Funktionstest |

Ein Push auf einen Feature-Branch startet die Synchronisation automatisch. Der
Entwickler kontrolliert dann in M/Text, ob die Änderung wie erwartet funktioniert.

Beim Merge des Pull Requests gelangt der Squash-Commit in den geschützten
Zielbranch. Dadurch startet automatisch die Synchronisation mit der
M/Text-Funktionstestumgebung.

Ein manueller Vollabgleich kann mit einer vollständigen Commit-SHA gestartet
werden. In GitHub Actions werden dafür der Branch und die Commit-SHA
ausgewählt. Die Tabelle zeigt, in welches M/Text-Ziel die Projekte übertragen
werden.

### Gemeinsames M/Text-Projektpaket

Synchronisation und Release verwenden dasselbe Projektpaket. Ein F-Archiv
enthält den vollständigen Projektbaum. Ein D-Archiv enthält neue und geänderte
Dateien sowie eine Löschliste. Beide Archive sind gzip-komprimierte TAR-Dateien
mit der Endung `.tgz`.

Ein FULL besteht aus einem F-Archiv und einem leeren D-Archiv. Ein DELTA besteht
aus einem D-Archiv. Der Name eines Archivs wird aus Mandantenkürzel,
Projektcode und `F` oder `D` gebildet. Der Name ohne `.tgz` ist beim Release
zugleich der Mainframe-Member.

Das F-Archiv enthält das Projektverzeichnis mit allen Dateien. Das D-Archiv
enthält das Projektverzeichnis mit den zu übernehmenden Dateien und die
Löschliste `<Mandantenkürzel><Projektcode>D.txt`. In der Löschliste steht je
Zeile ein repositorybezogener Pfad. Beim FULL sind Projektverzeichnis und
Löschliste des D-Archivs leer.

Neben den Archiven liegt für jedes Projekt eine JSON-Informationsdatei. Sie
beschreibt den tatsächlich paketierten Stand und hat folgenden Aufbau:

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

Die Angaben unter `von` entfallen bei einem FULL. Bei einem DELTA bezeichnen
sie den Vergleichsstand. `bis` bezeichnet den paketierten Zielstand. Die
Elemente sind Tupel aus Git-Status und projektbezogenem Pfad. Zulässig sind
`A`, `M`, `D` und `T`. Bei einem FULL werden alle enthaltenen Dateien mit `A`
aufgeführt. Die Schlüssel `F` und `D` unter `sha256` bezeichnen die vorhandenen
Archive. Die Dateinamen werden aus der festen Paketnamensregel abgeleitet.

Mandant und Repository ergeben sich aus dem Mandanten-Repository und dem
Übergabeauftrag. Sie werden in der projektbezogenen Informationsdatei nicht
wiederholt. Die Informationsdatei liegt neben den Archiven, damit sie deren
SHA-256-Prüfsummen enthalten kann.

Für die Synchronisation ist ein DELTA die Änderung des auslösenden
Git-Ereignisses. Der Workflow vergleicht dessen vorherigen und neuen Commit.
Für ein Release ist ein DELTA kumulativ und vergleicht den regulären
`.100`-Tag mit dem Release-Tag. Ein in `serverSync` gespeicherter Commit ist
keine Vergleichsbasis.

### CIFS-Übergabe und Übernahme nach `serverSync`

Der Runner legt die Projektarchive und Informationsdateien vollständig in
einem auftragsbezogenen CIFS-Übergabeverzeichnis ab. Erst danach meldet er dem
Adapter den Auftrag und dessen Pfad. Das Übergabeverzeichnis ist nicht
`serverSync`.

Vom Adapter wird folgende Verarbeitung erwartet: Er prüft die
Informationsdateien und Prüfsummen, übernimmt die Projektpakete nach
`serverSync` und startet danach die M/Text-Synchronisation. Bei einem FULL
spielt er das F-Archiv und anschließend das leere D-Archiv ein. Bei einem DELTA
spielt er das D-Archiv ein und entfernt die in der Löschliste genannten Pfade.
Eine Umbenennung wird als Löschung des bisherigen und Hinzufügen des neuen
Pfads verarbeitet. Dann enthält `serverSync` nach der Übernahme vollständige
Projektverzeichnisse.

Der Workflow verändert `serverSync` nicht selbst und führt keinen eigenen
Vergleichsstand für dieses Verzeichnis.

Ein Projekt ohne Änderungen benötigt bei einer automatischen Synchronisation
keine Übergabe. Bei der ersten Synchronisation über GitHub Actions, beim
Wechsel der führenden Releaselinie und beim manuellen Vollabgleich wird ein
FULL erzeugt. Der manuelle Vollabgleich verwendet den ausgewählten Commit. Der
Branch bestimmt das M/Text-Ziel.

Jede Projektübergabe muss idempotent verarbeitet werden. Derselbe Auftrag kann
nach einem Abbruch oder einer fehlenden Rückmeldung erneut verarbeitet werden
und führt zum gleichen Zielstand. Der Workflow bildet die Auftrags-ID aus
Mandant, Repository, Releaselinie, Zielstufe, Branch, Vergleichsstand,
Ziel-Commit und Projekten. Ein technischer Wiederanlauf erhält damit trotz
eines neuen CIFS-Verzeichnisses dieselbe Auftrags-ID. Die Behandlung von
Wiederholungen, Teilannahmen und die projektbezogene Antwort legt der
Adaptervertrag fest.

Nach dem vollständigen Schreiben meldet der Workflow den Auftrag mit folgendem
JSON an den Adapter:

```json
{
  "auftrag": "...",
  "mandant": "FI",
  "repository": "FinanzInformatik/fi_lbs_entw_oms_fi",
  "releaselinie": "R261",
  "zielstufe": "Funktionstest",
  "branch": "release/R261",
  "von": "...",
  "bis": "...",
  "projekte": ["LOMS_Basis"],
  "pfad": "/cifs/..."
}
```

`von` und `bis` enthalten die Commit-SHAs des Git-Ereignisses. Bei einem FULL
entfällt `von`. `pfad` bezeichnet das vollständig geschriebene
Übergabeverzeichnis. Die Projektdateien und ihre Prüfsummen stehen in den dort
liegenden Informationsdateien.

Folgende technische Angaben sind noch mit dem Adapterbetrieb festzulegen:

- CIFS-Basispfad sowie Schreib- und Leserechte
- Antwort des Adapters je Projekt und Zeitpunkt der erfolgreichen Annahme
- Aufbewahrung und Bereinigung abgeschlossener Übergaben
- Bestätigung der oben erwarteten Verarbeitung von Archiven und Löschliste

Der bestätigte CIFS-Basispfad wird als Organisationsvariable
`MTEXT_CIFS_ROOT` für die Mandanten-Repositories bereitgestellt. Der
wiederverwendbare Sync-Workflow liest diese Variable im Kontext des aufrufenden
Mandanten-Repositories.

## 4. Release-Erstellung und Mainframe-Übergabe

### Release-Tags

Release-Tags folgen dem Muster `vnnn.nnn` oder `vnnn.nnnx`, beispielsweise
`v261.100`, `v261.108` oder `v261.108a`. Der optionale Buchstabe kennzeichnet
eine Beta-Lieferung.

Für reguläre Releases ohne Buchstabensuffix ist der Release-Freigabe-PR der
Regelweg. Ein Benutzer startet den Vorbereitungsworkflow auf `main` oder dem
passenden `release/Rnnn`. Der Workflow verwendet den aktuellen Stand des
ausgewählten Branches und die im Wartungstool vergebene Release-Version. Eine
beliebige Commit-SHA muss nicht eingegeben werden.

Der Workflow legt den Freigabe-Branch an. Den Pull Request dazu eröffnet der
Antragsteller anschließend selbst. Damit ist er dessen Autor, und GitHub lässt
niemanden den eigenen Pull Request genehmigen. Die Zustimmung einer zweiten
Person ergibt sich dadurch aus der Schutzregel des Lieferbranches und muss
nicht zusätzlich nachgebildet werden.

Der Release-Freigabe-PR zeigt:

- den ausgewählten Branch und seine Commit-SHA
- die Release-Version aus dem Wartungstool
- den Bezugsstand der Lieferung, der bei einer FULL-Lieferung entfällt
- die betroffenen Projekte
- die enthaltenen Änderungen und Löschungen

Der Workflow schreibt diese Angaben nach
`.github/release-approvals/<Release-Tag>.json`. Die Datei enthält je Projekt
dieselben Felder `projekt`, `stand` und `elemente` wie die spätere
Informationsdatei. Die Prüfsummen entstehen erst beim Paketbau und sind daher
nicht Teil der Freigabeanforderung. Der Pull Request nimmt diese Datei in
den Lieferbranch auf und macht den geprüften Umfang dort dauerhaft
nachvollziehbar.

Eine zweite Person prüft, dass dieser Stand in M/Text-Funktionstest geprüft
wurde und der ausgewiesene Umfang geliefert werden soll. Ändert sich der
fachliche Branchstand oder die Mandantenkonfiguration während der Freigabe,
muss der Freigabe-PR mit dem neuen Stand erzeugt werden. Nach Review und Merge
prüft der Workflow die GitHub-Daten des Pull Requests und den versionierten
Freigabenachweis. Danach erstellt der Workflow den regulären Release-Tag auf
dem Merge-Commit des Pull Requests und startet die Lieferung.

Der Merge-Commit trägt gegenüber dem freigegebenen Commit ausschließlich den
Freigabenachweis. Weil der Tag auf ihm liegt, enthält der getaggte Stand diesen
Nachweis, und der Releasebau kann ihn dort lesen und erneut gegen den
freigegebenen Lieferumfang prüfen.

Fehlt `releasefreigabe` in der Mandantenkonfiguration, gilt dieser
Pull-Request-Ablauf. Mit dem Wert `direkter_tag` kann ein Mandant reguläre
Release-Tags durch einen berechtigten Benutzer erstellen lassen. Diese
Konfigurationsänderung unterliegt selbst dem Pull-Request-Verfahren.

Ein regulärer Tag, der bei geltender Pull-Request-Freigabe außerhalb des
Freigabeworkflows erstellt wurde, wird vom zentralen Release-Workflow
abgelehnt. Der Tag wird nicht automatisch gelöscht oder verschoben. Der
Mandant wendet sich zur Klärung und gegebenenfalls zur Löschung an die
FI-GitHub-Administration.

Beta-Tags mit Buchstabensuffix können in beiden Konfigurationen lokal oder in
GitHub erstellt und gepusht werden. Sie können nicht für eine produktive
Lieferung verwendet werden und benötigen deshalb keinen Release-Freigabe-PR.

Für alle Release-Tags gelten außerdem folgende Regeln:

- Die Release-Version enthält keinen Schrägstrich
- Der Tag liegt auf einem Commit eines geschützten Branches
- Ein vorhandener Release-Tag wird nicht auf einen anderen Commit verschoben

### Release automatisch bauen und übertragen

Ein zulässiger Release-Tag startet den zentralen Workflow in `mtext_actions`.
Er checkt den markierten Commit aus, erzeugt für jedes Projekt das gemeinsame
M/Text-Projektpaket und überträgt dessen F- oder D-Archive an den Mainframe.
Die JSON-Informationsdatei bleibt beim GitHub-Artefakt und wird nicht als
Mainframe-Member übertragen.

### Lieferarten FULL und DELTA

Die Release-Version `100`, beispielsweise bei `v261.100` oder `v261.100a`,
erzeugt für jedes einbezogene Projekt eine FULL-Lieferung. Sie besteht aus
einem F-Element mit dem vollständigen Projektstand und einem zusätzlichen
leeren D-Element.

Die nachgelagerte Ressourcen-Aktualisierung entpackt bei einer FULL-Lieferung
zuerst das F-Element. Ist auch ein D-Element vorhanden, entpackt sie dieses
anschließend und löscht die in dessen Löschliste aufgeführten Pfade. Das leere
D-Element ersetzt bei der Übergabe das gleichnamige D-Element einer früheren
Lieferung. Dadurch kann ein vorheriges DELTA den neuen FULL-Stand nicht wieder
verändern.

Jede andere Release-Version derselben Releaselinie erzeugt ein kumulatives
DELTA gegen den regulären `.100`-Tag. Das D-Element enthält alle seitdem neuen
und geänderten Dateien sowie eine Löschliste. `v261.108`, `v261.108a` und
`v261.108b` enthalten damit jeweils alle Änderungen seit `v261.100`.

Das Entpacken eines DELTAs entfernt keine Dateien, die im gelieferten Stand
nicht mehr vorkommen. Die Löschliste nennt deshalb die seit `.100` gelöschten
repositoryrelativen Dateipfade. Nach dem Entpacken entfernt die
Ressourcen-Aktualisierung diese Dateien aus `serverSync`. Eine Umbenennung wird
als Löschen des bisherigen und Hinzufügen des neuen Pfads behandelt.

### CodePipeline-Elemente

Der Name eines Elements ist zugleich sein Mainframe-Member. Er setzt sich aus
Mandantenkürzel, Projektcode und Elementart zusammen:

```text
<Mandantenkürzel><Projektcode><F|D>
```

Beispielsweise bezeichnet `BYAUTOND` das DELTA-Element für
`LOMS_Autonom[BY]`. Eine FULL-Lieferung von `LOMS_Basis` der FI erzeugt
`FIBASISF` mit dem vollständigen Projektstand sowie ein leeres `FIBASISD`.

Die Projektcodes werden wie folgt gebildet:

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

Für den Inhalt der Elemente gilt:

- Ein F-Element enthält den vollständigen Projektbaum
- Ein reguläres D-Element enthält die seit `.100` neuen und geänderten Dateien
  sowie die Löschliste
- Das bei einer FULL-Lieferung zusätzlich erzeugte D-Element enthält ein leeres
  Projektverzeichnis und eine leere Löschliste

### Releaseartefakt

Das GitHub-Actions-Artefakt enthält die erzeugten Archive, die zugehörigen
JCL-Dateien und die projektbezogenen JSON-Informationsdateien. Es wird 30 Tage
aufbewahrt. Der Übergabejob überträgt die Archive unter ihren Membernamen und
reicht die zugehörige JCL ein. Die Informationsdateien werden nicht an den
Mainframe übertragen.

Schlägt die Übergabe fehl, kann dasselbe Artefakt erneut übergeben werden. Die
Pakete müssen dafür nicht neu gebaut werden.

Nach der Mainframe-Übergabe erstellt der zentrale Workflow im
Mandanten-Repository ein GitHub Release zum vorhandenen Release-Tag. Die
Release-Beschreibung nennt Release-Tag, Lieferart und Commit-SHA. Sie
bestätigt die technische Übergabe und enthält die JSON-Informationsdateien.
Diese dienen als Lieferbeleg. Die fachliche Freigabe ist bei einem regulären
Release bereits durch den Release-Freigabe-PR erteilt.

### Mainframe-Übergabe

Für die technische Vorbereitung wird angenommen, dass der Mainframe explizites
FTPS anbietet. Die FTPS-Variante muss der Mainframe-Betrieb noch bestätigen.
Unter dieser Annahme wird das erzeugte FULL- oder DELTA-Paket zunächst unter
seinem Membernamen in `IEA.LOMS.TONICZ` übertragen. Der Client prüft das
Mainframe-Zertifikat mit dem System-Vertrauensspeicher des Runners und schützt
Steuerungs- und passive Datenverbindungen mit TLS. Anschließend kopiert die
beim Paketbau aus `templates/mainframe-upload.jcl` erzeugte JCL den Member nach
`IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ` und registriert ihn in CodePipeline. Dabei
gelten `STRMNAME=BOAS`, `MTYPE=TONICZ` und `MNAME=<Membername>`.

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
    release-approvals/
      <Release-Tag>.json
    workflows/
      check-resources.yml
      release-approval.yml
      sync-resources.yml
      release.yml
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
      release-approval-finalize.yml
      release-approval-prepare.yml
      release.yml
      reusable-check-resources.yml
      reusable-dispatch.yml
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
| M/Text-Entwicklung synchronisieren | Push auf `feature/Rnnn/<Bezeichnung>` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `mtext.py sync-resources` | Projekte aus dem Commit mit der M/Text-Entwicklungsumgebung synchronisieren |
| M/Text-Funktionstest synchronisieren | Push oder Merge auf `main` oder `release/Rnnn` sowie manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `mtext.py sync-resources` | Projekte aus dem Commit mit der M/Text-Funktionstestumgebung synchronisieren |
| Reguläres Release freigeben | Manueller Start auf dem Lieferbranch, selbst eröffneter Freigabe-PR und dessen Merge | `release-approval.yml` | `reusable-dispatch.yml` → `release-approval-prepare.yml` oder `release-approval-finalize.yml` | `mtext.py release-approval` | Regulärer Release-Tag auf dem Merge-Commit der Freigabe erstellt |
| Release bauen und übertragen | Push eines Tags `vnnn.nnn` oder `vnnn.nnnx` | `release.yml` | `reusable-dispatch.yml` → `release.yml` | `mtext.py build-release`, `publish-mainframe`, danach `publish-github-release` | FULL oder DELTA an den Mainframe übertragen, GitHub Release mit Lieferinformationen erstellt |
| `mtext_actions` testen | Pull Request oder Push auf `main` in `mtext_actions` | keiner | `ci.yml` | `python -m unittest discover` | Zentrale Tests ausgeführt |

### Trigger-Workflows in den Mandanten-Repositories

Die Trigger-Workflows reagieren auf Änderungen und starten die
Verarbeitung in `mtext_actions`:

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `check-resources.yml` | Pull Request oder manueller Start | Mandantenkonfiguration und geänderte konfigurierte Ressourcen oder den gewählten Vollstand prüfen, Syntaxbefunde als Warnungen anzeigen |
| `release-approval.yml` | Manueller Start oder Merge eines Release-Freigabe-PR | Freigabe-Branch vorbereiten oder den regulären Release-Tag auf dem Merge-Commit erstellen |
| `sync-resources.yml` | Push auf einen Feature-, `main`- oder Release-Branch sowie manueller Start | Projekte nach M/Text-Entwicklung oder -Funktionstest übertragen |
| `release.yml` | Release-Tag | Release-Erstellung starten |

Syntaxbefunde aus `check-resources.yml` dienen als Hinweise und verhindern den
Merge nicht.

### Zentrale Workflows

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `reusable-check-resources.yml` | Aufruf durch `check-resources.yml` | Mandantenkonfiguration sowie JSON- und XML-Ressourcen ohne Zugriff auf Zielsysteme prüfen |
| `reusable-dispatch.yml` | Aufruf durch `release.yml` oder `release-approval.yml` | Benannten zentralen Workflow mit seinen Eingaben starten |
| `reusable-sync-resources.yml` | Aufruf durch `sync-resources.yml` | Projekte nach M/Text übertragen |
| `release-approval-prepare.yml` | Start durch `reusable-dispatch.yml` | Freigabenachweis erzeugen und auf dem Freigabe-Branch veröffentlichen |
| `release-approval-finalize.yml` | Start durch `reusable-dispatch.yml` | Nach geprüftem Merge den regulären Release-Tag erstellen |
| `release.yml` | Start durch `reusable-dispatch.yml` | FULL- und DELTA-Pakete erstellen, an den Mainframe übertragen und die Lieferinformationen im Mandanten-Repository bereitstellen |
| `ci.yml` | Pull Request oder Push auf `main` in `mtext_actions` | Tests ausführen |
| `update-mandant-workflows.yml` | Manueller Start | Verweise auf `mtext_actions` in den Mandanten-Workflows aktualisieren |

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
| `RELEASE_APPROVAL_READY` | Freigabenachweis für den Pull Request wurde erzeugt | – |
| `RELEASE_APPROVAL_VALIDATED` | Merge und Freigabenachweis passen zum freizugebenden Commit | – |
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
| `releasefreigabe` | `pull_request` oder `direkter_tag`. Ohne das Feld gilt `pull_request`. |
| `excluded_projects` | Projektverzeichnisse, die weder synchronisiert noch paketiert werden |
| `hostprofile` | Assignment und CodePipeline-Stage je Hostprofil |

Beispiel:

```json
{
  "mandant": {
    "kuerzel": "FI",
    "releaselinie": "R270",
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
`main` steht sie im Feld `releaselinie`. Mandanten, die reguläre Release-Tags
durch einen berechtigten Benutzer erstellen lassen, setzen zusätzlich:

```json
{
  "mandant": {
    "releasefreigabe": "direkter_tag"
  }
}
```

Ohne diese ausdrückliche Ausnahme gilt die Freigabe über Pull Request.

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
| `release/Rnnn` | Geschützt, fachliche Änderung über Pull Request im Vier-Augenprinzip, Erstellung aus geschütztem Branch oder Release-Tag |
| `feature/Rnnn/<Bezeichnung>` | Keine zusätzliche Schutzregel |
| Reguläre Release-Tags `vnnn.nnn` | Bei Pull-Request-Freigabe erstellt der technische Freigabeworkflow den Tag. Ein außerhalb dieses Ablaufs erzeugter Tag startet keine Lieferung. |
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
veröffentlicht die Freigabe-Branches, liest den zusammengeführten Freigabe-PR
und erstellt die freigegebenen Tags sowie die GitHub Releases mit den
Informationsdateien.

Ob organisationsweite Tag-Rulesets die Erstellung und Löschung der
Release-Tags zusätzlich einschränken, ist mit der FI-GitHub-Administration zu
prüfen. Die Lieferfreigabe verlässt sich nicht darauf. Der zentrale
Release-Workflow lehnt einen regulären Tag ab, wenn die konfigurierte
Pull-Request-Freigabe nicht nachgewiesen ist.

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
