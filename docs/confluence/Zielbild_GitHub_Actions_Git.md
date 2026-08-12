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
- Release-Tags folgen dem geschützten Muster `v{Release-Version}`

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
    │ Release-Tag auf main oder release/Rnnn
    ▼
zentraler Paketbau und Mainframe-Übergabe durch mtext_actions
```

Bei einem Feature-Push werden die M/Text-Projekte automatisch mit der
M/Text-Entwicklungsumgebung synchronisiert. Ein Merge nach `main` oder
`release/Rnnn` synchronisiert sie automatisch mit der
M/Text-Funktionstestumgebung. Ein Release-Tag startet automatisch den Paketbau
und die Mainframe-Übergabe.

### Entscheidungen und Nutzen

| Entscheidung | Nutzen |
|---|---|
| Branches nach dem organisationsweiten Leitfaden | `main`, Release- und Feature-Branches reichen für Entwicklung und Wartung aus. Zusätzliche Prozess-Branches oder Cherry-Picks zwischen M/Text-Entwicklung und M/Text-Funktionstest sind nicht nötig. |
| Feature-Push nach M/Text-Entwicklung | Eine Änderung kann vor dem Pull Request im passenden M/Text-Ziel geprüft werden. |
| Pull Request mit Squash Merge | Jeder Pull Request wird als ein fachlicher Commit in den Zielbranch übernommen. Review und Arbeitscommits bleiben im Pull Request sichtbar. |
| `serverSync` zwischen den Synchronisationen weiterverwenden | Bei einem Push werden neue, geänderte und gelöschte Ressourcen übertragen. Unveränderte Projekte müssen nicht erneut kopiert werden. |
| Geschützter Release-Tag als Lieferauslöser | Der Tag verweist auf den in M/Text-Funktionstest geprüften Commit und kann später nicht verschoben werden. Er startet automatisch den Paketbau und die Mainframe-Übergabe. |
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

## 3. M/Text-Synchronisation

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

### M/Text-Transport nach `serverSync`

Für M/Text ist das lokale `serverSync`-Verzeichnis die Grundlage für die
Synchronisierung mit der internen Ressourcen-Verwaltung. Dort wird wie bisher
der gesamte Projektbaum abgelegt, passend zu dem letzten synchronisierten
Commit. Anschließend wird via M/Text-Adapter die Synchronisierung angestoßen.

Der Transport nach `serverSync` ist derzeit noch festzulegen:

| Variante | Ablauf | Zu klären | Aufwand |
|---|---|---|---|
| PUT an den Adapter | Der Runner überträgt die Ressourcen an den Adapter. Dieser schreibt `serverSync` und stößt danach die Synchronisierung an. | HTTP-Vertrag, Authentifizierung und Größenlimits | mittel bis hoch |
| Direkter Sharezugriff | Der Runner schreibt auf das Netzlaufwerk und ruft danach den bestehenden Adapter auf. | Erreichbarkeit, Pfad und Schreibrechte | gering |
| GitHub-Actions-Artefakt | Der Workflow speichert die ausgecheckten M/Text-Projekte als Artefakt. Der Adapter oder M/Text lädt sie herunter und schreibt `serverSync`. | Zugriff auf GitHub Actions, Zuständigkeit für den Download und Aufbewahrungsfrist | mittel |

Unabhängig vom Transportweg werden jeweils die M/Text-Projekte aus dem
ausgewählten Commit ausgecheckt. Es werden normaler Weise nur die Änderungen
zum vorhandenen Stand zu M/Text übertragen, es sei denn es handelt sich um die
erste Synchronisierung über GitHub Actions, um einen Wechsel der führenden
Releaselinie, oder um eine manuelle Wiederherstellung.

Bei einer manuellen Wiederherstellung wird mit der Commit-SHA ausgewählt,
welche Version der M/Text-Projekte wiederhergestellt werden soll. Der in GitHub
Actions ausgewählte Branch gibt dann vor, welches M/Text-Ziel synchronisiert
wird. Die Synchronisierung ist idempotent und kann bei Abbrüchen / Fehlern
einfach wiederholt werden.

## 4. Release-Erstellung und Mainframe-Übergabe

### Release-Tags

Für Release-Tags gelten die organisationsweit eingerichteten Regeln des
Leitfadens:

- Der Name folgt `v{Release-Version}`, beispielsweise `v261.100` oder
  `v261.108`
- Die Release-Version enthält keinen Schrägstrich
- Der Tag liegt auf einem Commit eines geschützten Branches
- Ein Release-Tag wird nach der Erstellung nicht gelöscht

Der Release-Tag entspricht der zentral vorgegebenen Release-Version. Vor dem
Push muss sorgfältig geprüft werden, dass der Tag auf dem vorgesehenen Commit
liegt. Eine nachträgliche Korrektur unter demselben Release-Tag ist im
vorgesehenen Verfahren nicht möglich.

### Release automatisch bauen und übertragen

Wird ein Release-Tag in ein Mandanten-Repository gepusht, startet automatisch
der passende Workflow in `mtext_actions`. Er checkt den mit dem Tag markierten
Commit aus, baut daraus die benötigten FULL- und DELTA-Pakete und überträgt sie
an den Mainframe.

### Lieferarten FULL und DELTA

Ein Tag mit der Endung `.100`, beispielsweise `v261.100`, erzeugt für jedes
einbezogene Projekt eine FULL-Lieferung. Sie besteht aus einem F-Element mit
dem vollständigen Projektstand und einem zusätzlichen leeren D-Element.

Jeder weitere Release-Tag derselben Releaselinie erzeugt ein kumulatives DELTA
gegen den `.100`-Tag. Das D-Element enthält alle seitdem neuen und geänderten
Dateien sowie eine Löschliste. `v261.108` enthält damit alle Änderungen seit
`v261.100`.

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

### Releaseartefakt und Manifest

Für jedes Projekt wird zusätzlich eine Informationsdatei erzeugt. Sie nennt
die Änderungen seit dem vorherigen Release und den Inhalt des TAR-Archivs. Die
Mandanten verwenden diese Angaben, um zu prüfen, ob die gewünschten Änderungen
im Paket enthalten sind.

Die erzeugten Pakete, Informationsdateien, das Manifest und die Prüfsummen
werden bei der zentralen Workflow-Ausführung als GitHub-Artefakt gespeichert.
Das Manifest beschreibt, was geliefert wurde und aus welchem Repository-Stand
die Lieferung entstanden ist. Vor der nachfolgenden Mainframe-Übergabe werden
die Pakete und Informationsdateien mit dem Manifest abgeglichen.

Schlägt die Übergabe fehl, kann dasselbe Artefakt erneut übergeben werden. Die
Pakete müssen dafür nicht neu gebaut werden.

### Kompatibilität zum bisherigen Lieferweg

Im bisherigen Jenkins-/SVN-Ablauf wurden die erzeugten Pakete und
Informationsdateien zusätzlich nach `/nfs/mtext/trans` kopiert. Der alte Hook
selbst liest sie von dort nicht wieder ein. Für die Mainframe-Übergabe verwendet
er die Pakete aus seinem Arbeitsverzeichnis. Im neuen Ablauf übernimmt das
GitHub-Artefakt die Ablage für die technische Übergabe.

Die Paketnamen, Mainframe-Member und Pfade innerhalb der FULL- und
DELTA-Archive bleiben gleich. Auch das leere D-Paket einer FULL-Lieferung und
die Löschliste eines DELTAs bleiben erhalten. Die TAR-Metadaten werden jetzt
vereinheitlicht, damit Wiederholungen nicht durch abweichende Zeitstempel
unterschiedliche Pakete erzeugen. In den Namen der Lieferbelege stehen
entsprechend dem neuen Tagformat `v261.100` und `v261.108` statt `R261.100` und
`R261.108`.

Nach der Mainframe-Übergabe erstellt der zentrale Workflow im
Mandanten-Repository ein GitHub Release zum vorhandenen Release-Tag. Die
Release-Beschreibung fasst die Änderungen und den Paketinhalt zusammen. Die
Informationsdateien werden zusätzlich als Dateien an das GitHub Release
angehängt. Damit können die Mandanten die Lieferung direkt in ihrem Repository
prüfen und die vollständigen Angaben bei Bedarf herunterladen. Ein Zugriff auf
`mtext_actions` oder das bisherige Verzeichnis `/nfs/mtext/trans` ist dafür
nicht erforderlich.

### Mainframe-Übergabe

Für die Mainframe-Übergabe wird das erzeugte FULL- oder DELTA-Paket zunächst
unter seinem Membernamen in `IEA.LOMS.TONICZ` übertragen. Anschließend kopiert
die JCL-Datei `templates/mainframe-upload.jcl` aus `mtext_actions` den Member
nach `IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ` und registriert ihn in CodePipeline.
Dabei gelten `STRMNAME=BOAS`, `MTYPE=TONICZ` und `MNAME=<Membername>`.
Änderungen an dieser JCL können vor dem Merge im Pull Request geprüft werden.

Der Paketbau ist von der Mainframe-Übergabe getrennt. Übergaben desselben
Mandanten werden nacheinander ausgeführt. Verschiedene Mandanten können
gleichzeitig liefern.

### Mainframe-Zugangsdaten

Die Mainframe-Zugangsdaten liegen im Repository `mtext_actions`:

| Name | Ablage |
|---|---|
| `MAINFRAME_FTP_HOST` | Repositoryvariable |
| `MAINFRAME_FTP_USER` | Repositoryvariable |
| `MAINFRAME_FTP_PASSWORD` | Repository-Secret |

Der technische FTP-Benutzer wird für die Übergaben aller Mandanten verwendet.

## 5. Repositories

### Mandanten-Repositories

Ein Mandanten-Repository folgt diesem Aufbau:

```text
fi_lbs_entw_oms_<kuerzel>/
  .github/
    config.json
    workflows/
      check-resources.yml
      validate-config.yml
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
      release.yml
      reusable-check-resources.yml
      reusable-release-dispatch.yml
      reusable-release.yml
      reusable-sync-resources.yml
      reusable-validate-config.yml
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
      github_release.py
      mainframe.py
      manifest.py
      process.py
      release.py
      sync.py
    build_release.py
    check_resources.py
    publish_github_release.py
    publish_mainframe.py
    sync_resources.py
    validate_config.py
    workflow_configuration.py
  templates/
    mainframe-upload.jcl
  tests/
    <automatisierte Tests>
```

## 6. Workflows

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Trigger-Workflow | Zentraler Workflow | Python-Skript | Ergebnis |
|---|---|---|---|---|---|
| Trigger-Workflows aktualisieren | Manueller Start in `mtext_actions` mit der gewünschten Commit-SHA | keiner | `update-mandant-workflows.yml` | `workflow_configuration.py` | Geschützte Mandantenbranches verwenden die neue `mtext_actions`-Version |
| Mandantenkonfiguration prüfen | Push mit einer Änderung an `.github/config.json` | `validate-config.yml` | `reusable-validate-config.yml` | `validate_config.py` | Konfiguration geprüft |
| JSON- und XML-Ressourcen prüfen | Pull Request oder manueller Start | `check-resources.yml` | `reusable-check-resources.yml` | `check_resources.py` | Geänderte konfigurierte Ressourcen oder gewählter Vollstand geprüft, Syntaxbefunde als nicht blockierende Warnungen angezeigt |
| M/Text-Entwicklung synchronisieren | Push auf `feature/Rnnn/<Bezeichnung>` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync_resources.py` | Projekte aus dem Commit mit der M/Text-Entwicklungsumgebung synchronisieren |
| M/Text-Funktionstest synchronisieren | Push oder Merge auf `main` oder `release/Rnnn` sowie manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync_resources.py` | Projekte aus dem Commit mit der M/Text-Funktionstestumgebung synchronisieren |
| Release bauen und übertragen | Push eines Tags `vnnn.nnn` | `release.yml` | `reusable-release-dispatch.yml` → `release.yml` → `reusable-release.yml` | `build_release.py`, `publish_mainframe.py`, danach `publish_github_release.py` | FULL oder DELTA an den Mainframe übertragen, GitHub Release mit Lieferinformationen erstellt |
| `mtext_actions` testen | Pull Request oder Push auf `main` in `mtext_actions` | keiner | `ci.yml` | `python -m unittest discover` | Zentrale Tests ausgeführt |

### Trigger-Workflows in den Mandanten-Repositories

Die Trigger-Workflows reagieren auf Änderungen und starten die
Verarbeitung in `mtext_actions`:

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `check-resources.yml` | Pull Request oder manueller Start | Geänderte konfigurierte Ressourcen oder den gewählten Vollstand prüfen und Befunde als Warnungen anzeigen |
| `validate-config.yml` | Änderung an `.github/config.json` | Mandantenkonfiguration prüfen |
| `sync-resources.yml` | Push auf einen Feature-, `main`- oder Release-Branch sowie manueller Start | Projekte nach M/Text-Entwicklung oder -Funktionstest übertragen |
| `release.yml` | Release-Tag | Release-Erstellung starten |

Syntaxbefunde aus `check-resources.yml` dienen als Hinweise und verhindern den
Merge nicht.

### Zentrale Workflows

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `reusable-check-resources.yml` | Aufruf durch `check-resources.yml` | JSON- und XML-Ressourcen ohne Zugriff auf Zielsysteme prüfen |
| `reusable-validate-config.yml` | Aufruf durch `validate-config.yml` | Mandantenkonfiguration prüfen |
| `reusable-sync-resources.yml` | Aufruf durch `sync-resources.yml` | Projekte nach M/Text übertragen |
| `reusable-release-dispatch.yml` | Aufruf durch `release.yml` im Mandanten-Repository | `release.yml` in `mtext_actions` starten |
| `release.yml` | Start durch `reusable-release-dispatch.yml` | `reusable-release.yml` aufrufen |
| `reusable-release.yml` | Aufruf durch `release.yml` in `mtext_actions` | FULL- und DELTA-Pakete erstellen, an den Mainframe übertragen und die Lieferinformationen im Mandanten-Repository bereitstellen |
| `ci.yml` | Pull Request oder Push auf `main` in `mtext_actions` | Tests ausführen |
| `update-mandant-workflows.yml` | Manueller Start | Verweise auf `mtext_actions` in den Trigger-Workflows aktualisieren |

### Protokolle und Rückmeldung

GitHub Actions übernimmt `stdout` und `stderr` der Workflows in das Protokoll.
Die Python-Skripte schreiben ein erfolgreiches Ergebnis als JSON nach `stdout`
und Warnungen oder Fehler nach `stderr`. Bei der Konfigurationsprüfung und der
M/Text-Synchronisation sind diese Ausgaben im Mandanten-Repository sichtbar.

Die Release-Erstellung läuft dagegen als eigener Workflow in `mtext_actions`.
Ihr Ergebnis und die Informationen zum Paket werden deshalb nach Abschluss im
GitHub Release des Mandanten-Repositories angezeigt.

### Aktualisierung der Trigger-Workflows

Wenn die Mandanten-Repositories eine neue Version von `mtext_actions`
verwenden sollen, starten die zuständigen Admins
`update-mandant-workflows.yml` manuell. Der Workflow trägt die gewünschte
Version in die vorhandenen Trigger-Workflows ein und schreibt für jeden
Zielbranch einen administrativen Rollout-Commit.

Die Workflowdateien gehören zu den Branches der Mandanten-Repositories. Daher
aktualisiert der Workflow `main` und jeden vorhandenen Release-Branch getrennt.
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
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinienzuordnung wurden geprüft | – |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig | `2` |
| `SOURCE_FAILED` | Checkout, Commit, Branch oder Tag können nicht als Quelle verwendet werden | `3` |
| `RESOURCE_TRANSFER_FAILED` | Die Projekte konnten nicht unter `serverSync` bereitgestellt werden | `5` |
| `ADAPTER_FAILED` | Der M/Text-Adapter war nicht erreichbar oder hat die Anfrage abgelehnt | `6` |
| `ADAPTER_ACCEPTED` | Der M/Text-Adapter hat die Anfrage angenommen | – |
| `PACKAGE_FAILED` | Paket, Lieferbeleg oder Manifest konnten nicht korrekt erstellt oder geprüft werden | `4` |
| `ARTIFACT_READY` | Die Releasepakete wurden erstellt und geprüft | – |
| `MAINFRAME_TRANSFER_FAILED` | Die FTP- oder JES-Übergabe ist fehlgeschlagen | `7` |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden per FTP und JES übergeben | – |
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
`main` steht sie im Feld `releaselinie`.

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
| Release-Tags `v{Release-Version}` | Organisationsweit geschützte Tags nach dem Leitfaden |
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
`mtext_actions`. Es gilt für die zugeordneten Mandanten-Repositories und besitzt
dort `Contents: read and write` sowie `Workflows: read and write`. Der
technische Benutzer ist in den Schutzregeln als Ausnahme von der
Pull-Request-Pflicht für den administrativen Workflow-Rollout hinterlegt. Das
Token aktualisiert damit die Trigger-Workflows und erstellt die GitHub Releases
mit den Lieferinformationen.

## 9. Mögliche Phase 2

Die erste Ausbaustufe bleibt bewusst auf die sichere Ablösung des bestehenden
Lieferwegs begrenzt. Nach einem stabilen Produktivbetrieb können insbesondere
folgende Erweiterungen bewertet werden:

- den nachgelagerten fachlichen Status in M/Text und auf dem Mainframe abfragen
  und im Workflow anzeigen (Polling)
- die FTP-/JES-Übergabe auf einen verschlüsselten Transport umstellen, sobald
  das Zielsystem dafür einen verbindlichen Vertrag bereitstellt
- Betriebsmetriken und kompakte Laufzusammenfassungen ergänzen, ohne
  mandantenübergreifende oder vertrauliche Details offenzulegen
- zusätzliche E-Mail-Benachrichtigungen für relevante Workflow-Ergebnisse
  ergänzen, ohne den fachlichen Laufstatus von der Benachrichtigung abhängig zu
  machen
- Aktualisierungen gepinnter Actions sowie ergänzende Workflow-, Shell-, Typ-
  und Abdeckungsprüfungen automatisieren
