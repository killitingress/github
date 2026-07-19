# Migrations- und Cutover-Runbook

**Zweck:** Verbindliche Vorbereitung und Durchführung der SVN-Migration sowie
des produktiven harten Cutovers

**Zielbild:** [GitHub Actions und Git](./Zielbild_GitHub_Actions_Git.md)

**Soll-Ablauf:**
[Architekturdiagramm](../../Architektur_Soll_GitHub_Actions_Git.drawio)

**Operative Vorbereitung:** [Nächste Schritte](./Naechste_Schritte.md)

**Bedienung nach Aktivierung:** [Benutzeranleitung](./Benutzeranleitung.md)

## 1. Rahmen, Umfang und Verantwortlichkeiten

Voraussichtlich im November/Dezember 2026 wird ein fest benannter Stand der
SVN-Repositories nach Git übernommen. Dieser Abzug dient dem nichtproduktiven
Test-Parallelbetrieb. Jenkins und SVN bleiben währenddessen produktiv. Der
Teststand wird nicht laufend mit SVN abgeglichen.

Für den ab Januar 2027 geplanten Cutover wird nach einem Änderungsfreeze der
freigegebene SVN-Endstand mit demselben abgenommenen Verfahren nach Git
übertragen und geprüft. Während der Umschaltung liefert nur eines der beiden
Systeme produktiv.

Ziel-Repositories sind `mtext-fi`, `mtext-autonom`, `mtext-by`, `mtext-lh`,
`mtext-nw`, `mtext-os` und `mtext-sa`. Vor dem ersten Abzug wird verbindlich
dokumentiert, ob das vorhandene Mandantenkürzel `IT` durch eines dieser
Repositories abgedeckt ist oder ein zusätzliches Ziel-Repository benötigt.

Für Testabzug und Cutover werden mindestens folgende Rollen namentlich
besetzt:

| Rolle | Verantwortung |
|---|---|
| Cutover-Leitung | Ablauf koordinieren, Go-/No-Go und Abschluss protokollieren |
| Migrationsteam | SVN-Abzug, Git-Import und technische Importnachweise erstellen |
| Zentrales Automatisierungsteam | Freigegebene Version von `mtext-actions`, Workflows und technische Prüfungen verantworten |
| Technischer Konfigurationskreis | Mandantenkonfiguration und Releaselinienzuordnung freigeben |
| Mandanten-Release-Team | Bereitstellungsbranches, Release-Tags und Freigaben je Mandant prüfen |
| M/Text- und Mainframe-Betrieb | Zielzugriffe, technische Annahme und fachliche Zielkontrolle bestätigen |

Jeder Migrationslauf erhält ein Protokoll mit verantwortlicher Person, Beginn
und Ende, SVN-Quelle und -Revision, Version des Migrationsverfahrens,
Ziel-Repository, freigegebener Version von `mtext-actions`, Ergebnis der
Prüfungen und getroffener Fortsetzungsentscheidung.

## 2. Voraussetzungen und Go-/No-Go

Ein Testabzug oder produktiver Cutover beginnt nur, wenn sein Umfang, seine
Quellen und seine Verantwortlichen feststehen. Für den produktiven Cutover
müssen zusätzlich alle aktivierungsrelevanten Punkte aus
[Nächste Schritte](./Naechste_Schritte.md) abgeschlossen und nachgewiesen sein.

### Technische Voraussetzungen

- Die Ziel-Repositories, die Branches `Rnnn/Entwicklung`, `Rnnn/Abnahme` und
  `Rnnn/Bereitstellung` sowie der vorgesehene Default Branch sind eingerichtet.
- Die zentrale Einrichtungsprüfung bestätigt für alle Mandanten-Workflows
  dieselbe unveränderliche, freigegebene Version von `mtext-actions`.
  Technische Platzhalter oder bewegliche Referenzen sind nicht vorhanden.
- Der repositoryübergreifende Workflowaufruf, der technisch nur lesende
  Checkout der zentralen Implementierung und alle vollständig gepinnten Actions
  funktionieren auf GitHub Enterprise Server 3.20.4.
- Rulesets schützen Stage-Branches, `.github/workflows/**/*` und
  `.github/config.json`. Force-Pushes und das Löschen der Stage-Branches sind
  gesperrt.
- Die Environments `Entwicklung`, `Abnahme` und `Bereitstellung` sind
  eingerichtet. Nur der Publish-Job kann `Bereitstellung` verwenden und muss
  dort manuell freigegeben werden.
- Der Lebenszyklus der Release-Tags ist eingerichtet und abgenommen. Ein
  Release-Kandidat kann vor der Freigabe kontrolliert zurückgenommen werden;
  nach der Freigabe sind Änderung und Löschung gemäß der verbindlichen
  Betriebsregel unzulässig.
- Das offizielle `runs-on`-Kennzeichen des ausgewählten FI-Runnerangebots ist
  eingetragen. Python-Laufzeit, Git, Zertifikate und die benötigten
  Netzwerkpfade sind auf diesem Runner geprüft. Bereitstellung, Absicherung,
  Wartung und Bereinigung des Runners liegen außerhalb des Projekts.
- M/Text-Transport, `serverSync`-Zielstand, Wiederanlauf und das Entfernen
  veralteter Projekte sind abgenommen.
- Mainframe-Secrets liegen ausschließlich im Environment `Bereitstellung`.
  JCL, FTP und JES wurden mit der vorgesehenen ISPW-Instanz nichtproduktiv
  geprüft.
- Sicherung, Rückfallverfahren, Entscheidungsberechtigte und erreichbare
  Ansprechpartner für das Cutover-Fenster sind festgelegt.

### Go-/No-Go-Entscheidung

Die Cutover-Leitung protokolliert vor dem Änderungsfreeze und erneut nach der
Prüfung des finalen Imports eine ausdrückliche Go-/No-Go-Entscheidung. Ein
offener Pflichtnachweis, eine nicht eindeutige Quellrevision oder ein
abweichendes Prüfergebnis führt zu No-Go. Die produktive Umschaltung beginnt
erst nach einem dokumentierten Go.

## 3. Testabzug vorbereiten und abnehmen

Der Testabzug erprobt genau das Verfahren, das später für den finalen Import
verwendet wird. Manuelle Korrekturen am importierten Ergebnis werden nicht zum
Ersatz für eine Korrektur des wiederholbaren Migrationsverfahrens.

### Importumfang festlegen

| Status | Tätigkeit | Verbindliches Ergebnis |
|---|---|---|
| offen | SVN-Quellen festlegen | Repository-URL, Pfad und exakte Revision sind je Ziel-Repository dokumentiert |
| offen | Branchmatrix erstellen | Die SVN-Quellen für Entwicklung, Abnahme und Bereitstellung jeder aktiven Releaselinie sind eindeutig den Git-Branches zugeordnet |
| offen | Projektmatrix freigeben | Projektverzeichnisse, Fragmentnamen, Liefercodes und Ausschlüsse sind je Mandant dokumentiert |
| erforderlich | Release-Basen festlegen | Je aktiver Releaselinie sind der benötigte freigegebene `.100`-Tag und alle weiterhin benötigten freigegebenen Folgetags benannt |
| offen | Tagnamen normalisieren | Beispielsweise wird `R260.101_MText` zu `R260.101`. Jede Zuordnung nennt Quelltag, Zieltag und Ziel-Commit |
| offen | Nicht freigegebene Stände ausschließen | Irrtümliche Tags, `Verbunden mit Bereitstellung*.txt`, Backup-/Fusion-Sonderstände und andere nicht freigegebene Marker werden nicht als Releases übernommen |
| offen | Projektausschlüsse festlegen | Testdatenprojekte dürfen in Git liegen, werden aber über `excluded_projects` von Synchronisation und Lieferung ausgeschlossen |
| separate Aufgabe | SVN-Autoren zuordnen | Bestehende SVN-Namen sind eindeutig Git-Identitäten zugeordnet |
| offen | SVN-Eigenschaften behandeln | `svn:externals`, EOL, Keywords, executable, leere Verzeichnisse, Mergeinfo und große Dateien sind inventarisiert und ihre Behandlung dokumentiert |
| optional | Weitere Historie übernehmen | Zusätzliche Historie und ältere freigegebene Tags werden nur mit dokumentiertem Umfang importiert |

Ein normalisierter Tag darf nur genau einem SVN-Tag und genau einem Ziel-Commit
zugeordnet sein. Eine Namenskollision oder ein widersprüchlicher Ziel-Commit
stoppt den Import.

### Mandantenkonfiguration erzeugen

Für jedes Ziel-Repository wird eine `.github/config.json` mit mindestens folgenden
fachlich bestätigten Werten erzeugt und durch `validate-config` geprüft:

- `kuerzel` und exakter Repositoryname,
- `ispw` mit `T` oder `P`,
- Mainframe-`subsystem`,
- `hostprofile` mit Assignment und gültigem CodePipeline-Stage-Code,
- ausdrücklich ausgeschlossene Projekte.

Die zentrale Datei `config/releaselinien.json` ordnet jeder der drei aktiven
Releaselinien ihre `mtext_linie` und ein im Mandanten vorhandenes `hostprofil`
zu. Die Zuordnung wird rollierend gepflegt. Zugangsdaten werden nicht
importiert und stehen nicht in Git.

### Import nachweisen

Der Testabzug ist je Ziel-Repository erst abgenommen, wenn mindestens folgende
Nachweise vorliegen:

- SVN-Quelle und -Revision sowie Git-Ziel-Commit sind eindeutig verbunden.
- Alle vorgesehenen Stage-Branches existieren und zeigen auf die bestätigten
  Stände.
- Projekt- und Dateibestand stimmen nach den dokumentierten EOL-, Keyword- und
  Eigenschaftsbehandlungen mit der Quelle überein. Abweichungen sind erklärt
  und freigegeben.
- Jeder importierte Release-Tag besitzt das Format `Rnnn.nnn`, zeigt auf den
  dokumentierten Commit und ist vom Bereitstellungsbranch seiner Releaselinie
  erreichbar.
- Für jeden DELTA-Tag ist der `.100`-Tag derselben Releaselinie ein Vorgänger
  in der Git-Historie.
- `validate-config` endet für jeden Mandanten mit `CONFIG_VALIDATED`.
- Ein vollständiger Sync nach Entwicklung und Abnahme stellt den erwarteten
  Zielstand her. Die fachliche Kontrolle in M/Text ist dokumentiert.
- Ein FULL und ein DELTA erzeugen die erwarteten Archive, Informationsdateien,
  Löschlisten und JCL-Werte. Der Vergleich mit dem bisherigen Lieferweg ist
  dokumentiert.
- Ein nichtproduktiver Publish-Lauf prüft Artefakt, konfigurierte ISPW-Instanz,
  JCL und unmittelbare FTP-/JES-Übergabe. Die nachgelagerte fachliche Kontrolle
  erfolgt separat.
- Abbruch und Wiederanlauf von M/Text-Synchronisation und Mainframe-Übergabe
  wurden gemäß dem jeweiligen Zielvertrag praktisch geprüft.

## 4. Finalen Import durchführen

1. Das vereinbarte Änderungsfreeze für den Jenkins-/SVN-Prozess aktivieren.
2. Zeitpunkt, letzte freigegebene SVN-Revision und ausstehende Lieferungen
   protokollieren. Laufende Jenkins-Jobs kontrolliert beenden.
3. Den wiederherstellbaren SVN-Ausgangsstand und die vorhandene
   GitHub-Konfiguration sichern.
4. Den freigegebenen SVN-Endstand mit derselben versionierten und im
   Testabzug abgenommenen Migrationslogik importieren.
5. `.github/config.json`, Stage-Branches, Default Branch, Projekte, Dateien und
   Release-Tags anhand der Nachweise aus Kapitel 3 prüfen.
6. Je importiertem DELTA die Erreichbarkeit vom Bereitstellungsbranch und die
   Abstammung vom zugehörigen `.100`-Tag automatisch prüfen.
7. Einen für den Import benötigten zeitlich begrenzten Bypass protokollieren
   und nach dem Import entfernen. Importierte freigegebene Tags anschließend
   mit ihren vollständigen Ziel-SHAs im Cutover-Protokoll festhalten; sie
   unterliegen unmittelbar der Betriebsregel für freigegebene Tags.
8. Die zentrale Einrichtungsprüfung ausführen und bestätigen, dass alle
   Mandanten-Workflows dieselbe unveränderliche, freigegebene Version der
   zentralen Automation verwenden.
9. Die zweite Go-/No-Go-Entscheidung protokollieren. Bei No-Go bleiben Jenkins
   und SVN führend und der GitHub-Stand wird nicht produktiv freigegeben.

## 5. Führendes System umschalten und prüfen

Nach dem zweiten Go wird in dieser Reihenfolge umgeschaltet:

1. Jenkins-Trigger und Jenkins-Job für diesen Prozess deaktivieren und
   bestätigen, dass kein zugehöriger Job mehr läuft.
2. SVN für diesen Prozess schreibschützen. Eine endgültige Stilllegung erfolgt
   erst nach Ablauf des vereinbarten Beobachtungszeitraums.
3. Git und GitHub Actions für den Prozess als führende Quelle freigeben.
4. Rulesets, Environments, Workflowzugriff, FI-Runner-Kennzeichen und minimale
   `GITHUB_TOKEN`-Rechte nochmals in der produktiven Einstellung kontrollieren.
5. Einen festgelegten Commit nach `Rnnn/Entwicklung` pushen und sowohl
   `ADAPTER_ACCEPTED` als auch den fachlich richtigen Stand in
   M/Text-Entwicklung bestätigen.
6. Die freigegebene Änderung per Cherry-Pick nach `Rnnn/Abnahme` übernehmen
   und dort technische sowie fachliche Synchronisation bestätigen.
7. Den bestätigten Stand nach `Rnnn/Bereitstellung` übernehmen und nachweisen,
   dass dieser Push allein keine Lieferung startet.
8. Die freigegebenen FULL- und DELTA-Smoke-Tests mit vorab benannten Tags
   ausführen. Vor der manuellen Freigabe werden Tag, Ziel-Commit, Manifest und
   Build-Protokoll kontrolliert.
9. Nach der Freigabe die unmittelbare FTP-/JES-Annahme sowie den
   nachgelagerten fachlichen Mainframe-Status separat bestätigen. Ein
   freigegebener Tag wird weder verschoben noch gelöscht.
10. Ergebnisse, verwendete Commits, Tags, Artefakte, Freigaben und fachliche
    Bestätigungen im Cutover-Protokoll festhalten.

`ADAPTER_ACCEPTED` bestätigt nur die unmittelbare Adapterantwort.
`MAINFRAME_SUBMITTED` bestätigt nur die unmittelbare FTP-/JES-Annahme. Keiner
der beiden Status ersetzt die fachliche Kontrolle im jeweiligen Zielsystem.

## 6. Abbruch und Rückfall

Der Cutover wird mindestens bei einem der folgenden Ereignisse angehalten:

- Quellrevision, Branch-, Tag- oder Dateizuordnung ist nicht eindeutig.
- Ein Pflichtnachweis oder eine erforderliche Freigabe fehlt.
- Workflowversion, Ruleset, Environment, FI-Runner, Netzwerkpfad oder Secret ist
  nicht wie abgenommen verfügbar.
- Der Zielstand in M/Text weicht vom freigegebenen Commit ab.
- FULL, DELTA, Manifest, JCL oder konfigurierte ISPW-Instanz weichen vom
  bestätigten Vertrag ab.
- Die Wirkung einer Mainframe-Übergabe ist unklar oder nur teilweise erfolgt.
- Ein freigegebener Release-Tag wurde verändert oder gelöscht.

Vor dem ersten produktiven Git-Commit oder einer externen Wirkung kann nach
dokumentierter Entscheidung auf Jenkins und das weiterhin unveränderte SVN
zurückgeschaltet werden. Der nicht freigegebene GitHub-Import wird dabei
gesperrt und als fehlgeschlagener Lauf dokumentiert.

Sind nach der Umschaltung bereits neue Git-Commits, freigegebene Tags oder
externe Wirkungen entstanden, ist eine automatische Rückkehr unzulässig. Die
Cutover-Leitung friert weitere Änderungen ein. Migrationsteam, Release-Team
und Zielsystembetrieb gleichen Git- und SVN-Stände sowie bereits erfolgte
M/Text- und Mainframe-Wirkungen ab und entscheiden dokumentiert über
Fortsetzung oder kontrollierte Rückmigration. Eine Mainframe-Übergabe wird bei
unklarem Annahmestatus nicht ungeprüft wiederholt.

Die konkreten administrativen Schritte zum Wiederaktivieren von Jenkins und
zum Aufheben des SVN-Schreibschutzes werden vor dem Cutover getestet, im
Betriebsprotokoll hinterlegt und dürfen nur von den benannten Verantwortlichen
ausgeführt werden.

## 7. Cutover abnehmen und abschließen

Der Cutover ist erst abgeschlossen, wenn mindestens folgende Kriterien erfüllt
und im Cutover-Protokoll bestätigt sind:

- Kein GitHub-Workflow benötigt Jenkins oder SVN. Jenkins löst für diesen
  Prozess keine Jobs mehr aus und SVN ist schreibgeschützt.
- Für jeden Mandanten sind SVN-Endrevision, Git-Ziel-Commit, Branchmatrix,
  Projektbestand, Konfiguration und alle importierten Release-Tags geprüft.
- Sicherungs-, Sonder- und nicht freigegebene Stände wurden nur im
  ausdrücklich freigegebenen Umfang übernommen.
- Alle Mandanten-Repositories verwenden laut zentraler Einrichtungsprüfung
  dieselbe unveränderliche, freigegebene Version der Automation; weitere
  Actions sind vollständig gepinnt.
- Rulesets, Environments, Tag-Betriebsregel, FI-Runner-Zuordnung und minimale
  Berechtigungen sind praktisch wirksam.
- Pushes nach Entwicklung und Abnahme synchronisieren genau den bestätigten
  Commit. Ein Push nach Bereitstellung erzeugt ohne Tag keine Lieferung.
- `.100` erzeugt FULL. Jeder importierte oder neu freigegebene DELTA-Tag besitzt
  `.100` als Vorgänger und erzeugt das kumulative DELTA gegen diese Basis.
- Irrtümliche Release-Kandidaten können vor der Freigabe kontrolliert
  zurückgenommen werden. Freigegebene Tags sind unveränderlich.
- Ressourcenbereitstellung, Wiederanlauf, Adapterantwort, Artefaktprüfung,
  JCL, konfigurierte ISPW-Instanz und unmittelbare Mainframe-Übergabe sind
  erfolgreich geprüft.
- Fachliche Verantwortliche haben den Zielstand in M/Text und den
  Mainframe-Endstatus bestätigt.
- Gleichzeitige Schreibvorgänge auf dasselbe Ziel werden verhindert. Läufe für
  unterschiedliche Mandanten können wie vorgesehen parallel arbeiten.
- Protokolle enthalten keine Secrets und alle erforderlichen Nachweise sind
  revisionssicher abgelegt.

Während des vereinbarten Beobachtungszeitraums werden fehlgeschlagene Läufe,
Wiederanläufe und Zielabweichungen durch die benannten Verantwortlichen
überwacht. Erst nach dessen erfolgreichem Abschluss werden Jenkins und SVN
gemäß Betriebskonzept endgültig stillgelegt und der Cutover formal geschlossen.
