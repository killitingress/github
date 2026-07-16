# Migrations- und Cutover-Runbook

**Zweck:** Verbindliche Vorbereitung und Durchführung der SVN-Migration sowie
des produktiven harten Cutovers

**Operative Vorbereitung:** [Nächste Schritte](./Naechste_Schritte.md)

**Bedienung nach Aktivierung:** [Benutzeranleitung](./Benutzeranleitung.md)

## 1. Rahmen und Zeitplan

Voraussichtlich im November/Dezember 2026 wird zunächst ein Abzug der
SVN-Repositories nach Git kopiert. Dieser Stand dient dem Test-Parallelbetrieb;
Jenkins und SVN tragen weiterhin den produktiven Prozess. Eine laufende
Synchronisation des Testbestands mit SVN ist nicht erforderlich.

Für den ab Januar 2027 geplanten produktiven harten Cutover wird der dann
freigegebene aktuelle SVN-Stand abschließend nach Git übertragen und geprüft.
Während der Umschaltung gibt es keinen gleichzeitigen produktiven
Lieferbetrieb aus Jenkins/SVN und GitHub.

Ziel-Repositories sind `mtext-fi`, `mtext-autonom`, `mtext-by`, `mtext-lh`,
`mtext-nw`, `mtext-os` und `mtext-sa`.

## 2. Migration vorbereiten

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| geplant November/Dezember 2026 | Ersten SVN-Abzug für den Test-Parallelbetrieb erstellen | GitHub-Testumgebung mit dokumentiertem SVN-Ausgangsstand; Jenkins und SVN bleiben produktiv |
| offen | Import-Allowlist erstellen | Aktive Linien `R260`, `R261`, `R270` und die drei fachlichen Stufen sind je SVN-Repository festgelegt |
| offen | Projektmatrix inventarisieren und freigeben | Repositoryinhalt, Projekt-Allowlist und historisch festgelegte Lieferdateinamen sind je Mandant und gegebenenfalls je Releaselinie dokumentiert |
| erforderlich | Release-Basen importieren | Je aktiver Linie werden mindestens der `.100`-Stand und alle danach entstandenen Tags übernommen |
| offen | SVN-Pfade auf Git abbilden | Beispielsweise wird `branches/Entwicklung/R260.100_MText/<Projekt>` zu Branch `R260/Entwicklung` mit Pfad `<Projekt>` |
| offen | Tagnamen normalisieren | Beispielsweise wird `R260.101_MText` zu `R260.101`; die Entfernung von `_MText` wird protokolliert |
| offen | Nicht freigegebene SVN-Artefakte ausschließen | `Verbunden mit Bereitstellung*.txt`, Backup-/Fusion-Sonderstände und andere nicht freigegebene Marker werden nicht übernommen |
| offen | Repositoryinhalt und Projekt-Allowlist unterscheiden | Testdatenprojekte wie `LOMS_Testdaten` und `LOMS_Testdaten_Autonom` können im Repository liegen, bleiben aber außerhalb der Auslieferung |
| separate Aufgabe | SVN-Autoren zuordnen | Bestehende SVN-Namen sind in der Autoren-Mappingdatei auf Git-Identitäten abgebildet |
| offen | SVN-Eigenschaften inventarisieren | `svn:externals`, EOL, Keywords, executable, leere Verzeichnisse, Mergeinfo und große Dateien sind behandelt |
| optional | Weitere Historie und ältere Tags importieren | So viel Elementhistorie wie praktikabel bleibt erhalten, ohne den Cutover zu blockieren |
| geplant ab Januar 2027 | Finalen SVN-Stand übertragen | Seit dem ersten Abzug entstandene produktive Änderungen sind übernommen und der freigegebene Endstand ist verifiziert |

Der erste Abzug eröffnet nur den Test-Parallelbetrieb. Finaler Import,
SVN-Freeze und Deaktivierung von Jenkins werden erst durch den separat
freigegebenen produktiven Cutover ausgelöst.

## 3. Produktiven Cutover durchführen

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

## 4. Cutover abnehmen

Der Cutover ist erst abgeschlossen, wenn mindestens folgende Kriterien erfüllt
sind:

- Kein GitHub-Workflow benötigt Jenkins oder SVN und Jenkins löst für diesen
  Prozess keine Jobs mehr aus.
- Für jeden Mandanten sind der letzte migrierte SVN-Stand, sein Git-Commit und
  alle weiterhin benötigten Release-Tags dokumentiert und geprüft.
- Sicherungs- und Sonderstände wurden nur nach ausdrücklicher Freigabe
  übernommen.
- Alle Mandanten-Repositories verwenden dieselbe freigegebene Version der
  zentralen Automation.
- Pushes nach Entwicklung und Abnahme lösen genau die vorgesehene
  M/Text-Verteilung aus; ein Push nach Bereitstellung erzeugt ohne Tag keine
  Lieferung.
- `.100` erzeugt FULL, andere gültige Release-Tags derselben Linie erzeugen
  ein kumulatives DELTA gegen `.100`.
- Ressourcenbereitstellung, Adapterantwort, Artefaktprüfung, JCL und die
  unmittelbare Mainframe-Übergabe wurden auf dem vorgesehenen Betriebsweg
  erfolgreich geprüft.
- Gleichzeitige Schreibvorgänge auf dasselbe Ziel werden verhindert; Läufe für
  unterschiedliche Mandanten dürfen wie vorgesehen parallel arbeiten.
