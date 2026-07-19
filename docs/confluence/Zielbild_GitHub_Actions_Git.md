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
Abnahme und Bereitstellung. Als Stage wird in diesem Dokument ein Abschnitt
des Freigabe- und Lieferprozesses bezeichnet.

Der Ablauf ist:

1. Ein Push nach `Rnnn/Entwicklung` verteilt den Stand an das
   M/Text-Entwicklungssystem (z.B. en01e.ltoms.intern).
2. Fachlich freigegebene Änderungen werden nach `Rnnn/Abnahme` übernommen und
   an das M/Text-Abnahmesystem verteilt (z.B. en01a.ltoms.intern).
3. Abgenommene Änderungen werden nach `Rnnn/Bereitstellung` übernommen. Der
   Push allein erzeugt noch keine Mainframe-Lieferung.
4. Erst ein Release-Tag wie `R261.108` baut die Lieferung. Vor der technischen
   Übergabe an den Mainframe ist eine manuelle Freigabe erforderlich.

Der M/Text-Adapter bleibt die zentrale Schnittstelle. Für den Weg nach
`serverSync` stehen ein PUT an den Adapter, der direkte Sharezugriff des von der FI
bereitgestellten Runners und der Download eines GitHub-Actions-Artefakts durch
Adapter oder M/Text zur Wahl. Der Transportweg wird vor dem Integrationslauf
festgelegt. Die Mainframe-Übergabe erfolgt weiterhin per FTP und JES.

## 2. Verbindliche Rahmenbedingungen

- Der Wechsel von SVN/Jenkins zu Git/GitHub Actions findet zu einem festen
  Zeitpunkt statt. Danach gibt es keinen parallelen produktiven Lieferbetrieb.
- Das bisherige Jenkins-Skript wird nicht weiterentwickelt oder technisch
  portiert. Nur die weiterhin benötigten Regeln, Zuordnungen und
  Übergabeverfahren werden übernommen.
- Jeder Mandant erhält ein eigenes privates GitHub-Repository. Namen und
  grundsätzlicher Aufbau orientieren sich an den bisherigen
  Mandantenstrukturen.
- Die Automatisierung in `mtext-actions` wird zentral durch die FI verwaltet
  und von den Mandanten-Repositories in einer ausdrücklich festgelegten
  Version verwendet.
- `mtext-actions` ist ein privates Repository. Direkten Zugriff erhalten nur
  die zentralen Automatisierungsverantwortlichen. Text-Entwickler der
  Mandanten werden dort nicht als Repositorymitglieder berechtigt.
- Jeder Lauf verarbeitet genau einen Git-Stand, den die Commit-SHA kennzeichnet.
- Der Mandant ergibt sich aus dem Repository und seiner Konfiguration. Er kann
  beim Start eines Laufs nicht frei gewählt werden.
- Die Releaselinien `R260`, `R261` und `R270` erhalten getrennte Branches für
  Entwicklung, Abnahme und Bereitstellung.
- Geheimnisse und Zugangsdaten liegen in den GitHub-Einstellungen, nicht in Git.
- Eine weitergehende Statusabfrage bei M/Text oder auf dem Mainframe wird in
  der ersten Ausbaustufe nicht eingeführt.

## 3. Was aus dem bisherigen Verfahren übernommen wird

Das Jenkins-Skript erledigt heute unter anderem die M/Text-Verteilung, den Bau
von FULL- und DELTA-Paketen, die Erstellung von Inhalts- und Löschlisten sowie
die Übergabe an den Mainframe. Diese fachlichen Ergebnisse werden weiterhin
benötigt.

Nicht übernommen werden die technischen Altlasten des bisherigen Verfahrens.
Dazu gehören langlebige SVN-Arbeitskopien auf Netzlaufwerken,
Reparaturkommandos für blockierte Arbeitsverzeichnisse und zur Laufzeit
erzeugte Skripte mit Zugangsdaten. Die neue Lösung arbeitet stattdessen je Lauf
mit einem frisch ausgecheckten, eindeutig bestimmten Git-Stand.

Die bisherigen Lieferdateien geben folgende Kompatibilitätsregeln vor:

- FULL- und DELTA-Pakete behalten ihre historisch festgelegten Dateinamen. Der
  dafür benötigte Liefercode ist dem freigegebenen Projektnamen zentral
  zugeordnet und kann nicht im Mandanten-Repository geändert werden.
- Ein DELTA-Paket enthält weiterhin die nach dem CodePipeline-Element benannte
  Löschliste.
- Ressourcen behalten ihre fachlichen Projektpfade. Bei Fragmentprojekten
  gehört das Mandantenkürzel in eckigen Klammern zum Projektnamen, zum Beispiel
  `LOMS_Autonom[BY]`.
- Zu jedem Paket wird eine Informationsdatei erzeugt. Sie beschreibt den
  Inhalt und den Vergleich zum vorherigen Release, bestimmt aber nicht den
  Inhalt des DELTA-Pakets.
- Die vorhandenen Unterschiede in den Pfaden von FULL- und DELTA-Archiven
  bleiben zunächst erhalten, damit bestehende Empfänger die Dateien weiterhin
  verarbeiten können.
- Archive werden reproduzierbar erzeugt: Derselbe Quellstand und dieselbe
  Konfiguration ergeben denselben Inhalt.

## 4. Zielarchitektur und Verantwortlichkeiten

Die Lösung besteht aus vier Bereichen:

| Bereich | Verantwortung |
|---|---|
| Mandanten-Repository | M/Text-Ressourcen, Mandantenkonfiguration und schlanke aufrufende Workflows |
| Zentrales Repository `mtext-actions` | Gemeinsame Prüfungen, Synchronisation, Paketbau und Mainframe-Übergabe |
| GitHub Actions | Ausführung der Abläufe, Freigaben und Protokollierung |
| Von der FI bereitgestellter GitHub-Actions-Runner | Ausführung der Workflows auf dem offiziell verfügbaren Runnerangebot der FI. Bereitstellung, Absicherung, Wartung und Bereinigung des Runnerangebots liegen außerhalb des Projekts |

Ein Mandanten-Repository enthält ausschließlich die Ressourcen und Angaben
des jeweiligen Mandanten. Das zentrale Repository enthält keine
Mandantenressourcen, sondern nur die gemeinsam verwendete Automatisierung.

Mandanten-Repositories dürfen die freigegebenen wiederverwendbaren Workflows
über die GitHub-Actions-Zugriffsrichtlinie aufrufen. Diese technische Freigabe
erteilt ihren Benutzern keinen direkten Zugriff auf `mtext-actions`. Die Logs
der aufgerufenen Jobs sind dagegen im Mandanten-Repository sichtbar und
enthalten deshalb weder Secrets noch unnötige interne Details.

Zu Beginn jedes Jobs stellt GitHub automatisch ein `GITHUB_TOKEN` bereit. Der
Job authentifiziert sich damit gegenüber GitHub, beispielsweise beim Checkout
des eigenen privaten Repositories oder bei einem API-Aufruf. Das Token gilt nur
für den Job; seine Rechte werden im Workflow über `permissions` begrenzt und
beziehen sich ausschließlich auf das Repository, in dem der Workflow läuft.

Der Checkout der zentralen Python-Implementierung verwendet deshalb eine
gesonderte, nur lesende technische Berechtigung. Das automatisch erzeugte
`GITHUB_TOKEN` des Mandantenlaufs kann diesen repositoryübergreifenden Checkout
nicht übernehmen. Auch die gesonderte Berechtigung vermittelt den Benutzern
keinen direkten Repositoryzugriff.

Push-Rulesets schützen die aufrufenden Workflows vor Änderungen durch
Text-Entwickler. Die Mandantenkonfiguration ist ebenfalls von der normalen
Ressourcenpflege getrennt. Die konkreten Rollen und Bypässe beschreibt
Kapitel 6.

Die Text-Entwickler bearbeiten Briefressourcen in der M/Text Workbench und
nutzen ihren Git-Client für Commit und Push. GitHub im Browser dient für
Laufkontrolle, Wiederholungen, Freigaben und die Prüfung von Release-Tags. Für
die tägliche Arbeit ist keine Git-Kommandozeile nötig.

Für die gezielte Übernahme einzelner Änderungen zwischen den Stages erhalten
die dafür berechtigten Text-Entwickler zusätzlich einen geeigneten Git-Client.
Das konkrete Produkt, seine Bereitstellung und der verbindliche Bedienweg
werden vor dem Pilotbetrieb festgelegt und abgenommen. Das Release-Team
verwendet diesen Client außerdem zum Anlegen, Pushen und kontrollierten Löschen
von Release-Tags.

Jeder Mandant benennt ein Release-Team für den Bereitstellungsbranch und die
Release-Tags. Die Verantwortlichen können sich je Mandant unterscheiden, ohne
die Automatisierung in `mtext-actions` zu verzweigen. Verwendet werden
ausschließlich Git-Tags; GitHub Releases gehören nicht zum Lieferprozess.
Schutzregeln und Tag-Lebenszyklus sind in Kapitel 6 festgelegt, der Bedienablauf
in Kapitel 7.

Für jeden Lauf checkt GitHub Actions sowohl den ausgewählten Stand des
Mandanten-Repositories als auch eine festgelegte `mtext-actions`-Version aus.
Dadurch ist später nachvollziehbar, welche Quellen und
welche Automatisierung verwendet wurden.

Die Verteilung nach Entwicklung oder Abnahme überträgt alle nicht
ausgeschlossenen Projektverzeichnisse des ausgewählten Commits. FULL und DELTA
gelten nur für die spätere Mainframe-Lieferung.

### M/Text-Transport nach `serverSync`

Der heutige Ablauf schreibt den Ressourcenstand zuerst nach `serverSync` (via
NFS-Share) und sendet danach einen POST-Request an den M/Text-Adapter (LTOMA).
Dieser Ablauf ist die Ausgangslage, legt den künftigen Transport aber noch
nicht fest.

Unabhängig vom Transportweg entsteht auf `serverSync` derselbe vollständige
Verzeichnisbaum mit denselben relativen Pfaden, Dateinamen und Dateiinhalten
wie im bisherigen Jenkins-/SVN-Verfahren. Die Veröffentlichung erfolgt erst,
nachdem der gesamte Stand erfolgreich übertragen wurde. Entfernte oder neu
ausgeschlossene Projekte dürfen nicht als veralteter Bestand liegen bleiben.
Transportdateien und technische Metadaten gehören nicht in den von M/Text
ausgewerteten Bestand.

Für einen BY-Stand sieht der veröffentlichte Zielbaum beispielsweise so aus:

```text
serverSync/
  LOMS_Basis[BY]/
    <vollständiger Projektbaum>
  LOMS_Autonom[BY]/
    <vollständiger Projektbaum>
```

Es gibt keine zusätzliche Paketwurzel. Archiv, Manifest und andere
Transportdateien liegen nicht unter `serverSync`.

Für die Versorgung von `serverSync` werden drei Varianten bewertet:

| Variante | Ablauf und Verantwortung | Vor der Entscheidung zu klären | Aufwand |
|---|---|---|---|
| PUT an den Adapter | Der Runner überträgt die Ressourcendaten per PUT-Request an den Adapter. Der Adapter prüft die Übertragung, schreibt zunächst in einen temporären Bereich, veröffentlicht den vollständigen Stand nach `serverSync` und startet die interne Synchronisation. Der Runner benötigt keinen Sharezugriff. | HTTP-Vertrag, Authentifizierung, Größenlimits, Prüfsummen, Zeitgrenzen, Wiederholung, Parallelität und Erfolgsstatus | mittel bis hoch |
| Direkter Sharezugriff des Runners | Der Runner stellt den vollständigen Stand auf dem NFS-/Netzlaufwerk des M/Text-Servers bereit und ruft erst danach den Adapter auf. Staging, Veröffentlichung und Wiederanlauf liegen damit in der GitHub-Automatisierung. Diese Variante entspricht dem aktuellen Entwicklungsstand. | Verfügbarkeit und Einbindung des Shares, Pfad, Rechte, Kapazität, atomare Ersetzung, Schutz vor parallelen Schreibvorgängen und Bereinigung nach Fehlern | gering |
| Download eines Actions-Artefakts | Der Runner lädt den bereits für `serverSync` zusammengestellten Verzeichnisbaum als eigenes Sync-Artefakt hoch. Adapter oder M/Text laden ihn über die GitHub-Actions-Artefakt-API herunter, prüfen die Prüfsumme, entpacken ihn temporär, veröffentlichen den Stand nach `serverSync` und starten die interne Synchronisation. | Übergabe von Repository, Lauf- oder Artefakt-ID und Prüfsumme, technische Identität mit `Actions: read`, Erreichbarkeit, Aufbewahrungsfrist, Wiederholung und Bereinigung | mittel |

Das Sync-Artefakt der Downloadvariante ist nur ein technischer
Transportbehälter. Es enthält kein zusätzliches inneres M/Text-Paket und ist
von den FULL-/DELTA-Releaseartefakten für den Mainframe getrennt.

Vor dem nichtproduktiven Integrationslauf wird genau eine Variante ausgewählt.
Die Entscheidung berücksichtigt Netzwerk- und Sicherheitsvorgaben,
Betriebsverantwortung, Datenmengen und Laufzeiten, atomare Veröffentlichung,
Parallelität, Wiederanlauf und Nachvollziehbarkeit. Anschließend werden der
Adaptervertrag und die Zuständigkeiten für Übertragung, Prüfung,
Veröffentlichung, Start der internen Synchronisation und Fehlerbehandlung
verbindlich festgeschrieben. Implementiert wird nur der ausgewählte Weg; eine
allgemeine Transportschicht für alle drei Varianten ist nicht vorgesehen.

Der bestehende Prozess auf dem Mainframe-Zielsystem IZE9 bleibt unverändert.

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
  .github/workflows/
  config/
  scripts/
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
  tests/
```

Die Module folgen den fachlichen Abläufen. `sync.py` enthält Staging,
`serverSync` und Adapteraufruf; `mainframe.py` enthält JCL und FTP/JES.
Pfad- und Wertprüfungen stehen direkt an der jeweils zuständigen Eingangs-
oder Systemgrenze. Intern erzeugte Werte werden nicht in weiteren Schichten
erneut validiert.

`mtext-fi` dient als Muster für die Mandanten-Repositories. Alle sichtbaren
Verzeichnisse in der Repositorywurzel werden synchronisiert und in
Releasepakete aufgenommen. `LOMS_Testdaten` soll ebenfalls in das Repository
übernommen werden, ist aber über `excluded_projects` in `.github/config.json`
von der Synchronisation und den Releasepaketen ausgeschlossen.

Die Workflows im Mandanten-Repository legen nur Auslöser und die zugehörigen
GitHub Environments fest; die Verarbeitung erfolgt in `mtext-actions`. Im
aktuellen Entwicklungsstand enthalten die zentralen Workflows noch den
Platzhalter für das Runner-Kennzeichen der FI. Die Mandanten-Workflows verwenden
für den zentralen Workflow- und Codebezug noch eine nicht lauffähige Folge aus
Nullen.

Im gemeinsamen Workspace liegt der zur Übernahme vorgesehene Inhalt des
zentralen Repositorys unter `mtext-actions`. Im Zielbetrieb werden das
Mandanten-Repository und das Automatisierungs-Repository `mtext-actions` als
eigenständige GitHub-Repositories unter `j517120/mtext-fi` und
`j520730/mtext-actions` geführt. Nach fachlicher
Bestandsaufnahme und Freigabe folgen `mtext-autonom`, `mtext-by`, `mtext-lh`,
`mtext-nw`, `mtext-os` und `mtext-sa` demselben Muster.

Vor dem ersten Integrationslauf werden Runner-Kennzeichen und zentrale
Workflowversion finalisiert. GitHub Enterprise erlaubt den vorgesehenen
Mandanten-Repositories den Workflowaufruf, ohne deren Benutzer direkt am
zentralen Repository zu berechtigen. Die noch ausstehenden Einrichtungs- und
Abnahmepunkte stehen in [Nächste Schritte](./Naechste_Schritte.md).

## 6. GitHub-Konfiguration

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Die folgenden
Einstellungen bilden den verbindlichen Zielzustand. Ihre Einrichtung und
praktische Abnahme werden in [Nächste Schritte](./Naechste_Schritte.md)
nachgehalten.

### Repositories und Zugriffe

| Gegenstand | Zielzustand |
|---|---|
| Mandanten-Repositories | Für jeden Mandanten besteht ein eigenes privates Repository. Die berechtigten Text-Entwickler sehen und bearbeiten nur die für sie vorgesehenen Mandanten-Repositories. |
| Zentrales Repository | `mtext-actions` ist privat und nur für das zentrale Automatisierungsteam direkt zugänglich. Mandanten-Repositories dürfen ausschließlich die freigegebenen wiederverwendbaren Workflows aufrufen. |
| Default Branch | Der Entwicklungsbranch der führenden Releaselinie ist eingestellt, zunächst `R261/Entwicklung`. Beim Wechsel der führenden Linie wird die Einstellung angepasst. |
| Technischer Konfigurationskreis | Nur der benannte Verantwortlichenkreis darf `.github/config.json` ändern. |
| Mandanten-Release-Team | Nur das jeweilige Release-Team darf nach `Rnnn/Bereitstellung` pushen und Release-Tags anlegen oder im erlaubten Zeitraum zurücknehmen. |

### Schutzregeln für Branches, Pfade und Tags

| Schutzbereich | Zielzustand |
|---|---|
| `Rnnn/Entwicklung` und `Rnnn/Abnahme` | Berechtigte Text-Entwickler dürfen pushen. Force-Pushes und das Löschen der Branches sind gesperrt. |
| `Rnnn/Bereitstellung` | Reguläre Pushes sind auf das Mandanten-Release-Team begrenzt. Force-Pushes und das Löschen des Branches sind gesperrt. |
| `.github/workflows/**/*` | Ein Push-Ruleset schützt die zentral vorgegebenen Aufrufdateien auf allen Branches. Nur das zentrale Automatisierungsteam besitzt einen kontrollierten Bypass. |
| `.github/config.json` | Eine Pfadregel trennt Änderungen der Mandantenkonfiguration von der normalen Ressourcenpflege. Nur der technische Konfigurationskreis besitzt den erforderlichen Bypass. |
| Tags `Rnnn.nnn` | Nur das Mandanten-Release-Team darf passende Tags erstellen. Ein irrtümlicher Tag darf nur vor der Freigabe des Publish-Jobs und nach Abbruch des zugehörigen Laufs gelöscht und neu angelegt werden. Nach der Freigabe sind Änderung und Löschung gemäß der verbindlichen Betriebsregel unzulässig. |

Ein statisches Tag-Ruleset kann den Wechsel vom Release-Kandidaten zum
freigegebenen Tag nicht allein abbilden. Deshalb gilt folgende Betriebsregel:

1. Bis zur Freigabe des Publish-Jobs ist der Tag ein Release-Kandidat. Bei
   einem Irrtum bricht das Release-Team zuerst den zugehörigen Workflow-Lauf
   ab. Erst danach darf es den Tag löschen, den Bereitstellungsstand
   korrigieren und den Tag erneut anlegen.
2. Unmittelbar vor der Freigabe vergleicht das Release-Team Tagname und
   vollständige Ziel-SHA aus dem Build-Ergebnis mit dem vorgesehenen Stand des
   Bereitstellungsbranches.
3. Mit der Freigabe ist der Tag freigegeben. Ab diesem Zeitpunkt darf er weder
   verschoben noch gelöscht werden. Eine fachliche Korrektur erfolgt durch
   einen neuen Commit und einen neuen Release-Tag.
4. Wird ein freigegebener Tag dennoch verändert oder gelöscht, werden weitere
   Freigaben gestoppt. Das Release-Team stellt den Tag ausschließlich auf der
   im freigegebenen Workflow-Lauf ausgewiesenen Ziel-SHA wieder her und meldet
   den Vorgang als Betriebsstörung.

### Environments und Secrets

Ein GitHub Environment bildet eine Zielstufe ab und bündelt die dafür geltenden
Schutzregeln, etwa zulässige Branches oder Tags und erforderliche Freigaben.
Seine Secrets stehen ausschließlich Jobs zur Verfügung, die dieses Environment
binden und dessen Schutzregeln erfüllen.

| Environment | Verwendung und Schutz |
|---|---|
| `Einrichtung` | Wird ausschließlich vom manuell gestarteten Einrichtungsworkflow in `mtext-actions` gebunden. Es stellt nach Freigabe das auf die vorgesehenen Repositories begrenzte technische Token für die Workflowänderungen bereit. |
| `Entwicklung` | Wird ausschließlich vom Sync-Job für den Entwicklungsbranch gebunden. Eine manuelle Freigabe und stufenspezifische Environment-Secrets sind dafür nicht vorgesehen. |
| `Abnahme` | Wird ausschließlich vom Sync-Job für den Abnahmebranch gebunden. Eine manuelle Freigabe und stufenspezifische Environment-Secrets sind dafür nicht vorgesehen. |
| `Bereitstellung` | Wird ausschließlich vom Publish-Job gebunden. Eine berechtigte Person muss die Mainframe-Übergabe manuell freigeben; ein verpflichtendes Vier-Augen-Prinzip oder eine Sperre der Selbstfreigabe ist nicht vorgesehen. Nur zulässige Release-Tags dürfen dieses Environment verwenden. |

Die Mainframe-Zugangsdaten `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und
`MAINFRAME_FTP_PASSWORD` liegen ausschließlich als Secrets im Environment
`Bereitstellung`. Sie werden weder in Git gespeichert noch an den Build-Job
übergeben.

### GitHub Actions und Ausführung

Nach abgeschlossener Einrichtung gelten für die Ausführung der Workflows die
folgenden technischen Festlegungen:

| Gegenstand | Ergebnis der Einrichtung |
|---|---|
| Zentrale Workflowversion | Jeder Aufruf verwendet die für seinen Rollout festgelegte unveränderliche Version von `mtext-actions`. Deren vollständige Commit-SHA wird vom zentralen Automatisierungsteam freigegeben und ist keine Eingabe der Text-Entwickler oder Release-Verantwortlichen. |
| Actions-Zugriff | Nur die vorgesehenen Mandanten-Repositories dürfen die wiederverwendbaren Workflows aus `mtext-actions` aufrufen. Der zentrale Codebezug erhält eine gesonderte technische Leseberechtigung. Weitere Actions sind auf freigegebene und vollständig gepinnte Versionen begrenzt. |
| `GITHUB_TOKEN` | GitHub erzeugt das kurzlebige Token automatisch für jeden Job. Die fachlichen Workflows begrenzen seine Rechte auf das Lesen des aufrufenden Mandanten-Repositories; Schreibrechte auf Branches oder Tags sind nicht vorgesehen. |
| Einrichtungsberechtigung | Nur der Einrichtungsworkflow erhält über das Environment `Einrichtung` das Secret `WORKFLOW_CONFIGURATION_TOKEN`. Die technische Identität ist auf `mtext-actions` und die vorgesehenen Mandanten-Repositories begrenzt und besitzt dort den erforderlichen Zugriff auf die geschützten Branches. Der Workflow nimmt ausschließlich `.github/workflows` in seine Commits auf. |
| Runnerangebot der FI | Die Jobs verwenden einen offiziell von der FI bereitgestellten GitHub-Actions-Runner. Das zugehörige `runs-on`-Kennzeichen wird aus dem Runnerangebot der FI übernommen und in den zentralen Workflows fest eingetragen. Bereitstellung, Absicherung, Wartung und Bereinigung des Runners liegen außerhalb des Projekts. |
| Laufzeitvoraussetzungen | Für die Workflows müssen Python 3.14, Git, die verwendeten Node-20-Actions sowie die benötigten Netzwerk- und Zertifikatspfade verfügbar sein. `runner-preflight.sh` prüft die benötigten Programme zu Beginn jedes Jobs. |
| Logs | Ausgaben wiederverwendbarer Workflows sind im Mandanten-Repository sichtbar. Sie enthalten keine Secrets und keine unnötigen internen Angaben. |
| Artefakte | Releaseartefakte werden standardmäßig 30 Tage aufbewahrt. Ihre Namen enthalten Repository und Release-Tag. |

### Reproduzierbare Einrichtung und Aktualisierung

Der manuelle Workflow **Configure workflow files** in `mtext-actions` richtet
die Workflowdateien eines Mandanten erstmals ein und aktualisiert sie bei jeder
neuen freigegebenen `mtext-actions`-Version. Er setzt den Aufruf der zentralen
Workflows und den Checkout der Python-Implementierung auf dieselbe
unveränderliche Commit-SHA. Damit ist für jeden Mandantenbranch eindeutig
festgelegt, welche Version der Automatisierung er verwendet.

Vor dem ersten Lauf werden der Runner der FI, dessen Repositoryvariable
`FI_RUNNER_LABEL` sowie das Environment `Einrichtung` mit dem Secret
`WORKFLOW_CONFIGURATION_TOKEN` bereitgestellt. Der Workflow wird in GitHub mit
drei Angaben gestartet:

- vollständige Commit-SHA der freigegebenen `mtext-actions`-Version,
- vollständiger Name des Mandanten-Repositories,
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

Auch die Aktualisierung der Mandanten läuft ausschließlich über diesen
Workflow. Für eine neue freigegebene `mtext-actions`-Version legt das zentrale
Automatisierungsteam eine Rollout-Matrix aus Mandanten-Repositories und
Branches fest und startet für jeden Eintrag einen Lauf mit derselben SHA. Ein
erneuter Lauf für einen bereits erreichten Zielzustand erzeugt keinen weiteren
Commit. Der Rollout ist abgeschlossen, wenn alle vorgesehenen Branches auf die
freigegebene SHA verweisen; bereits laufende Workflows behalten ihre beim Start
festgelegte Version.

Das technische Token ist auf `mtext-actions` und die vorgesehenen
Mandanten-Repositories begrenzt. Der privilegierte Job führt keinen Code aus
dem Mandanten-Repository aus. Seine Python-Implementierung liegt versioniert
unter `src/workflow_configuration.py` in `mtext-actions`.

Nicht zu diesem Workflow gehört der noch offene API-Teil für Repositories,
Stage-Branches, Default Branches, Rulesets, weitere Environments und
Actions-Zugriffe. Er prüft den erreichten Zustand nach jeder Änderung erneut,
speichert keine geheimen Werte und kontrolliert bei Secrets nur die
vereinbarten Namen. Fachliche Entscheidungen, Rollenbesetzung,
Zugangsdatenübergabe sowie Pilot-, Freigabe- und Go-/No-Go-Entscheidungen
bleiben menschliche Aufgaben.

## 7. Branches, Weitergabe und Auslöser

Jede aktive Releaselinie besitzt drei Branches, zum Beispiel:

```text
R260/Entwicklung
R260/Abnahme
R260/Bereitstellung
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
und einzeln gepusht; ein GitHub Release wird nicht erzeugt. Bis zur Freigabe
der Mainframe-Übergabe ist er ein Release-Kandidat und kann nach der in Kapitel
6 festgelegten Betriebsregel kontrolliert zurückgenommen werden. Die Freigabe
bindet den Tagnamen dauerhaft an den geprüften Ziel-Commit. Eine spätere
Korrektur verwendet einen neuen Commit und einen neuen Release-Tag.

Der zusätzliche Git-Client für die Auswahl und Übernahme einzelner Änderungen
in Abnahme und Bereitstellung wird vor dem Pilotbetrieb ausgewählt,
bereitgestellt und praktisch abgenommen. Ein direkter Cherry-Pick ist über die
GitHub-Weboberfläche allein nicht verfügbar.

Die Mandanten-Repositories erhalten keinen zusätzlichen `main`-Branch. Als
Default Branch dient der Entwicklungsbranch der aktuell führenden Linie,
zunächst `R261/Entwicklung`. Beim Wechsel der führenden Linie aktualisiert die
Einrichtungsautomation diese Einstellung.

Manuelle Wiederholungen sind möglich, müssen aber denselben Commit verwenden.
Vor einer erneuten M/Text-Verteilung prüft der Workflow, ob dieser Commit zum
ausgewählten Branch gehört.

### Neue Releaselinie einrichten

Eine neue Linie erhält drei Branches, je einen für Entwicklung, Abnahme und
Bereitstellung, sowie einen Eintrag in
[`config/releaselinien.json`](../../mtext-actions/config/releaselinien.json).
Ein vollständiges Beispiel steht unter
[Zentrale Releaselinienzuordnung](#zentrale-releaselinienzuordnung). Der
Eintrag enthält nur die fachliche Releaselinie, die technische M/Text-Linie und
den Namen eines in
`.github/config.json` vorhandenen Hostprofils. Hosts, Stage-Suffixe,
serverSync-Pfad und Tagformat werden unverändert zentral abgeleitet. Die
JCL-Werte stammen aus der Mandantenkonfiguration und dem zugeordneten
Hostprofil. Die Zuordnung wird rollierend gepflegt: Beim Aufnehmen einer neuen
Releaselinie wird die ausgeschiedene Zuordnung entfernt, sodass genau drei
aktive Releaselinien enthalten sind.

Ausgangspunkt der neuen Branches ist der fachlich bestätigte letzte
Release-Tag der bisherigen Linie. Dessen vollständiger Projektstand wird über
den manuellen Sync-Workflow einmal nach Entwicklung und einmal nach Abnahme
übertragen und anschließend in M/Text fachlich geprüft.

## 8. Workflows, Trigger und Abhängigkeiten

Die Mandanten-Repositories enthalten nur die fachlichen Auslöser. Sie rufen
fest gepinnte wiederverwendbare Workflows aus `mtext-actions` auf. Die
eigentliche Fachlogik liegt in Python.

### Gesamtzusammenhang

| Prozessschritt | Auslöser | Mandanten-Workflow | Zentraler Workflow | Python-Kommando | Ergebnis |
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
Abnahme startet daher den vollständigen Ressourcensync. Dabei werden die
sichtbaren, nicht unter `excluded_projects` genannten Projektverzeichnisse
übertragen.

Die Synchronisation wartet nicht auf den Abschluss der separaten
Konfigurationsprüfung. Wenn ein Push nach Entwicklung oder Abnahme zugleich
`.github/config.json` ändert, können beide Abläufe unabhängig voneinander laufen.
Synchronisation und Release-Erstellung prüfen die verwendete Konfiguration vor
dem Zugriff auf externe Systeme erneut.

### Mandantenseitige YAML-Workflows

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
| `python -m workflow_configuration` | `configure-workflows.yml` | Zentraler Checkout entspricht der freigegebenen `mtext-actions`-SHA. Bestätigtes Runner-Kennzeichen. Vollständige Workflow- und Codebezüge. Diffs sind fehlerfrei und die abschließende Einrichtungsprüfung ist leer | Geprüfte lokale Workflow-Commits für `mtext-actions` und den Mandantenbranch; der Workflow pusht sie anschließend in der erforderlichen Reihenfolge |
| `validate-config` | `reusable-validate-config.yml` | Bekanntes Mandantenkürzel, Repositoryidentität, gültige CodePipeline-Stage-Codes, eindeutige Projektcodes und vorhandene Hostprofile der Releaselinien | Status `CONFIG_VALIDATED` |
| `sync-resources` | `reusable-sync-resources.yml` | Branch und Environment stimmen überein. Vollständige SHA. Checkout entspricht SHA. Commit ist aus dem Remote-Branch erreichbar. Projektbäume enthalten keine Symlinks | Vollständiger Projektstand nach `serverSync`, Adapteraufruf gemäß Transportvertrag, Status `ADAPTER_ACCEPTED` |
| `build-release` | Job `build` in `reusable-release.yml` | Tagformat und konfigurierte Releaselinie. Tag aus Bereitstellungsbranch erreichbar. Checkout entspricht Tag-SHA. DELTA-Basis `.100`. Projektbäume enthalten keine Symlinks | Reproduzierbare FULL-/DELTA-Archive, Informationsdateien und `manifest.json` mit SHA-256. Status `ARTIFACT_READY` |
| `publish-mainframe` | Job `publish` in `reusable-release.yml` | Artefaktpfade, Dateigrößen und SHA-256 aus dem Manifest; JCL-Werte beim Rendern; FTP-Secrets vor der Übergabe | JCL je Paket, FTP-Übertragung und Übergabe an JES. Status `MAINFRAME_SUBMITTED` |

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
| `hostprofile` | Ein oder mehrere frei benannte Hostprofile mit `assignment` und `stage`; `stage` ist einer der CodePipeline-Stage-Codes `FKTE`, `FKTF`, `JURJ`, `JURP`, `SVTS` oder `VPTV` |

Alle anderen sichtbaren Verzeichnisse direkt unter der Repositorywurzel werden
als Projekte synchronisiert und paketiert; versteckte Verzeichnisse werden
ignoriert. Die bestehende JCL verwendet `stage` als CodePipeline-`LEVEL`. Ein
zusätzlicher Levelwert wird nicht eingeführt. Fachlich bestätigte Änderungen
der Mandantenzuordnung werden mit der Konfiguration versioniert. Zugangsdaten
gehören nicht in diese Datei.

Die FI ist für die unfragmentierten Basisprojekte maßgeblich, `mtext-autonom` für
`LOMS_Autonom`. Die übrigen Mandanten enthalten Fragmentprojekte mit dem
Mandantenkürzel in eckigen Klammern. Testdatenprojekte werden nach Git
übernommen, aber über `excluded_projects` nicht ausgeliefert.

### Zentrale Releaselinienzuordnung

Die zentrale Datei
[`config/releaselinien.json`](../../mtext-actions/config/releaselinien.json)
enthält rollierend die Zuordnung von genau drei aktiven fachlichen
Releaselinien zur jeweiligen technischen M/Text-Linie und zum zugehörigen
Hostprofil. Ihr aktueller Inhalt ist:

```json
{
  "R260": {"mtext_linie": "en03", "hostprofil": "JUR"},
  "R261": {"mtext_linie": "en01", "hostprofil": "FKT"},
  "R270": {"mtext_linie": "en02", "hostprofil": "JUR"}
}
```

Die beiden Felder heißen verbindlich `mtext_linie` und `hostprofil`. Das
genannte Hostprofil muss in der jeweiligen `.github/config.json` vorhanden
sein.

Vor einer Verteilung oder Lieferung wird die gesamte benötigte Konfiguration
geprüft. Unbekannte Mandanten, Releaselinien, Zielumgebungen oder zusätzliche
Konfigurationsfelder führen zu einem Fehler. Es gibt keine stillschweigende
Rückfallregel auf Werte der FI. Den Auslöser des Config-Checks beschreibt Kapitel
8.

## 10. FULL- und DELTA-Lieferungen

Ein Tag mit der Endung `.100`, zum Beispiel `R261.100`, erzeugt eine
vollständige Lieferung aller sichtbaren, nicht ausgeschlossenen Projekte.

Jeder andere gültige Release-Tag derselben Releaselinie erzeugt ein
kumulatives DELTA gegen den `.100`-Tag. Ein Tag `R261.108` enthält somit alle
neuen, geänderten und gelöschten Dateien seit `R261.100`. Frühere
DELTA-Lieferungen müssen nicht lückenlos eingespielt worden sein.
Die `.100`-Basis muss in der Git-Historie ein Vorgänger des Ziel-Tags sein.
Git bestimmt die geänderten, neuen, gelöschten und umbenannten Pfade mit
`git diff`; Python erzeugt daraus das historisch kompatible TAR-Archiv, die
Löschliste und die Informationsdatei mit reproduzierbaren Dateimetadaten.

### CodePipeline-Elemente

Für jedes ausgelieferte Projekt entsteht ein CodePipeline-Element. Sein Name
ist zugleich der Mainframe-Member und setzt sich aus Mandantenkürzel,
historischem Liefercode und Lieferart zusammen:

```text
<Mandantenkürzel><Liefercode><F|D>
```

Die Archivdatei trägt denselben Namen mit der Endung `.tgz`. Beispielsweise
bezeichnet `BYAUTOND` das DELTA-Element für `LOMS_Autonom[BY]` und
`FIBASISF` das FULL-Element für `LOMS_Basis` des Mandanten mit dem Kürzel `FI`.

| Projekt | Liefercode |
|---|---|
| `Configuration` | `CONFI` |
| `Fonts` | `FONTS` |
| `LOMS_Framework` | `FRAME` |
| `LOMS_Basis` | `BASIS` |
| `LOMS_PKA` | `PKA` |
| `LOMS_Autonom` | `AUTON` |

Bei Fragmentprojekten wird für die Namensbildung das Mandantenkürzel in
eckigen Klammern entfernt. `LOMS_Autonom[BY]` verwendet daher die Zuordnung
`LOMS_Autonom` → `AUTON`; daraus entstehen `BYAUTONF` und `BYAUTOND`. Ein
FULL-Element enthält den vollständigen Projektbaum. Ein DELTA-Element enthält
die kumulativ seit `.100` neuen und geänderten Dateien sowie die Löschliste.
Die `_INFO_...txt` gehört zum Releasebeleg, wird aber nicht als
CodePipeline-Element registriert. Liefercodes und Elementnamen sind zentral
festgelegt und keine Felder der Mandantenkonfiguration.

### Historischer Übergabestand unter `/nfs/mtext/trans`

Der Jenkins-Ablauf kopiert jedes erzeugte Projektpaket nach
`/nfs/mtext/trans` und übergibt dasselbe Paket anschließend per FTP und JES an
den Mainframe. Daneben legt er eine lesbare Informationsdatei ab. Der
historische Bestand ist deshalb sowohl Beleg für den Mainframe-Vertrag als auch
Referenz für Dateinamen, Archivstruktur und Informationsinhalt.

Der logische Bestand folgt diesem Schema:

```text
/nfs/mtext/trans/
  <Mandantenkürzel><Liefercode><F|D>.tgz
  _INFO_<Mandantenkürzel>-<Projekt>-<FULL|DELTA>-<Release>-<Vorrelease>.txt
```

Vier seinerzeit ausgewertete Referenzdateien belegen zwei reale Lieferungen:

| Referenzdatei | Bedeutung und belegter Inhalt |
|---|---|
| `BYAUTOND.tgz` | DELTA für `LOMS_Autonom[BY]`; enthält die seit dem `.100`-Stand neuen und geänderten Ressourcen sowie `BYAUTOND.txt` als Löschliste |
| `_INFO_BY-LOMS_Autonom[BY]-DELTA-R260.234-R260.178.txt` | Informationsdatei zum DELTA; enthält den direkten Vergleich `R260.178` zu `R260.234` und die vollständige TAR-Inhaltsliste |
| `OSAUTONF.tgz` | FULL für `LOMS_Autonom[OS]`; enthält den vollständigen Projektbaum des FULL-Releases |
| `_INFO_OS-LOMS_Autonom[OS]-FULL-R260.100-R251.510.txt` | Informationsdatei zum FULL; enthält den direkten Vergleich `R251.510` zu `R260.100` und die vollständige TAR-Inhaltsliste |

Die innere Struktur unterscheidet sich nach Lieferart:

```text
OSAUTONF.tgz
  ./LOMS_Autonom[OS]/
    <vollständiger Projektbaum>

BYAUTOND.tgz
  LOMS_Autonom[BY]/
    <seit R260.100 neue oder geänderte Ressourcendateien>
  BYAUTOND.txt
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
Beim BY-Beispiel nennt die Informationsdatei 14 Änderungen zwischen
`R260.178` und `R260.234`; das DELTA-Archiv enthält dagegen 33 Dateien
einschließlich der Löschliste. Auch die Löschliste enthält Pfade, die nicht im
direkten Vorrelease-Vergleich vorkommen. Der Paketinhalt und die Löschliste
werden somit kumulativ gegen `R260.100` gebildet. Die Informationsdatei
dokumentiert nur die Änderungen gegen `R260.178` und bestimmt den Paketinhalt
nicht.

Die Paketnamen unter `trans` enthalten keinen Release-Tag. Eine neue Lieferung
desselben Mandanten, Projekts und Liefertyps überschreibt daher das zuvor dort
liegende Archiv. Der sichtbare Archivbestand ist die jeweils letzte kumulative
Lieferung und keine Folge inkrementeller DELTA-Pakete. Der Releasebezug steht
im Namen der Informationsdatei.

Das historische FULL verwendet TAR-Pfade mit `./`-Präfix, das DELTA verwendet
Pfade ohne dieses Präfix. Besitzer, Gruppe, Modus und Zeitstempel stammten aus
dem Jenkins-Arbeitsbereich. Die GitHub-Automatisierung behält die logischen
Pfade bei und setzt die Dateimetadaten reproduzierbar fest.

### Actions-Artefakt und Manifest

Im Zielablauf ersetzt das je Workflow-Lauf aufbewahrte Actions-Artefakt mit
Manifest und Prüfsummen das feste Verzeichnis `trans` als technische Grenze
zwischen Paketbau und Mainframe-Übergabe. Das veröffentlichte Paket behält
seinen historisch festgelegten Dateinamen, seinen fachlichen Inhalt und seine
logische Archivstruktur.

Ein DELTA-Artefakt für ein Projekt der FI enthält beispielsweise:

```text
Release-Artefakt/
  FIBASISD.tgz
  _INFO_FI-LOMS_Basis-DELTA-R261.108-R261.107.txt
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
dem unveränderten Paket wiederholt werden. Das Paket wird dabei nicht neu
gebaut.

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
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden technisch übergeben. Der spätere Mainframe-Job kann trotzdem noch fehlschlagen und wird durch das Release-Team auf dem Host kontrolliert. |

Ein HTTP-Fehler des M/Text-Adapters gilt immer als fehlgeschlagener Lauf. Ein
Status zwischen 200 und 299 bestätigt nur die unmittelbare Annahme der
Anfrage.

Die Automatisierung fragt weder bei M/Text noch auf dem Mainframe nach dem
späteren fachlichen Endstatus.

## 13. Qualitätsmerkmale, Grenzen und weitere Ausbaustufe

### Tragende Qualitätsmerkmale

Gemessen an modernen Praktiken für GitHub Actions und automatisierte
Softwarelieferungen ist der Kern der Lösung qualitativ stark: Der Ablauf ist
nachvollziehbar, die gemeinsame Logik zentralisiert, die externe Wirkung
begrenzt und die Lieferung reproduzierbar. Die noch offenen Punkte betreffen
überwiegend die konkrete Plattformkonfiguration der FI, den gewählten
M/Text-Transport und die betriebliche Abnahme.

Die folgenden Eigenschaften gelten für alle Mandanten:

| Qualitätsmerkmal | Umsetzung und Nutzen |
|---|---|
| Durchgängiger Gesamtablauf | Die fachliche Kette führt geradlinig von Entwicklung über Abnahme und Bereitstellung zum Release-Tag, zum geprüften Artefakt und erst nach Freigabe zur externen Übergabe. Jeder Übergang besitzt einen eindeutigen Auslöser und ein überprüfbares Ergebnis; verdeckte Nebenwege oder parallele Lieferlogiken entstehen nicht. |
| Wartbare Automatisierung in `mtext-actions` | Die Mandanten-Workflows enthalten nur Trigger, feste Zielzuordnung und den Aufruf der freigegebenen zentralen Workflows in `mtext-actions`. Eine gemeinsame Python-Implementierung, wenige CLI-Kommandos, die zentrale Releaselinienzuordnung und getrennte Konfigurationen begrenzen Abhängigkeiten und Änderungsstellen. Jobs, Freigabegrenzen und externe Wirkung bleiben in den Workflows sichtbar; neue Mandanten benötigen keine Kopie der Fachlogik. |
| Eindeutige und reproduzierbare Lieferung | Jeder Lauf verarbeitet einen vollständigen Commit-SHA. Mit der Freigabe bilden Tagname und Ziel-Commit die dem Bereitstellungsbranch zugeordnete, unveränderliche Release-Identität. Gleiche Eingaben erzeugen bytegleiche Archive; historische Namen, Verzeichnisstrukturen, Löschlisten und JCL-Verträge bleiben erhalten. |
| Getrennte Verantwortlichkeiten | Mandantenressourcen und -konfiguration liegen in den Mandanten-Repositories, die gemeinsame Implementierung in `mtext-actions`, Schutz und Freigaben in GitHub und die Runnerbereitstellung bei der FI. Dadurch bleiben fachliche Pflege, die Automatisierung in `mtext-actions` und Plattformbetrieb getrennt. |
| Minimale Berechtigungen und kontrollierte Wirkung | Die fachlichen Workflows erhalten nur Leserechte auf Repositoryinhalte. Ausschließlich der manuelle Einrichtungsworkflow besitzt über sein geschütztes Environment eine auf die vorgesehenen Repositories begrenzte Schreibberechtigung und nimmt nur `.github/workflows` in seine Commits auf. Zugangsdaten liegen in GitHub Environments und werden erst im jeweils berechtigten Job verwendet. Konfigurationsprüfung und Paketbau benötigen keinen Zielsystemzugriff; Synchronisation und Mainframe-Übergabe erfolgen nur in den vorgesehenen Jobs und werden je Ziel serialisiert. |
| Geprüfte Build-Publish-Grenze | Der Paketbau ist von der Mainframe-Übergabe getrennt. Das einmal erzeugte Artefakt wird unmittelbar vor der externen Wirkung anhand von Pfad, Größe und SHA-256 geprüft. |
| Kleine technische Angriffsfläche | Die Anwendung verwendet nur die Python-Standardbibliothek, führt Git ohne Shell aus und prüft Symlinks sowie externe Werte an ihren Systemgrenzen. |
| Überprüfbarer Vertrag | Automatisierte Tests decken Konfiguration, Git-Bezüge, FULL und DELTA, Manifest, JCL, Ressourcensynchronisation, FTP/JES und Workflowgrenzen ab. Stabile Statuswerte unterscheiden die Fehlerklassen. |
| Ausführliche, rollengerechte Dokumentation | Zielbild, Ablaufdiagramm, Benutzeranleitung, Workflow-README, fachlicher Vertrag, Migrations-Runbook und offene Schritte beschreiben Architektur, Bedienung, Betrieb und Einführung aus jeweils passender Sicht. Entscheidungen und Restarbeiten bleiben nachvollziehbar, ohne dass Anwender den Python-Code verstehen müssen. |

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
