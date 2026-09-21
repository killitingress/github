# Zielbild für die Ablösung von Jenkins und SVN

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in GitHub verprobt. Während dieser Testphase bleibt der
bisherige Prozess produktiv. Unmittelbar vor der für Anfang 2027 geplanten
Produktivsetzung wird der dann gültige SVN-Stand nach Git übertragen.
Danach sind Git und GitHub Actions im FI-Netz für diesen Prozess führend und
SVN wird zusammen mit dem EN4920-Netz abgebaut.

Jeder Mandant erhält ein eigenes Git-Repository in github.intern mit seinen
M/Text-Ressourcen, Trigger-Workflows und einer relevanten Konfigurationsdatei.
Die gemeinsam genutzte und im Folgenden beschriebene CI/CD-Automatisierung
nennen wir `mtext_actions`. Sie führt Validierungen, Synchronisierung und
Lieferung an CodePipeline zentral durch.

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
in den Zielbranch übernommen. Dabei entsteht ein neuer Commit.

Wird ein Feature-Branch nach GitHub gepusht, werden seine M/Text-Projekte
automatisch mit der M/Text-Entwicklungsumgebung synchronisiert, damit das
Feature vom Entwickler dort vorab getestet werden kann. Ein Merge nach `main`
oder `release/nnn` synchronisiert in der Folge automatisch die entsprechende
M/Text-Funktionstestumgebung. Dort soll das Feature dann von der LBS getestet
und fachlich freigegeben werden. Danach kann der Feature-Branch wieder gelöscht
werden.

Eine Mainframe-Lieferung kann entweder von `main` oder `release/nnn`
durchgeführt werden und verwendet dann den dort vorbereiteten Ressourcenstand,
oder auf einer in `bereitstellung/nnn.nnn` zusammengestellten Teillieferung. Ein
Vorbereitungs-Workflow nutzt ein Gihub-Issue um die Details zur Lieferung
festzuhalten. Mittels Kommentar wird eine Lieferung freigegeben und dadurch die
Pakete gebaut und an den Mainframe übergeben. Nach erfolgreicher Übergabe
entsteht der Liefer-Tag im Mandantenrepository.

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
Ressourcenstand ist für eine Lieferung bereit
```

#### Lieferablauf

```text
Lieferung vorbereiten
    │ Branch auswählen (bereitstellung/nnn.nnn, main oder release/nnn)
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

Mit jedem OSPlus-Release, also zweimal im Jahr, wechselt die produktive
Releaselinie auf `main`. Wird beispielsweise `270` produktiv, bleibt der
bisherige Stand von `main` als `release/261` für die weitere Pflege erhalten.

Für diesen Wechsel wird in `feature/270/releasewechsel` der Stand von
`release/270` vorbereitet und die Mandantenkonfiguration auf Releaselinie
`270` gesetzt. Dabei ist zu klären, welche Änderungen der bisherigen
produktiven Linie seit ihrem letzten Liefer-Tag übernommen werden sollen.
Der fachlich abgestimmte Stand wird anschließend über einen Pull Request mit
Squash Merge nach `main` übernommen.

Nach dem Wechsel lassen sich weitere Releaselinien, etwa `release/271`, von
`main` abzweigen. Ein initialier Abgleich mit M/Text hat über **Ressourcen
synchronisieren** manuell zu erfolgen.

Sobald eine Releaselinie nicht mehr vorgehalten werden muss, kann ihr
Release-Branch gelöscht werden. Die bereits gelieferten Stände bleiben
über ihre Liefer-Tags erreichbar.

## 3. Synchronisierung

### Zielermittlung

Jede Releaselinie ist einer technischen ETAPS-Linie zugeordnet. Zu jeder
ETAPS-Linie gehören eine M/Text-Entwicklungsumgebung und eine
M/Text-Funktionstestumgebung, jeweils in Stage 1 (Institut 297).

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

### Inhalt einer Synchronisierung

Ausgangspunkt für eine Synchronisierung ebenso wie für eine Lieferung, ist der
zu der Commit-SHA des Laufes zugehörige Ressourcenstand. Welche Projekte daraus
an den Adapter übertragen werden, ergibt sich aus der Mandantenkonfiguration
und dem ermittelten Änderungs-Umfang.

Es werden entweder alle konfigurierten Projekte übertragen (FULL), in welchem
Fall je Projekt das vollständige Projektverzeichnis als F-Archiv übertragen
wird. Oder es werden nur die vom Vergleich gegenüber der vorherigen
(erfolgreichen) Synchronisierung abweichenden Inhalte übertragen (DELTA),
inklusive einer Löschliste, als D-Archiv.

### Projektarchive

Synchronisierung und Mainframe-Lieferung verwenden dasselbe Archivformat:
je M/Text-Projekt ein gzip-komprimiertes TAR-Archiv (`.tgz`).

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

Die Löschliste eines D-Archivs nennt je Zeile den repositorybezogenen Pfad
einer zu entfernenden Datei, einschließlich des Projektnamens. Eine Umbenennung
erscheint als Löschung des bisherigen und Hinzufügen des neuen Pfades. Das
Löschlistenformat bleibt gegenüber dem Jenkins-Ablauf unverändert.

#### Informationsdaten der Synchronisierung

Bei der Synchronisierung via LTOMA stehen die Informationsdaten zu jedem
Archiv im initialen POST-Body. Sie legen den Umfang der hochzuladenden
Archive fest. `scope.von` (bei DELTA) beschreibt den Ausgangsstand und
`scope.bis` den zu synchronisierenden Zielstand. Beide enthalten mit
`referenz` den Branchnamen und mit `commit` die festgehaltene Commit-SHA.
`sha256` ist die Prüfsumme des Archivs.

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

### Ablauf einer Synchronisierung

Adapter und M/Text teilen sich den gemeinsamen Pfad `serverSync/` (ehemals ein
NFS Share im EN4920). Dieser enthält die Projektverzeichnisse aller Mandanten
und bildet wie im alten Ablauf die Basis der M/Text-Synchronisierung.
Ein **Synchronisierungsauftrag** umfasst alle Archive, die mit einer
M/Text-Umgebung synchronisiert werden sollen. Der Workflow überträgt die
zusammengestellten Archive einzeln per HTTP PUT an LTOMA.

Vor dem Archivbau prüft der Workflow die Erreichbarkeit des Adapters mittels
`GET /vMtextAdapter/version`. Schlägt der Aufruf fehl, endet der Lauf mit
`ADAPTER_FAILED`. Bei der manuellen Auswahl `Beide` werden beide Zieladapter vorab geprüft.

Für einen neuen Auftrag gilt folgender Ablauf:

1. Der Workflow bildet die Auftrags-ID als `<GITHUB_RUN_ID>-<Mandantenkürzel>`
   und initiiert darunter einen Auftrag via POST-Request an LTOMA. Im POST-Body
   kündigt er alle Archive und deren Prüfsummen an. Der Adapter antwortet mit
   der Auftrags-ID und dem Status `ready`.
2. Der Workflow lädt jedes angekündigte Archiv nacheinander mit einem eigenen
   PUT-Request unter der Auftrags-ID hoch. Der Adapter speichert die
   Upload-Dateien zunächst außerhalb von `serverSync/` und prüft direkt nach
   Empfang eines Archivs dessen Prüfsumme. Während noch nicht alle Uploads des
   Auftrags abgeschlossen sind, antwortet der Adapter auf Statusabfragen via
   GET mit `uploading`.
3. Sobald alle angekündigten Archive vollständig und korrekt vorliegen, setzt
   der Adapter den Auftrag auf `processing`. Ein Lock je Mandantenkürzel
   verhindert, dass mehrere Aufträge desselben Mandanten gleichzeitig dessen
   Projektbestand verändern oder eine M/Text-Synchronisierung ausführen. Andere
   Mandanten dürfen parallel verarbeitet werden. Ist der Lock belegt, bleibt
   der Auftrag im Status `processing`, bis er verarbeitet werden kann.
4. Unter dem Lock wendet der Adapter die Archive auf `serverSync/` an und
   ruft anschließend LTOMS auf, damit dieser den M/Text-Ressourcen-Cache
   auf Basis von `serverSync`
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
`GET /vMtextAdapter/sync2/{auftrag_id}/execution` nach einem bestehenden Auftrag. Die
Auftrags-ID bleibt beim Wiederholen desselben GitHub-Laufs erhalten. Antwortet
der Adapter mit HTTP 404, baut der Workflow die Archive und startet den
beschriebenen Ablauf.

Besteht der Auftrag bereits in `processing`, wartet der Workflow auf dessen
Abschluss. Bei `succeeded` übernimmt er das Ergebnis und räumt den Auftrag
auf. In beiden Fällen entfallen Archivbau und Uploads. Einen Auftrag in
`ready`, `uploading` oder `failed` löscht er und startet mit neu gebauten
Archiven unter derselben Auftrags-ID erneut.

Ein neuer GitHub-Lauf verwendet eine neue Auftrags-ID. Die Laufzusammenfassung
zeigt die verwendeten Git-Commits und Zielumgebungen und verweist auf die
M/Text-Ausgabe im Laufartefakt `mtext-ergebnis`.

### Auslöser und Reihenfolge

Die automatische Synchronisierung folgt dem Entwicklungsablauf: Ein Push auf
`feature/nnn/<Bezeichnung>` überträgt die Ressourcen nach Entwicklung, ein
Pull Request mit Squash Merge nach `main` oder `release/nnn` nach Funktionstest.
Maßgeblich ist jeweils der Ressourcenstand des auslösenden Commits.

Beim manuellen Start gilt mit `Branchstandard` dieselbe Zielzuordnung wie im
automatischen Ablauf.
Alternativ lassen sich `Entwicklung`, `Funktionstest` oder `Beide` auswählen,
wobei bei `Beide` zuerst Entwicklung und anschließend Funktionstest
abgeglichen wird.

Innerhalb eines Mandanten-Repositories werden die Läufe mit ihrer Prüfung
und Synchronisierung nacheinander ausgeführt. Ein neuer Start lässt den
laufenden Abgleich weiterlaufen, kann jedoch einen bereits wartenden Lauf
ersetzen. Wenn manuelle Abgleiche aufeinander aufbauen, muss deshalb der eine
abgeschlossen sein, bevor der nächste gestartet wird. Andere
Mandanten-Repositories können währenddessen unabhängig davon arbeiten.

## 4. Mainframe-Lieferung

Die Mainframe-Lieferung verwendet dasselbe Archivformat wie die
Synchronisierung, aber einen anderen Transportweg über CodePipeline der IZE9,
MT91 und letztlich im Batch via LXT90#SV, Travic-Link und dessen Folgejob
(`ressourcen_aktualisieren.sh`).

### Liefer-Tags und Lieferstand

Liefer-Tags kennzeichnen die an CodePipeline gelieferten Stände und folgen
dem Muster `rnnn.nnn`, beispielsweise `r261.100` oder `r261.108`. Als
ungeschützte Tags können sie auch für Teillieferungen aus einem
Bereitstellungsbranch verwendet werden.

Für eine Teillieferung werden ausgewählte Änderungen in einem ungeschützten
Branch `bereitstellung/nnn.nnn` zusammengestellt. Als Ausgangspunkt bietet
sich der vorherige Liefer-Tag der Releaselinie an, dessen Stand die bereits
gelieferten Änderungen enthält. Weitere Squash-Commits lassen sich mit EGit
per Cherry-Pick ergänzen. Wer stattdessen von `main` oder `release/nnn`
ausgeht, nimmt dessen gesamten Ressourcenstand in die Lieferung auf. Für ein
DELTA muss der Commit des `.100`-Tags derselben Releaselinie ein Vorfahr des
vorbereiteten Commits sein.

Im Freigabe-Issue werden die Abweichungen gegenüber dem vorherigen Liefer-Tag
gezeigt. Dafür zählt der höchste vorhandene Liefer-Tag mit kleinerer
Tag-Nummer, unabhängig davon, ob sein Commit ein Vorfahr des vorbereiteten
Commits ist. Der Archivinhalt richtet sich dagegen nach dem Hauptrelease:
`.100` liefert FULL mit einem leeren D-Archiv, während Zwischenreleases ein
kumulatives DELTA gegenüber diesem `.100`-Tag enthalten.

Diese Aufteilung ergibt sich aus der Verarbeitung im Travic-Link-Folgejob,
der zuerst das F-Archiv und anschließend das D-Archiv entpackt. Weil beide
im Upload-Verzeichnis erhalten bleiben, muss ein neues Hauptrelease das
bisherige D-Archiv durch ein leeres ersetzen. Bei einem Zwischenrelease
bleibt hingegen das F-Archiv bestehen und ergibt zusammen mit dem neuen
D-Archiv den aktuellen Lieferstand.

Vorbereitung und Freigabe erfolgen über die folgenden Workflows.

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

Die vorbereitete Lieferung wird mit dem Kommentar `/freigabe` im offenen
Freigabe-Issue gestartet. Dazu ist die Repository-Berechtigung `maintain`
oder `admin` erforderlich, wobei auch die vorbereitende Person selbst
freigeben darf. Die im Issue festgehaltene Commit-SHA bestimmt den zu
liefernden Ressourcenstand, der Titel den vorgesehenen Liefer-Tag.

Mit der ersten Freigabe wechselt das Status-Label von `lieferung:vorbereitet`
zu `lieferung:gestartet`. Anschließend baut der Shared Workflow aus
`mtext_actions` die Archive und JCL-Dateien, übergibt sie an den Mainframe und
erzeugt den annotierten Liefer-Tag mit Verweis auf das Freigabe-Issue. Zur
Kontrolle stehen die Lieferdateien 30 Tage im Laufartefakt `release` bereit.

Nach erfolgreichem Abschluss dokumentiert ein Kommentar im Issue den
Liefer-Tag sowie Namen und SHA-256-Prüfsummen der übertragenen Archive. Mit
dem Label `lieferung:abgeschlossen` wird das Issue danach geschlossen.
Soll ein bereits getaggter Stand nochmals übertragen werden, lässt sich dies mit
`/wiederholung` aus demselben Issue anstoßen.

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

Im Mandanten-Repository befinden sich die Trigger-Workflows. Die eigentlichen
Arbeitsschritte liegen in `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Die
Trigger-Workflows nutzen dessen `main` Branch.

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

| Aktion | Auslöser | Trigger-Workflow | Shared Workflow | Python-Aufrufe |
|---|---|---|---| --- |
| Ressourcen prüfen | Manueller Start auf einem ausgewählten Branch | `check-resources.yml` | `shared-check-resources.yml` | `mtext.py resources check` |
| M/Text-Entwicklung synchronisieren | Push auf `feature/nnn/<Bezeichnung>` oder manueller Start | `sync-resources.yml` | `shared-check-resources.yml`, danach `shared-sync-resources.yml` | `mtext.py resources check`, danach `mtext.py resources sync` |
| M/Text-Funktionstest synchronisieren | PR-Merge nach `main` oder `release/nnn` sowie manueller Start | `sync-resources.yml` | `shared-check-resources.yml`, danach `shared-sync-resources.yml` | `mtext.py resources check`, danach `mtext.py resources sync` |
| Lieferung vorbereiten | Manueller Start auf `main`, `release/nnn` oder `bereitstellung/nnn.nnn` | `lieferung-vorbereiten.yml` | `shared-check-resources.yml`, danach `shared-lieferung-check.yml` | `mtext.py resources check`, danach `mtext.py delivery check` |
| Lieferung freigeben und ausführen | Kommentar `/freigabe` im offenen Freigabe-Issue durch eine Person mit `maintain` oder `admin` | `lieferung-ausfuehren.yml` | `shared-lieferung-ausfuehren.yml` | `mtext.py delivery resolve`, danach `mtext.py release build`, danach `mtext.py release mainframe`, danach `mtext.py delivery tag`, danach `mtext.py delivery complete` |
| Lieferung wiederholen | Kommentar `/wiederholung` im zugehörigen Issue einer bereits getaggten Lieferung durch eine Person mit `maintain` oder `admin` | `lieferung-ausfuehren.yml` | `shared-lieferung-ausfuehren.yml` | `mtext.py delivery resolve`, danach `mtext.py release build`, danach `mtext.py release mainframe`, danach `mtext.py delivery complete` |
| `mtext_actions` testen | Pull Request, Push auf `main` oder manueller Start in `mtext_actions` | `ci.yml` | – | `python -m unittest discover` |

### Shared Workflows

| Datei | Auslöser | Aufgabe |
|---|---|---|
| `shared-check-resources.yml` | Aufruf durch `check-resources.yml`, `sync-resources.yml` oder `lieferung-vorbereiten.yml` | Mandantenkonfiguration und konfigurierte Ressourcen ohne Zugriff auf Zielsysteme prüfen |
| `shared-sync-resources.yml` | Aufruf durch `sync-resources.yml` | Projekte nach M/Text übertragen |
| `shared-lieferung-check.yml` | Aufruf durch `lieferung-vorbereiten.yml` | Liefer-Tag aus dem Branch ableiten und Lieferumfang im Freigabe-Issue anzeigen |
| `shared-lieferung-ausfuehren.yml` | Aufruf durch `lieferung-ausfuehren.yml` | Freigabe und Lieferstand prüfen, Archive und JCL für FULL oder DELTA erzeugen, an den Mainframe übertragen, den angenommenen Commit taggen und das Ergebnis im Freigabe-Issue festhalten |
| `ci.yml` | Pull Request oder Push auf `main` oder manueller Start | Tests ausführen |

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
