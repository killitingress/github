# Offene Arbeiten in GitHub

| Status | Tätigkeit | Fertig, wenn |
|---|---|---|
| ☐ | Zentrale CI/CD-Version bereitstellen | Die Änderungen in `mtext_actions` sind nach erfolgreicher **Zentraler Testsuite** in `main` zusammengeführt. Die Commit-SHA dieser Version ist für den Rollout festgehalten. |
| ☐ | Zentrales Repository konfigurieren | `WORKFLOW_CONFIGURATION_TOKEN`, `MAINFRAME_FTPS_PASSWORD` sowie `MAINFRAME_FTPS_HOST`, `MAINFRAME_FTPS_PORT` und `MAINFRAME_FTPS_USER` sind eingerichtet. Der technische Zugriff kann die zugeordneten Mandanten-Repositories lesen, Liefer-Tags erstellen, GitHub Releases veröffentlichen und Workflowdateien aktualisieren. |
| ☐ | Runner und Organisationsvariable bereitstellen | Der Runner mit den Labels `self-hosted` und `linux` kann GitHub, CIFS, Adapter und Mainframe erreichen. `MTEXT_CIFS_ROOT` ist als Organisationsvariable gesetzt. |
| ☐ | Mandanten-Repositories anlegen | Der freigegebene Ausgangsstand und die benötigten Liefer-Tags sind importiert. `main`, die vorherige Releaselinie und die kommende Releaselinie bestehen. Die organisationsweiten Regeln schützen `main` und `release/nnn`. `.github/config.json` enthält die Angaben des Mandanten. |
| ☐ | Mandantenzugriff und zentrale Zuordnungen einrichten | Jedes Mandanten-Repository enthält `MTEXT_ACTIONS_TOKEN`. `config/mandanten.json` und `config/releaselinien.json` enthalten die benötigten Mandanten, Releaselinien, ETAPS-Linien und Hostprofile. |
| ☐ | Mandanten-Workflows ausrollen | **Mandanten-Workflows aktualisieren** wurde mit der freigegebenen Commit-SHA ausgeführt. Die Workflowdateien in `main` und den vorhandenen `release/nnn` verweisen auf diese SHA. Es bestehen keine Verweise auf `0000000000000000000000000000000000000000`. |
| ☐ | M/Text-Ablauf abnehmen | Feature-Push, Pull Request mit Squash Merge, Synchronisation nach M/Text-Entwicklung und M/Text-Funktionstest sowie der Wechsel der führenden Releaselinie funktionieren im Mandanten-Repository. |
| ☐ | Mainframe-Lieferung abnehmen | FULL mit `.100`, kumulatives DELTA, Teillieferung, Direktlieferung, Vier-Augen-Freigabe und **Lieferung erneut übergeben** laufen erfolgreich. Liefer-Tag, Mainframe-Übergabe und GitHub Release zeigen denselben Git-Stand. |
| ☐ | Produktiv umstellen | Der freigegebene SVN-Endstand ist importiert, die vorgesehenen Mandanten arbeiten mit den ausgerollten Workflows und GitHub ist für den Ablauf führend. |
