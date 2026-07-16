# Zielbild für die Ablösung von Jenkins und SVN

**Dokumenttyp:** Verbindliches fachliches und technisches Zielbild

**Geltungsbereich:** Verteilung von M/Text-Ressourcen und Bereitstellung von
Mainframe-Lieferungen

Dieses Dokument beschreibt, wie Git und GitHub Actions den bisherigen Prozess
mit SVN und Jenkins ablösen sollen. Es konzentriert sich auf die dauerhaften
fachlichen und technischen Entscheidungen. Der aktuelle Arbeitsstand steht
unter [Nächste Schritte](./Naechste_Schritte.md), die Bedienung unter
[Benutzeranleitung](./Benutzeranleitung.md). Einzelheiten zur Implementierung
stehen in den README-Dateien der beiden Repositories.

Die
[Soll-Grafik GitHub Actions/Git](../../Architektur_Soll_GitHub_Actions_Git.drawio)
zeigt den Ablauf von einer Änderung bis zur M/Text-Verteilung oder
Mainframe-Übergabe. Die
[Ist-Grafik Jenkins/SVN](../../Architektur_Ist_Jenkins_SVN.drawio) dokumentiert
den bisherigen Prozess.

## 1. Kurzfassung

SVN wird durch Git und Jenkins durch GitHub Actions ersetzt. Dafür wird
voraussichtlich ab November oder Dezember 2026 ein SVN-Abzug nach Git
übernommen und in einer nichtproduktiven GitHub-Umgebung erprobt. Während
dieser Testphase bleibt der bisherige Prozess produktiv. Unmittelbar vor der
für Januar 2027 geplanten Produktivsetzung wird der dann freigegebene
SVN-Endstand nach Git übertragen. Danach sind Git und GitHub Actions für diesen
Prozess führend; eine dauerhafte Synchronisation mit SVN gibt es nicht.

Jeder Mandant erhält ein eigenes Repository mit seinen M/Text-Ressourcen und
seiner Konfiguration. Die gemeinsame Automatisierung liegt in einem zentralen
Repository. So bleiben die Mandantendaten getrennt, während alle Mandanten
dieselben geprüften Abläufe verwenden.

Eine Änderung durchläuft weiterhin die Stufen Entwicklung, Abnahme und
Bereitstellung:

1. Ein Push nach `Rnnn/Entwicklung` verteilt den Stand an das
   M/Text-Entwicklungssystem.
2. Nach fachlicher Prüfung wird derselbe Stand nach `Rnnn/Abnahme` übernommen
   und an das M/Text-Abnahmesystem verteilt.
3. Freigegebene Änderungen werden nach `Rnnn/Bereitstellung` übernommen. Der
   Push allein erzeugt noch keine Mainframe-Lieferung.
4. Erst ein Release-Tag wie `R261.108` baut die Lieferung. Vor der technischen
   Übergabe an den Mainframe ist eine manuelle Freigabe erforderlich.

Die bestehenden Schnittstellen bleiben zunächst erhalten: M/Text wird über
den vorhandenen Adapter angesprochen, die Mainframe-Übergabe erfolgt weiterhin
per FTP und JES. GitHub Actions kann dabei nur die unmittelbare Annahme durch
die Schnittstelle bestätigen. Der spätere fachliche Abschluss im Zielsystem
ist nicht Bestandteil dieser ersten Ausbaustufe.

## 2. Verbindliche Rahmenbedingungen

- Der produktive Wechsel von SVN/Jenkins zu Git/GitHub Actions erfolgt zu
  einem festgelegten Zeitpunkt. Danach gibt es keinen parallelen produktiven
  Lieferbetrieb.
- Das bisherige Jenkins-Skript wird nicht weiterentwickelt oder technisch
  portiert. Nur die weiterhin benötigten Regeln, Zuordnungen und
  Übergabeverfahren werden übernommen.
- Jeder Mandant erhält ein eigenes privates GitHub-Repository. Namen und
  grundsätzlicher Aufbau orientieren sich an den bisherigen
  Mandantenstrukturen.
- Die gemeinsame Automatisierung wird zentral durch die FI verwaltet und von
  den Mandanten-Repositories in einer ausdrücklich festgelegten Version
  verwendet.
- `mtext-actions` ist ein privates Repository. Direkten Zugriff erhalten nur
  die zentralen Automatisierungsverantwortlichen; Text-Entwickler der
  Mandanten werden dort nicht als Repositorymitglieder berechtigt.
- Jeder Lauf verarbeitet genau einen eindeutig bestimmten Git-Stand. Seine
  technische Kennung ist der Commit-SHA.
- Der Mandant ergibt sich aus dem Repository und seiner Konfiguration. Er kann
  beim Start eines Laufs nicht frei gewählt werden.
- Aktive Releaselinien erhalten getrennte Branches für Entwicklung, Abnahme
  und Bereitstellung. Derzeit sind dies `R260`, `R261` und `R270`.
- Geheimnisse und Zugangsdaten werden nicht in Git gespeichert, sondern über
  die dafür vorgesehenen GitHub-Einstellungen bereitgestellt.
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

- FULL- und DELTA-Pakete behalten ihre historisch festgelegten Dateinamen. Die
  dafür benötigte Projektkennung wird zentral aus dem freigegebenen
  Projektnamen abgeleitet und kann nicht im Mandanten-Repository geändert
  werden.
- Ein DELTA-Paket enthält eine Löschliste mit dem Namen
  entsprechend der bisherigen Namensregel.
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
| Mandanten-Repository | M/Text-Ressourcen, Projektzuordnungen, mandantenspezifische technische Übergabewerte und dünne Workflows |
| Zentrales Repository `mtext-actions` | Gemeinsame Prüfungen, Synchronisation, Paketbau und Mainframe-Übergabe |
| GitHub Actions | Ausführung der Abläufe, Freigaben und Protokollierung |
| Self-hosted Runner | Ausführung innerhalb des internen Netzes und Zugriff auf M/Text, Netzlaufwerk und Mainframe |

Ein Mandanten-Repository enthält ausschließlich die Ressourcen und Angaben
des jeweiligen Mandanten. Das zentrale Repository enthält keine
Mandantenressourcen, sondern nur die gemeinsam verwendete Automatisierung.

Mandanten-Repositories dürfen die freigegebenen wiederverwendbaren Workflows
über die GitHub-Actions-Zugriffsrichtlinie aufrufen. Diese technische Freigabe
erteilt ihren Benutzern keinen direkten Zugriff auf `mtext-actions`. Die
Ausgaben der aufgerufenen Jobs erscheinen jedoch in den Workflow-Logs des
Mandanten-Repositories. Deshalb werden Logs grundsätzlich als
mandantensichtbar behandelt und enthalten weder Secrets noch unnötige interne
Details.

Damit die technische Freigabe nicht über veränderte aufrufende Workflows
zweckentfremdet werden kann, dürfen Text-Entwickler der Mandanten keine Dateien
unter `.github/workflows/` ändern oder neu anlegen. Ein Push-Ruleset schützt
diesen Pfad auf allen Branches; nur die zentralen
Automatisierungsverantwortlichen erhalten einen kontrollierten Bypass.
`config/mandant.json` wird ebenfalls von der normalen Ressourcenpflege
getrennt und darf nur durch den benannten technischen Verantwortlichenkreis
geändert werden.

Die Text-Entwickler bearbeiten Briefressourcen in der M/Text Workbench und
verwenden deren integrierten Git-Client für Commit und Push. GitHub im Browser
dient der Laufkontrolle, manuellen Wiederholungen, Freigaben, Release-Tags und
den weitergehenden Verwaltungsaufgaben. Die tägliche Ressourcenarbeit setzt
keine Git-Kommandozeile voraus.

Für die gezielte Übernahme einzelner Änderungen zwischen den Stufen erhalten
die dafür berechtigten Text-Entwickler zusätzlich einen geeigneten Git-Client.
Das konkrete Produkt, seine Bereitstellung und der verbindliche Bedienweg
werden vor dem Pilotbetrieb festgelegt und abgenommen.

Die Berechtigungen werden je Mandanten-Repository vergeben. Jeder Mandant
benennt ein Release-Team, das als einzige reguläre Gruppe direkt nach
`Rnnn/Bereitstellung` pushen und neue Release-Tags anlegen darf. So können die
Verantwortlichen je Mandant unterschiedlich sein, ohne die gemeinsame
Automation zu verzweigen. Force-Pushes und das Löschen von Stufenbranches
bleiben verboten. Bereits angelegte Release-Tags dürfen auch vom Release-Team
nicht verändert oder gelöscht werden.

Für jeden Lauf checkt GitHub Actions sowohl den ausgewählten Stand des
Mandanten-Repositories als auch eine festgelegte Version der zentralen
Automatisierung aus. Dadurch ist später nachvollziehbar, welche Quellen und
welche Automatisierung verwendet wurden.

Die Verteilung nach Entwicklung oder Abnahme überträgt immer den vollständigen
konfigurierten Projektstand des ausgewählten Commits. FULL und DELTA betreffen
nur die spätere Mainframe-Lieferung und nicht die M/Text-Synchronisation.

Der M/Text-Adapter und der bestehende Prozess auf dem Mainframe-Zielsystem
IZE9 bleiben zunächst unverändert. Mit der bestätigten technischen Übergabe
endet der hier beschriebene GitHub-Prozess. Das anschließende
KM-Bereitstellungsverfahren bis zur Produktion liegt außerhalb dieses
Zielbilds.

## 5. Repositories und aktueller Entwicklungsstand

Ein Mandanten-Repository folgt diesem Grundaufbau:

```text
mtext-<mandant>/
  .github/workflows/
    validate-config.yml
    sync-resources.yml
    release.yml
  config/
    mandant.json
  <M/Text-Projekte>
```

Das zentrale Repository enthält die wiederverwendbaren Workflows, die
gemeinsame Python-Anwendung, geprüfte Konfigurationsregeln, das JCL-Template
und die automatisierten Tests:

```text
mtext-actions/
  .github/workflows/
  config/
  src/lbs_delivery/
  templates/
  tests/
```

`mtext-fi` dient als Muster für die Mandanten-Repositories. In
`config/mandant.json` sind derzeit die fünf FI-Projekte aufgeführt, die
synchronisiert und in Releasepakete aufgenommen werden. `LOMS_Testdaten` soll
ebenfalls in das Repository übernommen werden, ist aber wie bisher nicht
Bestandteil der Synchronisation oder der Releasepakete.

Die Workflows im Mandanten-Repository legen nur Auslöser und explizite
Zielstufen fest. Die Verarbeitung erfolgt durch die zentralen Workflows aus
`mtext-actions`. Im aktuellen Entwicklungsstand enthalten die Verweise auf
diese zentralen Workflows noch eine nicht lauffähige Folge aus Nullen als
Platzhalter.

Im gemeinsamen Workspace liegen `mtext-fi` und `mtext-actions` derzeit als
Verzeichnisse nebeneinander. Im Zielbetrieb werden sie als eigenständige
GitHub-Repositories unter `j517120/mtext-fi` und `j520730/mtext-actions`
geführt. Nach fachlicher Bestandsaufnahme und Freigabe werden auch
`mtext-autonom`, `mtext-by`, `mtext-lh`, `mtext-nw`, `mtext-os` und
`mtext-sa` nach diesem Muster eingerichtet.

Vor dem ersten Integrationslauf wird der Platzhalter in allen
Mandanten-Workflows durch die vollständige Kennung einer freigegebenen Version
von `mtext-actions` ersetzt. GitHub Enterprise muss den
Mandanten-Repositories außerdem den Zugriff auf die zentralen Workflows
erlauben, ohne deren Benutzer direkt am zentralen Repository zu berechtigen.
Beides wird mit einem nichtproduktiven Lauf geprüft.

## 6. Branches, Weitergabe und Auslöser

Jede aktive Releaselinie besitzt drei Branches, zum Beispiel:

```text
R260/Entwicklung
R260/Abnahme
R260/Bereitstellung
```

Damit ist aus jedem Branchnamen eindeutig erkennbar, zu welcher Releaselinie
und Stufe er gehört. Ein gemeinsamer Stufenbranch mit mehreren
Releaseverzeichnissen, wie er in SVN verwendet wurde, wird nicht fortgeführt.

Für größere oder gemeinsam bearbeitete Änderungen kann ein Feature-Branch
verwendet werden. Er löst keine Verteilung aus. Kleine Änderungen dürfen auch
direkt auf dem Entwicklungsbranch entstehen. Ein Feature-Branch ist keine
zusätzliche fachliche Stufe.

Ein Push nach `Rnnn/Entwicklung` oder `Rnnn/Abnahme` startet automatisch die
M/Text-Verteilung für die entsprechende Stufe. Beim Übergang zur nächsten
Stufe wird eine fachlich ausgewählte Änderung per Cherry-Pick übernommen. Der
Cherry-Pick erzeugt auf dem Zielbranch einen neuen Commit mit einer neuen SHA;
weitergegeben wird dieselbe Änderung, nicht derselbe Commit. Die
vollständige Quell-SHA wird nach einer verbindlichen Konvention im neuen
Ziel-Commit dokumentiert. Die Workflow-Trigger verwenden das allgemeine
Namensmuster `Rnnn/<Stufe>`; ob eine konkrete Linie aktiv ist, entscheidet
ausschließlich die zentrale Deploymentkonfiguration.

Ein Push nach `Rnnn/Bereitstellung` erzeugt noch keine Lieferung. Erst ein Tag
im Format `Rnnn.nnn` startet den Paketbau. Dabei wird geprüft, ob der Tag zur
angegebenen Releaselinie gehört und vom Bereitstellungsbranch erreichbar ist.
Der Tag ist danach die unveränderliche Identität dieser Lieferung und wird
durch Tag-Rulesets gegen Änderung, Force-Push und Löschung geschützt.

Der zusätzliche Git-Client für die Auswahl und Übernahme einzelner Änderungen
nach Abnahme und Bereitstellung wird vor dem Pilotbetrieb ausgewählt,
bereitgestellt und praktisch abgenommen. Ein direkter Cherry-Pick ist über die
GitHub-Weboberfläche allein nicht verfügbar. Soll der erweiterte Ablauf später
vollständig im Browser stattfinden, ist ein kurzlebiger Auswahlbranch mit
einem normalen Pull Request der bevorzugte GitHub-native Weg. Dafür ist kein
eigener fachlicher Validate-Workflow erforderlich. Eine alternativ eingeführte
schreibende Automation müsste einen eigenen, ausdrücklich freizugebenden
Sicherheitsvertrag erhalten.

Die Mandanten-Repositories erhalten keinen zusätzlichen `main`-Branch. Als
Default Branch dient der Entwicklungsbranch der aktuell führenden Linie,
zunächst `R261/Entwicklung`. Beim Wechsel der führenden Linie wird diese
Einstellung manuell angepasst.

Manuelle Wiederholungen sind möglich, müssen aber denselben Commit verwenden.
Vor einer erneuten M/Text-Verteilung prüft der Workflow, ob dieser Commit zum
ausgewählten Stufenbranch gehört.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Die verwendeten
GitHub-Actions-Bausteine und der interne Runner müssen vor der Aktivierung auf
dieser konkreten Version geprüft werden.

## 7. Konfiguration

Jedes Mandanten-Repository enthält seine eigene Konfiguration. Sie beschreibt
unter anderem:

- den Mandanten und das zugehörige Repository,
- die zu verarbeitenden Projekte,
- die für den Mandanten variablen technischen Übergabewerte.

Diese `config/mandant.json` ist ein versionierter Bestandteil des fachlichen
Lieferstands und keine frei veränderbare Laufzeitkonfiguration. `projects`
bildet die gemeinsame Projekt-Allowlist für Synchronisation und Release;
linien- oder stufenspezifische Zusatzprojekte sind nicht vorgesehen. Dadurch
bleibt auch bei einem späteren Release eines älteren Tags nachvollziehbar,
welche Projekte und technischen Übergabewerte zu genau diesem Stand gehörten.
Eine Zentralisierung außerhalb des Mandanten-Repositories würde diese
gemeinsame Versionierung von Ressourcen und Mandantenmapping auflösen und ist
deshalb nicht vorgesehen.

Zu den mandantenspezifischen Übergabewerten gehören das Subsystem sowie je
Übergabeprofil Assignment und fachlicher Stage-Code. Die bestehende JCL nennt
diesen Stage-Code historisch `LEVEL`; ein zusätzlicher Levelwert wird nicht
eingeführt. Diese Werte dürfen bei einer fachlich bestätigten Änderung der
Mandantenzuordnung versioniert in `mandant.json` angepasst werden. Der zentral
verwaltete Test-/Produktionswert und Zugangsdaten gehören nicht in diese Datei.

Die zentrale Konfiguration beschreibt die gemeinsamen Releaselinien,
Zielstufen, M/Text-Adressen und Dateinamensregeln. Derzeit gelten folgende
Zuordnungen:

| Releaselinie | Technische M/Text-Linie |
|---|---|
| `R260` | `en03` |
| `R261` | `en01` |
| `R270` | `en02` |

Vor einer Verteilung oder Lieferung wird die gesamte benötigte Konfiguration
geprüft. Unbekannte Mandanten, Releaselinien, Zielumgebungen oder zusätzliche
Konfigurationsfelder führen zu einem Fehler. Es gibt keine stillschweigende
Rückfallregel auf FI-Werte.

Zusätzlich startet jede Änderung an `config/mandant.json` bereits beim Push
einen nebenwirkungsfreien Config-Check. Er validiert Schema,
Repository-Identität, fachliche Eindeutigkeit und interne Querverweise der
Deploymentkonfiguration, verwendet aber weder Secrets noch Environments oder
externe Zielzugriffe. Da der derzeitige Prozess keine Pull Requests
voraussetzt, liefert der Check bewusst nur frühes Feedback und ist kein
technisch erzwungenes Gate. Config-Änderungen werden fachlich mit den benannten
Mandanten- und Betriebsverantwortlichen abgestimmt. Falls Config-Änderungen
später über Pull Requests freigegeben werden, kann `config/mandant.json`
zusätzlich einem verbindlichen Code-Owner-Verfahren unterstellt werden.

FI ist für die unfragmentierten Basisprojekte maßgeblich, `mtext-autonom` für
`LOMS_Autonom`. Die übrigen Mandanten enthalten Fragmentprojekte mit dem
Mandantenkürzel in eckigen Klammern. Welche Projekte in einem Repository
liegen und welche davon tatsächlich synchronisiert oder paketiert werden,
kann sich unterscheiden. Testdatenprojekte werden zwar nach Git übernommen,
aber nicht ausgeliefert.

Noch nicht vollständig inventarisierte Mandanten werden erst nach fachlicher
Prüfung ihrer Projekte und Zuordnungen für den produktiven Betrieb
freigegeben.

## 8. FULL- und DELTA-Lieferungen

Ein Tag mit der Endung `.100`, zum Beispiel `R261.100`, erzeugt eine
vollständige Lieferung aller Projekte der Mandantenkonfiguration.

Jeder andere gültige Release-Tag derselben Releaselinie erzeugt ein
kumulatives DELTA gegen den `.100`-Tag. Ein Tag `R261.108` enthält somit alle
neuen, geänderten und gelöschten Dateien seit `R261.100`. Frühere
DELTA-Lieferungen müssen nicht lückenlos eingespielt worden sein.

Zu jeder Lieferung wird ein Manifest erzeugt. Diese Begleitdatei nennt unter
anderem Mandant, Release, Quellstand, enthaltene Dateien und deren Prüfsummen.
Vor der Mainframe-Übergabe werden die Dateien erneut damit verglichen. So wird
sichergestellt, dass genau das zuvor gebaute und freigegebene Paket übergeben
wird.

Ein fehlgeschlagener Übergabeversuch kann innerhalb desselben GitHub-Laufs mit
dem unveränderten Paket wiederholt werden. Das Paket wird dabei nicht neu
gebaut.

Bei der Migration werden für jede aktive Releaselinie mindestens der
`.100`-Stand und alle späteren Tags übernommen. Aus einem bisherigen SVN-Namen
wie `R260.101_MText` wird der Git-Tag `R260.101`. Die Übernahme älterer
Historie, SVN-Eigenschaften, Autoren und großer Dateien wird im
Migrationskonzept gesondert behandelt.

## 9. Mainframe-Übergabe und JCL

Die JCL liegt künftig als eigene versionierte Template-Datei vor. Änderungen
an der Mainframe-Ansteuerung sind dadurch sichtbar und können unabhängig vom
Programmcode geprüft werden.

Für jede Übergabe werden ausschließlich die im bisherigen Verfahren
benötigten, geprüften Werte in das Template eingesetzt. Historisch feste Werte
bleiben fest; nur tatsächlich mandantenspezifische Zuordnungen werden aus der
Mandantenkonfiguration übernommen. Fehlende, unbekannte oder syntaktisch
unzulässige Werte führen vor der Übergabe zu einem Fehler. Zugangsdaten werden
weder in die JCL noch in die Protokolle geschrieben.

Der Release-Workflow trennt den Paketbau von der Mainframe-Übergabe. Der
Paketbau benötigt keinen Zugriff auf das Zielsystem. Erst der Übergabeschritt
erhält Zugriff auf die geschützte Umgebung `Bereitstellung` und wartet dort
auf eine manuelle Freigabe.

Übergaben desselben Mandanten werden nacheinander ausgeführt. Verschiedene
Mandanten können gleichzeitig liefern.

## 10. Status und Fehler

Die Lösung meldet nur den Status, den sie selbst sicher feststellen kann:

| Status | Bedeutung |
|---|---|
| `CONFIG_VALIDATED` | Mandanten- und Deploymentkonfiguration wurden ohne externen Zielzugriff technisch geprüft. |
| `VALIDATION_FAILED` | Eingaben oder Konfiguration sind ungültig. Es wurde noch kein Zielsystem angesprochen. |
| `SOURCE_FAILED` | Der angegebene Commit, Branch oder Tag konnte nicht eindeutig aufgelöst werden. |
| `RESOURCE_TRANSFER_FAILED` | Die Ressourcen konnten nicht in den Übergabebereich für M/Text geschrieben werden. |
| `ADAPTER_FAILED` | Der M/Text-Adapter war nicht erreichbar oder hat die Anfrage abgelehnt. |
| `ADAPTER_ACCEPTED` | Der M/Text-Adapter hat die Anfrage unmittelbar angenommen. Dies ist noch kein fachlicher Endstatus. |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder Manifest konnten nicht korrekt erstellt werden. |
| `ARTIFACT_READY` | Das Releasepaket wurde vollständig erstellt und geprüft. |
| `MAINFRAME_TRANSFER_FAILED` | Die unmittelbare FTP-/JES-Übergabe ist fehlgeschlagen. |
| `MAINFRAME_SUBMITTED` | Paket und JCL wurden technisch übergeben. Der spätere Mainframe-Job kann trotzdem noch fehlschlagen. |

Ein HTTP-Fehler des M/Text-Adapters gilt immer als fehlgeschlagener Lauf. Ein
Status zwischen 200 und 299 bestätigt nur die unmittelbare Annahme der
Anfrage.

Die erste Ausbaustufe fragt weder bei M/Text noch auf dem Mainframe nach dem
späteren fachlichen Endstatus.
