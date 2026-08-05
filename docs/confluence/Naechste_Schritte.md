# Nächste Schritte (OPL)

## 1. Technische Grundlagen festlegen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 1.1 | bestätigt | GitHub-Plattform festhalten | <ul><li>GitHub Enterprise Server 3.20.4 ist die voraussichtliche Zielplattform.</li></ul> |
| 1.2 | offen | Repositories anlegen | <ul><li>`<team>/mtext-actions` und `<team>/mtext-fi` sind angelegt. Teams wurden definiert und Berechtigungen über IDNeo vergeben.</li><li>Alle weiteren Mandanten-Repositories und das Issue-Tracker-Repository `mtext-support` wurden angelegt.</li></ul> |
| 1.3 | bestätigt | `mtext-actions` gegen den fachlichen Vertrag prüfen | <ul><li>Die Akzeptanztests für `workflow_configuration` und die vier fachlichen CLI-Kommandos sind erfolgreich vorab getestet.</li><li>FULL und DELTA, Artefaktprüfung, JCL, FTP-/JES-Übergabe, Ressourcensynchronisation und Workflowgrenzen sind vorab getestet und abgedeckt.</li></ul> |
| 1.4 | offen | Mandantenspezifische Verantwortliche benennen | <ul><li>Für jeden Mandanten sind die relevanten Personen namentlich zugeordnet, Benutzer eingerichtet und zugewiesen.</li></ul> |

## 2. Runnerangebot der FI bereitstellen und prüfen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 2.1 | offen | Runner der FI bereitstellen | <ul><li>Der Runner kann genutzt werden.</li><li>Sein bestätigtes `runs-on`-Kennzeichen ist in `mtext-actions` als Repositoryvariable `FI_RUNNER_LABEL` hinterlegt.</li></ul> |
| 2.2 | offen | Einheitliche Laufzeitvorbereitung bestätigen | <ul><li>Python ist in der geforderten Version ab 3.11 verfügbar.</li></ul> |
| 2.3 | offen | GHES-Artefakt-Actions prüfen | <ul><li>`upload-artifact` v3.2.2 läuft auf GHES 3.20.4 erfolgreich.</li><li>`download-artifact` v3.1.0 läuft auf GHES 3.20.4 erfolgreich.</li></ul> |

## 3. GitHub-Einstellungen und Berechtigungen einrichten

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 3.1 | offen | Technische Einrichtungsberechtigung hinterlegen | <ul><li>Das Environment `Einrichtung` enthält `WORKFLOW_CONFIGURATION_TOKEN`.</li><li>Der Zugriff auf Mandanten-Repositories ist auf die freigegebenen Branches begrenzt.</li></ul> |
| 3.2 | offen | Stage-Branches und Default Branch einrichten | <ul><li>Für `R260`, `R261` und `R270` bestehen jeweils `Entwicklung`, `Abnahme` und `Bereitstellung`.</li><li>`R261/Entwicklung` ist als erster Default Branch eingestellt.</li></ul> |
| 3.3 | offen | Repositoryübergreifenden Zugriff auf `mtext-actions` einrichten | <ul><li>Die vorgesehenen Mandanten-Repositories können die wiederverwendbaren Workflows aus `mtext-actions` aufrufen.</li><li>Der technische Checkout der Python-Implementierung aus `mtext-actions` ist ausschließlich lesend.</li><li>Workflowaufruf und Checkout wurden praktisch geprüft.</li></ul> |
| 3.4 | offen | Branchschutz für die drei Stages einrichten | <ul><li>Berechtigte Text-Entwickler können nach Entwicklung und Abnahme pushen.</li><li>Nur das Mandanten-Release-Team kann nach Bereitstellung pushen.</li><li>Nicht berechtigte Pushes werden abgewiesen.</li><li>Löschen und Force-Pushes werden auf allen Stage-Branches abgewiesen.</li></ul> |
| 3.6 | offen | Workflowdateien und Mandantenkonfiguration schützen | <ul><li>Normale Ressourcen-Pushes mit Änderungen an `.github/workflows/**/*` werden abgewiesen.</li><li>Änderungen an `.github/config.json` sind auf den technischen Konfigurationskreis begrenzt.</li></ul> |
| 3.7 | offen | GitHub Environments konfigurieren | <ul><li>Die Environments `Einrichtung` und `Bereitstellung` besitzen die vorgesehenen Branch- und Tagregeln.</li><li>Der Publish-Job kann `Bereitstellung` verwenden.</li></ul> |
| 3.8 | offen | Schutz der Release-Tags praktisch testen | <ul><li>Ein Test hält fest, dass ein Tag wie `R261.108` in GitHub technisch so geschützt werden kann, dass nur das Mandanten-Release-Team ihn erstellen, verändern oder löschen darf.</li></ul> |
| 3.9 | offen | Rücknahme irrtümlicher Release-Tags abnehmen | <ul><li>Das Mandanten-Release-Team kann einen irrtümlichen Tag löschen.</li><li>Vor dem Löschen wird der dadurch gestartete Workflow-Lauf abgebrochen.</li><li>Ein neu angelegter Tag startet einen neuen Release-Workflow.</li></ul> |

## 4. Workflowdateien einrichten und aktualisieren

Der Workflow **Configure workflow files** aus `configure-workflows.yml`
bearbeitet pro Lauf einen Mandantenbranch. Das Python-Modul
`workflow_configuration` bereitet die geprüften Commits vor. Der Workflow
pusht sie erst nach erfolgreicher Abschlussprüfung.

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 4.1 | offen | `Configure workflow files` abnehmen | <ul><li>Der Workflow aktualisiert `mtext-fi` wie gewünscht.</li><li>Die Workflows in `mtext-fi` nutzen danach `mtext-actions` korrekt.</li></ul> |
| 4.2 | offen | Restliche Mandanten-Workflows konfigurieren | <ul><li>Alle weiteren Mandanten-Repositories werden wie in 4.1 eingerichtet.</li></ul> |

## 5. M/Text-Transport entscheiden und abnehmen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 5.1 | offen | Linien- und URL-Mapping einrichten | <ul><li>`R260` verwendet `en03`, `R261` verwendet `en01` und `R270` verwendet `en02`.</li><li>LTOMA und LTOMS sind jeweils unter `https://en0[1,2,3][e,a].ltom[a,s].intern` verfügbar.</li></ul> |
| 5.2 | offen | Transportweg nach `serverSync` festlegen | <ul><li>Eine der im [Zielbild](./Zielbild_GitHub_Actions_Git.md#mtext-transport-nach-serversync) beschriebenen Varianten ist ausgewählt und implementiert.</li><li>Erfolgsprüfung, Fehlergrenzen und Wiederanlauf sind festgelegt.</li></ul> |
| 5.3 | offen | Zertifikate und M/Text-Netzwerkpfade prüfen | <ul><li>Die interne CA ist im Truststore des Runners vorhanden.</li><li>Der Runner erreicht die ausgewählten M/Text-Ziele.</li></ul> |
| 5.4 | offen | Kompatibilität des gewählten Transports nachweisen | <ul><li>Dateien und Verzeichnisse unter `serverSync` entsprechen dem bisherigen Verfahren.</li></ul> |
| 5.5 | offen | Fehler- und Wiederanlaufverhalten abnehmen | <ul><li>Ein Abbruch während Übertragung oder Veröffentlichung startet keine interne Synchronisation.</li><li>Ein Wiederanlauf stellt den vollständigen Stand jedes verarbeiteten Projekts her.</li><li>Für vollständig entfernte oder neu ausgeschlossene zusätzliche Projekte ist eine sichere Bereinigungsregel festgelegt, die keine Verzeichnisse anderer Mandanten-Repositories berührt.</li></ul> |
| 5.6 | offen | Config-Check und Synchronisation prüfen | <ul><li>Der Config-Check endet mit `CONFIG_VALIDATED`.</li><li>Der vollständige Projektstand eines festgelegten Commits wird über den gewählten Transport bereitgestellt.</li><li>Der Wiederanlauf desselben Commits ist erfolgreich.</li></ul> |

## 6. Mainframe-Übergabe einrichten und abnehmen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 6.1 | offen | FTP-Secrets hinterlegen | <ul><li>`Bereitstellung` enthält `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD`.</li><li>Die Einrichtungsprüfung bestätigt nur das Vorhandensein der Secret-Namen.</li></ul> |
| 6.2 | offen | Mainframe-Netzwerkpfade prüfen | <ul><li>Der Runner erreicht Mainframe-FTP und JES.</li></ul> |
| 6.4 | offen | Historischen `trans`-Vertrag abnehmen | <ul><li>Paketnamen und Inhalte sowie FULL- und DELTA-Pfade entsprechen den Referenzlieferungen.</li><li>Ein FULL erzeugt je Projekt das vollständige F-Paket und das zusätzliche leere D-Paket.</li></ul> |
| 6.5 | offen | JCL und unmittelbare Übergabe prüfen | <ul><li>Die konfigurierte ISPW-Instanz erscheint korrekt in Dataset und Programmaufruf.</li><li>FTP-Anmeldung, Übertragung und `SITE FILETYPE=JES` sind erfolgreich.</li><li>Das gerenderte JCL wird erfolgreich übergeben.</li></ul> |

## 7. Git-Client und Bedienabläufe abnehmen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 7.1 | offen | Funktionalität des Git-Clients in der Workbench abnehmen | <ul><li>Die Fähigkeiten des integrierten Clients sind geprüft und in der Bedienungsanleitung dokumentiert.</li></ul> |
| 7.2 | offen | Ressourcenarbeit, Stage-Weitergabe und Rücknahme abnehmen | <ul><li>Status, Änderungen, Commit und Push sind in den vorgesehenen Clients praktisch geprüft.</li><li>Ein Cherry-Pick kann bei einem Konflikt fortgesetzt oder vollständig abgebrochen werden.</li><li>Die Abläufe entsprechen der [Benutzeranleitung](./Benutzeranleitung.md).</li></ul> |

## 8. Test-Parallelbetrieb vorbereiten

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 8.1 | offen | Importumfang und Release-Basen freigeben | <ul><li>Aktive Releaselinien, Projekte, Dateinamen und Ausschlüsse sind je Mandant inventarisiert.</li><li>Je aktiver Releaselinie sind mindestens der `.100`-Stand und alle späteren als Releases benötigten Tags zur Übernahme benannt.</li></ul> |
| 8.2 | offen | Ersten SVN-Abzug erstellen | <ul><li>Alle Mandanten-Repositories besitzen einen dokumentierten SVN-Ausgangsstand für die Tests.</li></ul> |
| 8.3 | offen | Nichtproduktiven End-to-End-Pilot abnehmen | <ul><li>Git-Clients und Schutzregeln sind praktisch geprüft.</li><li>M/Text-Synchronisation und Wiederanlauf sind erfolgreich.</li><li>FULL- und DELTA-Release einschließlich Mainframe-Übergabe sind erfolgreich.</li></ul> |
| 8.4 | offen | Mandanten konnten eigene Abläufe erfolgreich testen | <ul><li>Vorbereitende Tätigkeiten der Mandanten konnten erfolgreich durchgeführt und abgenommen werden.</li></ul> |
