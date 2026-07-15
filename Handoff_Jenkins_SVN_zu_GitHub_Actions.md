# Handoff: Harter Cut von Jenkins/SVN zu GitHub Actions/Git

**Stand:** 15. Juli 2026  
**Adressat:** Technische Verantwortliche, Betrieb und Umsetzungsteam<br>
**Historische Primärquelle:** `LBS_SVN_Hook_v0.4.bash`  
**Ziel:** Neuaufbau der Automatisierung für getrennte mandantenbezogene GitHub-Repositories mit GitHub Actions

**Dokumentation:** [Übersicht](docs/README.md) ·
[Benutzeranleitung](docs/confluence/Benutzeranleitung.md) ·
[Soll-Grafik](Architektur_Soll_GitHub_Actions_Git.drawio)

## 1. Executive Summary

Jenkins und SVN werden gemeinsam durch GitHub Actions und Git ersetzt. Es gibt keinen parallelen Produktivbetrieb, keine Synchronisation zwischen SVN und Git und keine Weiterentwicklung des vorhandenen Jenkins-Skripts. Zum vereinbarten Umschaltpunkt wird der relevante Quellstand aus SVN nach Git übertragen, SVN für diesen Prozess außer Betrieb genommen und ausschließlich das neue GitHub-Zielbild aktiviert.

`LBS_SVN_Hook_v0.4.bash` dient nur noch als fachliche Referenz. Aus ihm werden Projektmapping, Voll-/Deltalogik, M/Text-Übergabe, Mainframe-Übertragung, JCL-Inhalt und Ergebnisdateien extrahiert. Seine technische Struktur und seine Fehlerbehandlung werden nicht portiert.

Die erste Zielversion behält die bestehenden Integrationsverfahren bewusst bei:

- Der M/Text-Adapter wird weiterhin synchron über seinen vorhandenen HTTP-Endpunkt aufgerufen.
- Die Mainframe-Übergabe bleibt zunächst bei FTP und JCL-Submit.
- Für M/Text und Mainframe wird in der ersten Ausbaustufe kein Job-ID-Polling implementiert.
- Der Workflow bewertet damit den unmittelbar verfügbaren Übergabe- beziehungsweise HTTP-Status. Ein fachlicher Langzeitstatus außerhalb dieses Vertrags ist nicht Bestandteil der ersten Ausbaustufe.

Die neue Lösung bildet den bisherigen fachlichen Promotionsweg ausdrücklich ab: Für jede aktive Releaselinie existieren die physischen Branches `<Releaselinie>/Entwicklung`, `/Abnahme` und `/Bereitstellung`. Eine Änderung wird zunächst nach Entwicklung übernommen und zum zugehörigen M/Text-Entwicklungsserver verteilt. Die Promotion nach Abnahme verteilt denselben Stand zum M/Text-Abnahmeserver. Ausgewählte Änderungen werden anschließend über einen UTC-datierten Auswahlbranch nach Bereitstellung übernommen. Ein vom Benutzer gesetzter Release-Tag auf diesem Stand startet FULL oder DELTA und übergibt das Artefakt an den bestehenden Mainframe-Prozess.

Ein Pull Request ist dabei die kontrollierte GitHub-Hülle für Prüfung, Nachvollziehbarkeit und Merge. Er verteilt selbst keine Ressourcen. Erst der Merge erzeugt einen Push auf den Zielbranch und löst den zuständigen Deployment-Workflow aus. Ein verpflichtendes fremdes Review wird nicht eingeführt; der Ersteller darf nach erfolgreichen Checks selbst mergen. Direkte Pushes auf die Stufenbranches werden durch Branchschutz verhindert.

Für die fachliche Implementierung wird Python als einheitliche Sprache empfohlen. GitHub-Actions-YAML bleibt reine Orchestrierung. Bash wird auf kurze Aufrufe und einen optionalen Runner-Preflight begrenzt. Die JCL wird als versionierte Template-Datei abgelegt und zur Laufzeit mit validierten Werten gerendert.

## 2. Verbindliche Rahmenbedingungen

- Harter Cut von Jenkins/SVN zu GitHub Actions/Git.
- Kein gleichzeitiger produktiver Einsatz beider Systeme.
- Keine Änderungen mehr an `LBS_SVN_Hook_v0.4.bash`.
- Keine Übernahme langlebiger SVN-Working-Copies nach Git.
- Keine erste Ausbaustufe mit Job-ID- oder Status-Polling.
- Adapter- und Mainframe-Verfahren bleiben zunächst fachlich unverändert.
- Historische Jenkins-/SVN-Probleme sind Informations- und Testkontext, kein eigener Umsetzungsbacklog.
- Jeder Mandant erhält ein eigenes GitHub-Quellrepository entsprechend der bisherigen SVN-Trennung, zum Beispiel `mtext-fi` und `mtext-by`.
- Git wird nach dem Cut die einzige Quelle für Ressourcen und mandantenspezifische Konfiguration.
- Gemeinsame Workflows, Python-Logik und das JCL-Template werden zentral versioniert und von den Mandanten-Repositories in einer festgelegten Version verwendet.
- GitHub Actions wird nach dem Cut der einzige Orchestrator für diesen Prozess.
- Deployment- und Release-Läufe arbeiten immer auf einem exakten Git-Commit-SHA.
- Die physischen Git-Branches heißen für die aktiven Linien `R260`, `R261` und `R270` jeweils `<Releaselinie>/Entwicklung`, `/Abnahme` und `/Bereitstellung`.
- Der Mandantenkontext wird aus dem jeweiligen migrierten Repository und dessen versionierter Konfiguration bestimmt, nicht aus einem frei eingebbaren Deploymentparameter.
- Pull Requests prüfen Promotions; ein fremdes Review ist nicht verpflichtend. Erst der Merge auf den Zielbranch löst eine Verteilung aus.
- Push auf `Rxxx/Entwicklung` verteilt zum M/Text-Entwicklungsserver.
- Push auf `Rxxx/Abnahme` verteilt zum M/Text-Abnahmeserver.
- Push auf `Rxxx/Bereitstellung` allein baut noch kein Release; erst ein gültiger Release-Tag startet FULL oder DELTA.

## 3. Historische Ist-Architektur als Referenz

Das alte Bash-Skript vereint mehrere fachlich unabhängige Aufgaben:

- SVN-Working-Copies auf NFS anlegen, aktualisieren und reparieren;
- Release, Linie, Stage, Umgebung, Mandant und Projektliste auflösen;
- Ressourcen für Entwicklung und Abnahme bereitstellen;
- den M/Text-Adapter per HTTP aufrufen;
- Voll- und Deltalieferungen aus SVN-Tags erzeugen;
- TAR-Archive, Inhaltslisten und Löschlisten erzeugen;
- Dateien nach `/nfs/mtext/trans` kopieren;
- Pakete per FTP zum Mainframe übertragen;
- JCL als zahlreiche eingebettete `echo`-Zeilen erzeugen und absenden;
- Informationsdateien und E-Mails erzeugen;
- temporäre Verzeichnisse und Dateien aufräumen.

Diese Liste ist die Grundlage für Vollständigkeitsprüfungen. Sie ist keine Empfehlung für die Zielstruktur.

### 3.1 Durch Screenshot belegte SVN-Struktur

Der Screenshot des Repository-Browsers bestätigt für den Mandanten FI:

```text
/svn/mtext-fi/
  branches/
    Entwicklung/
      R200.100_MText/
      R201.100_MText/
      ...
      R251.100_MText/
      R260.100_MText/
      R261.100_MText/
    Abnahme/
    Bereitstellung/
  tags/
    R201.100_MText/
    R201.136_MText/
    R201.176_MText/
    R201.220_MText/
    ...
```

Die Mandanten besitzen getrennte SVN-Repositories. `mtext-fi` ist daher nicht nur ein Pfadparameter in einem gemeinsamen Repository; daneben existieren eigenständige Repositories wie `mtext-by`. Dieses Trennungsmodell wird im Git-Zielbild als ein GitHub-Repository pro Mandant beibehalten.

Der Screenshot zeigt außerdem, dass ein Branch mehrere Releaseverzeichnisse enthält und dass Tags jeweils einen vollständigen Projektbaum enthalten. Sichtbare Projekte sind unter anderem `Configuration`, `Fonts`, `LOMS_Basis`, `LOMS_Framework` und `LOMS_Testdaten`. Unter `LOMS_Basis` liegen fachliche Unterstrukturen wie `.templatetree`, `Anlagen`, `Bausteine`, `Daten`, `Funktionen`, `Grafiken` und `Vorlagen`.

Historische Sondernamen wie `R210.100_MText_BACKUP` und `R230.100_MText-Fusion_NordWest` belegen, dass nicht jedes Verzeichnis automatisch als produktiver Release-Ref migriert werden darf. Die Migration verwendet eine explizite Allowlist der fachlich relevanten Branches, Releaseverzeichnisse und Tags.

Die im Screenshot sichtbare Projektliste weicht teilweise von der aktuellen FI-Liste des Bash-Skripts ab, die beispielsweise `LOMS_PKA` enthält. Projektlisten werden deshalb je Mandant und gegebenenfalls je Releaselinie inventarisiert und nicht allein aus einer globalen statischen Liste abgeleitet.

Zwei weitere Screenshots vom 15. Juli 2026 belegen die Master-/Fragmentstruktur:

- `mtext-by/branches/Entwicklung/R260.100_MText` enthält
  `LOMS_Autonom[BY]`, `LOMS_Basis[BY]`, `LOMS_Testdaten[BY]` und
  `LOMS_Testdaten_Autonom[BY]`.
- `mtext-autonom/branches/Entwicklung/R261.100_MText` enthält die Masterprojekte
  `LOMS_Autonom` und `LOMS_Testdaten_Autonom`.

Fachlich wurde bestätigt, dass das Fragmentmuster für alle Mandanten außer FI
und IT gilt. IT wird im Zielbild nicht als `mtext-it`, sondern als
`mtext-autonom` geführt. Repositoryinhalt ist dabei nicht gleich
Delivery-Allowlist: Das historische Skript synchronisiert und paketiert bei FI
die fünf bekannten Hauptprojekte, bei `mtext-autonom` nur `LOMS_Autonom` und
bei den Fragmentmandanten nur `LOMS_Basis[Kürzel]` und
`LOMS_Autonom[Kürzel]`. Testdatenprojekte werden migriert, aber nicht in die
Delivery-Allowlist aufgenommen. Der alte FI-Sonderpfad `LOMS_Basis[FI]`
entfällt mit R251.

### 3.2 Durch `trans/`-Referenzdateien belegtes Lieferformat

Die vier bereitgestellten Dateien bilden zwei reale Lieferbeispiele ab:

| Beispiel | Typ | Belegter Inhalt |
|---|---|---|
| `BYAUTOND.tgz` | DELTA für `LOMS_Autonom[BY]` | geänderte beziehungsweise neue Ressourcendateien plus `BYAUTOND.txt` als Löschliste |
| `_INFO_BY-LOMS_Autonom[BY]-DELTA-R260.234-R260.178.txt` | Information zum DELTA | direkter Vergleich `R260.178 -> R260.234` und vollständige TAR-Inhaltsliste |
| `OSAUTONF.tgz` | FULL für `LOMS_Autonom[OS]` | vollständiger Projektbaum des Full-Releases |
| `_INFO_OS-LOMS_Autonom[OS]-FULL-R260.100-R251.510.txt` | Information zum FULL | direkter Vergleich `R251.510 -> R260.100` und vollständige TAR-Inhaltsliste |

Das BY-Beispiel trennt zwei Bedeutungen eindeutig:

- Der direkte Vorrelease-Vergleich in der `_INFO`-Datei enthält 14 Änderungen zwischen `R260.178` und `R260.234`.
- Das DELTA-Archiv enthält 33 Dateien einschließlich Löschliste und enthält Ressourcen, die nicht in diesen 14 direkten Änderungen stehen.
- `BYAUTOND.txt` enthält Löschpfade, die ebenfalls nicht im direkten Vorrelease-Vergleich vorkommen.

Damit ist belegt, dass `_INFO_...txt` nicht die fachliche Quelle des Paketinhalts ist. Das beobachtete Ergebnis stimmt mit der Bash-Logik überein: Der Paketinhalt und die Löschliste werden aus dem kumulativen Vergleich gegen den `.100`-Stand gebildet; der direkte Vorrelease-Vergleich dient nur der Information. Eine vollständige bytegenaue Validierung der `.100`-Basis erfordert zusätzlich die zugehörigen Quellstände oder Referenz-Tags.

Weitere belegte Formatregeln:

- Paketname: `<Mandant><Paketcode>F.tgz` für FULL und `<Mandant><Paketcode>D.tgz` für DELTA, hier `OSAUTONF.tgz` und `BYAUTOND.tgz`.
- Löschliste: `<Mandant><Paketcode>D.txt` im Wurzelverzeichnis des DELTA-Archivs; jede Zeile ist ein relativer Ressourcenpfad ohne `VORRELEASE/`-Präfix.
- Ressourcenwurzel: Projektname einschließlich Mandantensuffix in eckigen Klammern, zum Beispiel `LOMS_Autonom[BY]/`.
- Informationsdatei: `_INFO_<Mandant>-<Projekt>-<Typ>-<Release>-<Vorrelease>.txt`.
- Die Informationsdatei enthält sowohl eine SVN-artige `A`-/`M`-/`D`-Zusammenfassung als auch die ausführliche TAR-Inhaltsliste.
- Das historische FULL-Archiv verwendet Pfade mit `./`-Präfix, das DELTA-Beispiel Pfade ohne dieses Präfix. Ob ein Verbraucher diese Differenz benötigt, wird durch Charakterisierungstests geklärt; die Zielimplementierung vereinheitlicht sie nicht ungeprüft.
- Die historischen Archive enthalten reale Besitzer-, Gruppen-, Modus- und Zeitstempelwerte. Die Zielimplementierung legt diese Metadaten bewusst und reproduzierbar fest, nachdem die Verträglichkeit mit dem Mainframe-Verbraucher belegt ist.

Diese Dateien waren Entwicklungshinweise zur Extraktion von Formatregeln. Sie werden nicht als Test-Fixtures oder dauerhafter Repository-Bestand übernommen. Die Beispiele sind kein Ersatz für die Inventarisierung aller Mandanten, Projekte und Releaselinien.

## 4. Historische Fehlerbilder und ihre Bedeutung für das Zielbild

| Beobachtung im Altsystem | Historische Ursache | Konsequenz für GitHub Actions/Git |
|---|---|---|
| Globales `set -e` führte zu unerwarteten Abbrüchen | Kritische, optionale und erwartbare Fehler lagen im selben Monolithen | kleine Einzweckmodule, definierte Exceptions und explizite Workflow-Schrittstatus |
| Alte `VORRELEASE`-Workspaces blockierten Folgeläufe | temporäre SVN-Verzeichnisse wurden nur im Happy Path entfernt | frischer GitHub-Actions-Workspace je Lauf und laufbezogene temporäre Verzeichnisse |
| Mailfehler beeinflussten den Buildstatus | Benachrichtigung war mit fachlicher Verarbeitung gekoppelt | Benachrichtigung als abschließender, nicht fachlich bestimmender Schritt |
| `svn cleanup` und `svn revert -R` waren langsam | langlebige, große SVN-Working-Copies auf NFS | exakter frischer Git-Checkout; keine SVN-Reparaturbefehle im Zielbild |
| `curl` lieferte HTTP 400 mit `Could not receive Message` | Adapter bildete einen internen MTextCSProxy-Timeout auf HTTP 400 ab | HTTP-Status und Response-Body sichtbar protokollieren; Nicht-2xx beendet den Sync-Workflow fehlerhaft |
| MTextCSProxy überschritt den Read Timeout | blockierender nachgelagerter Sync dauerte länger als der CXF-Timeout | in Ausbaustufe 1 vorhandenen Vertrag beibehalten und Timeout transparent melden; Polling bleibt außerhalb des ersten Scopes |
| FTP/JCL-Submit hatte keinen fachlichen Abschlussstatus | Übergabe und Mainframe-Verarbeitung waren nicht getrennt beobachtbar | Ausbaustufe 1 meldet präzise `übergeben` statt einen nicht belegten fachlichen Mainframe-Erfolg |
| Credentials wurden in `upload.py` materialisiert | dynamisch erzeugtes Python-Skript enthielt FTP-Zugangsdaten | statisches Python-Modul liest Secrets nur zur Laufzeit aus geschützter Umgebung |

Die genannten Risiken werden nicht mehr im Jenkins-Skript behoben. Sie bestimmen lediglich die Zieltests und verhindern, dass dieselben Strukturprobleme neu implementiert werden.

## 5. Zielarchitektur und Verantwortlichkeiten

### Mandantenbezogene GitHub-Repositories

- pro Mandant existiert ein eigenes Quellrepository, zum Beispiel `mtext-fi` oder `mtext-by`;
- jedes Repository enthält die migrierten Ressourcen, `config/mandant.json` und dünne aufrufende Workflows;
- Branches, Tags und Commit-SHAs gelten immer innerhalb genau dieses Mandanten-Repositories;
- der Mandant wird aus der geprüften Repository-Identität ermittelt und nicht als frei eingebbarer Workflow-Parameter akzeptiert;
- die Repositories enthalten keine Secrets und keine generierten credentialhaltigen Dateien.

### Zentrales Automatisierungs-Repository

- enthält wiederverwendbare GitHub-Actions-Workflows, das installierbare Python-Paket, das JCL-Template, gemeinsame Schemata und Tests;
- wird von jedem Mandanten-Repository über eine unveränderliche Commit-SHA oder einen kontrolliert aktualisierten Release-Tag referenziert;
- verhindert auseinanderlaufende Kopien von Python-, Workflow- und JCL-Logik in `mtext-fi`, `mtext-by` und weiteren Mandanten-Repositories;
- ändert den Mandantenkontext nicht: Ressourcen und mandantenspezifische Konfiguration werden weiterhin aus dem jeweils auslösenden Mandanten-Repository gelesen.

### GitHub Actions

- reagiert auf Pull Requests, Pushes, Release-Tags und manuelle Starts;
- validiert Inputs und Konfiguration vor externen Seiteneffekten;
- orchestriert Python-Kommandos;
- verwaltet Environments, Secrets, Concurrency und Artefakte;
- berichtet den Status, den die aktuelle Integrationsschnittstelle tatsächlich liefert.

### Self-hosted Runner

- wird benötigt, sofern NFS, M/Text-Adapter und Mainframe nur intern erreichbar sind;
- stellt Git, eine freigegebene Python-3-Version und die erforderlichen Netzwerk-/Mountzugriffe bereit;
- wird vom Plattformteam gepatcht, gehärtet und mit stabilen Runner-Labels versehen;
- verwendet einen frischen oder zuverlässig bereinigten Arbeitsbereich je Job.

### M/Text-Adapter und MTextCSProxy

- bleiben in Ausbaustufe 1 unverändert;
- der Adapter wird über den vorhandenen synchronen HTTP-Aufruf angesprochen;
- ein 2xx-Status bedeutet Erfolg gemäß aktuellem Adaptervertrag;
- ein Nicht-2xx-Status oder Curl-Transportfehler lässt den Workflow fehlschlagen;
- ein darüber hinausgehender fachlicher Jobstatus wird zunächst nicht ermittelt.

### Mainframe und Code Pipeline

- erhalten Paket und JCL über das bestehende Übergabeverfahren;
- die Zielversion trennt JCL-Template, Rendering und Übertragung sauber;
- der initiale Workflow endet nach bestätigter technischer Übergabe gemäß vorhandenem FTP/JES-Vertrag;
- ein späterer finaler Jobstatus ist kein Bestandteil der ersten Implementierungsstufe.

## 6. Sprach- und Laufzeitentscheidung

GitHub Actions kann `run`-Schritte unter Linux mit Bash ausführen und unterstützt auch `python` als Shell-Auswahl. Auf einem self-hosted Runner sind Betriebssystem und installierte Werkzeuge jedoch eigene Betriebsverantwortung. Python muss dort installiert und im `PATH` verfügbar sein. Diese Aussagen entsprechen der offiziellen [Workflow-Syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), der [Python-Anleitung](https://docs.github.com/en/actions/tutorials/build-and-test-code/python) und der [Self-hosted-Runner-Referenz](https://docs.github.com/en/actions/reference/runners/self-hosted-runners).

### Empfehlung

- **Workflow-Orchestrierung:** YAML unter `.github/workflows`.
- **Fachliche Implementierung:** Python 3 in einem installierbaren Repository-Paket.
- **Bash:** nur für sehr kurze Aufrufe und optional `scripts/runner-preflight.sh`.
- **JCL:** versioniertes Text-Template, Rendering durch Python.
- **Tests:** Python-Unit- und Integrationstests.

Python ist hier geeigneter als ein wachsender Satz von Shell-Skripten, weil die Lösung strukturierte Konfiguration, Git-Diff-Auswertung, Dateimanipulation, HTTP, FTP, JCL-Rendering, Fehlerobjekte und automatisierte Tests benötigt.

Die einheitliche Sprache bedeutet nicht, dass in Workflow-YAML kein `run:` vorkommt. Ein Schritt wie `python -m lbs_delivery sync-resources ...` startet lediglich die Python-Anwendung. Fachliche Verzweigungen und Dateiverarbeitung bleiben aus YAML und Bash heraus.

### Runner-Vertrag

- Linux-Runner mit explizitem Runner-Label.
- Zielplattform GitHub Enterprise Server 3.20.4; GitHub-hosted Runner sind dort nicht vorgesehen.
- Organisationsweit freigegebene und im Repository dokumentierte Python-3-Minor-Version.
- Version in `.python-version` oder `pyproject.toml` festgeschrieben.
- Python auf dem self-hosted Runner vorinstalliert oder aus einem internen Toolcache bereitgestellt.
- Abhängigkeiten über `pyproject.toml` und eine reproduzierbare Lockdatei.
- Kein unkontrollierter Download aus öffentlichen Paketquellen während eines Deployment-Laufs.
- `git`, `tar` nur dann als externe Tools verwenden, wenn ihr Verhalten im Runner-Vertrag festgelegt ist.
- Node-20-Unterstützung für die auf GHES vorgesehenen v3-Artefakt-Actions.

GitHub Enterprise Server 3.20 bündelt die offiziellen Repositories
`actions/upload-artifact` und `actions/download-artifact`. Da die v4-
Artefakt-Actions den auf GHES nicht verfügbaren neuen Artefaktdienst verwenden,
pinnt der Entwurf die offiziellen Node-20-v3-Varianten. Die konkrete
Verfügbarkeit der Commit-SHAs im internen `actions`-Namespace bleibt Teil des
nichtproduktiven Runner-Preflights. Siehe
[GitHub-Dokumentation für GHES 3.20](https://docs.github.com/en/enterprise-server@3.20/admin/managing-github-actions-for-your-enterprise/managing-access-to-actions-from-githubcom/about-using-actions-in-your-enterprise).

## 7. Empfohlene Repository-Struktur

```text
mtext-fi/                         # analog mtext-by, mtext-nw, ...
  .github/
    workflows/
      validate.yml               # dünner Aufruf des zentralen Workflows
      sync-resources.yml         # dünner Aufruf des zentralen Workflows
      release.yml                # dünner Aufruf des zentralen Workflows
  config/
    mandant.json                 # nur FI-spezifische Projekte und Mappings
  <migrierte M/Text-Ressourcen>
  README.md

mtext-actions/                   # gemeinsames Automatisierungs-Repository
  .github/
    workflows/
      ci.yml
      reusable-validate-pr.yml
      reusable-sync-resources.yml
      reusable-release.yml
  config/
    mandant.schema.json
    deployments.schema.json
    deployments.json             # umgebungsbezogene, nicht geheime Mappings
  src/
    lbs_delivery/
      __init__.py
      cli.py
      config.py
      git_refs.py
      resources.py
      mtext_adapter.py
      release.py
      manifest.py
      mainframe.py
      jcl.py
      paths.py
      errors.py
      schemas/
        manifest.schema.json
  templates/
    mainframe-upload.jcl
  scripts/
    runner-preflight.sh
  tests/
    unit/
    integration/
  pyproject.toml
  .python-version
  requirements.lock
  README.md
```

Die Workflow-Dateien in den Mandanten-Repositories enthalten nur Trigger, minimale Berechtigungen und den versionierten Aufruf des zentralen wiederverwendbaren Workflows. Fachlogik wird dort nicht dupliziert. Die zentrale Referenz wird nicht auf einen beweglichen Branch wie `main`, sondern auf eine freigegebene unveränderliche Version gesetzt.

Die fachlichen Einstiegspunkte `validate-pr`, `sync-resources`,
`build-release` und `publish-mainframe` sind als Subcommands eines Pakets
umgesetzt. Dadurch teilen sie Konfigurationsauflösung, Fehlercodes und Tests
ohne Copy-and-paste.

Die Workflows setzen alle Pflichtargumente. Für die lokale Referenz zeigt die
CLI ihre jeweils aktuelle vollständige Schnittstelle selbst an:

```bash
PYTHONPATH=mtext-actions/src python -m lbs_delivery validate-pr --help
PYTHONPATH=mtext-actions/src python -m lbs_delivery sync-resources --help
PYTHONPATH=mtext-actions/src python -m lbs_delivery build-release --help
PYTHONPATH=mtext-actions/src python -m lbs_delivery publish-mainframe --help
```

Ohne `--execute` führen sowohl `sync-resources` als auch `publish-mainframe`
nur lokale, nebenwirkungsfreie Vorarbeiten aus. Der Publish-Aufruf validiert
dabei Manifest und Prüfsummen und rendert das JCL, überträgt aber nichts per
FTP/JES.

## 8. Git-Branch-, Promotion- und Workflowmodell

Im SVN lagen mehrere Releaseverzeichnisse unter gemeinsamen Stufenbranches.
Git verwendet stattdessen je Releaselinie eigene Stufenbranches, beispielsweise
`R260/Entwicklung`, `R260/Abnahme` und `R260/Bereitstellung`. Dadurch sind
Historie, Pull-Request-Ziel, Branchschutz und Deploymentauslöser je Linie
eindeutig. Die Alternative mit gemeinsamen Branches und Releaseordnern würde
Pfadfilter benötigen und könnte Änderungen mehrerer Linien in einem Pull
Request vermischen. Diese bewusste Abweichung wird auch im Confluence-Zielbild
dokumentiert.

Ein zusätzlicher `main`-Branch wird nicht angelegt. Der Default Branch ist der
Entwicklungsbranch der aktuell führenden Linie, zunächst
`R261/Entwicklung`, und wird beim Linienwechsel manuell umgestellt.

### Bedeutung des Pull Requests

Ein Pull Request ist in diesem Zielbild kein zusätzlicher fachlicher Lieferweg. Er ersetzt die heute manuell ausgeführte und anschließend commitete SVN-Merge-Stufe durch einen sichtbaren, prüfbaren GitHub-Prozess:

```text
Quellbranch auswählen
-> Änderungen und Commits im Pull Request anzeigen
-> automatisierte Validierung ausführen
-> nach erfolgreichen Checks selbst oder durch einen anderen Berechtigten mergen
-> in Zielbranch mergen
-> Push-Ereignis auf Zielbranch
-> zuständigen Sync- oder Releaseprozess starten
```

Der `pull_request`-Workflow hat keine externen Seiteneffekte. Er verteilt nichts zum M/Text-Server und veröffentlicht nichts auf dem Mainframe. Diese Aktionen beginnen erst nach dem Merge.

### Fachlicher Git-Ablauf

1. Eine Änderung an Tonic-Brief-Ressourcen wird im jeweiligen mandantenabhängigen Git-Repository lokal auf einem kurzlebigen Feature-Branch erstellt.
2. Der Feature-Branch folgt `feature/<Releaselinie>/<Issue>-<Kurzname>`, wird nach GitHub gepusht und per Pull Request nach `<Releaselinie>/Entwicklung` übernommen.
3. Der Merge erzeugt dort einen Push; `sync-resources.yml` verteilt den exakten Merge-Commit zum zugehörigen M/Text-Entwicklungsserver.
4. Die Promotion erfolgt über einen Pull Request von `<Releaselinie>/Entwicklung` nach `<Releaselinie>/Abnahme`.
5. Der Merge verteilt denselben Stand zum M/Text-Abnahmeserver.
6. Für eine Bereitstellung wird ein Branch wie `release/R260-20260715T143000Z` angelegt.
7. Die ausgewählten Commits aus Abnahme werden gezielt per `git cherry-pick` in diesen Auswahlbranch übernommen.
8. Ein Pull Request übernimmt den gesammelten Stand nach `<Releaselinie>/Bereitstellung`.
9. Nach dem Merge setzt ein Benutzer auf genau diesem Commit einen Release-Tag. Eine zusätzliche Tagschutzregel ist zunächst nicht vorgesehen.
10. `release.yml` leitet aus dem Tag den Branch `<Releaselinie>/Bereitstellung` ab, prüft die Erreichbarkeit und erzeugt FULL oder DELTA.

Der Release-Branch und der Pull Request ersetzen damit das heutige einzelne Mergen ausgewählter SVN-Commits mit anschließendem Sammel-Commit. Die einzelnen Git-Commits bleiben standardmäßig nachvollziehbar. Ein zusätzlicher Squash ist für den Paketbau nicht erforderlich.

### Workflow-Aufteilung nach Git-Ereignis

| GitHub-Ereignis | Workflow | Zweck | Python-Module und Skripte | Externe Seiteneffekte |
|---|---|---|---|---|
| `pull_request` nach `Rxxx/Entwicklung`, `/Abnahme` oder `/Bereitstellung` | `validate.yml` | Änderung oder Promotion vor dem Merge prüfen | `validate-pr` | keine |
| `push` auf `Rxxx/Entwicklung` | `sync-resources.yml` | Ressourcen zum M/Text-Entwicklungsserver verteilen | `sync-resources`, `resources.py`, `mtext_adapter.py` | NFS/Dateiübergabe und HTTP-Aufruf Entwicklung |
| `push` auf `Rxxx/Abnahme` | `sync-resources.yml` | Ressourcen zum M/Text-Abnahmeserver verteilen | `sync-resources`, `resources.py`, `mtext_adapter.py` | NFS/Dateiübergabe und HTTP-Aufruf Abnahme |
| `push` eines Tags `Rnnn.nnn` auf einem `Rnnn/Bereitstellung`-Commit | `release.yml` | anhand der Endung FULL oder DELTA bauen, Manifest erzeugen und Publish aufrufen | `build-release`, `release.py`, `manifest.py` | Artefaktablage; danach manuell freigegebene Mainframe-Übergabe |
| interner Publish-Job nach erfolgreichem Build | `release.yml` | freigegebenes Artefakt übertragen, JCL rendern und absenden | `publish-mainframe`, `mainframe.py`, `jcl.py`, `templates/mainframe-upload.jcl` | FTP/JES nach Environment-Freigabe |
| `workflow_dispatch` | `sync-resources.yml` oder `release.yml` | kontrollierter Neuaufruf mit Commit-SHA oder vorhandenem Tag | identische Python-Subcommands | abhängig vom Workflow |

### `validate.yml`

1. Repository auf exakten Commit auschecken.
2. Freigegebene Python-Version bereitstellen.
3. Abhängigkeiten reproduzierbar installieren.
4. Schema und alle Konfigurationsdateien validieren.
5. Zulässige Promotionsrichtung und identische Releaselinie prüfen: Feature nach Entwicklung, Entwicklung nach Abnahme, UTC-Auswahlbranch nach Bereitstellung.
6. Keine zentralen Unit-Tests wiederholen; diese laufen im CI von `mtext-actions`.
7. Keine internen Zielsysteme aufrufen.

### `sync-resources.yml`

1. Releaselinie und Zielumgebung strikt aus `Rxxx/Entwicklung` oder `Rxxx/Abnahme` auflösen.
2. Exakten Commit auschecken.
3. Bei manuellem Wiederanlauf prüfen, dass der Commit aus dem ausgewählten Stufenbranch erreichbar ist.
4. Ressourcenliste für Mandant und Umgebung bestimmen.
5. Ressourcen in ein laufbezogenes Staging-Verzeichnis schreiben.
6. Den Stand über den bestehenden serverSync-/NFS-Vertrag bereitstellen, solange dieser vom Adapter benötigt wird.
7. Den vorhandenen Adapter-Endpunkt einmal synchron aufrufen.
8. Transport, HTTP-Status und Response-Body protokollieren.
9. Nur dokumentierte 2xx-Antworten als Workflow-Erfolg behandeln.
10. Kein Job-ID-Polling ausführen.

### `release.yml`

1. Tagformat `Rnnn.nnn` und Mandant validieren.
2. Prüfen, dass der getaggte Commit aus dem abgeleiteten Branch `Rnnn/Bereitstellung` erreichbar ist.
3. Bei Endung `.100` eine FULL-Lieferung erzeugen.
4. Bei jeder anderen dreistelligen Endung eine DELTA-Lieferung gegen den zugehörigen `.100`-Tag derselben Releaselinie erzeugen.
5. Basis- und Ziel-Tag in unveränderliche Commit-SHAs auflösen.
6. FULL oder DELTA aus Git erzeugen.
7. Löschliste, Inhaltsliste, Metadaten und SHA-256-Prüfsummen erzeugen.
8. Artefakt und Manifest in GitHub Actions speichern.
9. Das Mainframe-Environment und dessen Freigaberegeln anwenden.
10. Den Publish-Job desselben Workflows mit dem zuvor erzeugten Artefakt starten.

### Publish-Job in `release.yml`

1. Artefakt anhand Manifest und SHA-256 verifizieren.
2. JCL aus `templates/mainframe-upload.jcl` rendern.
3. Paket mit dem bestehenden FTP-Verfahren übertragen.
4. Gerenderte JCL mit dem bestehenden JES-Verfahren absenden.
5. Den vorhandenen unmittelbaren Übergabestatus auswerten.
6. Kein Mainframe-Job-Polling ausführen.
7. Temporär gerenderte JCL über den Job-Workspace bereinigen.

## 9. Architekturskizzen

Die Architektur ist in zwei getrennten, editierbaren Draw.io-Dateien dokumentiert. Beide Dateien können über **Import a Diagram** in Gliffy importiert und dort als Gliffy-Diagramm weiterbearbeitet werden.

- [Ist-Ablauf Jenkins/SVN](./Architektur_Ist_Jenkins_SVN.drawio)
- [Soll-Ablauf GitHub Actions/Git](./Architektur_Soll_GitHub_Actions_Git.drawio)
- [Benutzeranleitung für den Soll-Ablauf](./docs/confluence/Benutzeranleitung.md)

Die Ist-Skizze zeigt Entwicklung, Abnahme, Bereitstellung, kumulatives Delta gegen `.100`, separaten Vorrelease-Informationsvergleich, NFS, Adapter, M/Text sowie FTP/JCL/Mainframe.

Die Soll-Skizze zeigt getrennte Mandanten-Repositories, das zentrale Automatisierungs-Repository, Feature-Branch, Pull Requests und Merge-Trigger für `Rxxx/Entwicklung`, `Rxxx/Abnahme` und `Rxxx/Bereitstellung`, die vorgeschlagenen Workflows und Python-Module, FULL-/DELTA-Erzeugung, das versionierte JCL-Template und die zunächst unveränderte Mainframe-Übergabe. Status-Polling bleibt außerhalb der ersten Ausbaustufe.

## 10. Konfigurationsmodell

Fachliche Mappings werden aus dem Bash-Skript in versionierte, schemavalidierte Dateien übertragen. Secrets bleiben außerhalb der Repositories. Mandantenspezifische und gemeinsame Konfiguration werden getrennt.

Beispiel `config/mandant.json` im Repository `mtext-fi`:

```json
{
  "schema_version": 1,
  "mandant": {
    "code": "FI",
    "repository": "mtext-fi",
    "subsystem": "LOMS",
    "projects": [
      {"name": "Configuration", "source_path": "Configuration", "package_code": "CONFI"},
      {"name": "LOMS_Basis", "source_path": "LOMS_Basis", "package_code": "BASIS"}
    ],
    "stages": {
      "FKT": {"assignment": "LOMS000066", "level": "FKTE"},
      "JUR": {"assignment": "LOMS000067", "level": "JURP"}
    },
    "sync_overrides": []
  }
}
```

Beispiel `config/deployments.json` im zentralen Automatisierungs-Repository:

```json
{
  "schema_version": 1,
  "release_lines": {
    "R260": {"line": "en03", "stage": "JUR"},
    "R261": {"line": "en01", "stage": "FKT"},
    "R270": {"line": "en02", "stage": "JUR"}
  },
  "environments": {
    "Entwicklung": {"code": "E", "logical_branch": "Entwicklung", "deploy_on_push": true, "mtext_target_key": "entwicklung"},
    "Abnahme": {"code": "A", "logical_branch": "Abnahme", "deploy_on_push": true, "mtext_target_key": "abnahme"},
    "Bereitstellung": {"logical_branch": "Bereitstellung", "deploy_on_push": false, "release_on_tag": true}
  }
}
```

Die Stufen behalten ihre bisherige Großschreibung. FI ist Master für die unfragmentierten Projekte; `mtext-autonom` ist Master für `LOMS_Autonom`. Die übrigen Mandanten verwenden Fragmentprojekte mit Mandantenkürzel in eckigen Klammern. Testdatenprojekte können Repositoryinhalt sein, bleiben aber wie im bisherigen Skript außerhalb der Delivery-Allowlist.

Die Adapterziele folgen dem bestätigten Mapping `R261 -> en01`,
`R270 -> en02`, `R260 -> en03`. Entwicklung verwendet den Hostsuffix `e`,
Abnahme `a`, zum Beispiel
`https://en01e.ltoma.intern/vMtextAdapter/sync`. Der Payload bleibt
`{"mandant":"MAN","institut":"INR"}`, benötigt zunächst keine
Authentifizierung und wertet jeden 2xx-Status als unmittelbare Annahme. Der
serverSync-Sharepfad ist noch auf dem vorgesehenen Runner zu bestätigen.

Validierungsregeln:

- unbekannte Schlüssel und unbekannte Mandanten ablehnen;
- Übereinstimmung von `mandant.repository` mit dem auslösenden GitHub-Repository zwingend prüfen;
- keine Default-Zuordnung auf FI/LOMS;
- Releaseformat, Tagformat und erlaubte Zielumgebung explizit prüfen;
- Projekt- und Package-Codes eindeutig halten;
- Branch-zu-Umgebung-Mapping eindeutig halten;
- keine Secrets, Passwörter oder geheimen URLs in JSON-Konfiguration speichern;
- aufgelöste Konfiguration ohne Secrets im Job-Summary dokumentieren.

## 11. Git- und Release-Modell

### Quellstand

- Jeder Lauf verwendet `github.sha` beziehungsweise einen daraus aufgelösten Commit-SHA.
- `HEAD` wird nicht als dauerhaftes Deployment-Merkmal gespeichert.
- Branch und Tag dienen als Auslöser; der Commit-SHA ist die technische Identität des Laufs.
- `Rxxx/Entwicklung` und `Rxxx/Abnahme` sind Deployment-Branches; ein Merge dorthin löst die jeweilige M/Text-Verteilung aus.
- `Rxxx/Bereitstellung` ist der Release-Stand; ein Merge dorthin erzeugt ohne Tag noch keine Lieferung.
- Branchschutz erzwingt Pull Requests und verhindert direkte produktive Pushes.

### FULL

- Ein Tag im Format `Rnnn.100`, zum Beispiel `R261.100`, erzeugt das vollständige Paket aus seinem Commit-SHA.
- Der Tag muss auf einem Commit liegen, der aus dem gleichnamigen Branch `Rnnn/Bereitstellung` erreichbar ist.
- Dateireihenfolge, Pfade, Rechte und Zeitstempel werden für reproduzierbare Archive normalisiert.
- Inhalt, Löschliste, Manifest und SHA-256 werden als gemeinsames Artefakt gespeichert.

### DELTA

- Ein Release-Tag derselben Linie mit einer anderen dreistelligen Endung, zum Beispiel `R261.108`, erzeugt eine Deltalieferung.
- Die Basis ist der zugehörige `.100`-Tag derselben Releaselinie, im Beispiel `R261.100`; das Ziel ist der aktuelle Release-Tag.
- Beide Referenzen werden vor Verarbeitung in Commit-SHAs aufgelöst und im Manifest gespeichert.
- `git diff --name-status` ist die Quelle für neue, geänderte, gelöschte und umbenannte Dateien.
- Die Behandlung von Umbenennungen wird in Charakterisierungstests gegen das bisherige Lieferformat abgesichert.
- Die `.100`-Basis wird direkt aus der Releaselinie abgeleitet; eine lexikografische Suche nach dem vorherigen Release wird nicht für die Paketbasis verwendet.

Das ist ein **kumulatives Delta seit dem Vollrelease**. `R261.108` enthält damit alle für die Lieferung relevanten Änderungen zwischen `R261.100` und `R261.108`, nicht nur die Änderungen zwischen `R261.107` und `R261.108`.

Dieses Verhalten ist für die Auslieferung robust und wird im ersten Git-Zielbild beibehalten:

- Ein Empfänger auf Stand `R261.100` kann direkt das aktuelle Delta anwenden und muss nicht alle Zwischendeltas lückenlos besitzen.
- Eine ausgefallene oder übersprungene frühere Lieferung erzeugt keine unterbrochene Delta-Kette.
- Erneut enthaltene geänderte Dateien werden durch die bestehende Importlogik ersetzt; die Verträglichkeit wiederholter Löschungen wird als Integrationstest abgesichert.
- Der Nachteil wachsender Deltaarchive innerhalb einer Releaselinie wird zugunsten der geringeren Abhängigkeit von historischen Einzellieferungen akzeptiert.

Der separate Vergleich mit dem direkten Vorrelease erzeugt im alten Skript lediglich `diff_tags_change.txt` für die Information beziehungsweise Mail. Er steuert nicht den Inhalt von `diff_change.txt`, aus dem Archiv und Löschliste gebaut werden.

Dass unter `/nfs/mtext/trans` scheinbar nur die jüngste Differenz liegt, entsteht durch die festen Dateinamen. Jede neue Lieferung kopiert ihr Archiv erneut nach `${MANDANT}${PACKAGE_CODE}D.tgz` und überschreibt damit die vorherige Datei desselben Mandanten und Pakettyps. Der sichtbare Bestand ist daher die zuletzt erzeugte kumulative Lieferung, nicht eine Historie inkrementeller Commit-Deltas.

GitHub-Actions-Artefakte werden dagegen pro Workflow-Lauf versioniert aufbewahrt. Der feste technische Name für die Mainframe-Übergabe kann bestehen bleiben, während Manifest, Tag, Basis-SHA und Ziel-SHA die konkrete Lieferung eindeutig identifizieren.

### Migration historischer Stände

- Für die aktiven Linien werden `.100` und alle späteren Tags zwingend importiert; weiter zurückreichende Historie und ältere Tags sind Nice-to-have.
- SVN-Tags wie `R260.101_MText` erhalten die dokumentierte Git-Entsprechung `R260.101`.
- SVN-Stufenpfade werden bewusst auf Branches wie `R260/Entwicklung` abgebildet; das Releaseverzeichnis wird nicht als zusätzliche Wurzel übernommen.
- Marker `Verbunden mit Bereitstellung*.txt` sowie nicht freigegebene Backup-/Fusion-Stände werden ausgeschlossen.
- Der Inhalt relevanter Tags wird vor Freigabe gegen den SVN-Stand verglichen.
- SVN-Properties, Externals, Autorenidentitäten und große Dateien werden im Migrationsprotokoll explizit behandelt.
- Nach dem Cut entstehen keine neuen Änderungen mehr in SVN.

## 12. JCL als versioniertes Template

Die JCL wird nicht mehr als Folge von `echo`-Anweisungen in Python oder Bash eingebettet. Sie liegt vollständig lesbar unter `templates/mainframe-upload.jcl`.

Beispiel für eindeutige Platzhalter:

```text
//COPYOUT  DD DISP=SHR,DSN=IEA.ISPW@@ISPW@@.BOAS.@@LEVEL@@.TONICZ
  APPLID=@@SUBSYS@@
  SUBAPPL=@@SUBSYS@@
  MNAME=@@MEMBER@@
  PROJNO=@@ASSIGNMENT@@
  CLVL=@@LEVEL@@
  SLVL=@@LEVEL@@
```

Die Marker `@@NAME@@` kollidieren nicht mit vorhandenen JCL-Inhalten wie `$DEFINE_TSI`. `jcl.py` rendert das Template mit einer Whitelist zulässiger Felder und bricht bei fehlenden oder übrig gebliebenen Markern ab.

Rendering-Regeln:

- Template ist versioniert und durch Code Review sichtbar.
- Eingabewerte stammen ausschließlich aus validierter Konfiguration und Manifest.
- Pflichtfelder sind `ISPW`, `LEVEL`, `SUBSYS`, `MEMBER` und `ASSIGNMENT`.
- Werte werden gegen erlaubte Zeichensätze und Maximallängen geprüft.
- Gerenderte JCL liegt nur im laufbezogenen temporären Verzeichnis.
- Gerenderte JCL enthält keine Credentials.
- Tests prüfen den Renderer mit kontrollierten Testwerten und Eingabegrenzen.
- FTP- und JES-Code verarbeitet eine fertige JCL-Datei und erzeugt sie nicht selbst.

## 13. Status- und Fehlermodell der ersten Ausbaustufe

| Status | Bedeutung | Workflow-Ergebnis |
|---|---|---|
| `VALIDATION_FAILED` | Konfiguration, Input, Tag oder Template ungültig | Fehler ohne externe Seiteneffekte |
| `SOURCE_FAILED` | Commit oder Basisreferenz nicht auflösbar | Fehler |
| `PACKAGE_FAILED` | FULL-/DELTA-Paket, Liste oder Manifest fehlerhaft | Fehler |
| `ARTIFACT_READY` | Paket und Manifest erfolgreich erzeugt und geprüft | Build erfolgreich |
| `RESOURCE_TRANSFER_FAILED` | Bereitstellung nach serverSync/NFS fehlgeschlagen | Sync fehlgeschlagen, kein Adapteraufruf |
| `ADAPTER_ACCEPTED` | Adapter antwortet gemäß bestehendem Vertrag mit dokumentiertem 2xx | Sync-Workflow erfolgreich |
| `ADAPTER_FAILED` | Transportfehler oder Nicht-2xx, einschließlich bekanntem HTTP 400 | Sync-Workflow fehlgeschlagen |
| `MAINFRAME_SUBMITTED` | FTP/JES-Übergabe gemäß bestehendem unmittelbarem Vertrag akzeptiert | Publish-Workflow erfolgreich mit Status `übergeben` |
| `MAINFRAME_TRANSFER_FAILED` | FTP- oder JES-Übergabe unmittelbar fehlgeschlagen | Publish-Workflow fehlgeschlagen |
| `NOTIFICATION_FAILED` | optionale Benachrichtigung fehlgeschlagen | Warnung, fachlicher Status bleibt erhalten |

Die Bezeichnungen vermeiden einen nicht belegten Endstatus. `MAINFRAME_SUBMITTED` bedeutet nicht, dass der Mainframe-Job fachlich erfolgreich abgeschlossen wurde. `ADAPTER_ACCEPTED` beschreibt nur den Erfolg nach dem heute sichtbaren synchronen Adaptervertrag.

## 14. Harter Cut und Migrationsplan

### Etappe 1: Zielverhalten aus dem Altsystem extrahieren

- alle Jenkins-Inputs und Mappings dokumentieren;
- Projektmatrix je Mandant und gegebenenfalls je Releaselinie übernehmen;
- produktive Branches, Releaseverzeichnisse und Tags je Mandanten-Repository explizit von Sicherungs- und Sonderverzeichnissen abgrenzen;
- aus den Referenzpaketen abgeleitete Formatregeln fachlich dokumentieren;
- JCL aus dem Skript in ein geprüftes Template übertragen;
- Adapter- und Mainframe-Aufrufvertrag als Integrationstest beschreiben;
- keine Änderung am Jenkins-Skript durchführen.

### Etappe 2: GitHub-Repositories und Python-Paket aufbauen

- zentrales Automatisierungs-Repository und mindestens ein repräsentatives Mandanten-Repository als Zielstruktur anlegen;
- dünne aufrufende Workflows im Mandanten-Repository mit unveränderlicher Referenz auf die zentrale Automatisierung anlegen;
- Konfigurationsschema und Mappings implementieren;
- Python-CLI und Module implementieren;
- Tests für Konfiguration, Git-Diff, Paketbau, Manifest und JCL erstellen;
- Workflows zunächst ohne produktive Secrets und ohne produktive Zielaufrufe validieren.

### Etappe 3: Self-hosted Runner und Integrationen vorbereiten

- Runner mit Git, freigegebener Python-Version, Netzwerk und NFS-Zugriff bereitstellen;
- Runner-Labels und GitHub Environments konfigurieren;
- Secrets für SVN werden nicht mehr benötigt;
- Adapter- und Mainframe-Secrets in den jeweiligen GitHub Environments hinterlegen;
- nichtproduktive Integrationsläufe mit kontrollierten Testzielen ausführen;
- Workflow-Concurrency pro Zielumgebung und Mandant konfigurieren.

### Etappe 4: Repository-Migration und Abnahme

- für jedes Mandanten-Repository einen vorläufigen SVN-Import zur Entwicklung und Prüfung verwenden;
- relevante Historie, Branches und Tags getrennt je Mandant nach Git übertragen;
- Dateiinhalte und relevante Release-Tags je Mandant gegen das zugehörige SVN-Repository verifizieren;
- FULL-/DELTA-Ergebnisse gegen die gesicherten Referenzen vergleichen;
- Abnahmeprotokoll für Git-Inhalte, Workflows, JCL und Zielübergaben erstellen.

### Etappe 5: Produktiver harter Cut

1. Änderungsfreeze in SVN aktivieren.
2. Letzten freigegebenen SVN-Stand und alle benötigten Tags nach Git übertragen.
3. Inhalt und Referenzmapping automatisiert verifizieren.
4. Jenkins-Trigger und Jenkins-Job für diesen Prozess deaktivieren.
5. SVN für diesen Prozess schreibschützen oder gemäß Betriebskonzept stilllegen.
6. Git als einzige führende Quelle markieren.
7. Produktive GitHub-Environments und Secrets freigeben.
8. GitHub-Actions-Workflows aktivieren.
9. Einen definierten Smoke-Test pro fachlichem Pfad ausführen.

Zwischen den Schritten 4 bis 8 existiert ein kontrolliertes Wartungsfenster, aber kein paralleler Produktivbetrieb.

## 15. Akzeptanzkriterien

### Repository und Cut

- Nach dem Cut benötigt kein Workflow Jenkins oder SVN.
- Jenkins löst für diesen Prozess keine Jobs mehr aus.
- Für jeden Mandanten existiert genau ein freigegebenes GitHub-Quellrepository.
- Der Git-Commit des letzten migrierten SVN-Stands ist je Mandant dokumentiert und inhaltlich verifiziert.
- Alle weiterhin benötigten Release-Tags sind im jeweils richtigen Mandanten-Repository vorhanden und geprüft.
- Sicherungs- und Sonderverzeichnisse werden nur nach expliziter Freigabe als Branch oder Tag migriert.
- Die Mandanten-Repositories referenzieren dieselbe freigegebene Version der zentralen Automatisierung.
- Für jede produktive Git-Aktion existiert genau ein zuständiger Workflow.

### Workflows

- Pull Requests führen keine externen Deployments oder Übertragungen aus.
- Ein Merge nach `Rxxx/Entwicklung` löst genau eine Verteilung zum M/Text-Entwicklungsserver aus.
- Ein Merge von `Rxxx/Entwicklung` nach `Rxxx/Abnahme` löst genau eine Verteilung zum M/Text-Abnahmeserver aus.
- Ein Merge nach `Rxxx/Bereitstellung` löst ohne Release-Tag keine Paketierung aus.
- Ein Tag `Rnnn.100` auf einem `Rnnn/Bereitstellung`-Commit löst genau eine FULL-Lieferung aus.
- Ein Tag `Rnnn.xxx` mit `xxx` ungleich `100` löst genau eine DELTA-Lieferung gegen `Rnnn.100` aus.
- Ein UTC-datierter Auswahlbranch kann ausgewählte Commits aus Abnahme aufnehmen, ohne ungeplante Abnahme-Commits nach Bereitstellung zu übernehmen.
- Manuelle Wiederholungen verwenden validierte Inputs; ein M/Text-Commit muss aus dem ausgewählten Stufenbranch erreichbar sein.
- Concurrency verhindert zwei gleichzeitige Schreibvorgänge auf dasselbe Ziel.

### Implementierung

- Fachliche Logik liegt in Python und nicht in umfangreichen YAML- oder Bash-Blöcken.
- Der Runner-Preflight enthält keine Fachlogik.
- Konfiguration wird vor jedem externen Seiteneffekt gegen das Schema validiert.
- Keine Credentials erscheinen in Repository, Logs, Artefakten oder gerenderten Dateien.
- Alle Fehler liefern stabile interne Fehlercodes und bereinigte Meldungen.

### FULL und DELTA

- Derselbe Commit und dieselbe Konfiguration erzeugen reproduzierbare Paketinhalte.
- Manifest und SHA-256 identifizieren das veröffentlichte Artefakt eindeutig.
- Deltas enthalten alle neuen und geänderten Dateien sowie die vollständige Löschliste.
- Das Delta für `R261.108` entspricht dem Git-Vergleich `R261.100 -> R261.108`.
- Eine Datei, die nach `R261.100`, aber vor `R261.107` geändert wurde und zwischen `R261.107` und `R261.108` unverändert blieb, ist weiterhin im Delta `R261.108` enthalten.
- Der Informationsvergleich zum direkten Vorrelease beeinflusst den Paketinhalt nicht.
- Umbenennungen und Sonderzeichen werden mit gezielt erzeugten Testdaten abgedeckt.
- Paketname, Projektwurzel, `./`-Präfix, Löschlistenpfad und Informationsdateiname sind mit dem historischen Verbraucher verifiziert.
- Ein fehlgeschlagener Publish-Lauf kann dasselbe unveränderte Artefakt erneut verwenden.

### M/Text und Mainframe

- Der Adapter wird erst nach erfolgreicher Ressourcenbereitstellung aufgerufen.
- Response-Body, HTTP-Status und Curl-Transportfehler sind im Job sichtbar.
- HTTP 400 kann nicht als erfolgreicher Workflow enden.
- In der ersten Ausbaustufe gibt es kein M/Text-Status-Polling.
- JCL liegt als versioniertes Template vor und wird strikt gerendert.
- Mainframe-Paket und JCL werden nach bestehendem Verfahren übergeben.
- Der Workflow bezeichnet die Mainframe-Übergabe als `MAINFRAME_SUBMITTED` und nicht als fachlichen Enderfolg.
- In der ersten Ausbaustufe gibt es kein Mainframe-Job-Polling.

## 16. Implementierungsparameter und Entscheidungsstand

### Belegte Erkenntnisse

- Das historische Skript verarbeitet pro Lauf genau ein Mandanten-Repository und stellt keine repositoryübergreifende Kombination aus FI-, Autonom- und Fragmentprojekten her.
- `createProject` und `updateProject` führen beide zu einem vollständigen Projektstand der ausgewählten Revision; FULL und DELTA unterscheiden nur die Mainframe-Paketbildung.
- `.100` ist die Basis eines Vollreleases; spätere Deltas derselben Linie werden kumulativ gegen `.100` gebildet.
- `_MText` ist ausschließlich Bestandteil alter SVN-Pfade und wird von Paket, JCL, Adapter und Mainframe nicht benötigt.
- FI-Assignment/Level sowie Mainframe-Dataset, JES-Ziel und unmittelbares FTP-/JES-Verfahren sind aus dem Bestand belegt und bleiben konfigurierbar.

### Bestätigte Entscheidungen

- Repositories: `j520730/mtext-actions`, `j517120/mtext-fi` sowie später `mtext-autonom`, `mtext-by`, `mtext-lh`, `mtext-nw`, `mtext-os`, `mtext-sa`.
- Aktive Linien: `R261 -> en01`, `R270 -> en02`, `R260 -> en03`.
- Branches: `<Releaselinie>/Entwicklung`, `/Abnahme`, `/Bereitstellung`; zunächst ist `R261/Entwicklung` Default Branch, kein zusätzlicher `main`.
- Feature-Branches: `feature/<Releaselinie>/<GitHub-Issue>-<Kurzname>`; Auswahlbranches: `release/<Releaselinie>-<UTC-Zeitstempel>`.
- Drei gemeinsame GitHub Environments; nur Mainframe in `Bereitstellung` verlangt eine manuelle Freigabe.
- Keine verpflichtende fremde Pull-Request-Freigabe und zunächst kein Tagschutz.
- Python 3.14, Runnerlabel vorläufig `mtext-delivery`, Artefaktaufbewahrung 30 Tage.
- Zielplattform GitHub Enterprise Server 3.20.4.
- Adapter ohne Authentifizierung, bestätigter Dummy-Payload, jeder 2xx-Status erfolgreich, kein Polling.
- Mainframe-Dataset `IEA.LOMS.TONICZ`, JES-Ziel `LIT9028A`, Timeout 60 Sekunden, kein Polling.
- Mainframe-Übergaben verschiedener Mandanten dürfen parallel laufen; innerhalb eines Mandanten werden sie standardmäßig serialisiert.

### Annahmen des aktuellen Entwurfs

- Der vorhandene serverSync-Pfad bleibt bis zur Bestätigung als vorläufiges Template bestehen.
- Der künftige Runner vertraut der internen CA für `*.ltoma.intern`; dies wird nicht vorausgesetzt, sondern getestet.
- Die GitHub-Enterprise-Freigabe erlaubt den zentralen Workflowaufruf über die beiden Namespaces; der zusätzliche Code-Checkout wird praktisch verifiziert.
- Die fest gepinnten Node-20-v3-Artefakt-Actions sind im internen `actions`-Namespace verfügbar und mit dem vorgesehenen self-hosted Runner kompatibel; dies wird praktisch verifiziert.

### Noch manuell festzulegen oder auszuführen

- tatsächlicher serverSync-Mountpfad;
- endgültiges Runnerlabel, Runnerbereitstellung, Wheelhousepfad und Netzwerkfreigaben;
- GitHub-Enterprise-Actions-Zugriff und gegebenenfalls kurzlebiger Installation-Token für den zentralen Checkout;
- Verfügbarkeit der gepinnten `upload-artifact`-/`download-artifact`-SHAs und Node-20-Action-Runtime auf GHES 3.20.4;
- vollständiger freigegebener Commit-SHA von `mtext-actions` statt Null-SHA;
- Environment-Secrets, Mainframe-Variablen, Branchrulesets und Required Checks;
- SVN-Autorenmapping sowie Behandlung von Properties, Externals, leeren Verzeichnissen und großen Dateien;
- genaue Import-Allowlist; ältere Tags und weiter zurückreichende Elementhistorie sind Nice-to-have;
- nichtproduktive Integrationsläufe und Aktivierung der drei versionierten Vertragsschalter.

Keiner dieser Punkte erfordert eine Änderung am alten Jenkins-Skript.

## 17. Priorisierte nächste Schritte

Die operative Liste mit konkretem Konfigurationsort, einzutragendem Wert und
Status steht in
[`docs/confluence/Naechste_Schritte.md`](docs/confluence/Naechste_Schritte.md).

Lokal umgesetzt sind das zentrale Python-Paket, drei wiederverwendbare
Workflows, ein zentraler CI-Workflow, Schemas, JCL-Template, Runner-Preflight,
FI-Konfiguration und die drei dünnen Mandantenworkflows. Externe Verträge
bleiben durch versionierte Schalter und den Null-SHA gesperrt.

Konfigurationen werden als JSON gegen geschlossene Schemata validiert und als
einfache JSON-Dokumente weiterverarbeitet. Nur schemaübergreifende fachliche
Querverweise werden in kleinen Hilfsfunktionen geprüft. Das Releasemanifest
besitzt ebenfalls ein mit dem Python-Paket ausgeliefertes geschlossenes Schema
und wird beim Erzeugen wie beim späteren Publish vollständig geprüft.

Vor einem nichtproduktiven Integrationslauf sind insbesondere GitHub-
Repositories und Branchrulesets, Environments, Runner, Wheelhouse,
repositoryübergreifender Actions-Zugriff, serverSync-Pfad sowie Mainframe-
Secrets einzurichten. Danach folgen kontrollierte Integrationsläufe, der
SVN-Import mit dokumentierter Pfad-/Tag-Abbildung und schließlich das separat
freizugebende Cutover-Runbook.

Job-ID-Polling für M/Text oder Mainframe gehört nicht zu diesen initialen
Schritten und wird nicht als Abhängigkeit für den Cut behandelt.

## 18. Dokumentationsstruktur und Pflege

Die vollständige Leseführung steht unter
[`docs/README.md`](docs/README.md). Für die tägliche Bedienung ist die
[`Benutzeranleitung`](docs/confluence/Benutzeranleitung.md) maßgeblich. Das
Confluence-Zielbild beschreibt Architektur und fachliche Entscheidungen;
`Migration_und_harter_Cut.md` und `Naechste_Schritte.md` trennen Cutover und
offene Betriebsarbeiten vom bereits implementierten lokalen Stand.

Die Soll-Grafik ist Bestandteil der verbindlichen Dokumentation. Änderungen
an Stufen, Triggern, Freigaben, Sicherheitsriegeln oder Statusbezeichnungen
werden deshalb gemeinsam in folgenden Artefakten gepflegt:

1. `Architektur_Soll_GitHub_Actions_Git.drawio`;
2. `docs/confluence/Benutzeranleitung.md`;
3. `docs/confluence/Zielbild_GitHub_Actions_Git.md`;
4. den betroffenen Repository-READMEs und Workflowverträgen;
5. `docs/confluence/Naechste_Schritte.md`, solange eine Änderung noch nicht
   aktiviert oder fachlich abgenommen ist.

Die historische Quelle `LBS_SVN_Hook_v0.4.bash` bleibt unverändert und dient
nur noch zur Nachvollziehbarkeit. Die früher daraus abgeleiteten ersten
Arbeitsaufträge sind mit dem vorhandenen Python-Paket, den Workflows, Schemata,
Tests und dem JCL-Template umgesetzt; offen sind die in Abschnitt 16 und in
„Nächste Schritte“ ausdrücklich genannten Integrations- und Cutover-Arbeiten.
