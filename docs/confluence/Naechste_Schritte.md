# Nächste Schritte

**Zweck:** Operative Restarbeiten bis zum Test-Parallelbetrieb

**Bezug:** [Zielbild](./Zielbild_GitHub_Actions_Git.md)

**Bedienung nach Aktivierung:** [Benutzeranleitung](./Benutzeranleitung.md)

**Migration und Produktivsetzung:**
[Migrations- und Cutover-Runbook](./Migration.md)

**Ablauf:** [Soll-Architektur Ablaufdiagramm](../../Architektur_Soll_GitHub_Actions_Git.drawio)

Diese Seite ist die Arbeitsliste für die erstmalige Einrichtung und die
nichtproduktive Abnahme. Bestätigte Punkte bleiben zur Orientierung sichtbar.
Architekturbegründungen, Bedienabläufe und das spätere Cutover stehen in den
verlinkten Dokumenten.

Wiederholbare technische Einstellungen werden nicht als Klickanleitung
abgearbeitet. Ein zentrales, idempotentes Einrichtungskommando wendet sie über
die GitHub-Enterprise-API an, zeigt Abweichungen vorab und prüft den erreichten
Zustand. Manuell bleiben fachliche Entscheidungen, Rollenbesetzung,
Zugangsdatenübergabe und praktische Abnahmen.

## 1. GitHub-Grundaufbau herstellen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Einrichtungsautomation erstellen und im Testbereich abnehmen | Ein versioniertes Kommando besitzt einen reinen Prüfmodus und einen Anwendungsmodus. Es verwaltet die vereinbarten Repositoryeinstellungen, Branches, Default Branches, Rulesets, Environments, Actions-Zugriffe und die zentrale Workflowversion für alle Mandanten. Secret-Werte bleiben außerhalb; vorhandene Secret-Namen und nicht automatisierbare Voraussetzungen werden nur geprüft |
| offen | Zentrales Repository `j520730/mtext-actions` und privates FI-Repository `j517120/mtext-fi` auf GitHub Enterprise anlegen beziehungsweise die lokalen Stände übernehmen | Das zentrale Repository ist nur für das Automatisierungsteam direkt zugänglich. Das FI-Repository enthält Ressourcen, Mandantenkonfiguration und schlanke Workflows |
| bestätigt | Zentrale Implementierung gegen den fachlichen Vertrag prüfen | Die vier CLI-Kommandos, FULL und DELTA, Artefaktprüfung, JCL, FTP-/JES-Vertrag, Ressourcensynchronisation und Workflowgrenzen sind durch Akzeptanztests abgedeckt |
| offen | Branches der aktiven Stages und Default Branch einrichten | Die Einrichtungsautomation stellt für `R260`, `R261` und `R270` jeweils die Branches `Entwicklung`, `Abnahme` und `Bereitstellung` sowie zunächst `R261/Entwicklung` als Default Branch her und weist Abweichungen aus |
| offen | Zentrale Workflowversion und repositoryübergreifenden Zugriff einrichten | Die Einrichtungsautomation verteilt genau eine freigegebene Version auf alle Aufrufe und prüft die Übereinstimmung der technischen Referenzen. Nur vorgesehene Mandanten-Repositories dürfen `mtext-actions` aufrufen. Für den Checkout der zentralen Python-Implementierung ist eine nur lesende technische Berechtigung festgelegt, da das `GITHUB_TOKEN` des Aufrufers auf dessen Repository begrenzt ist |
| offen | Git-Clients für Ressourcenarbeit, Stage-Weitergabe und Release-Tags abnehmen | M/Text Workbench und zusätzlicher Git-Client unterstützen gemeinsam die in der [Benutzeranleitung](./Benutzeranleitung.md#benötigte-git-funktionen) beschriebenen Funktionen einschließlich Konfliktbehandlung, verbindlicher Herkunftszeile beim Cherry-Pick, kontrollierter lokaler Ablage, Gegen-Commit nach einem Push sowie Anlegen, gezieltem Pushen und Löschen eines Git-Tags |
| bestätigt | GitHub-Plattform festhalten | GitHub Enterprise Server 3.20.4 |

## 2. Schutz- und Freigaberegeln konfigurieren

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Mandantenspezifische Verantwortliche benennen | Team für Ressourcenarbeit, technischer Konfigurationskreis und kleines Release-Team sind festgelegt |
| offen | Branchschutz für die drei Stages einrichten | Die Einrichtungsautomation lässt berechtigte Text-Entwickler nach Entwicklung und Abnahme pushen, begrenzt Bereitstellung auf das Release-Team und sperrt Löschen sowie Force-Pushes. Der Prüfmodus weist Regelabweichungen aus |
| offen | Zentrale Aufrufdateien und `.github/config.json` schützen | Die Einrichtungsautomation verhindert Änderungen an `.github/workflows/**/*` und der Mandantenkonfiguration durch normale Ressourcen-Pushes und begrenzt notwendige Bypässe. Vollständige Commit-SHAs für freigegebene Actions und wiederverwendbare Workflows werden zentral geprüft |
| offen | GitHub Environments konfigurieren | Die Einrichtungsautomation legt `Entwicklung`, `Abnahme` und `Bereitstellung` mit ihren Branch- beziehungsweise Tagregeln an. Nur die Mainframe-Übergabe in `Bereitstellung` braucht eine manuelle Freigabe. Eine berechtigte Person darf den selbst ausgelösten Lauf freigeben; ein verpflichtendes Vier-Augen-Prinzip ist nicht vorgesehen |
| offen | Lebenszyklus und Betriebsregel für Git-Tags einrichten | Die Einrichtungsautomation begrenzt Tags nach dem Muster `R[0-9][0-9][0-9].[0-9][0-9][0-9]` auf das Release-Team, soweit GHES dies statisch abbildet. Vor der Freigabe darf das Team einen irrtümlichen Tag erst nach Abbruch des zugehörigen Laufs zurücknehmen. Nach der Freigabe sind Verschieben und Löschen betrieblich verboten; Korrekturen verwenden einen neuen Commit und einen neuen Tag. Bei einer nachträglichen Abweichung werden weitere Freigaben gestoppt, der Tag auf der im freigegebenen Lauf ausgewiesenen Ziel-SHA wiederhergestellt und der Vorgang als Betriebsstörung gemeldet |
| offen | Cherry-Pick und Release-Tag praktisch abnehmen | Auswahl nach SHA, verbindliche Herkunftszeile, Konfliktbehandlung und Push auf den Zielbranch sind dokumentiert. Die durch den ausgewählten Git-Client erzeugte Tag-Art wird festgelegt und mit dem Workflow geprüft. Ein nichtproduktiver Git-Tag startet genau einen Release-Workflow. Der Test weist nach, dass seine Löschung keine Übergabe auslöst und dass ein irrtümlicher Tag vor der Freigabe kontrolliert zurückgenommen werden kann |

## 3. FI-Runnerangebot und technische Abhängigkeiten prüfen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | FI-Runner für die Workflows festlegen | Das offizielle `runs-on`-Kennzeichen des von FI bereitgestellten Runnerangebots ist bestätigt und in den zentralen Workflows fest eingetragen. Bereitstellung, Absicherung, Wartung und Bereinigung des Runners sind als FI-Leistung bestätigt und liegen außerhalb des Projekts |
| offen | Laufzeit auf dem FI-Runner prüfen | Python 3.14, Git und die Ausführung der verwendeten Node-20-Actions sind verfügbar. `scripts/runner-preflight.sh` ist erfolgreich |
| offen | GHES-Artefakt-Actions prüfen | Die in den Workflows gepinnten Node-20-Varianten von `upload-artifact` v3.2.2 und `download-artifact` v3.1.0 sind auf GHES 3.20.4 verfügbar. Version 4 wird nicht verwendet |
| offen | Zertifikate und Netzwerkpfade prüfen | Die interne CA ist im Truststore. Der Runner erreicht die gewählten M/Text-Ziele sowie Mainframe-FTP und JES, ohne die TLS-Prüfung zu deaktivieren |

## 4. M/Text-Transport entscheiden und abnehmen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| bestätigt | Linien- und URL-Mapping | `R260→en03`, `R261→en01`, `R270→en02`. Die Hosts heißen jeweils `enXXe` und `enXXa` |
| bestätigt | Heutigen Adaptervertrag als Ausgangslage festhalten | Der bestehende Ablauf schreibt zuerst nach `serverSync` und sendet danach einen POST mit `MAN` und `INR`. Dies legt den künftigen Transport noch nicht fest |
| offen | Transportweg nach `serverSync` entscheiden und Zielvertrag festschreiben | Genau eine der im [Zielbild](./Zielbild_GitHub_Actions_Git.md#mtext-transport-nach-serversync) beschriebenen Varianten wird ausgewählt: PUT an den Adapter, Sharezugriff des Runners oder Download eines Actions-Artefakts durch Adapter beziehungsweise M/Text. Verantwortlichkeiten, Authentifizierung, Prüfung und Wiederanlauf sind geklärt |
| offen | Kompatibilität des gewählten Transports nachweisen | Auf `serverSync` liegen dieselben Dateien und Verzeichnisse wie im bisherigen Verfahren. Transportdateien und Metadaten bleiben nicht im ausgewerteten Bestand |
| offen | Fehler- und Wiederanlaufverhalten des Zielstands abnehmen | Ein Abbruch während der Übertragung oder Veröffentlichung startet die interne Synchronisation nicht. Ein Wiederanlauf stellt den vollständigen Commit her. Entfernte oder neu ausgeschlossene Projekte bleiben nicht als veralteter Bestand unter `serverSync` liegen |
| offen | Config-Check und Synchronisation nichtproduktiv prüfen | Der Config-Check liefert `CONFIG_VALIDATED`. Ein vollständiger Projektstand wird erfolgreich über den gewählten Transport bereitgestellt und der Wiederanlauf ist geprüft |
| offen | Betriebsweg für einen unklaren M/Text-Endstatus festlegen | Anwender bewerten keine technischen Anwendungsprotokolle. Bei unklarer Wirkung übernimmt die benannte Anwendungsbetreuung die technische Statusklärung; Kontaktweg, benötigte Laufangaben und Rückmeldung an den Anwender sind festgelegt |

## 5. Mainframe-Übergabe einrichten und abnehmen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | FTP-Secrets im GitHub Environment `Bereitstellung` hinterlegen | `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD` werden sicher hinterlegt; die Einrichtungsprüfung bestätigt nur ihr Vorhandensein, ohne Werte auszulesen |
| bestätigt | Historischen JCL-Eingabevertrag fachlich bestätigen | Der mandantenspezifische Zielcode wird wie bisher über genau einen vorhandenen JCL-Platzhalter eingesetzt. Die Mandantenkonfiguration enthält die ISPW-Instanz und begrenzt sie auf `T` oder `P` |
| offen | Historischen `trans`-Vertrag gegen Referenzlieferungen abnehmen | Paketnamen, FULL- und DELTA-Pfade, Löschliste, Informationsdatei und kumulativer DELTA-Inhalt entsprechen dem im [Zielbild](./Zielbild_GitHub_Actions_Git.md#historischer-übergabestand-unter-nfsmtexttrans) dokumentierten Bestand |
| offen | JCL und unmittelbare Übergabe nichtproduktiv prüfen | Die konfigurierte ISPW-Instanz wird korrekt in Dataset und Programmaufruf eingesetzt. FTP-Antworten, `SITE FILETYPE=JES`, Submit, gerendertes JCL und Wiederholung mit demselben geprüften Artefakt sind abgenommen |
| offen | Fachliche Host-Endkontrolle festlegen | Das Release-Team kann den weiteren Jobstatus nach `MAINFRAME_SUBMITTED` selbst auf dem Host prüfen. Erfolgsmerkmal, Nachweis, Abbruchgrenze und Vorgehen bei unklarem oder fehlgeschlagenem Status sind dokumentiert |

## 6. Test-Parallelbetrieb vorbereiten

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| geplant November/Dezember 2026 | Ersten SVN-Abzug nach dem [Migrations- und Cutover-Runbook](./Migration.md) erstellen | Alle Mandanten-Repositories stehen mit dokumentiertem SVN-Ausgangsstand für Tests bereit. Jenkins und SVN bleiben produktiv |
| offen | Importumfang und Release-Basen je Mandant freigeben | Aktive Linien, Projekte, Dateinamen und Ausschlüsse sind inventarisiert. Je aktiver Linie werden mindestens der `.100`-Stand und alle späteren Tags übernommen |
| offen | Nichtproduktiven End-to-End-Pilot abnehmen | Git-Clients, Schutzregeln, M/Text-Synchronisation sowie FULL- und DELTA-Release einschließlich Mainframe-Übergabe sind geprüft |
