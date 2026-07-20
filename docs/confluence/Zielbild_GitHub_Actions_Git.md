# Zielbild für die Ablösung von Jenkins und SVN

**Dokumenttyp:** Zielbild für Fachlichkeit und Technik

**Geltungsbereich:** Verteilung von M/Text-Ressourcen und Bereitstellung von
Mainframe-Lieferungen

Dieses Dokument beschreibt den künftigen Prozess mit Git und GitHub Actions.
Den Arbeitsstand zeigt [Nächste Schritte](./Naechste_Schritte.md), die Bedienung
die [Benutzeranleitung](./Benutzeranleitung.md). Die
[Soll-Grafik GitHub Actions/Git](../../Architektur_Soll_GitHub_Actions_Git.drawio)
stellt den Ablauf von einer Änderung bis zur M/Text-Verteilung oder
Mainframe-Übergabe dar. Die
[Ist-Grafik Jenkins/SVN](../../Architektur_Ist_Jenkins_SVN.drawio) dokumentiert
den bisherigen Prozess.

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in einer nichtproduktiven GitHub-Umgebung erprobt. Während
dieser Testphase bleibt der bisherige Prozess produktiv. Unmittelbar vor der
für Januar 2027 geplanten Produktivsetzung wird der dann freigegebene
SVN-Endstand nach Git übertragen. Danach sind Git und GitHub Actions für diesen
Prozess führend. Eine dauerhafte Synchronisation mit SVN gibt es nicht.

Jeder Mandant erhält ein eigenes Repository mit seinen M/Text-Ressourcen und
seiner Konfiguration. Die gemeinsame Automatisierung liegt im zentralen
Repository `mtext-actions`. So bleiben die Mandantendaten getrennt, während
alle Mandanten dieselben geprüften Abläufe verwenden.

Eine Änderung durchläuft weiterhin die drei Prozess-Stages Entwicklung,
Abnahme und Bereitstellung für die Freigabe und Lieferung.

Der generelle Ablauf ist:

1. Ein Push nach `Rnnn/Entwicklung` verteilt den Stand an das
   M/Text-Entwicklungssystem, zum Beispiel `en01e.ltoms.intern`.
2. Fachlich freigegebene Änderungen werden nach `Rnnn/Abnahme` übernommen und
   an das M/Text-Abnahmesystem verteilt, zum Beispiel `en01a.ltoms.intern`.
3. Abgenommene Änderungen werden nach `Rnnn/Bereitstellung` übernommen. Der
   Push allein erzeugt noch keine Mainframe-Lieferung.
4. Erst ein Release-Tag wie `R261.108` baut die Lieferung. Vor der technischen
   Übergabe an den Mainframe ist eine manuelle Freigabe erforderlich.

Der M/Text-Adapter (LTOMA) bleibt die zentrale Schnittstelle. Für die
Bereitstellung unter `serverSync` auf dem M/Text-Server muss noch ein
Transportweg festgelegt werden. Die Übergabe an die IZE9 beziehungsweise
CodePipeline erfolgt weiterhin per FTP und JES.

## 2. Verbindliche Rahmenbedingungen

- Der Wechsel von SVN/Jenkins zu Git/GitHub Actions findet zu einem festen
  Zeitpunkt statt. Danach gibt es keinen parallelen produktiven Lieferbetrieb.
- Das bisherige Jenkins-Skript wird nicht weiterentwickelt oder technisch
  portiert. Nur die weiterhin benötigten Regeln, Zuordnungen und
  Übergabeverfahren werden übernommen.
- Jeder Mandant erhält ein eigenes GitHub-Repository. Namen und grundsätzlicher
  Aufbau orientieren sich an den bisherigen Mandantenstrukturen. Darin befinden
  sich die M/Text (Fragment-)Projekte.
- Die CI/CD-Automatisierung wird durch die FI zentral in `mtext-actions`
  versioniert und von den Mandanten-Repositories verwendet.
- `mtext-actions` ist ein privates Repository. Direkten Zugriff erhalten nur
  die Prozess-Verantwortlichen der FI.

## 3. Was gleich bleibt und was sich ändert

Die neue Lösung übernimmt die fachlichen Abläufe und die von M/Text und dem
Mainframe erwarteten Ergebnisse. Sie übernimmt nicht die dafür verwendete
SVN- und Jenkins-interne Arbeitsweise. Programmatisch umgesetzte und durch
automatisierte Tests abgesicherte Verträge gelten in diesem Kapitel als
erfüllt. Davon getrennt werden nur Eigenschaften externer Systeme als offen
benannt, die der Code weder festlegen noch prüfen kann.

### Fachlich und extern sichtbar gleich

| Bereich | Unveränderter Vertrag |
|---|---|
| Stagefolge | Änderungen durchlaufen weiterhin `Entwicklung`, `Abnahme` und `Bereitstellung`. Nur fachlich ausgewählte Änderungen werden in die nächste Stage übernommen. |
| M/Text-Synchronisation | Entwicklung und Abnahme stellen die vorgesehenen vollständigen Projektstände unter `serverSync` bereit und rufen danach denselben M/Text-Adapter LTOMA auf. |
| Bereitstellung | Das Übernehmen eines Stands nach Bereitstellung erzeugt noch keine Mainframe-Lieferung. Erst ein bestätigter Release-Tag startet den Paketbau. |
| Release-Lieferart | Ein Release mit der Endung `.100` ist FULL. Andere gültige Release-Tags derselben Releaselinie sind kumulative DELTA-Lieferungen gegen `.100`. |
| FULL-Inhalt | Für jedes Projekt entstehen das vollständige F-Paket und ein zusätzliches leeres D-Paket mit leerem Projektverzeichnis und leerer Löschliste. |
| DELTA-Inhalt | Das D-Paket enthält alle seit `.100` neuen und geänderten Dateien sowie die seitdem gelöschten Pfade in der Löschliste. Es hängt nicht davon ab, ob frühere DELTA-Lieferungen lückenlos eingespielt wurden. |
| Informationsdatei | Die Informationsdatei dokumentiert weiterhin den direkten Vergleich zum vorherigen Release und die Inhaltsliste des fachlichen Pakets. Sie bestimmt nicht den kumulativen DELTA-Inhalt. Das bei FULL zusätzlich erzeugte leere D-Paket erhält keine eigene Informationsdatei. |
| Namen und Archivstruktur | Paketnamen, Mainframe-Member, Projektpfade, Löschlistennamen sowie die unterschiedlichen Pfadformen der F- und D-Archive bleiben erhalten. |
| Mandantenprojekte | Der derzeit gültige Projektbestand der Mandanten bleibt der fachliche Referenzstand. Abweichungen werden sichtbar gemacht, ohne technisch eine unveränderliche Projektstruktur vorzuschreiben. |
| Mainframe-Übergabe | Die Pakete werden weiterhin per FTP in das bestehende Dataset übertragen und durch JES zur Registrierung in CodePipeline übergeben. Die vorhandenen JCL-Werte und Mainframe-Ziele bleiben Teil des Vertrags. |

### Eindeutige Trennung der beiden bisherigen Begriffspaare

Das Jenkins-Skript verwendet `FULL` und `DELTA` für zwei voneinander
unabhängige Entscheidungen. Zur eindeutigen Unterscheidung heißen sie in diesem
Zielbild **Jenkins-Arbeitskopienmodus** und **Release-Lieferart**:

| Begriff | Gültiger Bereich | Bedeutung im Jenkins-Skript | Umsetzung mit GitHub Actions |
|---|---|---|---|
| Arbeitskopienmodus `UMFANG=FULL` | `ART=Entwicklung` oder `ART=Abnahme` | Alle vorgesehenen SVN-Arbeitskopien werden gelöscht und für dieselbe Revision neu ausgecheckt. | Kein eigener Modus. Jede Synchronisation veröffentlicht vollständige Projektstände aus einem frischen Git-Checkout. |
| Arbeitskopienmodus `UMFANG=DELTA` | `ART=Entwicklung` oder `ART=Abnahme` | Alle vorgesehenen SVN-Arbeitskopien werden mit `svn update` auf dieselbe Revision gebracht. Dies ist der übliche automatisch ausgelöste Lauf und keine inhaltliche DELTA-Lieferung. | Kein eigener Modus. Die SVN-spezifische Aktualisierung einer langlebigen Arbeitskopie entfällt. |
| Release-Lieferart `FULL` | `ART=Bereitstellung`, Tag endet auf `.100` | Vollständiges F-Paket und zusätzliches leeres D-Paket je Projekt. | Beide Pakete werden erzeugt und übergeben. |
| Release-Lieferart `DELTA` | `ART=Bereitstellung`, andere gültige Tag-Endung | Kumulatives D-Paket gegen den `.100`-Stand derselben Releaselinie. | Das kumulative D-Paket wird gegen den `.100`-Tag erzeugt. |

Beide Arbeitskopienmodi hinterlassen nach einem erfolgreichen Lauf den
vollständigen versionierten Stand derselben SVN-Revision. Der Unterschied
betrifft Checkout und Aktualisierung der SVN-Arbeitskopien, nicht den
fachlichen Projektumfang. Die neue Lösung benötigt diesen Modus nicht, weil
sie keine langlebigen Arbeitskopien führt.

Der bisherige FULL-Ablauf überschreibt neben dem F-Member auch den zugehörigen
D-Member mit dem leeren D-Paket. Dies spricht dafür, dass der DELTA-Stand einer
neuen Releaselinie damit zurückgesetzt oder initialisiert werden soll. Diese
fachliche Wirkung in CodePipeline ist nicht bestätigt. Unabhängig von ihrer
Bewertung bleibt die nachweisbare Übergabe beider Pakete erhalten.

### Technisch und betrieblich anders

| Bereich | Bisheriges Verfahren | Neue Lösung | Grund der Änderung |
|---|---|---|---|
| Versionsverwaltung und Automation | SVN und Jenkins sind die führenden Systeme. | Git und GitHub Actions sind nach dem Cutover führend. | Quellen, Prüfungen und ausgeführte Automation sollen gemeinsam versioniert und einem Commit eindeutig zugeordnet sein. |
| Repository- und Branchstruktur | Releaselinien und Stages liegen in der SVN-Verzeichnisstruktur. | Jeder Mandant besitzt ein Repository mit je drei Branches pro aktiver Releaselinie. | Releaselinie und Stage sind im Branchnamen eindeutig. Trigger und Zugriffsregeln lassen sich daran ausrichten. |
| Übernahme zwischen Stages | Änderungen werden mit dem bisherigen SVN-Verfahren weitergegeben. | Fachlich ausgewählte Änderungen werden per Cherry-Pick übernommen. Die Quell-SHA wird im neuen Commit dokumentiert. | Git erzeugt bei der Übernahme einen neuen Commit. Die dokumentierte Quell-SHA erhält die Nachvollziehbarkeit. |
| M/Text-Arbeitsstand | Langlebige SVN-Arbeitskopien werden normalerweise mit `svn update` fortgeschrieben und bei `UMFANG=FULL` neu angelegt. | Jeder Lauf verwendet einen frischen Git-Checkout und veröffentlicht den vollständigen Stand jedes verarbeiteten Projekts. | SVN-Locks, lokale Abweichungen und Reparaturpfade entfallen. Der ausgelieferte Commit ist eindeutig. |
| Projektstruktur | Der Jenkins-Ablauf ruft eine fest eingebaute Projektmatrix auf. | Alle sichtbaren und nicht ausgeschlossenen Projektverzeichnisse werden verarbeitet. Die aktuelle Matrix dient als Warnungsreferenz. | Fachlich abgestimmte Änderungen der Projektstruktur sollen keinen vorherigen Umbau einer technischen Allowlist erfordern. |
| Projektcode | Die bekannten Projektcodes stehen in den einzelnen Jenkins-Aufrufen. | Der Projektcode wird einheitlich aus dem Projektnamen abgeleitet und auf Eindeutigkeit geprüft. | Zusätzliche Projekte bleiben paketierbar. Mehrdeutige Mainframe-Member werden weiterhin verhindert. |
| Releasebau und Übergabe | Paketbau und Mainframe-Übergabe erfolgen im selben Jenkins-Ablauf über den gemeinsamen Arbeitsbereich und `/nfs/mtext/trans`. | Der Build erzeugt ein geprüftes GitHub-Artefakt mit Manifest und Prüfsummen. Ein getrennter Publish-Job übergibt genau dieses Artefakt. | Der freigegebene Inhalt bleibt zwischen Build und externer Wirkung unverändert und nachweisbar. |
| Freigabe | Der Jenkins-Ablauf übergibt die gebauten Pakete unmittelbar. | Vor FTP und JES ist eine manuelle Freigabe im Environment `Bereitstellung` erforderlich. | Die externe Mainframe-Wirkung erhält eine sichtbare und geschützte Freigabegrenze. |
| Wiederholung | Ein Wiederanlauf kann den Arbeitsbereich und die Pakete erneut erzeugen. | Der Publish-Job kann innerhalb desselben Laufs mit dem bereits geprüften Artefakt wiederholt werden. | Ein Übergabefehler soll keinen unbemerkten Neubau mit anderem Inhalt verursachen. |
| Zugangsdaten | Das Jenkins-Skript erzeugt zur Laufzeit ein Uploadskript mit eingesetzten Zugangsdaten. | Secrets stehen nur dem berechtigten Publish-Job über das GitHub Environment zur Verfügung und werden nicht in erzeugte Skripte geschrieben. | Zugangsdaten sollen weder in Arbeitsdateien noch in Protokolle gelangen. |
| Dateimetadaten | TAR-Metadaten stammen aus dem jeweiligen Jenkins-Arbeitsbereich. | Releasearchive erhalten reproduzierbare Besitzer-, Modus- und Zeitangaben. | Gleiche Quellen und Konfigurationen sollen bytegleiche und überprüfbare Archive ergeben. |
| Status und Prüfungen | Erfolg und Fehler ergeben sich hauptsächlich aus Jenkins-Schritten und externen Kommandos. | Fachliche Prüfungen liefern feste Statuswerte. Manifest, SHA-256 und Exitcodes sichern die Grenzen zwischen Quelle, Paket und Übergabe. | Fehler sollen eindeutig zugeordnet werden und vor einer externen Wirkung abbrechen. |

### Kompatibilitätsregeln für die Lieferdateien

- FULL- und DELTA-Pakete behalten ihre festgelegten Dateinamen. Der Projektcode
  wird aus dem Projektnamen abgeleitet. Mandantensuffix und Präfix `LOMS_`
  entfallen. Anschließend werden höchstens die ersten fünf Zeichen in
  Großschreibung verwendet.
- Ein D-Paket enthält weiterhin die nach dem CodePipeline-Element benannte
  Löschliste.
- Ressourcen behalten ihre fachlichen Projektpfade. Bei Fragmentprojekten
  gehört das Mandantenkürzel in eckigen Klammern zum Projektnamen, zum Beispiel
  `LOMS_Autonom[BY]`.
- Die vorhandenen Unterschiede in den Pfaden von F- und D-Archiven bleiben
  erhalten, damit bestehende Empfänger die Dateien weiterhin verarbeiten
  können.
- Zu jedem Projekt wird eine Informationsdatei für das F-Paket oder das
  reguläre D-Paket erzeugt. Das bei `.100` zusätzlich erzeugte leere
  D-Paket erhält keine eigene Informationsdatei.

### Extern noch zu klären

- Für den Transport nach `serverSync` ist noch eine der in Kapitel 4
  beschriebenen Varianten auszuwählen.
- Es ist nicht bekannt, ob der M/Text-Adapter `.svn`-Metadaten oder
  Dateizeitstempel auswertet. Diese externe Eigenschaft entscheidet, ob der
  vollständige Git-Projektstand ohne weitere Anpassung dieselbe fachliche
  Verarbeitung auslöst wie der bisherige SVN-Arbeitsstand.
- Die genaue fachliche Wirkung des bei FULL mit einem leeren Paket
  überschriebenen D-Members in CodePipeline ist nicht bestätigt.
- Für vollständig entfernte oder neu ausgeschlossene Projekte ist eine sichere
  Bereinigungsregel festzulegen, die keine Projektverzeichnisse anderer
  Mandanten-Repositories verändert.

Namen, Inhalt und Archivstruktur der Releasepakete sowie Manifest, JCL und
FTP-/JES-Eingaben sind dagegen im Programm umgesetzt und durch automatisierte
Tests abgesichert. Sie sind keine offene fachliche Lücke.

## 4. Zielarchitektur und Verantwortlichkeiten

Die Lösung besteht aus vier Bereichen:

| Bereich | Verantwortung |
|---|---|
| Mandanten-Repository | M/Text-Ressourcen, Mandantenkonfiguration und Workflow-Trigger |
| Automatisierungs-Repository `mtext-actions` | Prüfungen, Synchronisation, Paketbau und Mainframe-Übergabe |
| GitHub Actions | Ausführung der Abläufe, Freigaben und Protokollierung |
| GitHub-Actions-Runner (FI) | Ausführung der Workflows auf dem offiziell verfügbaren Runnerangebot der FI. Bereitstellung, Absicherung, Wartung und Bereinigung des Runnerangebots liegen außerhalb des Projekts |

Ein Mandanten-Repository enthält ausschließlich die Ressourcen und die für
GitHub relevante Konfiguration des jeweiligen Mandanten. Das zentrale
Automatisierungs-Repository `mtext-actions` enthält keine Mandantenressourcen,
sondern nur die gemeinsam verwendete Automatisierung.

Mandanten-Repositories dürfen die wiederverwendbaren Workflows über eine
GitHub-Actions-Zugriffsrichtlinie aufrufen. Die Logs der aufgerufenen Jobs sind
im Mandanten-Repository sichtbar und enthalten deshalb weder Secrets noch
unnötige interne Details.

Die Administratoren legen die Berechtigungsregeln für GitHub Actions fest.
GitHub erzeugt für jeden Job ein `GITHUB_TOKEN` mit den daraus resultierenden
Rechten.

Push-Rulesets schützen die Workflow-Trigger in den Mandanten-Repositories vor
ungewünschten Änderungen. Die Mandantenkonfiguration ist ebenfalls von der
normalen Ressourcenpflege getrennt. Die konkreten Rollen und Bypässe beschreibt
Kapitel 6.

Die Text-Entwickler bearbeiten Briefressourcen in der M/Text Workbench und
nutzen darüber hinaus ihren Git-Client für weitere Aktionen wie Cherry-Picking
oder das Erstellen von Release-Tags. GitHub im Browser dient für Laufkontrolle,
Wiederholungen, Freigaben und die Prüfung von Release-Tags. Für die tägliche
Arbeit ist keine Git-Kommandozeile nötig.

Jeder Mandant benennt ein Mandanten-Release-Team für den
Bereitstellungsbranch und die Release-Tags. Die Verantwortlichen können sich
je Mandant unterscheiden.
Schutzregeln für Branches, Pfade und Tags sind in Kapitel 6 festgelegt, der
Bedienablauf in Kapitel 7.

Für jeden Lauf checkt GitHub Actions sowohl den ausgewählten Stand des
Mandanten-Repositories als auch eine festgelegte `mtext-actions`-Version aus.
Dadurch ist später nachvollziehbar, welche Quellen und
welche Automatisierung tatsächlich verwendet wurden.

### M/Text-Transport nach `serverSync`

Der heutige Ablauf stellt die zu synchronisierenden Ressourcen zuerst über ein
NFS-Share unter `serverSync` bereit. Danach sendet er einen POST-Request an den
M/Text-Adapter (LTOMA), der die interne Synchronisation mit dem M/Text-Server
(LTOMS) anstößt. Dieser Ablauf ist die Ausgangslage. Der künftige Transportweg
ist noch nicht festgelegt.

Unabhängig vom Transportweg entsteht für jedes synchronisierte Projekt auf
`serverSync` derselbe vollständige Verzeichnisbaum mit denselben relativen
Pfaden, Dateinamen und Dateiinhalten wie im bisherigen Jenkins-/SVN-Verfahren.
Die Veröffentlichung erfolgt erst, nachdem der gesamte Projektstand erfolgreich
übertragen wurde. Dadurch verschwinden innerhalb eines weiterhin
synchronisierten Projekts auch in Git entfernte Dateien. Mehrere
Mandanten-Repositories teilen sich `serverSync`. Ein Lauf darf deshalb keine
fremden Projektverzeichnisse bereinigen. Wie ein vollständig entferntes oder
neu ausgeschlossenes zusätzliches Projekt sicher zugeordnet und entfernt wird,
wird mit dem Transport- und Betriebskonzept festgelegt. Transportdateien und
technische Metadaten gehören nicht in den von M/Text ausgewerteten Bestand.

Beispiel:

```text
serverSync/
  LOMS_Basis[BY]/
    <vollständiger Projektbaum>
  LOMS_Autonom[BY]/
    <vollständiger Projektbaum>
```

Es gibt keine zusätzliche Paketwurzel. Archiv, Manifest und andere
Transportdateien liegen nicht unter `serverSync`.

Für die Versorgung von `serverSync` werden drei mögliche Varianten geprüft:

| Variante | Ablauf und Verantwortung | Vor der Entscheidung zu klären | Aufwand |
|---|---|---|---|
| PUT an den Adapter | Der Runner überträgt die Ressourcendaten per PUT-Request an den Adapter. Der Adapter prüft die Übertragung, schreibt zunächst in einen temporären Bereich, veröffentlicht den vollständigen Stand nach `serverSync` und startet die interne Synchronisation. Der Runner benötigt keinen Sharezugriff. | HTTP-Vertrag, Authentifizierung, Größenlimits, Prüfsummen, Zeitgrenzen, Wiederholung, Parallelität und Erfolgsstatus | mittel bis hoch |
| Direkter Sharezugriff des Runners | Der Runner stellt den vollständigen Stand auf dem NFS-/Netzlaufwerk des M/Text-Servers bereit und ruft erst danach den Adapter auf. Staging, Veröffentlichung und Wiederanlauf liegen damit in der GitHub-Automatisierung. Diese Variante entspricht dem aktuellen Entwicklungsstand. | Verfügbarkeit und Einbindung des Shares, Pfad, Rechte, Kapazität, atomare Ersetzung, Schutz vor parallelen Schreibvorgängen und Bereinigung nach Fehlern | gering |
| Download aus dem Artefaktspeicher von GitHub Actions | Der Workflow speichert den für `serverSync` vorbereiteten Verzeichnisbaum als Artefakt seines GitHub-Actions-Laufs. Eine noch festzulegende Zielkomponente lädt den Stand herunter, prüft ihn und veröffentlicht ihn unter `serverSync`. Danach startet sie die interne Synchronisation. Die Releaseartefakte für die Mainframe-Lieferung entstehen unabhängig davon. | Zuständige Zielkomponente, eindeutige Identifikation durch Repository, Workflow-Lauf und Artefakt-ID, technische Identität mit `Actions: read`, Prüfsumme, Erreichbarkeit, Aufbewahrungsfrist, Wiederholung und Bereinigung | mittel |

Vor dem nichtproduktiven Integrationslauf wird genau eine Variante ausgewählt.
Die Entscheidung berücksichtigt Netzwerk- und Sicherheitsvorgaben,
Betriebsverantwortung, Datenmengen und Laufzeiten, atomare Veröffentlichung,
Parallelität, Wiederanlauf und Nachvollziehbarkeit. Implementiert wird nur der
ausgewählte Weg.

Die Lösung ändert nicht die nachgelagerte Verarbeitung auf dem
Mainframe-Zielsystem IZE9. Sie übernimmt den dafür benötigten Übergabevertrag.

## 5. Repositories und aktueller Entwicklungsstand

Ein Mandanten-Repository folgt diesem Grundaufbau:

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

Das zentrale Repository enthält die wiederverwendbaren Workflows, die
gemeinsame Python-Anwendung, die zentrale Releaselinienzuordnung, das
JCL-Template und die automatisierten Akzeptanztests:

```text
mtext-actions/
  .github/
    workflows/
  config/
    releaselinien.json
  scripts/
    runner-preflight.sh
  src/lbs_delivery/
    cli.py
    config.py
    errors.py
    git.py
    mainframe.py
    manifest.py
    release.py
    sync.py
  templates/
    mainframe-upload.jcl
  tests/
```

Die Module folgen den fachlichen Abläufen. `sync.py` enthält Staging,
`serverSync` und Adapteraufruf. `mainframe.py` enthält JCL und FTP/JES.
Pfad- und Wertprüfungen stehen direkt an der jeweils zuständigen Eingangs-
oder Systemgrenze. Intern erzeugte Werte werden nicht in weiteren Schichten
erneut validiert. `runner-preflight.sh` ist der Einstiegspunkt in die
Python-Automatisierung.

`mtext-fi` dient als Muster für die Mandanten-Repositories. Alle sichtbaren
Verzeichnisse in der Repositorywurzel werden synchronisiert und in
Releasepakete aufgenommen. `LOMS_Testdaten` soll ebenfalls in das Repository
übernommen werden, ist aber über `excluded_projects` in `.github/config.json`
von der Synchronisation und den Releasepaketen ausgeschlossen.

Im Mandanten-Repository stehen nur kleine Trigger-Workflows. Sie legen fest,
wann eine Automatisierung startet und welches GitHub Environment sie verwendet. Die
eigentlichen Arbeitsschritte liegen im Repository `mtext-actions`. Bei der
Einrichtung (und bei späteren Updates) informiert ein besonderer Workflow die
Trigger-Workflows darüber, welche Version von `mtext-actions` zu verwenden
ist.

Im Zielbetrieb werden die Mandanten-Repositories und `mtext-actions` als
eigenständige GitHub-Repositories geführt. Die Mandanten-Repositories
`mtext-autonom`, `mtext-by`, `mtext-lh`, `mtext-nw`, `mtext-os` und `mtext-sa`
folgen demselben Muster wie `mtext-fi`. Repository-Owner und ergänzende
Repositories werden erst dokumentiert, wenn sie fachlich bestätigt sind.

Vor dem ersten Integrationslauf werden Runner-Kennzeichen und zentrale
Workflowversion finalisiert. Die noch ausstehenden Einrichtungs- und
Abnahmepunkte stehen in [Nächste Schritte](./Naechste_Schritte.md).

## 6. GitHub-Konfiguration

Für Planung und Abnahme ist GitHub Enterprise Server 3.20.4 als Zielplattform
festgelegt. Die folgenden Einstellungen definieren den gewünschten
Zielzustand.

### Repositories und Zugriffe

| Gegenstand | Zielzustand |
|---|---|
| Mandanten-Repositories | Für jeden Mandanten besteht ein eigenes privates Repository. |
| Zentrales Repository | `mtext-actions` ist privat und nur für das zentrale Automatisierungsteam direkt zugänglich. |
| Default Branch | Der Entwicklungsbranch der führenden Releaselinie – zunächst `R261/Entwicklung` – wird beim Wechsel der führenden Linie angepasst. |
| Technischer Konfigurationskreis | Der benannte Verantwortlichenkreis, der die Mandantenkonfiguration in `.github/config.json` ändern darf. |
| Mandanten-Release-Team | Der benannte Verantwortlichenkreis, der nach `Rnnn/Bereitstellung` pushen sowie Release-Tags anlegen darf. |

### Schutzregeln für Branches, Pfade und Tags

| Schutzbereich | Regel |
|---|---|
| `Rnnn/Entwicklung` und `Rnnn/Abnahme` | Berechtigte Text-Entwickler dürfen pushen. Force-Pushes und das Löschen der Branches sind gesperrt. |
| `Rnnn/Bereitstellung` | Reguläre Pushes sind auf das Mandanten-Release-Team begrenzt. Force-Pushes und das Löschen des Branches sind gesperrt. |
| `.github/workflows/**/*` | Ein Push-Ruleset schützt die zentral vorgegebenen Aufrufdateien auf allen Branches. |
| `.github/config.json` | Eine Pfadregel trennt Änderungen der Mandantenkonfiguration von der normalen Ressourcenpflege. |
| Tags `Rnnn.nnn` | Nur das Mandanten-Release-Team darf passende Tags erstellen oder löschen. |

Das Pushen eines Release-Tags startet den Release-Workflow. Wurde der Tag
irrtümlich angelegt, bricht das Mandanten-Release-Team deshalb zuerst den
zugehörigen Workflow-Lauf ab, löscht den Tag und legt bei Bedarf den richtigen
Tag neu an.
Für die Übergabe an CodePipeline ist eine manuelle Freigabe im Environment
`Bereitstellung` notwendig.

### Environments und Secrets

Ein GitHub Environment bildet eine Zielstufe ab und enthält alle dafür geltenden
Schutzregeln, etwa zulässige Branches oder Tags und erforderliche Freigaben.
Seine Secrets stehen ausschließlich Jobs zur Verfügung, die an dieses Environment
gebunden sind und dessen Schutzregeln erfüllen.

| Environment | Verwendung und Schutz |
|---|---|
| `Einrichtung` | Wird ausschließlich vom manuell gestarteten Einrichtungsworkflow in `mtext-actions` gebunden. Es stellt nach Freigabe das auf die vorgesehenen Repositories begrenzte technische Token für die Workflowänderungen bereit. |
| `Entwicklung` | Wird ausschließlich vom Sync-Job für den Entwicklungsbranch gebunden. Eine manuelle Freigabe und stufenspezifische Environment-Secrets sind dafür nicht vorgesehen. |
| `Abnahme` | Wird ausschließlich vom Sync-Job für den Abnahmebranch gebunden. Eine manuelle Freigabe und stufenspezifische Environment-Secrets sind dafür nicht vorgesehen. |
| `Bereitstellung` | Wird ausschließlich vom Publish-Job gebunden. Eine berechtigte Person muss die Mainframe-Übergabe manuell freigeben. Ein verpflichtendes Vier-Augen-Prinzip oder eine Sperre der Selbstfreigabe ist nicht vorgesehen. Nur zulässige Release-Tags dürfen dieses Environment verwenden. |

Die Mainframe-Zugangsdaten `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und
`MAINFRAME_FTP_PASSWORD` liegen ausschließlich als Secrets im Environment
`Bereitstellung`. Sie werden weder in Git gespeichert noch an den Build-Job
übergeben.

### GitHub Actions und Ausführung

Nach abgeschlossener Einrichtung gelten für die Ausführung der Workflows die
folgenden technischen Festlegungen:

| Gegenstand | Ergebnis der Einrichtung |
|---|---|
| Zentrale Workflowversion | Jeder Aufruf verwendet die für seinen Rollout festgelegte Version von `mtext-actions`. |
| Actions-Zugriff | Die Mandanten-Repositories dürfen die wiederverwendbaren Workflows aus `mtext-actions` aufrufen. |
| Einrichtungsberechtigung | Der Einrichtungsworkflow erhält über das Environment `Einrichtung` das Secret `WORKFLOW_CONFIGURATION_TOKEN`. |
| Runnerangebot der FI | Die Jobs verwenden einen offiziell von der FI bereitgestellten GitHub-Actions-Runner. Das zugehörige `runs-on`-Kennzeichen wird aus dem Runnerangebot der FI übernommen und in den zentralen Workflows fest eingetragen. |
| Laufzeitvorbereitung | `runner-preflight.sh` ist der gemeinsame Einstieg in die Python-Automatisierung. Es setzt die versionierte Laufzeitvorgabe aus `.python-version` durch und stellt den verwendeten Python-Pfad den folgenden Schritten bereit. Dadurch laufen alle Workflows mit derselben technischen Voraussetzung. |
| Logs | Ausgaben wiederverwendbarer Workflows sind im Mandanten-Repository sichtbar. |
| Artefakte | Releaseartefakte werden standardmäßig 30 Tage aufbewahrt. Ihre Namen enthalten Repository und Release-Tag. |

### Reproduzierbare Einrichtung und Aktualisierung

Der manuelle Workflow **Configure workflow files** wird genutzt um die
Workflow-Trigger eines Mandanten initial zu verdrahten und bei Updates von
`mtext-actions` aktuell zu halten. Dadurch wird für jeden Mandantenbranch
eindeutig festgelegt, welche Version der Automatisierung er verwendet.

Vor dem ersten Lauf werden der Runner der FI, dessen Repositoryvariable
`FI_RUNNER_LABEL` sowie das Environment `Einrichtung` mit dem Secret
`WORKFLOW_CONFIGURATION_TOKEN` bereitgestellt. Der Workflow wird in GitHub mit
drei Angaben gestartet:

- Commit-SHA der freigegebenen `mtext-actions`-Version,
- Name des zu pflegenden Mandanten-Repositories,
- zu aktualisierender Mandantenbranch.

Ein Lauf bearbeitet genau diesen einen Mandantenbranch:

1. Er checkt die angegebene `mtext-actions`-SHA und den Mandantenbranch aus und
   validiert beide Workflowdateisätze vor der ersten Änderung.
2. Er bindet Workflowaufruf und Python-Checkout des Mandanten gemeinsam an
   dieselbe `mtext-actions`-SHA.
3. Er zeigt die Änderungen im Workflow-Log und prüft, dass der Zielzustand
   vollständig erreicht ist.
4. Erst danach pusht er die geprüften Commits. Der Mandanten-Commit ändert nur
   `.github/workflows` und löst wegen seiner Skip-Anweisung keine
   M/Text-Synchronisation oder Releaseverarbeitung aus.

Bei der erstmaligen Einrichtung kann das feste Runner-Kennzeichen in
`mtext-actions` noch fehlen. Dann erzeugt der Lauf einmalig den dafür nötigen
Commit und verwendet dessen ausgewiesene SHA unmittelbar für den
Mandanten-Commit und alle weiteren Rollout-Ziele. Spätere Versionen enthalten
das Runner-Kennzeichen bereits und benötigen keinen zusätzlichen Commit in
`mtext-actions`.

## 7. Branches, Weitergabe und Auslöser

Jede aktive Releaselinie besitzt drei Branches, zum Beispiel:

```text
R261/Entwicklung
R261/Abnahme
R261/Bereitstellung
```

Damit ist aus jedem Branchnamen eindeutig erkennbar, zu welcher Releaselinie
und Stage er gehört. Ein gemeinsamer Branch je Stage mit mehreren
Releaseverzeichnissen, wie er in SVN verwendet wurde, wird nicht fortgeführt.

Für größere oder gemeinsam bearbeitete Änderungen kann ein Feature-Branch
verwendet werden. Er löst keine Verteilung aus. Kleine Änderungen dürfen auch
direkt auf dem Entwicklungsbranch entstehen. Ein Feature-Branch ist keine
zusätzliche Stage des Freigabeprozesses.

Ein Push nach `Rnnn/Entwicklung` oder `Rnnn/Abnahme` startet automatisch die
M/Text-Verteilung für die entsprechende Stage. Beim Übergang zur nächsten
Stage wird eine fachlich ausgewählte Änderung per Cherry-Pick übernommen. Der
Cherry-Pick erzeugt auf dem Zielbranch einen neuen Commit mit einer neuen SHA.
Weitergegeben wird dieselbe Änderung, nicht derselbe Commit. Die
vollständige Quell-SHA wird nach einer verbindlichen Konvention im neuen
Ziel-Commit dokumentiert. Ob die Releaselinie fachlich eingerichtet ist,
entscheidet die zentrale Releaselinienzuordnung.

Ein Push nach `Rnnn/Bereitstellung` erzeugt noch keine Lieferung. Erst ein Tag
im Format `Rnnn.nnn` startet den Paketbau. Dabei wird geprüft, ob der Tag zur
angegebenen Releaselinie gehört und vom Bereitstellungsbranch erreichbar ist.
Der Tag wird als Git-Tag mit dem freigegebenen zusätzlichen Git-Client angelegt
und einzeln gepusht. Ein GitHub Release wird nicht erzeugt. Wurde ein Tag
irrtümlich angelegt, wird der dadurch gestartete Workflow-Lauf vor dem Löschen
oder Korrigieren des Tags abgebrochen. Die spätere manuelle Freigabe betrifft
ausschließlich die Mainframe-Übergabe.

Der zusätzliche Git-Client für die Auswahl und Übernahme einzelner Änderungen
in Abnahme und Bereitstellung wird vor dem Pilotbetrieb ausgewählt,
bereitgestellt und praktisch abgenommen. Ein direkter Cherry-Pick ist über die
GitHub-Weboberfläche allein nicht verfügbar.

Die Mandanten-Repositories erhalten keinen zusätzlichen `main`-Branch. Als
Default Branch dient der Entwicklungsbranch der aktuell führenden Linie,
zunächst `R261/Entwicklung`. Beim Wechsel der führenden Linie aktualisiert die
Einrichtungsautomation diese Einstellung.

Manuelle Wiederholungen eines Workflows sind möglich, müssen aber denselben
Commit verwenden. Vor einer erneuten M/Text-Verteilung prüft der Workflow, ob
dieser Commit zum ausgewählten Branch gehört.

### Neue Releaselinie einrichten

Eine neue Linie erhält drei Branches, je einen für Entwicklung, Abnahme und
Bereitstellung, sowie einen Eintrag in
[`config/releaselinien.json`](../../mtext-actions/config/releaselinien.json).
(siehe [Zentrale Releaselinienzuordnung](#zentrale-releaselinienzuordnung)).
Der Eintrag enthält die fachliche Releaselinie, die technische ETAPS-Linie
und den Namen eines in `.github/config.json` vorhandenen Hostprofils. Die
JCL-Werte stammen aus der Mandantenkonfiguration und dem zugeordneten
Hostprofil. Die Zuordnung wird rollierend gepflegt: Beim Aufnehmen einer neuen
Releaselinie wird die ausgeschiedene Zuordnung entfernt, sodass immer drei
aktive Releaselinien enthalten sind.

Ausgangspunkt der neuen Branches ist normalerweise der letzte Release-Tag der
bisherigen Linie. Dessen vollständiger Projektstand wird über den manuellen
Sync-Workflow einmal nach Entwicklung und einmal nach Abnahme übertragen und
anschließend in M/Text fachlich geprüft.

## 8. Workflows, Trigger und Abhängigkeiten

Die Mandanten-Repositories enthalten nur die fachlichen Auslöser. Sie rufen
fest gepinnte wiederverwendbare Workflows aus `mtext-actions` auf. Die
eigentliche Fachlogik liegt in Python.

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Trigger-Workflow | Zentraler Workflow | Python-Kommando | Ergebnis |
|---|---|---|---|---|---|
| Workflowdateien einrichten oder `mtext-actions`-Version ausrollen | Manueller Start in `mtext-actions` mit freigegebener vollständiger SHA | keiner | `configure-workflows.yml` | `python -m workflow_configuration` | Zentrale Runnerwerte und Mandanten-Pins auf die gewählte Version geprüft und festgeschrieben |
| Mandantenkonfiguration prüfen | Push mit Änderung an `.github/config.json` auf einen Branch | `validate-config.yml` | `reusable-validate-config.yml` | `validate-config` | Konfiguration geprüft |
| Entwicklung synchronisieren | Push nach `Rnnn/Entwicklung` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync-resources` | Vollständiger Projektstand des Ziel-Commits nach M/Text-Entwicklung synchronisiert |
| Abnahme synchronisieren | Push eines per Cherry-Pick übernommenen Commits nach `Rnnn/Abnahme` oder manueller Start | `sync-resources.yml` | `reusable-sync-resources.yml` | `sync-resources` | Vollständiger Projektstand des Ziel-Commits nach M/Text-Abnahme synchronisiert |
| Bereitstellungsstand fortschreiben | Cherry-Pick und Push nach `Rnnn/Bereitstellung` | keiner | keiner | keines | Nur Git-Branch fortgeschrieben. Noch keine Lieferung |
| Release bauen und übergeben | Push eines Tags `Rnnn.nnn` oder manueller Start mit vorhandenem Tag | `release.yml` | `reusable-release.yml` | `build-release`, danach `publish-mainframe` | FULL/DELTA gebaut, geprüft und nach Freigabe per FTP/JES übergeben |
| `mtext-actions` testen | Pull Request in `mtext-actions` oder Push auf dessen `main` | entfällt | `ci.yml` | `unittest discover` | Zentrale Testfälle und Workflowverträge geprüft |

Die fachlichen Workflows verarbeiten den Stand, den die Benutzer auf dem
jeweiligen Branch hergestellt haben. Sie schreiben keine Commits, Branches oder
Tags. Ausschließlich der getrennte Einrichtungsworkflow schreibt die von ihm
vollständig geprüften technischen Workflowänderungen fest.

### Trigger in den Mandanten-Repositories

| Ereignis | Konfigurationsprüfung | Sync Entwicklung | Sync Abnahme | Release |
|---|---:|---:|---:|---:|
| Push auf einen Branch ohne Änderung an `.github/config.json` | nein | nur nach `Rnnn/Entwicklung` | nur nach `Rnnn/Abnahme` | nein |
| Push auf einen Branch mit Änderung an `.github/config.json` | ja | nur nach `Rnnn/Entwicklung` | nur nach `Rnnn/Abnahme` | nein |
| Push eines Tags `Rnnn.nnn` | nein | nein | nein | ja |
| Manueller Sync eines Ziel-Commits aus `Rnnn/Entwicklung` | nein | ja | nein | nein |
| Manueller Sync eines Ziel-Commits aus `Rnnn/Abnahme` | nein | nein | ja | nein |
| Manueller Release-Start mit vorhandenem Tag `Rnnn.nnn` | nein | nein | nein | ja |
| Pull Request im Mandanten-Repository | nein | nein | nein | nein |

Der Sync-Workflow besitzt keinen Pfadfilter. Jeder Push nach Entwicklung oder
Abnahme startet daher die vollständige Ressourcensynchronisation. Dabei werden
die sichtbaren, nicht unter `excluded_projects` genannten Projektverzeichnisse
übertragen.

Die Synchronisation wartet nicht auf den Abschluss der separaten
Konfigurationsprüfung. Wenn ein Push nach Entwicklung oder Abnahme zugleich
`.github/config.json` ändert, können beide Abläufe unabhängig voneinander laufen.
Synchronisation und Release-Erstellung prüfen die verwendete Konfiguration vor
dem Zugriff auf externe Systeme erneut.

### Mandantenseitige Trigger-Workflows

| Datei | Automatischer Trigger | Manueller Trigger | Abhängigkeit und Zweck |
|---|---|---|---|
| [`validate-config.yml`](../../mtext-fi/.github/workflows/validate-config.yml) | Push mit Änderung an `.github/config.json` auf einen Branch | keiner | Ruft `reusable-validate-config.yml` zur Prüfung der Mandantenkonfiguration auf |
| [`sync-resources.yml`](../../mtext-fi/.github/workflows/sync-resources.yml) | Push nach `Rnnn/Entwicklung` oder `Rnnn/Abnahme` | `workflow_dispatch` mit vollständiger `commit_sha` und zugehörigem `source_branch` | Ruft abhängig von der Branchendung `reusable-sync-resources.yml` mit festem GitHub Environment `Entwicklung` oder `Abnahme` auf |
| [`release.yml`](../../mtext-fi/.github/workflows/release.yml) | Push eines Tags `Rnnn.nnn` | `workflow_dispatch` mit vorhandenem `release_tag` | Ruft `reusable-release.yml` auf. Ein Push nach Bereitstellung allein ist kein Auslöser |

### Zentrale YAML-Workflows

| Datei | Trigger | Jobs und Abhängigkeiten | Implementierung und Wirkung |
|---|---|---|---|
| [`configure-workflows.yml`](../../mtext-actions/.github/workflows/configure-workflows.yml) | Manueller Start über `workflow_dispatch` in `mtext-actions` mit vollständiger freigegebener SHA | Exakten `mtext-actions`-Stand und gewählten Mandantenbranch auschecken → erforderliche Commits vorbereiten → leeren Zielzustand erzwingen → Diffs anzeigen → gegebenenfalls einmaligen zentralen Runner-Commit und anschließend den Mandanten-Commit pushen | Python-Implementierung in `mtext-actions`. Bindet das Environment `Einrichtung`, führt keinen Mandantencode aus und verwendet dessen begrenztes technisches Token ausschließlich für die Workflowdateien. |
| [`reusable-validate-config.yml`](../../mtext-actions/.github/workflows/reusable-validate-config.yml) | `workflow_call` | Mandanten-Commit auschecken → `mtext-actions` auschecken → Laufzeit vorbereiten → prüfen | `validate-config` |
| [`reusable-sync-resources.yml`](../../mtext-actions/.github/workflows/reusable-sync-resources.yml) | `workflow_call` | Exakten Mandanten-Commit mit vollständiger Historie auschecken → `mtext-actions` auschecken → Laufzeit vorbereiten → synchronisieren | `sync-resources --execute`. Stellt den vollständigen Zielstand nach dem festgelegten Transportvertrag unter `serverSync` bereit und startet die interne Synchronisation über den M/Text-Adapter |
| [`reusable-release.yml`](../../mtext-actions/.github/workflows/reusable-release.yml) | `workflow_call` | Job `build` erzeugt das Artefakt. Job `publish` hat `needs: build`, lädt genau dieses Artefakt und bindet das Environment `Bereitstellung` | `build-release`, danach `publish-mainframe --execute`. Übergabe per FTP/JES nach Freigabe |
| [`ci.yml`](../../mtext-actions/.github/workflows/ci.yml) | Pull Request oder Push auf `main` in `mtext-actions` | Repository auschecken → Laufzeit vorbereiten → Akzeptanztests ausführen | `python -m unittest discover -s tests -v` |

Die wiederverwendbaren Fachworkflows sind nur über `workflow_call` erreichbar.
Ihre Jobs und der zentrale Testjob verwenden das fest eingetragene
`runs-on`-Kennzeichen des ausgewählten Runnerangebots der FI. Nur der manuell
gestartete Einrichtungsworkflow liest dieses Kennzeichen aus der zuvor
eingerichteten Repositoryvariable `FI_RUNNER_LABEL`, weil er die festen Werte
erst in die übrigen zentralen Workflowdateien einträgt.

### Python-Programme und -Kommandos

| Kommando | Aufgerufen durch | Wesentliche Prüfungen und Abhängigkeiten | Ergebnis |
|---|---|---|---|
| `python -m workflow_configuration` | `configure-workflows.yml` | Zentraler Checkout entspricht der freigegebenen `mtext-actions`-SHA. Bestätigtes Runner-Kennzeichen. Vollständige Workflow- und Codebezüge. Diffs sind fehlerfrei und die abschließende Einrichtungsprüfung ist leer | Geprüfte lokale Workflow-Commits für `mtext-actions` und den Mandantenbranch. Der Workflow pusht sie anschließend in der erforderlichen Reihenfolge |
| `validate-config` | `reusable-validate-config.yml` | Bekanntes Mandantenkürzel, Repositoryidentität, gültige CodePipeline-Stage-Codes, eindeutige Projektcodes und vorhandene Hostprofile der Releaselinien | Status `CONFIG_VALIDATED` |
| `sync-resources` | `reusable-sync-resources.yml` | Branch und Environment stimmen überein. Vollständige SHA. Checkout entspricht SHA. Commit ist aus dem Remote-Branch erreichbar. Projektbäume enthalten keine Symlinks | Vollständiger Projektstand nach `serverSync`, Adapteraufruf gemäß Transportvertrag, Status `ADAPTER_ACCEPTED` |
| `build-release` | Job `build` in `reusable-release.yml` | Tagformat und konfigurierte Releaselinie. Tag aus Bereitstellungsbranch erreichbar. Checkout entspricht Tag-SHA. DELTA-Basis `.100`. Projektbäume enthalten keine Symlinks | Reproduzierbare FULL-/DELTA-Archive, Informationsdateien und `manifest.json` mit SHA-256. Status `ARTIFACT_READY` |
| `publish-mainframe` | Job `publish` in `reusable-release.yml` | Artefaktpfade, Dateigrößen und SHA-256 aus dem Manifest. JCL-Werte beim Rendern. FTP-Secrets vor der Übergabe | JCL je Paket, FTP-Übertragung und Übergabe an JES. Status `MAINFRAME_SUBMITTED` |

Die vier fachlichen Kommandos werden über
[`__main__.py`](../../mtext-actions/src/lbs_delivery/__main__.py)
und
[`cli.py`](../../mtext-actions/src/lbs_delivery/cli.py) gestartet. Die CLI übersetzt
fachliche Fehler in stabile Statuswerte und Prozess-Exitcodes. Ein von null
verschiedener Exitcode lässt den jeweiligen GitHub-Job fehlschlagen. Der
Einrichtungsworkflow startet dagegen das getrennte Modul
[`workflow_configuration.py`](../../mtext-actions/src/workflow_configuration.py)
direkt mit `python -m workflow_configuration`.

### Environments, Secrets und Serialisierung

| Bereich | Umsetzung |
|---|---|
| Entwicklung und Abnahme | Der Sync-Job bindet das fest gewählte Environment. Derzeit werden dort keine Secrets gelesen. |
| Bereitstellung | Nur der Publish-Job bindet dieses Environment. Die manuelle Freigabe wird in GitHub konfiguriert. |
| Mainframe-Secrets | Ausschließlich `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD` im Publish-Job |
| Sync-Serialisierung | Concurrency-Gruppe je Repository und Branch. Ein laufender Sync wird nicht aktiv abgebrochen. |
| Release-Serialisierung | Je Repository und Tag. Die Mainframe-Übergabe wird zusätzlich je Mandanten-Repository serialisiert. |
| Build-Publish-Grenze | Publish lädt genau das vom Build benannte Artefakt und vergleicht unmittelbar vor der externen Wirkung Pfad, Größe und SHA-256 jeder manifestierten Datei. |

## 9. Konfiguration

Die Datei `.github/config.json` ist ein versionierter Bestandteil des
Lieferstands und enthält genau einen `mandant`-Block. Dessen Felder haben einen
klar abgegrenzten Zweck:

| Feld | Bedeutung und Regel |
|---|---|
| `kuerzel` | Bekanntes Mandantenkürzel für Paketnamen und Fragmentprojekte |
| `repository` | Exakter Name des zugehörigen Mandanten-Repositories |
| `ispw` | Mandantenspezifische ISPW-Instanz `T` oder `P` |
| `subsystem` | Mainframe-Subsystem für JCL und CodePipeline |
| `excluded_projects` | Optionale Liste sichtbarer Projektverzeichnisse, die weder synchronisiert noch paketiert werden |
| `hostprofile` | Ein oder mehrere frei benannte Hostprofile mit `assignment` und `stage`. `stage` ist einer der CodePipeline-Stage-Codes `FKTE`, `FKTF`, `JURJ`, `JURP`, `SVTS` oder `VPTV` |

Alle anderen sichtbaren Verzeichnisse direkt unter der Repositorywurzel werden
als Projekte synchronisiert und paketiert. Versteckte Verzeichnisse werden
ignoriert. Die bestehende JCL verwendet `stage` als CodePipeline-`LEVEL`. Ein
zusätzlicher Levelwert wird nicht eingeführt. Fachlich bestätigte Änderungen
der Mandantenzuordnung werden mit der Konfiguration versioniert. Zugangsdaten
gehören nicht in diese Datei.

Der aktuelle Referenzstand der verarbeiteten Projekte lautet:

| Repository | Mandantenkürzel | Projekte |
|---|---|---|
| `mtext-fi` | `FI` | `Configuration`, `Fonts`, `LOMS_Framework`, `LOMS_Basis`, `LOMS_PKA` |
| `mtext-autonom` | `IT` | `LOMS_Autonom` |
| `mtext-by` | `BY` | `LOMS_Basis[BY]`, `LOMS_Autonom[BY]` |
| `mtext-lh` | `LH` | `LOMS_Basis[LH]`, `LOMS_Autonom[LH]` |
| `mtext-nw` | `NW` | `LOMS_Basis[NW]`, `LOMS_Autonom[NW]` |
| `mtext-os` | `OS` | `LOMS_Basis[OS]`, `LOMS_Autonom[OS]` |
| `mtext-sa` | `SA` | `LOMS_Basis[SA]`, `LOMS_Autonom[SA]` |

Diese Matrix dokumentiert den aktuellen fachlichen Stand, schreibt den
Lieferumfang aber technisch nicht fest. Zusätzliche Projekte und ein
abweichender Repositoryinhalt bleiben verarbeitbar. Die Konfigurationsprüfung
weist mit einer Warnung auf ein abweichendes Mandantenkürzel sowie fehlende
oder zusätzliche Projekte hin und beendet den Lauf deswegen nicht mit einem
Fehler.
Testdatenprojekte werden nach Git übernommen, aber üblicherweise über
`excluded_projects` von Synchronisation und Lieferung ausgeschlossen.

### Zentrale Releaselinienzuordnung

Die zentrale Datei `config/releaselinien.json` enthält rollierend die Zuordnung
von drei aktiven fachlichen Releaselinien zur jeweiligen technischen
ETAPS-Linie und dem zugehörigen Hostprofil. Ihr aktueller Inhalt ist:

```json
{
  "R260": {"etaps_linie": "en03", "hostprofil": "JUR"},
  "R261": {"etaps_linie": "en01", "hostprofil": "FKT"},
  "R270": {"etaps_linie": "en02", "hostprofil": "JUR"}
}
```

Vor einer Verteilung oder Lieferung wird die gesamte benötigte Konfiguration
geprüft. Unbekannte Mandanten, Releaselinien, Zielumgebungen oder zusätzliche
Konfigurationsfelder führen zu einem Fehler. Abweichungen vom aktuellen
Projekt-Referenzstand erzeugen ausschließlich Warnungen.

## 10. Release-Lieferarten FULL und DELTA

Ein Tag mit der Endung `.100`, zum Beispiel `R261.100`, erzeugt für jedes
sichtbare, nicht ausgeschlossene Projekt ein vollständiges F-Paket und ein
zusätzliches leeres D-Paket. Das D-Paket enthält nur das leere
Projektverzeichnis und eine leere Löschliste. Das bisherige Jenkins-Skript
erzeugt und übergibt bei FULL ebenfalls beide Pakete.

Jeder andere gültige Release-Tag derselben Releaselinie erzeugt ein
kumulatives DELTA gegen den `.100`-Tag. Ein Tag `R261.108` enthält somit alle
neuen, geänderten und gelöschten Dateien seit `R261.100`. Frühere
DELTA-Lieferungen müssen nicht lückenlos eingespielt worden sein.
Die `.100`-Basis muss in der Git-Historie ein Vorgänger des Ziel-Tags sein.
Git bestimmt die geänderten, neuen, gelöschten und umbenannten Pfade mit
`git diff`. Python erzeugt daraus das historisch kompatible TAR-Archiv, die
Löschliste und die Informationsdatei mit reproduzierbaren Dateimetadaten.

### CodePipeline-Elemente

Bei einer DELTA-Lieferung entsteht für jedes ausgelieferte Projekt ein
D-Element. Bei einer FULL-Lieferung entstehen ein F-Element mit dem
vollständigen Projektstand und zusätzlich ein leeres D-Element.
Der Elementname ist zugleich der Mainframe-Member und setzt sich aus
Mandantenkürzel, abgeleitetem Projektcode und Elementart zusammen.

```text
<Mandantenkürzel><Projektcode><F|D>
```

Beispielsweise bezeichnet `BYAUTOND` das DELTA-Element für `LOMS_Autonom[BY]`.
Eine FULL-Lieferung von `LOMS_Basis` der FI erzeugt `FIBASISF` mit dem
vollständigen Projektstand sowie ein leeres `FIBASISD`.

| Projekt | Abgeleiteter Projektcode |
|---|---|
| `Configuration` | `CONFI` |
| `Fonts` | `FONTS` |
| `LOMS_Framework` | `FRAME` |
| `LOMS_Basis` | `BASIS` |
| `LOMS_PKA` | `PKA` |
| `LOMS_Autonom` | `AUTON` |

Der Projektcode entsteht, indem ein vorhandenes Mandantensuffix und das Präfix
`LOMS_` entfernt und anschließend höchstens die ersten fünf Zeichen in
Großschreibung verwendet werden. Zwei Projekte desselben Repositorys dürfen
nicht denselben Projektcode ergeben. Ein F-Element enthält den vollständigen
Projektbaum. Ein reguläres D-Element enthält die kumulativ seit `.100` neuen und
geänderten Dateien sowie die Löschliste. Das beim FULL zusätzlich erzeugte
D-Element enthält ein leeres Projektverzeichnis und eine leere Löschliste. Die
`_INFO_...txt` gehört zum Releasebeleg, wird aber nicht als
CodePipeline-Element registriert. Projektcodes und Elementnamen sind keine
Felder der Mandantenkonfiguration.

### Historischer Übergabestand unter `/nfs/mtext/trans`

Der Jenkins-Ablauf kopiert jedes erzeugte Projektpaket nach
`/nfs/mtext/trans` und übergibt dasselbe Paket anschließend per FTP und JES an
den Mainframe. Daneben legt er eine lesbare Informationsdatei ab. Der
historische Bestand ist deshalb sowohl Beleg für den Mainframe-Vertrag als auch
Referenz für Dateinamen, Archivstruktur und Informationsinhalt.

Der logische Bestand folgt diesem Schema:

```text
/nfs/mtext/trans/
  <Mandantenkürzel><Projektcode><F|D>.tgz
  _INFO_<Mandantenkürzel>-<Projekt>-<FULL|DELTA>-<Release>-<Vorrelease>.txt
```

| Beispiel | Bedeutung und Inhalt |
|---|---|
| `BYAUTOND.tgz` | DELTA für `LOMS_Autonom[BY]`. Enthält die seit dem `.100`-Stand neuen und geänderten Ressourcen sowie `BYAUTOND.txt` als Löschliste. |
| `_INFO_BY-LOMS_Autonom[BY]-DELTA-R260.234-R260.178.txt` | Informationsdatei zum DELTA. Enthält den direkten Vergleich `R260.178` zu `R260.234` und die vollständige TAR-Inhaltsliste. |
| `OSAUTONF.tgz` | FULL für `LOMS_Autonom[OS]`. Enthält den vollständigen Projektbaum des FULL-Releases. |
| `OSAUTOND.tgz` beim FULL | Zusätzliches leeres D-Paket für `LOMS_Autonom[OS]`. Enthält das leere Projektverzeichnis und die leere Löschliste `OSAUTOND.txt`. |
| `_INFO_OS-LOMS_Autonom[OS]-FULL-R260.100-R251.510.txt` | Informationsdatei zum FULL. Enthält den direkten Vergleich `R251.510` zu `R260.100` und die vollständige TAR-Inhaltsliste. |

Die innere Struktur unterscheidet sich nach Lieferart:

```text
OSAUTONF.tgz
  ./LOMS_Autonom[OS]/
    <vollständiger Projektbaum>

BYAUTOND.tgz
  LOMS_Autonom[BY]/
    <seit R260.100 neue oder geänderte Ressourcendateien>
  BYAUTOND.txt

OSAUTOND.tgz beim FULL
  LOMS_Autonom[OS]/
  OSAUTOND.txt
```

Die Löschliste liegt im Wurzelverzeichnis des DELTA-Archivs. Jede Zeile nennt
einen relativen Ressourcenpfad ohne `VORRELEASE/`-Präfix. Die
Informationsdatei enthält zunächst eine SVN-artige Zusammenfassung mit
`A`, `M` und `D` für den Vergleich zum direkten Vorrelease und danach die
ausführliche Inhaltsliste des erzeugten TAR-Archivs.

Das gekürzte Format der beiden Textdateien sieht so aus:

```text
# BYAUTOND.txt
LOMS_Autonom[BY]/<Pfad einer seit R260.100 gelöschten Ressource>

# _INFO_BY-LOMS_Autonom[BY]-DELTA-R260.234-R260.178.txt
Subject: Bereitstellung BY - LOMS_Autonom[BY] - DELTA - Release R260.234

Folgende DIFFs wurden beim Vergleich zwischen R260.178 und R260.234 ... erkannt:
M       VORRELEASE/LOMS_Autonom[BY]/<Pfad einer geänderten Ressource>
D       VORRELEASE/LOMS_Autonom[BY]/<Pfad einer gelöschten Ressource>

Folgender Inhalt ist im TAR-Archiv ... enthalten:
LOMS_Autonom[BY]/<Pfad einer gelieferten Ressource>
BYAUTOND.txt
```

Paketinhalt und Informationsvergleich haben unterschiedliche Bezugsstände.
Der Paketinhalt und die Löschliste werden kumulativ gegen den `.100`-Stand
gebildet. Die Informationsdatei dokumentiert dagegen den Vergleich zum
direkten Vorrelease und bestimmt den Paketinhalt nicht.

Die Paketnamen unter `trans` enthalten keinen Release-Tag. Eine neue Lieferung
desselben Mandanten, Projekts und Liefertyps überschreibt daher das zuvor dort
liegende Archiv. Der sichtbare Archivbestand ist die jeweils letzte kumulative
Lieferung und keine Folge inkrementeller DELTA-Pakete. Der Releasebezug steht
im Namen der Informationsdatei.

Das historische FULL verwendet TAR-Pfade mit `./`-Präfix, das DELTA verwendet
Pfade ohne dieses Präfix - dies wird zunächst beibehalten. Besitzer, Gruppe,
Modus und Zeitstempel stammten aus dem Jenkins-Arbeitsbereich. Die
GitHub-Automatisierung behält die logischen Pfade bei und setzt die
Dateimetadaten reproduzierbar fest.

### Releaseartefakt und Manifest

Für jeden Release-Lauf speichert GitHub Actions die erzeugten Pakete zusammen
mit Manifest und Prüfsummen als Releaseartefakt. Der Publish-Job verwendet
genau dieses Artefakt für die Mainframe-Übergabe. Das bisherige feste
Verzeichnis `trans` wird für diesen Zweck nicht mehr benötigt. Dateinamen,
fachlicher Inhalt und Archivstruktur der Pakete bleiben unverändert.

Ein DELTA-Artefakt für ein Projekt der FI enthält beispielsweise:

```text
Release-Artefakt/
  FIBASISD.tgz
  _INFO_FI-LOMS_Basis-DELTA-R261.108-R261.107.txt
  manifest.json
```

Ein FULL-Artefakt enthält für dasselbe Projekt beide Mainframe-Pakete:

```text
Release-Artefakt/
  FIBASISF.tgz
  FIBASISD.tgz
  _INFO_FI-LOMS_Basis-FULL-R261.100-<Vorrelease>.txt
  manifest.json
```

Zu jeder Lieferung wird ein Manifest erzeugt. Die Begleitdatei nennt
Repository, Mandant, Release-Tag, Lieferart, Basis- und Vorgänger-Tag,
Ziel-SHA, JCL-Werte sowie alle Paket- und Informationsdateien mit Pfad, Größe
und SHA-256. Paketartefakte nennen zusätzlich ihren Mainframe-Member. Vor der
Mainframe-Übergabe werden genau diese Dateien mit den manifestierten Angaben
verglichen. So wird sichergestellt, dass das zuvor gebaute und freigegebene
Paket übergeben wird.

Der folgende gekürzte Ausschnitt zeigt die Verbindung zwischen Release,
Paket, Mainframe-Member und JCL-Werten. Dateigröße und Prüfsummen stehen
stellvertretend für die im jeweiligen Lauf berechneten Werte:

```json
{
  "artifacts": [
    {
      "kind": "package",
      "member": "FIBASISD",
      "path": "FIBASISD.tgz",
      "project": "LOMS_Basis",
      "sha256": "<SHA-256 des Pakets>",
      "size": 123456
    },
    {
      "kind": "information",
      "path": "_INFO_FI-LOMS_Basis-DELTA-R261.108-R261.107.txt",
      "project": "LOMS_Basis",
      "sha256": "<SHA-256 der Informationsdatei>",
      "size": 1234
    }
  ],
  "base_tag": "R261.100",
  "delivery_type": "DELTA",
  "jcl": {
    "ASSIGNMENT": "LOMS000066",
    "ISPW": "P",
    "LEVEL": "FKTE",
    "SUBSYS": "LOMS"
  },
  "mandant": "FI",
  "previous_tag": "R261.107",
  "release_tag": "R261.108",
  "repository": "mtext-fi",
  "target_sha": "<vollständige Commit-SHA>"
}
```

Ein fehlgeschlagener Übergabeversuch kann innerhalb desselben GitHub-Laufs mit
dem unveränderten Paket wiederholt werden (das Paket wird dabei nicht neu
gebaut).

## 11. Mainframe-Übergabe und JCL

Die JCL liegt als eigene versionierte Template-Datei vor. Änderungen
an der Mainframe-Ansteuerung sind dadurch sichtbar und unabhängig vom
Programmcode prüfbar.

Für jede Übergabe werden ausschließlich die fachlich festgelegten Werte in das
Template eingesetzt. Historisch feste Werte bleiben fest. Nur tatsächlich
mandantenspezifische Zuordnungen werden aus der Mandantenkonfiguration
übernommen. Die Werte für ISPW, CodePipeline-Stage, Subsystem, Assignment und
Mainframe-Member werden beim Rendern geprüft. Unbekannte Template-Marker führen
vor der Übergabe zu einem Fehler. Zugangsdaten werden weder in die JCL noch in
die Protokolle geschrieben.

Das Paket wird zunächst unter seinem Membernamen in
`IEA.LOMS.TONICZ` übertragen. Die JCL kopiert diesen Member nach
`IEA.ISPW<ISPW>.BOAS.<LEVEL>.TONICZ` und registriert ihn anschließend in
CodePipeline. Dabei gelten `STRMNAME=BOAS`, `MTYPE=TONICZ` und
`MNAME=<Membername>`. `APPLID` und `SUBAPPL` erhalten das Subsystem,
`PROJNO` das Assignment sowie `CLVL` und `SLVL` den CodePipeline-Stage-Code.

Der Release-Workflow trennt den Paketbau von der Mainframe-Übergabe. Der
Paketbau benötigt keinen Zugriff auf das Zielsystem. Erst der Übergabeschritt
erhält Zugriff auf die geschützte Umgebung `Bereitstellung` und wartet dort
auf eine manuelle Freigabe.

Übergaben desselben Mandanten werden nacheinander ausgeführt. Verschiedene
Mandanten können gleichzeitig liefern.

## 12. Status und Fehler

Die Lösung meldet nur den Status, den sie selbst sicher feststellen kann:

| Status | Bedeutung |
|---|---|
| `CONFIG_VALIDATED` | Mandantenkonfiguration und Releaselinienzuordnung wurden technisch geprüft. |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig. |
| `SOURCE_FAILED` | Der angegebene Commit, Branch oder Tag konnte nicht eindeutig aufgelöst werden. |
| `RESOURCE_TRANSFER_FAILED` | Die Ressourcen konnten nicht in den Übergabebereich für M/Text geschrieben werden. |
| `ADAPTER_FAILED` | Der M/Text-Adapter war nicht erreichbar oder hat die Anfrage abgelehnt. |
| `ADAPTER_ACCEPTED` | Der M/Text-Adapter hat die Anfrage unmittelbar angenommen. Dies ist noch kein fachlicher Endstatus. Bei unklarer Wirkung ermittelt die Anwendungsbetreuung den technischen Anwendungsstatus. |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder Manifest konnten nicht korrekt erstellt werden. |
| `ARTIFACT_READY` | Das Releasepaket wurde vollständig erstellt und geprüft. |
| `MAINFRAME_TRANSFER_FAILED` | Die unmittelbare FTP-/JES-Übergabe ist fehlgeschlagen. |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden technisch übergeben. Der spätere Mainframe-Job kann trotzdem noch fehlschlagen und wird durch das Mandanten-Release-Team auf dem Host kontrolliert. |

Ein HTTP-Fehler des M/Text-Adapters gilt immer als fehlgeschlagener Lauf. Ein
Status zwischen 200 und 299 bestätigt nur die unmittelbare Annahme der
Anfrage.

Die Automatisierung fragt weder bei M/Text noch auf dem Mainframe nach dem
späteren fachlichen Endstatus.

## 13. Qualitätsmerkmale, Grenzen und weitere Ausbaustufe

### Tragende Qualitätsmerkmale

Gemessen an modernen Best Practices für GitHub Actions und automatisierte
Softwarelieferungen besitzt die Lösung eine starke technische Grundlage. Die
Einordnung orientiert sich insbesondere an den GitHub-Empfehlungen zu
[wiederverwendbaren Workflows](https://docs.github.com/en/enterprise-server@3.20/actions/concepts/workflows-and-actions/reusing-workflow-configurations),
zum [sicheren Einsatz von GitHub Actions](https://docs.github.com/en/enterprise-server@3.20/actions/reference/security/secure-use)
und zu [geschützten Environments](https://docs.github.com/en/enterprise-server@3.20/actions/reference/workflows-and-actions/deployments-and-environments).

Für den Management-Überblick sind sowohl die tragenden Merkmale als auch die
noch offenen Grenzen wichtig.

| Qualitätsmerkmal | Umsetzung und Nutzen |
|---|---|
| Durchgängiger Gesamtablauf | Die fachliche Kette führt von Entwicklung über Abnahme und Bereitstellung zum Release-Tag. Erst das geprüfte Artefakt und die manuelle Freigabe führen zur externen Übergabe. Jeder Übergang hat einen eindeutigen Auslöser und ein prüfbares Ergebnis. |
| Zentral gepflegte Automatisierung | Die Trigger-Workflows enthalten nur Auslöser und feste Zielzuordnungen. Die gemeinsame Fachlogik liegt in wiederverwendbaren Workflows und einer Python-Implementierung in `mtext-actions`. Änderungen müssen dadurch nicht je Mandant kopiert werden. |
| Eindeutige und reproduzierbare Lieferung | Jeder Lauf verarbeitet einen vollständigen Commit-SHA. Das Manifest verbindet Release-Tag, Ziel-Commit und erzeugte Dateien. Gleiche Eingaben erzeugen bytegleiche Archive. Historische Namen, Verzeichnisstrukturen, Löschlisten und JCL-Verträge bleiben erhalten. |
| Getrennte Verantwortlichkeiten | Mandantenressourcen und -konfiguration, gemeinsame Automatisierung, GitHub-Schutzregeln und Runnerbetrieb haben jeweils einen klaren Eigentümer. |
| Minimale Berechtigungen und kontrollierte Wirkung | Die fachlichen Workflows erhalten nur Leserechte auf Repositoryinhalte. Die technische Schreibberechtigung ist auf den Einrichtungsworkflow und die vorgesehenen Workflowdateien begrenzt. Zugangsdaten liegen in Environments und stehen erst im berechtigten Job zur Verfügung. |
| Geprüfte Build-Publish-Grenze | Der Paketbau ist von der Mainframe-Übergabe getrennt. Das einmal erzeugte Artefakt wird unmittelbar vor der externen Wirkung anhand von Pfad, Größe und SHA-256 geprüft. |
| Begrenzte technische Angriffsfläche | Die Anwendung verwendet nur die Python-Standardbibliothek, führt Git ohne Shell aus und prüft Symlinks sowie externe Werte an ihren Systemgrenzen. Actions und wiederverwendbare Workflows werden mit vollständigen Commit-SHAs gebunden. |
| Automatisiert prüfbarer Vertrag | Tests decken Konfiguration, Git-Bezüge, FULL und DELTA, Manifest, JCL, Ressourcensynchronisation, FTP/JES und Workflowgrenzen ab. Stabile Statuswerte unterscheiden die Fehlerklassen. |

### Offene Grenzen und Risiken

| Grenze oder Risiko | Bedeutung und Umgang |
|---|---|
| M/Text-Transport noch nicht entschieden | Der direkte Sharezugriff ist implementiert, aber der spätere Transportweg ist noch auszuwählen und nichtproduktiv abzunehmen. Ohne diese Entscheidung ist die M/Text-Integration nicht betriebsbereit. |
| GitHub-Einrichtung noch nicht vollständig | Runner-Kennzeichen, repositoryübergreifende Zugriffe, Rulesets, Environments und technische Rollen müssen auf GitHub Enterprise Server 3.20.4 eingerichtet und praktisch geprüft werden. |
| Kein nachgelagerter fachlicher Endstatus | `ADAPTER_ACCEPTED` und `MAINFRAME_SUBMITTED` bestätigen nur die unmittelbare technische Annahme. Die fachliche Endkontrolle bleibt bis zu einer späteren Erweiterung eine Betriebsaufgabe. |
| Kein technisch erzwungenes Vier-Augen-Prinzip | Eine berechtigte Person darf den Release-Tag anlegen und die Mainframe-Übergabe freigeben. Falls Governance-Vorgaben eine Trennung verlangen, muss das Environment entsprechend angepasst werden. |
| Bestehender FTP-/JES-Transport | Die Mainframe-Übergabe übernimmt zunächst den vorhandenen FTP-Vertrag. Eine verschlüsselte Alternative kann erst umgesetzt werden, wenn das Zielsystem einen bestätigten Vertrag dafür bereitstellt. |
| Selbst gehosteter Runner als Vertrauensgrenze | Absicherung, Wartung und Bereinigung des FI-Runners liegen außerhalb der Anwendung. Diese Betriebsleistungen sind Voraussetzung für den sicheren Einsatz. |

### Mögliche Phase 2

Die erste Ausbaustufe bleibt bewusst auf die sichere Ablösung des bestehenden
Lieferwegs begrenzt. Die in [Nächste Schritte](./Naechste_Schritte.md) geführten
Einrichtungs- und Abnahmepunkte sind Voraussetzungen für die Aktivierung und
keine Phase-2-Themen. Nach einem stabilen Produktivbetrieb können insbesondere
folgende Erweiterungen bewertet werden:

- den nachgelagerten fachlichen Status in M/Text und auf dem Mainframe abfragen
  und im Workflow anzeigen (Polling),
- die FTP-/JES-Übergabe auf einen verschlüsselten Transport umstellen, sobald
  das Zielsystem dafür einen verbindlichen Vertrag bereitstellt,
- Betriebsmetriken und kompakte Laufzusammenfassungen ergänzen, ohne
  mandantenübergreifende oder vertrauliche Details offenzulegen,
- zusätzliche E-Mail-Benachrichtigungen für relevante Workflow-Ergebnisse
  ergänzen, ohne den fachlichen Laufstatus von der Benachrichtigung abhängig zu
  machen,
- Aktualisierungen gepinnter Actions sowie ergänzende Workflow-, Shell-, Typ-
  und Abdeckungsprüfungen automatisieren.
