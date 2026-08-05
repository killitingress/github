# Zielbild für die Ablösung von Jenkins und SVN

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Während der
Testphase bleibt der bisherige Prozess produktiv. Unmittelbar vor der
Produktivsetzung wird der freigegebene SVN-Endstand nach Git übertragen.
Danach sind Git und GitHub Actions für diesen Prozess führend.

Jeder Mandant erhält ein eigenes Repository mit seinen M/Text-Ressourcen und
seiner Konfiguration. Die gemeinsame Automatisierung liegt im zentralen
Repository `mtext-actions`.

Das Branch-Modell folgt dem organisationsweiten Leitfaden:

- `main` ist der geschützte, dauerhafte Branch der führenden Releaselinie.
- `release/Rnnn` enthält eine parallel gepflegte Releaselinie.
- Jede Änderung entsteht in einem Branch `feature/Rnnn/<Bezeichnung>`.
- Änderungen an `main` und `release/Rnnn` erfolgen über Pull Requests im
  Vier-Augenprinzip.
- Pull Requests werden mit Squash Merge zusammengeführt.
- Release-Tags folgen dem geschützten Muster `v{Release-Version}`.

Entwicklung und Abnahme sind keine Git-Branches. Sie bezeichnen die beiden
M/Text-Ziele einer Releaselinie.

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
M/Text-Abnahme der Releaselinie
    │ Release-Tag auf geschütztem Stand
    ▼
zentraler Paketbau und Mainframe-Übergabe durch mtext-actions
```

Ein normaler Feature-Push und ein Merge benötigen keine manuelle Tätigkeit
eines Administrators. Auch die Releaseverarbeitung startet automatisch durch
den Release-Tag.

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

Der weitere Slash innerhalb des Feature-Namens ist zulässig. Der Leitfaden
beschränkt Schrägstriche in der Release-Version von Release-Branches und
Release-Tags, nicht im Namen eines Feature-Branches.

Ein Feature-Branch wird vom geschützten Zielbranch seiner Releaselinie
erstellt:

- Für die führende Releaselinie ist `main` der Zielbranch.
- Für eine parallel gepflegte Linie ist `release/Rnnn` der Zielbranch.
- Ein Feature einer späteren Releaselinie kann bis zum Linienwechsel in seinem
  Feature-Branch entwickelt und in M/Text-Entwicklung getestet werden. Es wird
  erst zusammengeführt, wenn ein geschützter Zielbranch diese Releaselinie
  vertritt.

### Pull Requests und Squash Merge

Eine fertig entwickelte und in M/Text-Entwicklung geprüfte Änderung erhält
einen Pull Request auf den zugehörigen geschützten Zielbranch. Eine zweite
Person prüft die Änderung nach den organisationsweiten Vorgaben. Nach dem
erfolgreichen Review wird der Pull Request mit Squash Merge zusammengeführt.

In den Repository-Einstellungen ist `Allow squash merging` aktiviert. Die
anderen Mergeverfahren sind deaktiviert, damit alle Beteiligten denselben
Bedienweg verwenden.

Squash Merge wird aus folgenden Gründen verwendet:

- Ein Pull Request entspricht einem fachlich zusammengehörigen Commit.
- Zwischenstände und Korrektur-Commits aus dem Feature-Branch belasten den
  Verlauf des Zielbranches nicht.
- Der lineare Verlauf ist für wenig erfahrene Git-Anwender gut
  nachvollziehbar.
- Die Änderung kann über einen Commit zurückgenommen oder auf eine weitere
  Releaselinie übernommen werden.
- Review, Diskussion und ursprüngliche Commits bleiben im Pull Request
  nachvollziehbar.
- Der Entwickler muss zum Zusammenführen keinen Rebase durchführen.

Cherry-Picks gehören nicht zum normalen Weg von Entwicklung nach Abnahme. Sie
werden verwendet, wenn eine bereits zusammengeführte Änderung zusätzlich auf
eine andere Releaselinie übernommen werden soll. Der Squash-Commit bildet dafür
die vollständige Änderung ab.

### Wechsel der führenden Releaselinie

Der Wechsel folgt dem unternehmensweit vorgegebenen Releasezeitpunkt. Es gibt
zwei Hauptreleases pro Jahr.

Vor dem Wechsel wird für die bisher auf `main` geführte Linie bei weiterem
Pflegebedarf ein Branch `release/Rnnn` aus dem freigegebenen Stand erstellt.
Anschließend wird die Releaselinie von `main` in der Mandantenkonfiguration
fortgeschrieben. Die Verantwortlichen des jeweiligen Repositories führen den
Wechsel über Pull Requests durch.

Für `mtext-actions` und `mtext-fi` sind dies die FI-Fachverantwortlichen. Für
die weiteren Mandanten-Repositories sind es die jeweiligen
Mandantenverantwortlichen.

Release-Branches werden gelöscht, wenn keine Änderungen für die Linie mehr
erwartet werden. Der letzte Stand bleibt über die geschützten Release-Tags
wiederherstellbar.

## 3. M/Text-Synchronisation

### Zielermittlung

Die Releaselinie bestimmt die technische ETAPS-Linie. Jede ETAPS-Linie besitzt
ein Entwicklungs- und ein Abnahmeziel:

```text
en01e.ltoms.intern   Entwicklung
en01a.ltoms.intern   Abnahme
```

Die Zuordnung wird zentral in `mtext-actions/config/releaselinien.json`
gepflegt. Der derzeit vorgesehene rollierende Stand ist:

```json
{
  "R260": {"etaps_linie": "en03", "hostprofil": "JUR"},
  "R261": {"etaps_linie": "en01", "hostprofil": "FKT"},
  "R270": {"etaps_linie": "en02", "hostprofil": "JUR"}
}
```

Beim Ausscheiden von R260 kann R271 die ETAPS-Linie `en03` übernehmen.

Für die Zielermittlung gelten folgende Regeln:

| Git-Ereignis | Releaselinie | M/Text-Ziel |
|---|---|---|
| Push nach `feature/Rnnn/<Bezeichnung>` | `Rnnn` aus dem Feature-Branch | Entwicklung |
| Merge nach `release/Rnnn` | `Rnnn` aus dem Release-Branch | Abnahme |
| Merge nach `main` | `releaselinie` aus der Mandantenkonfiguration | Abnahme |

Ein Push auf einen Feature-Branch startet die Synchronisation automatisch. Sie
ist keine technische Pull-Request-Prüfung. Der Entwickler kontrolliert in
M/Text, ob die Änderung wie erwartet funktioniert.

Der Push des Squash-Commits auf einen geschützten Zielbranch entsteht durch den
Merge des Pull Requests und startet die Synchronisation nach Abnahme.

### Dauerhafter Stand unter `serverSync`

Das Verzeichnis `serverSync` bleibt zwischen den Läufen bestehen. LTOMA lässt
seinen Inhalt unangetastet. Die Automatisierung aktualisiert deshalb den
vorhandenen Stand und ruft anschließend den M/Text-Adapter auf.

Im normalen Lauf werden die Änderungen zwischen dem zuletzt erfolgreich
synchronisierten Commit und dem neuen Ziel-Commit übertragen:

- neue und geänderte Ressourcen werden nach `serverSync` geschrieben,
- in Git gelöschte Ressourcen werden aus dem zugehörigen Projektverzeichnis
  entfernt,
- unveränderte Ressourcen werden nicht erneut vom Runner übertragen.

Der zuletzt erfolgreich synchronisierte Commit wird je Repository,
Releaselinie und M/Text-Ziel festgehalten. Dadurch kann auch beim Wechsel
zwischen zwei Feature-Branches derselben Releaselinie der vollständige
Zielstand hergestellt werden.

Die erste Synchronisation und eine ausdrücklich gestartete Wiederherstellung
übertragen den vollständigen Projektstand. Dabei werden ausschließlich die dem
Mandanten-Repository zugeordneten Projektverzeichnisse behandelt. Andere
Mandantenstände im gemeinsam genutzten `serverSync` bleiben unberührt.

Läufe für dasselbe Repository, dieselbe Releaselinie und dasselbe M/Text-Ziel
werden nacheinander ausgeführt. Ein fehlgeschlagener Lauf schreibt den
erfolgreichen Commit nicht fort und kann mit demselben Ziel-Commit wiederholt
werden.

## 4. Release-Tags und Mainframe-Übergabe

### Release-Tags

Für Release-Tags gelten die organisationsweit eingerichteten Regeln des
Leitfadens:

- Der Name folgt `v{Release-Version}`, beispielsweise `v261.100` oder
  `v261.108`.
- Die Release-Version enthält keinen Schrägstrich.
- Der Tag liegt auf einem Commit eines geschützten Branches.
- Ein Release-Tag wird nach der Erstellung nicht gelöscht.

Die Mandanten-Repositories ergänzen dafür keine eigenen Berechtigungsregeln.
Welche Benutzer passende Tags erstellen dürfen, ergibt sich aus der
organisationsweiten Konfiguration.

Ein irrtümlich erstellter Release-Tag wird nicht verändert oder gelöscht. Die
Korrektur erfolgt mit einem neuen Commit und einem neuen Release-Tag.

### Automatischer zentraler Release-Lauf

Der Push eines Release-Tags im Mandanten-Repository startet automatisch einen
Workflow in `mtext-actions`. Der zentrale Lauf checkt den getaggten
Mandantenstand aus, baut die Releaseartefakte und übergibt sie an den
Mainframe.

Das normale Tagging erfordert keinen manuellen Start durch Administratoren.
Der Aufruf von `mtext-actions` erfolgt mit einem Fine-grained PAT eines
technischen GitHub-Benutzers. Das Token ist auf das Repository `mtext-actions`
begrenzt und besitzt `Actions: write` sowie `Contents: read`. Es wird als
`MTEXT_ACTIONS_TOKEN` in den Mandanten-Repositories gespeichert. Die
Leseberechtigung lädt die gepinnte Automatisierung für Synchronisation und
Konfigurationsprüfung. Die Schreibberechtigung startet den zentralen
Release-Workflow.

Die erforderliche Einschränkung lässt sich in GitHub auswählen. Vor der
Einrichtung wird noch geprüft, ob der erzeugte Token zunächst genehmigt werden
muss. Der Token besitzt eine begrenzte Laufzeit und wird vor Ablauf durch den
technischen Verantwortlichen erneuert. Ein manueller Release-Start durch
Administratoren ist keine Betriebsvariante.

### Zentrale Zugangsdaten

Die Mainframe-Zugangsdaten liegen im Repository `mtext-actions`:

| Name | Ablage |
|---|---|
| `MAINFRAME_FTP_HOST` | Repositoryvariable |
| `MAINFRAME_FTP_USER` | Repositoryvariable |
| `MAINFRAME_FTP_PASSWORD` | Repository-Secret |

Das FTP-Passwort liegt nicht in den Mandanten-Repositories. Der zentrale
technische FTP-Benutzer wird für die Übergaben aller Mandanten verwendet.

Der zentrale Workflow benötigt außerdem eine technische Leseberechtigung für
die konfigurierten Mandanten-Repositories. Eine für die Aktualisierung der
Mandanten-Workflows eingerichtete technische GitHub-Identität kann diese
Aufgabe übernehmen.

GitHub Environments werden nicht verwendet. Es gibt keine zusätzliche manuelle
Bereitstellungsfreigabe. Die fachliche Entscheidung für die Lieferung wird
durch das Erstellen des geschützten Release-Tags ausgedrückt.

## 5. Repositories und Workflows

### Mandanten-Repositories

Ein Mandanten-Repository folgt diesem Aufbau:

```text
mtext-<mandant>/
  .github/
    config.json
    workflows/
      validate-config.yml
      sync-resources.yml
      release.yml
  <M/Text-Projekte>
```

`mtext-fi` dient als Muster. Alle sichtbaren Projektverzeichnisse in der
Repositorywurzel werden synchronisiert und in Releasepakete aufgenommen, wenn
sie nicht in `.github/config.json` ausgeschlossen sind.

Die Mandanten-Workflows enthalten die fachlichen Git-Auslöser. Prüfung und
Synchronisation rufen eine festgelegte Version der zentralen Automatisierung
auf. Der Release-Trigger startet einen eigenständigen Lauf in `mtext-actions`,
damit das Mainframe-Secret im zentralen Repository bleibt.

### Zentrales Repository `mtext-actions`

`mtext-actions` enthält:

- wiederverwendbare Workflows für Konfigurationsprüfung und
  M/Text-Synchronisation,
- den zentral ausgeführten Release-Workflow,
- die Python-Implementierung,
- die Releaselinien- und Mandantenzuordnung,
- das JCL-Template,
- automatisierte Tests.

Jeder Lauf verarbeitet einen vollständigen Commit-SHA und eine festgelegte
Version von `mtext-actions`. Damit bleiben Quelle und Automatisierungsstand
nachvollziehbar.

### Aktualisierung der Mandanten-Workflows

Änderungen an den zentral vorgegebenen Mandanten-Workflows werden aus
`mtext-actions` vorbereitet. Für `main` und die gepflegten Release-Branches
eines Mandanten-Repositories wird jeweils ein Pull Request erstellt. Das
technische Token schreibt nicht direkt auf geschützte Branches.

Feature-Branches übernehmen die Workflowdateien von ihrem Ausgangsbranch. Ein
separater Rollout auf Feature-Branches ist nicht erforderlich.

Der Aktualisierungslauf liegt in `mtext-actions` und verwendet dort das
Repository-Secret `WORKFLOW_CONFIGURATION_TOKEN`. Ein Environment
`Einrichtung` wird nicht benötigt.

## 6. Konfiguration

### Mandantenkonfiguration

Die Datei `.github/config.json` ist Bestandteil des versionierten
Mandantenstands. Der Block `mandant` enthält:

| Feld | Bedeutung |
|---|---|
| `kuerzel` | Mandantenkürzel für Paketnamen und Fragmentprojekte |
| `releaselinie` | Releaselinie, die auf diesem Stand durch `main` vertreten wird |
| `ispw` | CodePipeline-Instanz `T` oder `P` |
| `excluded_projects` | Projektverzeichnisse, die weder synchronisiert noch paketiert werden |
| `hostprofile` | Mandantenspezifische Werte für die zentral zugeordneten Hostprofile |

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

Die Releaselinie eines Feature- oder Release-Branches wird aus dem Branchnamen
bestimmt. Das Feld `releaselinie` bestimmt die Zuordnung von `main`.

### Zentrale Zuordnungen

`config/mandanten.json` ordnet Mandantenkürzel und Repository eindeutig
einander zu. `config/releaselinien.json` ordnet jede aktive Releaselinie ihrer
technischen ETAPS-Linie und einem Hostprofil zu.

Die konkreten Profilnamen werden nicht fest verdrahtet. Fachlich zulässige
CodePipeline-Stages sind `FKTE`, `FKTF`, `JURJ`, `JURP`, `SVTS` und `VPTV`.

## 7. Release-Lieferarten FULL und DELTA

Ein Tag mit der Endung `.100`, beispielsweise `v261.100`, erzeugt für jedes
einbezogene Projekt ein vollständiges F-Paket und ein zusätzliches leeres
D-Paket. Das entspricht dem Vertrag des bisherigen Lieferwegs.

Jeder weitere Release-Tag derselben Releaselinie erzeugt ein kumulatives DELTA
gegen den `.100`-Tag. `v261.108` enthält damit alle neuen, geänderten und
gelöschten Dateien seit `v261.100`. Die `.100`-Basis muss in der Git-Historie
ein Vorgänger des Ziel-Tags sein.

Der Elementname setzt sich aus Mandantenkürzel, Projektcode und Elementart
zusammen:

```text
<Mandantenkürzel><Projektcode><F|D>
```

Beispielsweise bezeichnet `BYAUTOND` das DELTA-Element für
`LOMS_Autonom[BY]`. Eine FULL-Lieferung von `LOMS_Basis` der FI erzeugt
`FIBASISF` und das zusätzliche leere `FIBASISD`.

Für jeden Release-Lauf speichert GitHub Actions Pakete, Lieferbelege, Manifest
und Prüfsummen als Artefakt. Das Manifest verbindet Repository,
Mandantenkürzel, Release-Tag, Ziel-Commit, Lieferart, JCL-Werte und erzeugte
Dateien. Vor der Mainframe-Übergabe werden die Dateien gegen das Manifest
geprüft.

Ein fehlgeschlagener Übergabeversuch kann mit demselben Artefakt wiederholt
werden. Der Paketbau wird dabei nicht erneut ausgeführt.

## 8. Mainframe-Übergabe

Die JCL liegt als versionierte Template-Datei in `mtext-actions`. Änderungen an
der Mainframe-Ansteuerung sind dadurch über einen Pull Request prüfbar.

Das Paket wird zunächst unter seinem Membernamen in `IEA.LOMS.TONICZ`
übertragen. Die JCL kopiert den Member nach
`IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ` und registriert ihn anschließend in
CodePipeline. Dabei gelten `STRMNAME=BOAS`, `MTYPE=TONICZ` und
`MNAME=<Membername>`.

Der Paketbau ist von der Mainframe-Übergabe getrennt. Nur der zentrale
Übergabejob erhält das FTP-Passwort. Übergaben desselben Mandanten werden
nacheinander ausgeführt. Verschiedene Mandanten können gleichzeitig liefern.

## 9. Arbeit in der M/Text Workbench

Ein lokaler Git-Arbeitsbaum kann zu einem Zeitpunkt einen Branch anzeigen. Für
gleichzeitige Arbeiten an mehreren Releaselinien werden deshalb getrennte
lokale Klone und bei Bedarf getrennte Eclipse-Arbeitsbereiche verwendet. Jeder
Projektbaum zeigt auf den Git-Klon seiner Releaselinie oder Änderung.

Beispiel bei führender R270 und gepflegter R261:

| Tätigkeit | Lokaler Branch | Pull-Request-Ziel | M/Text-Entwicklung |
|---|---|---|---|
| Feature für R270 | `feature/R270/neuer-brief` | `main` | ETAPS-Linie von R270 |
| Fehlerkorrektur für R261 | `feature/R261/issue-5678` | `release/R261` | ETAPS-Linie von R261 |
| Länger laufendes Feature für R271 | `feature/R271/grosses-feature` | nach dem Linienwechsel `main` | ETAPS-Linie von R271 |

Der Entwickler kann die drei Änderungen unabhängig pushen und jeweils auf dem
zugeordneten Entwicklungsziel testen. Eine Änderung erscheint erst nach ihrem
Pull-Request-Merge auf dem jeweiligen Abnahmeziel.

Die konkrete Bedienung mit EGit wird in der Benutzeranleitung anhand dieser
Szenarien beschrieben und im Integrationslauf praktisch geprüft.

## 10. Schutz und Berechtigungen

| Gegenstand | Regel |
|---|---|
| `main` | Geschützt, keine Löschung oder Umbenennung, Änderung über Pull Request im Vier-Augenprinzip |
| `release/Rnnn` | Geschützt, Änderung über Pull Request im Vier-Augenprinzip, Erstellung aus geschütztem Branch oder Release-Tag |
| `feature/Rnnn/<Bezeichnung>` | Keine zusätzliche Schutzregel |
| Release-Tags `v{Release-Version}` | Organisationsweit geschützte Tags nach dem Leitfaden |
| Workflowdateien und Mandantenkonfiguration | Änderung über Pull Request und Review |
| Mainframe-Zugang | Repositoryvariablen und Repository-Secret in `mtext-actions` |

GitHub Environments, Stage-Branches, Bereitstellungsbranches und manuelle
Bereitstellungsfreigaben gehören nicht zum Zielbild.

## 11. Einführung in Stufen

### Stufe 1: Verbindlichen Git-Vertrag herstellen

- Branch- und Tagregeln dokumentieren
- Squash Merge als einziges Mergeverfahren einrichten
- Mandantenkonfiguration um die führende `releaselinie` ergänzen
- alte Stage-Branch-Verträge aus Dokumentation und Code entfernen

Ergebnis ist ein einheitlicher Vertrag für Branch, Pull Request, Tag und
M/Text-Ziel.

### Stufe 2: M/Text-Synchronisation umstellen

- Feature-Push mit M/Text-Entwicklung verbinden
- Merge nach `main` oder `release/Rnnn` mit M/Text-Abnahme verbinden
- dauerhaften `serverSync`-Stand und inkrementelle Übertragung implementieren
- initiale Vollsynchronisation und Wiederherstellung bereitstellen

Ergebnis ist der automatische Entwicklungs- und Abnahmeweg ohne
Prozess-Branches.

### Stufe 3: Zentralen Releaseweg umstellen

- Tagformat `v{Release-Version}` unterstützen
- zentralen Release-Workflow in `mtext-actions` ausführen
- FTP-Zugang ausschließlich in `mtext-actions` hinterlegen
- automatischen repositoryübergreifenden Start praktisch nachweisen

Ergebnis ist eine automatische Releaseverarbeitung ohne Environment und ohne
manuellen Start durch Administratoren.

### Stufe 4: Mandanten ausrollen und abnehmen

- Workflowänderungen per Pull Request in die Mandanten-Repositories verteilen
- EGit-Abläufe mit den vorgesehenen Arbeitsbereichen prüfen
- parallele Releaselinien und Linienwechsel erproben
- FULL, DELTA, M/Text-Synchronisation und Mainframe-Übergabe Ende zu Ende testen

Ergebnis ist der abgenommene Ablauf für den Produktivwechsel.

## 12. Offene technische Nachweise

Vor dem Integrationslauf sind folgende Punkte praktisch nachzuweisen:

- erfolgreicher `workflow_dispatch` und lesender Checkout mit dem auf
  `mtext-actions` begrenzten Fine-grained PAT sowie geklärte Genehmigung
- Erreichbarkeit des dauerhaften `serverSync` durch den FI-Runner
- Erreichbarkeit von LTOMA, Mainframe-FTP und JES
- tatsächliches `runs-on`-Kennzeichen des FI-Runners
- Verhalten des integrierten EGit-Clients für Branchwechsel, Push und Pull
  Requests

Diese Nachweise ändern das Branch- und Pull-Request-Modell nicht. Sie bestimmen
die technische Ausführung der bereits festgelegten Abläufe.
