# Nächste Schritte

Diese Seite ist die Arbeitsliste für die erstmalige Einrichtung und die
nichtproduktive Abnahme. Die Nummerierung gibt die vorgesehene
Ausführungsreihenfolge wieder. Als bestätigt markierte Schritte bleiben mit
ihren Nachweisen als Voraussetzungen sichtbar. Vorbereitungen ohne technische
Abhängigkeit dürfen parallel erfolgen. Angewendet und abgenommen werden die
Ergebnisse in der hier beschriebenen Reihenfolge.

Die Statusangaben geben den dokumentierten Arbeitsstand wieder. Vor der
Produktivsetzung werden auch bestätigte Punkte noch einmal im
Gesamtzusammenhang geprüft. Die letzte Spalte enthält die einzeln prüfbaren
Abnahmekriterien.

Ergänzende Dokumente:

- [Zielbild](./Zielbild_GitHub_Actions_Git.md)
- [Benutzeranleitung](./Benutzeranleitung.md)
- [Migrations- und Cutover-Runbook](./Migration.md)
- [Soll-Architektur als Ablaufdiagramm](../../Architektur_Soll_GitHub_Actions_Git.drawio)

Wiederholbare technische Einstellungen werden nicht als Klickanleitung
abgearbeitet. Der Workflow **Configure workflow files** richtet die
Workflowdateien ein und aktualisiert sie bei späteren Rollouts. Der noch offene
API-Teil übernimmt die übrigen GitHub-Einstellungen. Manuell bleiben fachliche
Entscheidungen, Rollenbesetzung, Zugangsdatenübergabe und praktische Abnahmen.

## 1. Technische Grundlagen festlegen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 1.1 | bestätigt | GitHub-Plattform festhalten | <ul><li>GitHub Enterprise Server 3.20.4 ist als Zielplattform verbindlich festgelegt.</li></ul> |
| 1.2 | offen | Repositories anlegen oder übernehmen | <ul><li>`j520730/mtext-actions` und `j517120/mtext-fi` bestehen auf der Zielplattform.</li><li>Nur das Automatisierungsteam hat direkten Zugriff auf `mtext-actions`.</li><li>`mtext-fi` enthält Ressourcen, Mandantenkonfiguration und Trigger-Workflows der FI.</li></ul> |
| 1.3 | bestätigt | `mtext-actions` gegen den fachlichen Vertrag prüfen | <ul><li>Die Akzeptanztests für `workflow_configuration` und die vier fachlichen CLI-Kommandos sind erfolgreich.</li><li>FULL und DELTA, Artefaktprüfung, JCL, FTP-/JES-Übergabe, Ressourcensynchronisation und Workflowgrenzen sind abgedeckt.</li></ul> |
| 1.4 | offen | Mandantenspezifische Verantwortliche benennen | <ul><li>Für jeden Mandanten sind die Personen für Ressourcenarbeit, technische Konfiguration und Releases namentlich zugeordnet.</li></ul> |
| 1.5 | offen | Pflichtangaben für den API-Teil bestätigen | <ul><li>GitHub-Host und Repositoryeigentümer sind festgelegt.</li><li>Team- und Bypass-IDs sind den benannten Verantwortlichen zugeordnet.</li><li>Ausgangs-Commits der Stage-Branches, Actions-Zugriffsebene und technische Leseberechtigung sind dokumentiert und freigegeben.</li></ul> |

## 2. Runnerangebot der FI bereitstellen und prüfen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 2.1 | offen | Runner der FI bereitstellen | <ul><li>Der Runner ist in GitHub verfügbar.</li><li>Sein bestätigtes `runs-on`-Kennzeichen ist in `mtext-actions` als Repositoryvariable `FI_RUNNER_LABEL` hinterlegt.</li></ul> |
| 2.2 | offen | Einheitliche Laufzeitvorbereitung bestätigen | <ul><li>Alle Workflows verwenden `scripts/runner-preflight.sh` als gemeinsame Laufzeitvorbereitung.</li><li>Die nachfolgenden Workflow-Schritte verwenden den vom Skript bereitgestellten Python-Pfad und müssen die Laufzeit nicht selbst bestimmen.</li></ul> |
| 2.3 | offen | GHES-Artefakt-Actions prüfen | <ul><li>`upload-artifact` v3.2.2 läuft auf GHES 3.20.4 erfolgreich.</li><li>`download-artifact` v3.1.0 läuft auf GHES 3.20.4 erfolgreich.</li></ul> |

## 3. GitHub-Einstellungen und Berechtigungen einrichten

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 3.1 | offen | Technische Einrichtungsberechtigung hinterlegen | <ul><li>Das Environment `Einrichtung` enthält `WORKFLOW_CONFIGURATION_TOKEN`.</li><li>Die technische Identität kann nur auf `mtext-actions` und die vorgesehenen Mandanten-Repositories zugreifen.</li><li>Der Zugriff auf Mandanten-Repositories ist auf die freigegebenen Branches begrenzt.</li></ul> |
| 3.2 | offen | API-Teil implementieren und im Testbereich abnehmen | <ul><li>Der API-Teil stellt den freigegebenen Zielzustand eines Test-Repositories her.</li><li>Die anschließende Rückleseprüfung bestätigt den vollständigen Zielzustand.</li><li>Eine Wiederholung erzeugt keine Änderung.</li><li>Secret-Werte werden weder gelesen noch geschrieben.</li></ul> |
| 3.3 | offen | Stage-Branches und Default Branch einrichten | <ul><li>Für `R260`, `R261` und `R270` bestehen jeweils `Entwicklung`, `Abnahme` und `Bereitstellung`.</li><li>`R261/Entwicklung` ist als erster Default Branch eingestellt.</li></ul> |
| 3.4 | offen | Repositoryübergreifenden Zugriff auf `mtext-actions` einrichten | <ul><li>Nur die vorgesehenen Mandanten-Repositories können die wiederverwendbaren Workflows aus `mtext-actions` aufrufen.</li><li>Der technische Checkout der Python-Implementierung aus `mtext-actions` ist ausschließlich lesend.</li><li>Workflowaufruf und Checkout wurden praktisch geprüft.</li></ul> |
| 3.5 | offen | Branchschutz für die drei Stages einrichten | <ul><li>Berechtigte Text-Entwickler können nach Entwicklung und Abnahme pushen.</li><li>Nur das Mandanten-Release-Team kann nach Bereitstellung pushen.</li><li>Nicht berechtigte Pushes werden abgewiesen.</li><li>Löschen und Force-Pushes werden auf allen Stage-Branches abgewiesen.</li></ul> |
| 3.6 | offen | Workflowdateien und Mandantenkonfiguration schützen | <ul><li>Normale Ressourcen-Pushes mit Änderungen an `.github/workflows/**/*` werden abgewiesen.</li><li>Änderungen an `.github/config.json` sind auf den technischen Konfigurationskreis begrenzt.</li><li>Bypässe bestehen nur für die jeweils benannten technischen Identitäten.</li></ul> |
| 3.7 | offen | GitHub Environments konfigurieren | <ul><li>Die Environments `Einrichtung` und `Bereitstellung` sind eingerichtet.</li><li>Entwicklung und Abnahme verwenden kein Environment.</li><li>Nur der Publish-Job kann `Bereitstellung` mit zulässigen Release-Tags verwenden.</li><li>Für die Mainframe-Übergabe sind keine erforderlichen Reviewer konfiguriert.</li></ul> |
| 3.8 | offen | Technische Tagberechtigungen abnehmen | <ul><li>Ein praktischer Test hält fest, welche Tagoperationen GHES 3.20.4 technisch begrenzen kann.</li><li>Alle technisch abbildbaren Operationen auf Tags im Format `Rnnn.nnn` sind auf das Mandanten-Release-Team beschränkt.</li></ul> |
| 3.9 | offen | Rücknahme irrtümlicher Release-Tags abnehmen | <ul><li>Das Mandanten-Release-Team kann einen irrtümlichen Tag löschen.</li><li>Ein bei der Korrektur noch laufender Ablauf kann abgebrochen werden.</li><li>Ein neu angelegter Tag startet genau einen neuen Release-Workflow.</li><li>Der korrigierte Lauf überschreibt die betreffenden Member und CodePipeline versioniert den neuen Stand.</li></ul> |

## 4. Workflowdateien einrichten und aktualisieren

Der Workflow **Configure workflow files** aus
[`configure-workflows.yml`](../../mtext-actions/.github/workflows/configure-workflows.yml)
bearbeitet pro Lauf genau einen Mandantenbranch. Das Python-Modul
`workflow_configuration` bereitet die geprüften Commits vor. Der Workflow
pusht sie erst nach erfolgreicher Abschlussprüfung.

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 4.1 | in Vorbereitung | `Configure workflow files` im Testbereich abnehmen | <ul><li>Der Lauf verlangt eine vollständige freigegebene `mtext-actions`-SHA, ein Mandanten-Repository und einen Zielbranch.</li><li>Beide Workflowdateisätze werden vor der ersten Änderung validiert.</li><li>Der Mandanten-Commit enthält ausschließlich Änderungen unter `.github/workflows`.</li><li>Workflowaufruf und Python-Checkout verwenden dieselbe `mtext-actions`-SHA.</li><li>Die Diffs werden vor dem Push im Workflow-Log angezeigt.</li><li>Die Abschlussprüfung ist leer, bevor ein Commit gepusht wird.</li><li>Eine Wiederholung für den erreichten Zielzustand erzeugt keinen Commit.</li></ul> |
| 4.2 | offen | Rollout-Matrix festlegen | <ul><li>Die Matrix enthält jedes zu aktualisierende Mandanten-Repository mit jedem betroffenen Branch.</li><li>Für alle Einträge ist dieselbe freigegebene Ausgangs-SHA angegeben.</li><li>Workflow-Lauf, Mandanten-Commit und Ergebnis werden je Eintrag nachgewiesen.</li></ul> |
| 4.3 | offen | Ersten Rollout-Lauf ausführen | <ul><li>Der Lauf verwendet die freigegebene Ausgangs-SHA.</li><li>Fehlt das feste Runner-Kennzeichen noch, erzeugt der Lauf einmalig einen Commit in `mtext-actions`.</li><li>Die im Log ausgewiesene SHA dieses Commits wird als Rollout-SHA in die Matrix übernommen.</li><li>Der bereits bearbeitete Mandantenbranch verweist auf diese Rollout-SHA.</li></ul> |
| 4.4 | offen | Verbleibende Mandantenbranches aktualisieren | <ul><li>Für jeden verbleibenden Matrixeintrag läuft **Configure workflow files** mit derselben Rollout-SHA.</li><li>Workflowaufruf und Python-Checkout jedes bearbeiteten Branches verweisen auf diese SHA.</li><li>Der erzeugte Mandanten-Commit und der erfolgreiche Lauf sind in der Matrix vermerkt.</li></ul> |
| 4.5 | offen | Rollout abschließend prüfen | <ul><li>Für jeden Matrixeintrag wird ein Kontrolllauf mit der Rollout-SHA ausgeführt.</li><li>Jeder Kontrolllauf endet erfolgreich und ohne neuen Commit.</li><li>Alle vorgesehenen Mandantenbranches verwenden dieselbe `mtext-actions`-Version.</li></ul> |

Bei späteren `mtext-actions`-Versionen werden die Schritte 4.2 bis 4.5
wiederholt. Das Runner-Kennzeichen ist dann bereits fest eingetragen, sodass
kein zusätzlicher Commit in `mtext-actions` entsteht.

## 5. M/Text-Transport entscheiden und abnehmen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 5.1 | bestätigt | Linien- und URL-Mapping bestätigen | <ul><li>`R260` verwendet `en03`, `R261` verwendet `en01` und `R270` verwendet `en02`.</li><li>Die Hosts heißen je Linie `enXXe` für Entwicklung und `enXXa` für Abnahme.</li></ul> |
| 5.2 | bestätigt | Heutigen Adaptervertrag als Ausgangslage festhalten | <ul><li>Der bestehende Ablauf schreibt zuerst nach `serverSync`.</li><li>Danach sendet er einen POST mit `MAN` und `INR`.</li><li>Dieser Istzustand legt den künftigen Transport nicht fest.</li></ul> |
| 5.3 | offen | Transportweg nach `serverSync` festlegen | <ul><li>Genau eine der im [Zielbild](./Zielbild_GitHub_Actions_Git.md#mtext-transport-nach-serversync) beschriebenen Varianten ist ausgewählt.</li><li>Verantwortlichkeiten und Authentifizierung sind dokumentiert.</li><li>Erfolgsprüfung, Fehlergrenzen und Wiederanlauf sind vertraglich festgelegt.</li></ul> |
| 5.4 | offen | Zertifikate und M/Text-Netzwerkpfade prüfen | <ul><li>Die interne CA ist im Truststore des Runners vorhanden.</li><li>Der Runner erreicht die ausgewählten M/Text-Ziele.</li><li>Die TLS-Prüfung bleibt aktiviert.</li></ul> |
| 5.5 | offen | Kompatibilität des gewählten Transports nachweisen | <ul><li>Dateien und Verzeichnisse unter `serverSync` entsprechen dem bisherigen Verfahren.</li><li>Transportdateien und `.svn`-Metadaten liegen nicht im ausgewerteten Bestand.</li><li>Neu gesetzte Dateizeitstempel lösen gegenüber einem bisherigen `svn update` keine abweichende fachliche Verarbeitung aus.</li></ul> |
| 5.6 | offen | Fehler- und Wiederanlaufverhalten abnehmen | <ul><li>Ein Abbruch während Übertragung oder Veröffentlichung startet keine interne Synchronisation.</li><li>Ein Wiederanlauf stellt den vollständigen Stand jedes verarbeiteten Projekts her.</li><li>Für vollständig entfernte oder neu ausgeschlossene zusätzliche Projekte ist eine sichere Bereinigungsregel festgelegt, die keine Verzeichnisse anderer Mandanten-Repositories berührt.</li></ul> |
| 5.7 | offen | Config-Check und Synchronisation nichtproduktiv prüfen | <ul><li>Der Config-Check endet mit `CONFIG_VALIDATED`.</li><li>Der vollständige Projektstand eines festgelegten Commits wird über den gewählten Transport bereitgestellt.</li><li>Der Wiederanlauf desselben Commits ist erfolgreich.</li></ul> |
| 5.8 | offen | Betriebsweg für einen unklaren M/Text-Endstatus festlegen | <ul><li>Eine benannte Anwendungsbetreuung übernimmt die technische Statusklärung.</li><li>Kontaktweg und benötigte Angaben zum Workflow-Lauf sind dokumentiert.</li><li>Der Anwender erhält eine fachlich verständliche Rückmeldung und muss keine technischen Anwendungsprotokolle bewerten.</li></ul> |

## 6. Mainframe-Übergabe einrichten und abnehmen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 6.1 | offen | FTP-Secrets hinterlegen | <ul><li>Das Environment `Bereitstellung` enthält `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD`.</li><li>Die Einrichtungsprüfung bestätigt nur das Vorhandensein der Secret-Namen.</li><li>Secret-Werte werden nicht ausgelesen oder protokolliert.</li></ul> |
| 6.2 | offen | Mainframe-Netzwerkpfade prüfen | <ul><li>Der Runner erreicht Mainframe-FTP und JES.</li><li>Die vorgesehene Zertifikatsprüfung ist aktiv.</li></ul> |
| 6.3 | bestätigt | Historischen JCL-Eingabevertrag bestätigen | <ul><li>Der mandantenspezifische Zielcode wird über den vorhandenen JCL-Platzhalter eingesetzt.</li><li>Die Mandantenkonfiguration enthält die ISPW-Instanz und erlaubt dort nur `T` oder `P`.</li></ul> |
| 6.4 | offen | Historischen `trans`-Vertrag abnehmen | <ul><li>Paketnamen, FULL- und DELTA-Pfade entsprechen den Referenzlieferungen.</li><li>Ein FULL erzeugt je Projekt das vollständige F-Paket und das zusätzliche leere D-Paket.</li><li>Löschliste und Informationsdatei entsprechen den Referenzlieferungen.</li><li>Das kumulative DELTA entspricht dem im [Zielbild](./Zielbild_GitHub_Actions_Git.md#historischer-übergabestand-unter-nfsmtexttrans) dokumentierten Vertrag.</li></ul> |
| 6.5 | offen | JCL und unmittelbare Übergabe nichtproduktiv prüfen | <ul><li>Die konfigurierte ISPW-Instanz erscheint korrekt in Dataset und Programmaufruf.</li><li>FTP-Anmeldung, Übertragung und `SITE FILETYPE=JES` sind erfolgreich.</li><li>Das gerenderte JCL wird erfolgreich übergeben.</li><li>Die Wiederholung verwendet dasselbe zuvor geprüfte Artefakt.</li></ul> |
| 6.6 | offen | Fachliche Host-Endkontrolle festlegen | <ul><li>Das Mandanten-Release-Team kann den Status nach `MAINFRAME_SUBMITTED` auf dem Host prüfen.</li><li>Erfolgsmerkmal und erforderlicher Nachweis sind dokumentiert.</li><li>Abbruchgrenze und Vorgehen bei unklarem oder fehlgeschlagenem Status sind festgelegt.</li></ul> |

## 7. Git-Clients und Bedienabläufe abnehmen

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 7.1 | offen | Aktualisierung des lokalen Branches abnehmen | <ul><li>Für die M/Text Workbench ist die verwendete Bedienfunktion dokumentiert und praktisch geprüft.</li><li>Für den zusätzlichen Git-Client ist die verwendete Bedienfunktion dokumentiert und praktisch geprüft.</li><li>Der lokale Branch lässt sich ohne automatischen Merge auf den aktuellen GitHub-Stand bringen.</li><li>Der erreichte Commit ist im jeweiligen Client prüfbar.</li></ul> |
| 7.2 | offen | Ressourcenarbeit, Stage-Weitergabe und Rücknahme abnehmen | <ul><li>Status, Änderungen, Commit und Push sind in den vorgesehenen Clients praktisch geprüft.</li><li>Ein Cherry-Pick dokumentiert die vollständige Quell-SHA und kann bei einem Konflikt fortgesetzt oder vollständig abgebrochen werden.</li><li>Eine lokale Zwischenablage kann kontrolliert wiederhergestellt werden.</li><li>Ein bereits gepushter Commit kann durch einen Gegen-Commit korrigiert werden.</li><li>Die Abläufe entsprechen der [Benutzeranleitung](./Benutzeranleitung.md#benötigte-git-funktionen).</li></ul> |
| 7.3 | offen | Release-Tag praktisch abnehmen | <ul><li>Tag-Art und Bedienweg sind für den ausgewählten Git-Client festgelegt.</li><li>Der Client überträgt gezielt genau den vorgesehenen Tag nach GitHub.</li><li>Die Übertragung startet genau einen Release-Workflow.</li><li>Die Löschung des Tags startet keine Mainframe-Übergabe.</li><li>Vor dem Löschen eines irrtümlichen Tags wird der dadurch gestartete Workflow-Lauf abgebrochen.</li></ul> |

## 8. Test-Parallelbetrieb vorbereiten

| Nr. | Status | Tätigkeit | Ergebnis |
|---|---|---|---|
| 8.1 | offen | Importumfang und Release-Basen freigeben | <ul><li>Aktive Releaselinien, Projekte, Dateinamen und Ausschlüsse sind je Mandant inventarisiert.</li><li>Je aktiver Releaselinie sind mindestens der `.100`-Stand und alle späteren als Releases benötigten Tags zur Übernahme benannt.</li></ul> |
| 8.2 | geplant November/Dezember 2026 | Ersten SVN-Abzug erstellen | <ul><li>Der Abzug folgt dem [Migrations- und Cutover-Runbook](./Migration.md).</li><li>Alle Mandanten-Repositories besitzen einen dokumentierten SVN-Ausgangsstand für die Tests.</li><li>Jenkins und SVN bleiben während des Test-Parallelbetriebs produktiv.</li></ul> |
| 8.3 | offen | Nichtproduktiven End-to-End-Pilot abnehmen | <ul><li>Git-Clients und Schutzregeln sind praktisch geprüft.</li><li>M/Text-Synchronisation und Wiederanlauf sind erfolgreich.</li><li>FULL- und DELTA-Release einschließlich Mainframe-Übergabe sind erfolgreich.</li></ul> |
