# Nächste Schritte (OPL)

`mtext_actions` bezeichnet in dieser Arbeitsliste das Repository
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions`.

## 1. Git-Vertrag umsetzen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 1.1 | bestätigt | Branch-Modell festlegen | `main`, `release/Rnnn` und `feature/Rnnn/<Bezeichnung>` sind im Zielbild beschrieben. Entwicklung und Abnahme sind M/Text-Ziele und keine Git-Branches. |
| 1.2 | offen | Geschützte Branches einrichten | `main` ist Default Branch und kann nicht gelöscht oder umbenannt werden. Änderungen an `main` und `release/Rnnn` sind ausschließlich über Pull Requests im Vier-Augenprinzip möglich. Force-Pushes sind gesperrt. |
| 1.3 | offen | Squash Merge einrichten | `Allow squash merging` ist aktiviert. Merge Commits und Rebase Merge sind deaktiviert. Ein Test-Pull-Request erzeugt einen Commit auf dem Zielbranch. |
| 1.4 | offen | Organisationsweite Tagregeln prüfen | Ein Tag wie `v261.108` kann auf einem Commit eines geschützten Branches erstellt und danach nicht gelöscht werden. Die Mandanten-Repositories besitzen keine abweichende Tagregel. |
| 1.5 | offen | Führende Releaselinie versionieren | `.github/config.json` enthält auf `main` die zugehörige `releaselinie`. Der Wechsel wird über einen Pull Request geprüft. |
| 1.6 | offen | Repositories und Verantwortliche einrichten | `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, die in `config/mandanten.json` zugeordneten Mandanten-Repositories und `FinanzInformatik/fi_lbs_entw_oms_mserie_support` sind angelegt. Die jeweiligen Repository-Verantwortlichen sind benannt und über IDNeo berechtigt. |

## 2. Runner und technische Berechtigungen bereitstellen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 2.1 | offen | Runner der FI bereitstellen | Das bestätigte `runs-on`-Kennzeichen ist als Repositoryvariable `FI_RUNNER_LABEL` in `mtext_actions` hinterlegt. Python ab Version 3.11 und Git stehen bereit. |
| 2.2 | offen | Repositoryübergreifenden Lesezugriff einrichten | Der zentrale Release-Workflow kann die in `config/mandanten.json` aufgeführten privaten Mandanten-Repositories und ihre Tags lesen. |
| 2.3 | offen | Fine-grained PAT für den zentralen Zugriff einrichten | Die Organisation `FinanzInformatik` und das Repository `fi_lbs_entw_oms_mtext_actions` sind auswählbar. Das Token erhält `Actions: read and write` und `Contents: read` auf diesem Repository. Tokeninhaber, erforderliche Genehmigung und Erneuerung vor Ablauf sind festgelegt. Ein Test lädt die freigegebene CI/CD-Version und startet dort den vorgesehenen Workflow. |
| 2.4 | offen | Zentralen Zugriff auf Mandanten-Repositories einrichten | `WORKFLOW_CONFIGURATION_TOKEN` liegt als Repository-Secret in `mtext_actions` und gilt für die vorgesehenen Mandanten-Repositories. Mit `Contents: read and write` und `Pull requests: read and write` kann es Aktualisierungs-Pull-Requests sowie GitHub Releases mit Informationsdateien erstellen. |

## 3. Mandantenkonfiguration und zentrale Zuordnungen anpassen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 3.1 | offen | Mandantenkonfiguration erweitern | Jeder `main`-Stand enthält das Feld `releaselinie`. Konfigurationsprüfung und Beispiele verwenden die bestätigten deutschen Feldnamen. |
| 3.2 | offen | Rollierende Releaselinien pflegen | `R260` verwendet `en03`, `R261` verwendet `en01` und `R270` verwendet `en02`. Beim Ausscheiden von R260 kann R271 `en03` übernehmen. |
| 3.3 | offen | Hostprofile prüfen | Jedes in `releaselinien.json` verwendete `hostprofil` besteht in der Mandantenkonfiguration. Die CodePipeline-Stage ist `FKTE`, `FKTF`, `JURJ`, `JURP`, `SVTS` oder `VPTV`. |
| 3.4 | offen | Mandantenzuordnung vervollständigen | `config/mandanten.json` enthält jedes Mandantenkürzel und das zugehörige Repository eindeutig. |

## 4. M/Text-Synchronisation umstellen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 4.1 | offen | Feature-Branches nach Entwicklung routen | Ein Push nach `feature/Rnnn/<Bezeichnung>` synchronisiert den Ziel-Commit automatisch mit dem Entwicklungsziel der Releaselinie. |
| 4.2 | offen | Geschützte Branches nach Abnahme routen | Ein Merge nach `release/Rnnn` synchronisiert die genannte Linie nach Abnahme. Ein Merge nach `main` verwendet die dort konfigurierte `releaselinie`. Ändert dieser Commit die Releaselinie, wird sein Vollstand zusätzlich nach Entwicklung übertragen. |
| 4.3 | offen | M/Text-Transportweg festlegen | PUT an den Adapter, direkter Sharezugriff und Download eines GitHub-Actions-Artefakts sind bewertet. Eine Variante und der zugehörige Adaptervertrag sind für den Integrationslauf festgelegt. |
| 4.4 | offen | Dauerhaften `serverSync`-Stand implementieren | Der unter `serverSync` vollständig bereitgestellte Commit wird je Repository, Releaselinie und M/Text-Ziel festgehalten. Ein normaler Lauf überträgt neue und geänderte Ressourcen und entfernt in Git gelöschte Ressourcen. Unveränderte Ressourcen werden nicht erneut übertragen. |
| 4.5 | offen | Manuellen Vollabgleich bereitstellen | Eine Commit-SHA stellt den vollständigen Stand der zugeordneten Projektverzeichnisse her. Der ausgewählte Branch bestimmt Releaselinie und Zielstufe. Andere Mandantenverzeichnisse bleiben unverändert. |
| 4.6 | offen | Parallelität begrenzen | Läufe desselben Mandanten-Repositories werden nacheinander ausgeführt. Verschiedene Mandanten-Repositories können ihre überschneidungsfreien Projektverzeichnisse gleichzeitig synchronisieren. Ein repositoryübergreifender Sperrmechanismus ist nicht erforderlich. |
| 4.7 | offen | Gewählten Transportweg technisch prüfen | Die für den gewählten Transportweg erforderlichen Verbindungen, Berechtigungen und internen Zertifikate stehen bereit. |
| 4.8 | offen | Synchronisation und Wiederanlauf abnehmen | Zwei abwechselnd gepushte Feature-Branches derselben Linie stellen jeweils ihren Zielstand her. Ein fehlgeschlagener Lauf kann mit demselben Ziel-Commit wiederholt werden. Nach einem teilweise geschriebenen Stand stellt die Wiederholung den vollständigen Zielstand her. |

## 5. Zentralen Releaseweg umstellen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 5.1 | offen | Tagformat umstellen | Releasebau und Tests erkennen `v261.100`, `v261.108` und entsprechende Tags anderer aktiver Linien. Alte Formate werden nicht als Release-Auslöser verwendet. |
| 5.2 | offen | Zentralen Workflow ausführen | Ein Release-Tag im Mandanten-Repository startet automatisch einen Lauf in `mtext_actions`. Der Lauf verarbeitet Repository, Tag und vollständigen Ziel-Commit. |
| 5.3 | offen | Mainframe-Zugang zentral hinterlegen | `MAINFRAME_FTP_HOST` und `MAINFRAME_FTP_USER` liegen als Repositoryvariablen in `mtext_actions`. `MAINFRAME_FTP_PASSWORD` liegt dort als Repository-Secret. Mandanten-Repositories enthalten diese Werte nicht. |
| 5.4 | offen | FULL, DELTA und Lieferkontrolle bereitstellen | `v261.100` erzeugt das vollständige F-Paket und das leere D-Paket. `v261.108` erzeugt ein kumulatives DELTA gegen `v261.100`. Paketnamen, Archivpfade und Löschlisten entsprechen einer Referenzlieferung aus dem bisherigen Verfahren. Im Mandanten-Repository besteht zum Tag ein GitHub Release mit einer verständlichen Zusammenfassung. Die Informationsdateien sind dort als Dateien angehängt. |
| 5.5 | offen | Mainframe-Übergabe prüfen | FTP-Anmeldung, Paketübertragung, JCL-Erzeugung und `SITE FILETYPE=JES` sind mit dem zentralen technischen Benutzer erfolgreich. |
| 5.6 | offen | Wiederanlauf prüfen | Ein fehlgeschlagener Übergabeversuch kann mit demselben geprüften Artefakt wiederholt werden. |

## 6. Workflow-Aktualisierung per Pull Request umstellen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 6.1 | offen | Schlanke Mandanten-Workflows einrichten | `main` und die gepflegten `release/Rnnn`-Branches enthalten den abgestimmten Mandanten-Workflow mit einem Synchronisationsjob. |
| 6.2 | offen | Rollout-Matrix anpassen | Die Matrix enthält `main` und die gepflegten `release/Rnnn`-Branches der Mandanten-Repositories. Stage- und Feature-Branches sind nicht enthalten. |
| 6.3 | offen | Aktualisierungs-Pull-Requests erstellen | Der zentrale Lauf trägt in bestehenden Mandanten-Workflows die vollständige Commit-SHA der freigegebenen CI/CD-Version ein und erstellt Aktualisierungsbranches und Pull Requests. Er pusht nicht direkt auf geschützte Branches. |
| 6.4 | offen | Idempotenz prüfen | Ein erneuter Lauf erzeugt keinen weiteren Pull Request, wenn die Zielbranch-Dateien bereits auf dem vorgesehenen Stand sind. |

## 7. Git-Client und Bedienabläufe abnehmen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 7.1 | offen | EGit-Grundablauf prüfen | Klonen, Feature-Branch erstellen, Status prüfen, committen, pushen und aktualisieren sind in der M/Text Workbench erfolgreich. |
| 7.2 | offen | Parallele Releaselinien prüfen | Getrennte Klone oder Eclipse-Arbeitsbereiche für R270 auf `main`, R261 auf `release/R261` und ein länger laufendes Feature für R271 sind praktisch erprobt. |
| 7.3 | offen | Pull-Request-Ablauf prüfen | Ein Feature wird in Entwicklung getestet, als Pull Request geprüft, mit Squash Merge zusammengeführt und danach in Abnahme synchronisiert. |
| 7.4 | offen | Linienübergreifende Korrektur prüfen | Ein Squash-Commit wird bei Bedarf per Cherry-Pick auf einen Feature-Branch einer weiteren Releaselinie übernommen und dort regulär über einen Pull Request weitergegeben. |
| 7.5 | offen | Release-Tag-Bedienung prüfen | Das Anlegen und Pushen eines zulässigen Release-Tags ist mit dem freigegebenen Git-Client nachvollziehbar dokumentiert. |

## 8. Migration und End-to-End-Abnahme

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 8.1 | offen | SVN-Importumfang freigeben | Aktive Releaselinien, Projekte, Ausschlüsse, `.100`-Basen und weitere benötigte Release-Stände sind je Mandant benannt. |
| 8.2 | offen | Testimport durchführen | `main`, benötigte `release/Rnnn`-Branches und geschützte `v...`-Tags bilden die freigegebenen SVN-Stände nachvollziehbar ab. |
| 8.3 | offen | Nichtproduktiven Gesamtablauf abnehmen | Feature-Push, Entwicklungstest, Pull Request, Squash Merge, Abnahmesynchronisation, FULL oder DELTA und Mainframe-Übergabe sind erfolgreich. |
| 8.4 | offen | Linienwechsel erproben | Die bisherige Hauptlinie wird als Release-Branch erhalten. Der erste `main`-Commit der neuen Releaselinie wird vollständig nach Entwicklung und Abnahme synchronisiert. Beide Linien können anschließend unabhängig geändert werden. |
| 8.5 | offen | Mandantentests abschließen | Die vorgesehenen Mandantenverantwortlichen und Entwickler haben ihre Bedienabläufe erfolgreich durchgeführt und bestätigt. |
| 8.6 | offen | Produktiven Endimport durchführen | Der freigegebene SVN-Endstand ist übernommen. Git und GitHub Actions sind für den Prozess führend. |
