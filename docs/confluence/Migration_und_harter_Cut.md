# Migration und harter Cut

**Stand:** 15. Juli 2026
**Bezug:** [Zielbild für die Ablösung von Jenkins und SVN](./Zielbild_GitHub_Actions_Git.md),
[Benutzeranleitung](./Benutzeranleitung.md) und
[Soll-Grafik](../../Architektur_Soll_GitHub_Actions_Git.drawio)

## Ziel und Grundsatz

Jenkins/SVN und GitHub Actions/Git werden nicht parallel produktiv betrieben.
Die Umstellung erfolgt in einem kontrollierten Wartungsfenster. Vor dem
Umschaltpunkt werden Zielsystem, Repositories, Referenzdaten und Integrationen
vorbereitet und abgenommen. Am Umschaltpunkt wird SVN für diesen Prozess
eingefroren, der letzte freigegebene Stand nach Git übernommen und anschließend
nur noch das neue Zielbild aktiviert.

Das historische Jenkins-/SVN-Skript bleibt während der gesamten Migration
Read-only. Es dient als Quelle für fachliche Regeln, wird aber weder repariert
noch für einen Parallelbetrieb erweitert. Historische Lieferdateien waren nur
temporäre Entwicklungsreferenzen; sie werden weder mitmigriert noch als
dauerhafte Test-Fixtures verwendet.

## Phase 1: Zielverhalten und Referenzbestand sichern

Zu Beginn werden die fachlich relevanten Informationen des Altsystems
vollständig inventarisiert. Dazu gehören Mandanten, Projekte, Releaselinien,
Stufen, Assignments, Level, Adapterziele, Paketnamen und JCL-Felder. Produktive
Branches, Releaseverzeichnisse und Tags werden je Mandanten-Repository über
eine explizite Allowlist von Sicherungs- und Sonderständen abgegrenzt.

Die anfängliche Analyse vorhandener FULL- und DELTA-Lieferungen hat die
kumulative DELTA-Bildung gegen den `.100`-Stand bestätigt. Diese Erkenntnis ist
in Konfiguration und synthetischen Tests festgeschrieben; die ursprünglichen
Lieferdateien bleiben kein Bestandteil der Ziel-Repositories oder Testsuite.
Der Adapter- und Mainframe-Vertrag unterscheidet klar zwischen technischer
Übergabe und fachlichem Endstatus.

Ein erster lokaler Bestands- und Konfigurationsentwurf einschließlich FI-
Konfiguration, Schema, JCL-Template und lokaler Tests liegt bereits vor. Seine
fachliche Abnahme und die Vervollständigung der übrigen Mandanten stehen noch
aus.

## Phase 2: Repositories und Automatisierung aufbauen

Das zentrale Automatisierungs-Repository und mindestens ein repräsentatives
Mandanten-Repository werden als belastbare Zielstruktur aufgebaut. Die
gemeinsame Automatisierung wird versioniert, getestet und von den
Mandanten-Repositories nur in einer festgelegten Version verwendet.

Validierung, Paketbildung, Manifest, JCL-Erzeugung und Fehlerstatus werden
zunächst vollständig ohne produktive Secrets und ohne produktive Zielaufrufe
geprüft. Pull-Request-Prüfungen bleiben grundsätzlich frei von externen
Seiteneffekten.

Die Mandanten-Repositories erhalten keinen zusätzlichen `main`-Branch. Der
Default Branch ist der Entwicklungsbranch der aktuell führenden Linie; zu
Beginn ist dies `R261/Entwicklung`. Bei einem rollierenden Linienwechsel wird
diese GitHub-Einstellung manuell angepasst. Workflow- und
Konfigurationsänderungen werden je aktiver Linie nach `Rxxx/Entwicklung`
eingebracht und anschließend über den normalen Promotionsweg weitergeführt.

## Phase 3: Runner und Integrationen vorbereiten

Der benötigte self-hosted Runner wird mit freigegebener Laufzeit,
Netzwerkzugriffen, NFS-Mounts und stabilen Labels bereitgestellt. Die drei
gemeinsamen GitHub Environments `Entwicklung`, `Abnahme` und `Bereitstellung`
trennen Zielstufen, Secrets und Freigaberegeln. Entwicklung und Abnahme laufen
nach dem Merge automatisch; die Mainframe-Übergabe wartet in
`Bereitstellung` auf manuelle Freigabe. Gleichzeitige Schreibzugriffe auf
dasselbe M/Text-Ziel sowie Mainframe-Übergaben desselben Mandanten werden
serialisiert.

Adapter und Mainframe werden ausschließlich gegen ausdrücklich freigegebene
nichtproduktive Ziele getestet. Dabei wird nur der vorhandene synchrone
Adapter- beziehungsweise FTP-/JES-Vertrag geprüft. Ein neues Job-Polling ist
keine Voraussetzung für den Cut.

## Phase 4: Vorläufige Migration und Abnahme

Für jeden Mandanten wird ein vorläufiger Import erstellt. Relevante Historie,
Branches und Tags werden getrennt nach Mandant übertragen. Dateiinhalte und
Release-Tags werden automatisiert gegen den entsprechenden SVN-Stand
verglichen.

Die SVN-Struktur wird bewusst in ein Git-gerechtes Branchmodell übersetzt. Aus
`branches/Entwicklung/R260.100_MText/<Projekt>` wird der Branch
`R260/Entwicklung` mit `<Projekt>` in der Wurzel. Entsprechend entstehen
`R260/Abnahme` und `R260/Bereitstellung`. Das Suffix `_MText` entfällt bei
Git-Tags, weil Repository und Kontext bereits eindeutig sind:
`R260.101_MText` wird zu `R260.101`. Diese Abweichungen werden im
Migrationsprotokoll ausdrücklich ausgewiesen.

Für jede aktive Linie müssen mindestens der `.100`-Tag und alle danach
entstandenen Release-Tags importiert werden; ohne `.100` ist der kumulative
DELTA-Bau nicht möglich. Ältere Linien, ältere Tags und möglichst umfassende
Elementhistorie sind Nice-to-have. Committexte, Zeitpunkte und SVN-Autoren
werden soweit praktikabel erhalten. Das Autoren-Mapping ist eine separate
Migrationsaufgabe.

`Verbunden mit Bereitstellung*.txt`, Backup-/Fusion-Verzeichnisse und andere
SVN-spezifische Marker werden über explizite Filter ausgeschlossen.
SVN-Properties, Externals, leere Verzeichnisse, Mergeinfo und große Dateien
werden gesondert inventarisiert.

Die Abnahme prüft Git-Inhalte, erforderliche Tags, Workflows, JCL und die
kontrollierten Zielübergaben. Sie stützt sich auf die freigegebenen Regeln und
synthetische Tests, nicht auf dauerhaft mitgeführte Golden-Master-Dateien.

## Phase 5: Produktiver Cutover

Der produktive Wechsel erfolgt in festgelegter Reihenfolge:

1. Für den betroffenen Prozess wird ein Änderungsfreeze in SVN aktiviert.
2. Der letzte freigegebene SVN-Stand einschließlich aller benötigten Tags wird
   je Mandant nach Git übertragen.
3. Inhalt und Referenzmapping werden automatisiert verifiziert und protokolliert.
4. Jenkins-Trigger und Jenkins-Job für diesen Prozess werden deaktiviert.
5. SVN wird für diesen Prozess schreibgeschützt oder gemäß Betriebskonzept
   stillgelegt.
6. Git wird als einzige führende Quelle gekennzeichnet.
7. Produktive GitHub Environments, Schutzregeln und Secrets werden freigegeben.
8. Die GitHub-Actions-Prozesse werden produktiv aktiviert.
9. Für Entwicklung, Abnahme und einen kontrollierten Releasepfad werden
   definierte Smoke-Tests ausgeführt und abgenommen.

Zwischen der Deaktivierung des Altsystems und der Aktivierung des Zielsystems
liegt ein kontrolliertes Wartungsfenster. Es gibt zu keinem Zeitpunkt zwei
gleichzeitig aktive produktive Orchestratoren.

## Nachweise und Freigabe

Für jeden Mandanten werden mindestens der letzte SVN-Stand, der zugehörige
Git-Commit, die übernommenen Release-Tags und das Ergebnis der Inhaltsprüfung
dokumentiert. Zusätzlich werden die freigegebene Automatisierungsversion, die
Environment-Konfiguration und die Ergebnisse der Smoke-Tests protokolliert.

Ein organisatorischer Rollback kann nur innerhalb des freigegebenen
Cutover-Konzepts erfolgen. Er darf nicht in einen unkontrollierten
Parallelbetrieb münden. Die konkrete Entscheidungskette, Verantwortlichkeiten
und Kommunikationswege werden vor dem produktiven Termin im Cutover-Runbook
festgelegt.
