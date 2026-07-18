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

## 1. GitHub-Grundaufbau herstellen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Zentrales Repository `j520730/mtext-actions` und privates FI-Repository `j517120/mtext-fi` auf GitHub Enterprise anlegen beziehungsweise die lokalen Stände übernehmen | Das zentrale Repository ist nur für das Automatisierungsteam direkt zugänglich. Das FI-Repository enthält Ressourcen, Mandantenkonfiguration und schlanke Workflows |
| bestätigt | Zentrale Implementierung gegen den fachlichen Vertrag prüfen | Die vier CLI-Kommandos, FULL und DELTA, Artefaktprüfung, JCL, FTP-/JES-Vertrag, Ressourcensynchronisation und Workflowgrenzen sind durch Akzeptanztests abgedeckt |
| offen | Branches der aktiven Stages und Default Branch einrichten | Für `R260`, `R261` und `R270` bestehen jeweils Branches der Stages `Entwicklung`, `Abnahme` und `Bereitstellung`. Zunächst ist `R261/Entwicklung` der Default Branch |
| offen | Zentrale Workflowversion pinnen und repositoryübergreifenden Actions-Zugriff freigeben | Alle aufrufenden Workflows verwenden denselben freigegebenen Commit-SHA. Nur vorgesehene Mandanten-Repositories rufen `mtext-actions` auf |
| offen | Zentralen Codebezug und mandantensichtbare Logs praktisch prüfen | Die ausgeführte Python-Anwendung stammt unveränderlich aus derselben freigegebenen Version wie der aufgerufene zentrale Workflow. Der Aufrufer kann kein anderes Automations-Repository, keine andere Version und keine andere Runnerklasse wählen. Ein Testlauf funktioniert über beide Namespaces und zeigt keine Secrets oder unnötigen internen Details. Falls nötig, wird ein kurzlebiges Installation-Token mit reinen Leserechten sicher in den Workflowvertrag aufgenommen |
| offen | Git-Clients für Ressourcenarbeit, Stage-Weitergabe und Release-Tags abnehmen | M/Text Workbench und zusätzlicher Git-Client unterstützen gemeinsam die in der [Benutzeranleitung](./Benutzeranleitung.md#benötigte-git-funktionen) beschriebenen Funktionen einschließlich Konfliktbehandlung, verbindlicher Herkunftszeile beim Cherry-Pick, kontrollierter lokaler Ablage, Gegen-Commit nach einem Push sowie Anlegen, gezieltem Pushen und Löschen eines Git-Tags |
| bestätigt | GitHub-Plattform festhalten | GitHub Enterprise Server 3.20.4 |

## 2. Schutz- und Freigaberegeln konfigurieren

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Mandantenspezifische Verantwortliche benennen | Team für Ressourcenarbeit, technischer Konfigurationskreis und kleines Release-Team sind festgelegt |
| offen | Branchschutz für die drei Stages einrichten | Berechtigte Text-Entwickler dürfen nach Entwicklung und Abnahme pushen. Bereitstellung ist auf das Release-Team begrenzt. Löschen und Force-Pushes sind gesperrt |
| offen | Zentrale Aufrufdateien und `.config.json` schützen | Normale Ressourcen-Pushes können weder `.github/workflows/**/*` noch die Mandantenkonfiguration verändern. Notwendige Bypässe sind eng begrenzt. Die GitHub-Actions-Richtlinie verlangt vollständige Commit-SHAs für Actions und wiederverwendbare Workflows |
| offen | GitHub Environments konfigurieren | `Entwicklung`, `Abnahme` und `Bereitstellung` sind angelegt. Nur die Mainframe-Übergabe in `Bereitstellung` braucht eine manuelle Freigabe. Eine berechtigte Person darf den selbst ausgelösten Lauf freigeben; ein verpflichtendes Vier-Augen-Prinzip ist nicht vorgesehen. Die zulässigen Tagmuster sind eingetragen |
| offen | Lebenszyklus und Schutz der Release-Tags einrichten | Verwendet werden ausschließlich Git-Tags und keine GitHub Releases. Nur das Release-Team darf Tags nach dem Muster `R[0-9][0-9][0-9].[0-9][0-9][0-9]` erstellen oder löschen. Vor der Freigabe kann es einen irrtümlichen Tag nach Abbruch des zugehörigen Laufs löschen und neu anlegen. Die Freigabe bindet Tagname und Ziel-Commit; danach sind Änderung und Löschung gesperrt. Da ein statisches Tag-Ruleset diesen Zustandswechsel nicht allein abbildet, wird eine technische Sperre oder eine revisionssicher überwachte Betriebsregel festgelegt |
| offen | Cherry-Pick und Release-Tag praktisch abnehmen | Auswahl nach SHA, verbindliche Herkunftszeile, Konfliktbehandlung und Push auf den Zielbranch sind dokumentiert. Die durch den ausgewählten Git-Client erzeugte Tag-Art wird festgelegt und mit dem Workflow geprüft. Ein nichtproduktiver Git-Tag startet genau einen Release-Workflow. Der Test weist nach, dass seine Löschung keine Übergabe auslöst, dass ein irrtümlicher Tag vor der Freigabe kontrolliert zurückgenommen werden kann und die festgelegte Schutzregel nach der Freigabe greift |

## 3. Runner und technische Abhängigkeiten bereitstellen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Self-hosted Runner und Laufzeit bereitstellen | Labels `self-hosted`, `linux`, `mtext-delivery`, Python 3.14, Git und die Ausführung von Node-20-Actions sind bestätigt. `scripts/runner-preflight.sh` ist erfolgreich |
| offen | Runnerzugriff und Lebenszyklus absichern | CI-Läufe sind von Runnern mit Zugriff auf M/Text und Mainframe getrennt. Runner-Gruppen erlauben nur die vorgesehenen Repositories und Workflows. Bereinigung oder Neuaufbau nach einem Job sowie Protokollaufbewahrung sind festgelegt und praktisch geprüft |
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
| offen | FTP-Secrets im GitHub Environment `Bereitstellung` hinterlegen | `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD` sind verfügbar |
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
