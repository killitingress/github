# Nächste Schritte

**Zweck:** Operative Restarbeiten für den Test-Parallelbetrieb und den späteren produktiven Cutover

**Bezug:** [Zielbild](./Zielbild_GitHub_Actions_Git.md)

**Bedienung nach Aktivierung:** [Benutzeranleitung](./Benutzeranleitung.md)

**Ablauf:** [Soll-Architektur Ablaufdiagramm](../../Architektur_Soll_GitHub_Actions_Git.drawio)

Diese Seite enthält nur noch Tätigkeiten, die nach dem lokalen
Implementierungsstand manuell oder durch konkrete Konfiguration auszuführen
sind. Architekturbegründungen stehen im Zielbild. Noch unbekannte Werte werden
offen ausgewiesen und vor dem jeweiligen Integrationslauf geklärt.

## 1. GitHub-Repositories erstmals einrichten

| Status | Tätigkeit | Ort | Konkreter Wert beziehungsweise Ergebnis |
|---|---|---|---|
| offen | Zentrales Repository anlegen beziehungsweise lokalen Stand übernehmen | GitHub Enterprise: `j520730/mtext-actions` | Standardbranch und Freigabeprozess für die zentrale Automatisierung festlegen |
| offen | FI-Repository anlegen beziehungsweise lokalen Stand übernehmen | GitHub Enterprise: `j517120/mtext-fi` | Ressourcen, `config/mandant.json` und dünne Workflows übernehmen |
| offen | Aktive Stufenbranches anlegen | `j517120/mtext-fi` | Je `R260`, `R261`, `R270`: `Entwicklung`, `Abnahme`, `Bereitstellung` |
| offen | Aktuellen Default Branch setzen | Repository Settings → Default branch | Zunächst `R261/Entwicklung`; beim rollierenden Linienwechsel manuell umstellen |
| offen | Zentrale Workflowversion pinnen | Alle Dateien unter `mtext-fi/.github/workflows/` in jeder aktiven Linie | Null-SHA durch denselben freigegebenen 40-stelligen Commit-SHA aus `mtext-actions` ersetzen |
| offen | Repositoryübergreifenden Actions-Zugriff aktivieren | `j520730/mtext-actions` → Settings → Actions → General → Access | Nutzung durch `j517120/mtext-fi` und spätere Mandanten-Repositories erlauben |
| offen | Zentralen Code-Checkout praktisch prüfen | Nichtproduktiver Config-, Sync- oder Release-Lauf | Prüfen, ob die Enterprise-Freigabe den Checkout über beide Namespaces ermöglicht; falls ein Installation-Token erforderlich ist, den Workflowvertrag vor Aktivierung um dessen sichere Übergabe erweitern |
| bestätigt | GitHub-Plattform festhalten | Betriebsdokumentation | GitHub Enterprise Server 3.20.4 |

## 2. Branch- und Environment-Regeln konfigurieren

| Status | Tätigkeit | Ort | Konkreter Wert beziehungsweise Ergebnis |
|---|---|---|---|
| offen | Mandantenspezifische Verantwortliche benennen | Je Mandanten-Repository | Team für Ressourcenarbeit sowie kleines Release-Team für `R*/Bereitstellung` und neue Release-Tags festlegen |
| offen | Direkte Pushes auf Entwicklung und Abnahme zulassen | Branchschutz für `R*/Entwicklung`, `R*/Abnahme` | Berechtigten Mitarbeiterkreis je Mandant festlegen; Force-Pushes und Löschen verbieten |
| offen | Pushes nach Bereitstellung begrenzen | Branchschutz für `R*/Bereitstellung` | Nur das benannte Release-Team darf direkt pushen; Force-Pushes und Löschen bleiben verboten |
| offen | GitHub Environment anlegen | Repository Settings → Environments | Gemeinsame Environments `Entwicklung`, `Abnahme`, `Bereitstellung` |
| offen | Environment-Regeln setzen | Environments | Keine zusätzliche Freigabe für Entwicklung und Abnahme; manuelle Freigabe vor Mainframe-Übergabe in `Bereitstellung` |
| offen | Zulässige Deploymentbranches eintragen | Environments | Generische Muster `R*/Entwicklung`, `R*/Abnahme` und für die Freigabe `R*/Bereitstellung` verwenden; die aktive Linie wird zentral validiert |
| offen | Erstellung von Release-Tags begrenzen | Tag-Ruleset für `R[0-9][0-9][0-9].[0-9][0-9][0-9]` | Nur das je Mandant benannte Release-Team darf neue passende Tags anlegen |
| offen | Release-Tags unveränderlich schützen | Separates Tag-Ruleset für dasselbe Muster | Updates, Force-Pushes und Löschungen ohne regulären Bypass verbieten; einen gegebenenfalls notwendigen administrativen Notfallweg separat festlegen |

## 3. Runner und Abhängigkeiten bereitstellen

| Status | Tätigkeit | Ort | Konkreter Wert beziehungsweise Ergebnis |
|---|---|---|---|
| offen | Self-hosted Runner bereitstellen | GitHub-Enterprise-Runnerverwaltung | Labels `self-hosted`, `linux`, `mtext-delivery` bestätigen und zuweisen |
| offen | Python und Git prüfen | Vorgesehener Runner | Python 3.14 und Git müssen verfügbar sein; `scripts/runner-preflight.sh` ausführen |
| offen | GHES-Artefakt-Actions prüfen | GHES-Organisation `actions` und nichtproduktiver Release-Lauf | `upload-artifact` v3.2.2-node20 (`c6a3b2bd78b3985e4b2f15397fec357f0fd808de`) und `download-artifact` v3.1.0-node20 (`ad191675b41f6a5b46da9a048cb6893812da158b`) müssen auf GHES 3.20.4 verfügbar sein; v4 ist nicht zu verwenden |
| offen | Action-Runtime des Runners prüfen | Vorgesehener Self-hosted Runner | Ausführung von Node-20-Actions mit den fest gepinnten Artefakt-SHAs bestätigen |
| offen | Internes Wheelhouse bereitstellen | Runner und Repository-/Organisationsvariable | `LBS_WHEELHOUSE` auf freigegebenen lokalen Pfad setzen; Installation bleibt `--no-index` |
| offen | Interne CA prüfen | Vorgesehener Runner | TLS-Aufruf gegen `https://en01e.ltoma.intern/vMtextAdapter/sync` testen; fehlende CA in den Truststore aufnehmen, TLS-Prüfung nicht deaktivieren |
| offen | Netzwerkpfade freigeben | Runner/Netzwerk | Zugriff auf serverSync-Share, `*.ltoma.intern`, Mainframe-FTP und JES ermöglichen |

## 4. M/Text-Konfiguration vervollständigen und abnehmen

| Status | Tätigkeit | Ort | Konkreter Wert beziehungsweise Ergebnis |
|---|---|---|---|
| bestätigt | Linien- und URL-Mapping | `mtext-actions/config/deployments.json` | `R260→en03`, `R261→en01`, `R270→en02`; Hosts jeweils `enXXe` und `enXXa` |
| bestätigt | Adaptervertrag | Dieselbe Datei | POST auf `/vMtextAdapter/sync`, Payload `MAN`/`INR`, kein Auth-Header, jeder 2xx-Status erfolgreich, kein Polling |
| offen | serverSync-Sharepfad bestätigen | `adapter.server_sync_path_template` in `mtext-actions/config/deployments.json` | Vorläufiges Template durch den tatsächlich gemounteten Pfad bestätigen oder ersetzen |
| offen | Nebenwirkungsfreien Config-Check prüfen | Push mit Änderung an `config/mandant.json` | `CONFIG_VALIDATED` ohne Environment, Secrets, serverSync-, Adapter- oder Mainframe-Zugriff bestätigen |
| offen | Nichtproduktiven Synchronisationslauf durchführen | Freigegebener Runner und nichtproduktive Ziele | Vollständigen Projektstand bereitstellen, Adapterantwort und Wiederanlauf prüfen |

## 5. Mainframe-Übergabe einrichten und abnehmen

| Status | Tätigkeit | Ort | Konkreter Wert beziehungsweise Ergebnis |
|---|---|---|---|
| offen | FTP-Secrets hinterlegen | GitHub Environment `Bereitstellung` | `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER`, `MAINFRAME_FTP_PASSWORD` |
| offen | Mainframe-Variablen hinterlegen | Repository-/Environment-Variablen | `MAINFRAME_DATASET=IEA.LOMS.TONICZ`, `MAINFRAME_JES_TARGET=LIT9028A`, `MAINFRAME_FTP_TIMEOUT=60` |
| offen | JCL und unmittelbare Übergabe nichtproduktiv prüfen | Freigegebener Mainframe-Testweg | FTP-Antworten, `SITE FILETYPE=JES`, Submit und gerendertes JCL abnehmen |

Die Mainframe-Übergabe wartet im Environment `Bereitstellung` auf manuelle
Freigabe. GitHub-Actions-Artefakte bleiben 30 Tage erhalten. Build und Publish
sind getrennte Jobs desselben Release-Workflows; vor der Übergabe werden
Manifest und Prüfsummen erneut geprüft. Übergaben werden je
Mandanten-Repository serialisiert; unterschiedliche Mandanten dürfen parallel
laufen.

Mit der bestätigten Übergabe an IZE9 endet der in GitHub Actions abgebildete
Lieferprozess. Der weitere, deutlich umfangreichere Weg bis Produktion wird
außerhalb dieser Automation nach dem bestehenden Betriebsverfahren gesteuert.

## 6. SVN-Abzug für Parallelbetrieb und Cutover vorbereiten

Voraussichtlich im November/Dezember 2026 wird zunächst ein Abzug der
SVN-Repositories nach Git kopiert. Auf diesem Stand wird die GitHub-Umgebung
für Tests bereitgestellt, während Jenkins und SVN weiterhin den produktiven
Prozess tragen. Eine laufende Synchronisation des Testbestands mit SVN ist
nicht erforderlich. Für den ab Januar 2027 geplanten produktiven harten
Cutover wird der dann freigegebene aktuelle SVN-Stand abschließend nach Git
übertragen und geprüft.

| Status | Tätigkeit | Ort | Konkreter Wert beziehungsweise Ergebnis |
|---|---|---|---|
| geplant November/Dezember 2026 | Ersten SVN-Abzug für den Test-Parallelbetrieb erstellen | Alle Mandanten-Repositories | GitHub-Testumgebung mit einem dokumentierten SVN-Ausgangsstand bereitstellen; Jenkins/SVN bleiben produktiv |
| offen | Import-Allowlist erstellen | Migrationskonfiguration je SVN-Repository | Aktive Linien `R260`, `R261`, `R270` und die drei fachlichen Stufen |
| offen | Projektmatrix inventarisieren und freigeben | Je Mandant und gegebenenfalls je Releaselinie | Repositoryinhalt, Projekt-Allowlist und Paketcode getrennt dokumentieren; nicht allein aus einer globalen Projektliste ableiten |
| erforderlich | Release-Basis importieren | Git-Tags je Mandanten-Repository | Je aktiver Linie mindestens `.100` und alle danach entstandenen Tags importieren |
| offen | SVN-Pfade auf Git abbilden | Migrationsskript/-konfiguration | `branches/Entwicklung/R260.100_MText/<Projekt>` → Branch `R260/Entwicklung`, Pfad `<Projekt>` |
| offen | Tagnamen normalisieren | Migrationsskript/-konfiguration | `R260.101_MText` → `R260.101`; Entfernung von `_MText` protokollieren |
| offen | SVN-Artefakte ausschließen | Migrationsfilter | `Verbunden mit Bereitstellung*.txt`, Backup-/Fusion-Sonderstände und andere nicht freigegebene Marker nicht übernehmen |
| offen | Repositoryinhalte und Projekt-Allowlist unterscheiden | Importprüfung und `config/mandant.json` | FI enthält auch `LOMS_Testdaten`, `mtext-autonom` auch `LOMS_Testdaten_Autonom`; Testdatenprojekte bleiben außerhalb der Projekt-Allowlist |
| separate Aufgabe | SVN-Autoren zuordnen | Autoren-Mappingdatei des Migrationstools | Bestehende SVN-Namen auf Git-Identitäten abbilden |
| offen | SVN-Eigenschaften inventarisieren | Read-only SVN-Analyse | `svn:externals`, EOL, Keywords, executable, leere Verzeichnisse, Mergeinfo und große Dateien behandeln |
| optional | Weitere Historie und ältere Tags importieren | Migrationskonfiguration | So viel Elementhistorie wie praktikabel erhalten; darf den Cutover nicht blockieren |
| geplant ab Januar 2027 | Finalen SVN-Stand für den produktiven Cutover übertragen | Alle Mandanten-Repositories | Seit dem ersten Abzug entstandene produktive Änderungen übernehmen und den freigegebenen Endstand verifizieren |

Ziel-Repositories sind `mtext-fi`, `mtext-autonom`, `mtext-by`, `mtext-lh`,
`mtext-nw`, `mtext-os` und `mtext-sa`. Der erste Abzug eröffnet nur den
Test-Parallelbetrieb. Der finale Import, SVN-Freeze sowie die Deaktivierung von
Jenkins sind eigene freizugebende Tätigkeiten des produktiven Cutovers und
werden nicht durch den lokalen Implementierungsstand ausgelöst.

## 7. Produktiven Cutover durchführen und abnehmen

Der produktive harte Cutover ist ab Januar 2027 vorgesehen. Er wird mit einem
eigenen freigegebenen Runbook durchgeführt; der vorherige Test-Parallelbetrieb
aktiviert ihn nicht automatisch. Die verbindliche Reihenfolge ist:

1. Änderungsfreeze für den bisherigen Jenkins-/SVN-Prozess aktivieren.
2. Den letzten freigegebenen SVN-Stand und alle weiterhin benötigten Tags je
   Mandant nach Git übertragen.
3. Inhalte, Pfadabbildungen, Tags und den letzten migrierten Commit je Mandant
   dokumentieren und automatisiert verifizieren.
4. Jenkins-Trigger und Jenkins-Job für diesen Prozess deaktivieren.
5. SVN für diesen Prozess schreibschützen oder gemäß Betriebskonzept
   stilllegen.
6. Git als einzige führende Quelle für diesen Prozess festlegen.
7. Die für den Regelbetrieb vorgesehenen GitHub Environments, Secrets und
   Workflows freigeben.
8. Je einen definierten Smoke-Test für Entwicklung und Abnahme sowie je einen
   FULL- und DELTA-Release durchführen und dokumentieren.

Während der eigentlichen Umschaltung gibt es keinen gleichzeitigen produktiven
Lieferbetrieb aus Jenkins/SVN und GitHub. Der Cutover ist erst abgenommen, wenn
mindestens folgende Kriterien erfüllt sind:

- Kein GitHub-Workflow benötigt Jenkins oder SVN und Jenkins löst für diesen
  Prozess keine Jobs mehr aus.
- Für jeden Mandanten sind der letzte migrierte SVN-Stand, sein Git-Commit und
  alle weiterhin benötigten Release-Tags dokumentiert und geprüft.
- Sicherungs- und Sonderstände wurden nur nach ausdrücklicher Freigabe
  übernommen.
- Alle Mandanten-Repositories verwenden dieselbe freigegebene Version der
  zentralen Automation.
- Pushes nach Entwicklung und Abnahme lösen jeweils genau die vorgesehene
  M/Text-Verteilung aus; ein Push nach Bereitstellung erzeugt ohne Tag keine
  Lieferung.
- `.100` erzeugt FULL, andere gültige Release-Tags derselben Linie erzeugen
  ein kumulatives DELTA gegen `.100`.
- Ressourcenbereitstellung, Adapterantwort, Artefaktprüfung, JCL und die
  unmittelbare Mainframe-Übergabe wurden auf dem vorgesehenen Betriebsweg
  erfolgreich geprüft.
- Gleichzeitige Schreibvorgänge auf dasselbe Ziel werden verhindert; Läufe für
  unterschiedliche Mandanten dürfen wie vorgesehen parallel arbeiten.

## 8. Wiederkehrende Konfigurationsarbeiten

Bei einer rollierenden Releaselinie sind folgende Änderungen abgestimmt
auszuführen:

1. Linienmapping und Adapterziele in
   `mtext-actions/config/deployments.json` aktualisieren.
2. Neue `<Releaselinie>/Entwicklung`, `/Abnahme` und `/Bereitstellung` anlegen
   und die ausgeschiedene Linie gemäß Aufbewahrungsregel stilllegen.
3. Default Branch auf den Entwicklungsbranch der neuen führenden Linie setzen.
4. Workflow- und Konfigurationsänderungen je aktiver Linie nach
   `Rnnn/Entwicklung` einbringen und anschließend normal nach Abnahme und
   Bereitstellung übernehmen. Es gibt keine automatisch schreibende
   branchübergreifende Verwaltungsautomation.
5. Assignment und Level bei betrieblichen Änderungen ausschließlich in
   `config/mandant.json` des betroffenen Mandanten anpassen.

Die dünnen Sync-Workflows enthalten keine Liste aktiver Releaselinien mehr.
Ihre generischen Branchmuster bleiben bei einem Linienwechsel unverändert;
unbekannte Linien werden durch `deployments.json` abgewiesen.

## 9. Spätere Erweiterungen

- E-Mail-Benachrichtigungen zusätzlich zu GitHub-Benachrichtigungen;
- optional mehr historische SVN-Tags und Elementhistorie;
- bei einer späteren PR-basierten Config-Pflege verbindliche Code-Owner- und
  Freigaberegel für Änderungen an `config/mandant.json`;
- bei entsprechendem Ergebnis der Pilotphase kurzlebiger Auswahlbranch mit
  normalem Pull Request nach `Rnnn/Bereitstellung`, ohne eigenen
  zusätzlichen Workflow für diesen Auswahlbranch;
- optionales M/Text- oder Mainframe-Status-Polling als eigener Ausbau, nicht
  als Voraussetzung für die erste Produktivsetzung.
