# Nächste Schritte (OPL)

## 1. Git-Vertrag umsetzen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 1.1 | bestätigt | Branch-Modell festlegen | `main`, `release/Rnnn` und `feature/Rnnn/<Bezeichnung>` sind im Zielbild beschrieben. Entwicklung und Abnahme sind M/Text-Ziele und keine Git-Branches. |
| 1.2 | offen | Geschützte Branches einrichten | `main` ist Default Branch und kann nicht gelöscht oder umbenannt werden. Änderungen an `main` und `release/Rnnn` sind ausschließlich über Pull Requests im Vier-Augenprinzip möglich. Force-Pushes sind gesperrt. |
| 1.3 | offen | Squash Merge einrichten | `Allow squash merging` ist aktiviert. Merge Commits und Rebase Merge sind deaktiviert. Ein Test-Pull-Request erzeugt einen Commit auf dem Zielbranch. |
| 1.4 | offen | Organisationsweite Tagregeln prüfen | Ein Tag wie `v261.108` kann auf einem Commit eines geschützten Branches erstellt und danach nicht gelöscht werden. Die Mandanten-Repositories besitzen keine abweichende Tagregel. |
| 1.5 | offen | Führende Releaselinie versionieren | `.github/config.json` enthält auf `main` die zugehörige `releaselinie`. Der Wechsel wird über einen Pull Request geprüft. |
| 1.6 | offen | Repositories und Verantwortliche einrichten | `mtext-actions`, `mtext-fi`, die weiteren Mandanten-Repositories und `mtext-support` sind angelegt. Die jeweiligen Repository-Verantwortlichen sind benannt und über IDNeo berechtigt. |

## 2. Runner und technische Berechtigungen bereitstellen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 2.1 | offen | Runner der FI bereitstellen | Das bestätigte `runs-on`-Kennzeichen ist als Repositoryvariable `FI_RUNNER_LABEL` in `mtext-actions` hinterlegt. Python ab Version 3.11 und Git stehen bereit. |
| 2.2 | offen | Repositoryübergreifenden Lesezugriff einrichten | Der zentrale Release-Workflow kann die in `config/mandanten.json` aufgeführten privaten Mandanten-Repositories und ihre Tags lesen. |
| 2.3 | teilweise bestätigt | Fine-grained PAT für den zentralen Zugriff einrichten | Die Organisation und `mtext-actions` sind auswählbar. Das Token erhält `Actions: read and write` und `Contents: read` auf diesem Repository. Tokeninhaber, erforderliche Genehmigung und Erneuerung vor Ablauf sind festgelegt. Ein Test lädt die gepinnte Automatisierung und startet den vorgesehenen Workflow in `mtext-actions`. |
| 2.4 | offen | Technische Workflow-Aktualisierung berechtigen | `WORKFLOW_CONFIGURATION_TOKEN` liegt als Repository-Secret in `mtext-actions`. Es kann Aktualisierungsbranches und Pull Requests in den vorgesehenen Mandanten-Repositories erstellen. |

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
| 4.2 | offen | Geschützte Branches nach Abnahme routen | Ein Merge nach `release/Rnnn` synchronisiert die genannte Linie nach Abnahme. Ein Merge nach `main` verwendet die dort konfigurierte `releaselinie`. |
| 4.3 | offen | Dauerhaften `serverSync`-Stand implementieren | Der zuletzt erfolgreich synchronisierte Commit wird je Repository, Releaselinie und M/Text-Ziel festgehalten. Ein normaler Lauf überträgt neue und geänderte Ressourcen und entfernt in Git gelöschte Ressourcen. Unveränderte Ressourcen werden nicht erneut übertragen. |
| 4.4 | offen | Vollsynchronisation bereitstellen | Der erste Lauf und ein Wiederherstellungslauf stellen den vollständigen Stand der zugeordneten Projektverzeichnisse her, ohne andere Mandantenverzeichnisse zu verändern. |
| 4.5 | offen | Parallelität begrenzen | Läufe für dasselbe Repository, dieselbe Releaselinie und dasselbe M/Text-Ziel werden nacheinander ausgeführt. Unterschiedliche Ziele können parallel laufen. |
| 4.6 | offen | M/Text-Netzwerkpfade prüfen | Der Runner erreicht `serverSync` und die LTOMA-Adressen der Entwicklungs- und Abnahmeziele. Die interne CA ist im Truststore vorhanden. |
| 4.7 | offen | Synchronisation und Wiederanlauf abnehmen | Zwei abwechselnd gepushte Feature-Branches derselben Linie stellen jeweils ihren Zielstand her. Ein fehlgeschlagener Lauf verändert den gespeicherten erfolgreichen Commit nicht. |

## 5. Zentralen Releaseweg umstellen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 5.1 | offen | Tagformat umstellen | Releasebau und Tests erkennen `v261.100`, `v261.108` und entsprechende Tags anderer aktiver Linien. Alte Formate werden nicht als Release-Auslöser verwendet. |
| 5.2 | offen | Zentralen Workflow ausführen | Ein Release-Tag im Mandanten-Repository startet automatisch einen Lauf in `mtext-actions`. Der Lauf verarbeitet Repository, Tag und vollständigen Ziel-Commit. |
| 5.3 | offen | Mainframe-Zugang zentral hinterlegen | `MAINFRAME_FTP_HOST` und `MAINFRAME_FTP_USER` liegen als Repositoryvariablen in `mtext-actions`. `MAINFRAME_FTP_PASSWORD` liegt dort als Repository-Secret. Mandanten-Repositories enthalten diese Werte nicht. |
| 5.4 | offen | FULL und DELTA abnehmen | `v261.100` erzeugt das vollständige F-Paket und das leere D-Paket. `v261.108` erzeugt ein kumulatives DELTA gegen `v261.100`. Manifest, Prüfsummen und Lieferbelege verwenden die neuen Tagnamen. |
| 5.5 | offen | Mainframe-Übergabe prüfen | FTP-Anmeldung, Paketübertragung, JCL-Erzeugung und `SITE FILETYPE=JES` sind mit dem zentralen technischen Benutzer erfolgreich. |
| 5.6 | offen | Wiederanlauf prüfen | Ein fehlgeschlagener Übergabeversuch kann mit demselben geprüften Artefakt wiederholt werden. |

## 6. Workflow-Aktualisierung per Pull Request umstellen

| Nr. | Status | Tätigkeit | Prüfergebnis |
|---|---|---|---|
| 6.1 | offen | Rollout-Matrix anpassen | Die Matrix enthält `main` und die gepflegten `release/Rnnn`-Branches der Mandanten-Repositories. Stage- und Feature-Branches sind nicht enthalten. |
| 6.2 | offen | Aktualisierungs-Pull-Requests erstellen | Der zentrale Lauf erstellt Aktualisierungsbranches und Pull Requests. Er pusht nicht direkt auf geschützte Branches. |
| 6.3 | offen | Idempotenz prüfen | Ein erneuter Lauf erzeugt keinen weiteren Pull Request, wenn die Zielbranch-Dateien bereits auf dem vorgesehenen Stand sind. |

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
| 8.4 | offen | Linienwechsel erproben | Die bisherige Hauptlinie wird als Release-Branch erhalten, `main` erhält die neue `releaselinie` und beide Linien können anschließend unabhängig geändert werden. |
| 8.5 | offen | Mandantentests abschließen | Die vorgesehenen Mandantenverantwortlichen und Entwickler haben ihre Bedienabläufe erfolgreich durchgeführt und bestätigt. |
| 8.6 | offen | Produktiven Endimport durchführen | Der freigegebene SVN-Endstand ist übernommen. Git und GitHub Actions sind für den Prozess führend. |
