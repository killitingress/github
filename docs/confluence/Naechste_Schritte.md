# Offene Arbeiten in GitHub

| Status | Tätigkeit | Fertig, wenn |
|---|---|---|
| ☐ | Vorgaben für Shared Workflows klären | Ziel-Organization, Repositoryzuschnitt, Sichtbarkeit, organisationsübergreifender Zugriff und GitHub-Actions-Richtlinien sind mit den GitHub-Admins festgelegt. |
| ☐ | Technische Identität klären | Eine vom persönlichen Benutzer unabhängige Authentisierung für beide Zugriffsrichtungen ist festgelegt. Bei einer GitHub App sind Eigentümer, Installationen und Repositoryberechtigungen geklärt. |
| ☐ | Zentrale CI/CD-Version bereitstellen | Die Änderungen in `mtext_actions` sind nach erfolgreicher **Zentraler Testsuite** in `main` zusammengeführt. Die Mandanten-Workflows verweisen auf `mtext_actions@main`. |
| ☐ | Zentrales Repository konfigurieren | Die festgelegte technische Identität, `MAINFRAME_FTPS_PASSWORD` sowie `MAINFRAME_FTPS_HOST`, `MAINFRAME_FTPS_PORT` und `MAINFRAME_FTPS_USER` sind eingerichtet. Der technische Zugriff kann die zugeordneten Mandanten-Repositories lesen, Liefer-Tags erstellen und GitHub Releases veröffentlichen. |
| ☐ | Runner bereitstellen | Der Runner mit den Labels `self-hosted` und `linux` kann GitHub und Mainframe erreichen. |
| ☐ | Transport nach `serverSync` klären | Eine der im Zielbild genannten Möglichkeiten ist ausgewählt und ihre technischen Voraussetzungen sind beschrieben. |
| ☐ | Mandanten-Repositories anlegen | Der freigegebene Ausgangsstand und die benötigten Liefer-Tags sind importiert. `main`, die vorherige Releaselinie und die kommende Releaselinie bestehen. Die organisationsweiten Regeln schützen `main` und `release/nnn`. `.github/config.json` enthält die Angaben des Mandanten. |
| ☐ | Mandantenzugriff und zentrale Zuordnungen einrichten | Die festgelegte technische Identität kann die Shared Workflows laden und zentrale Lieferworkflows starten. `config/mandanten.json` und `config/releaselinien.json` enthalten die benötigten Mandanten, Releaselinien, ETAPS-Linien und Hostprofile. |
| ☐ | M/Text-Ablauf abnehmen | Feature-Push, Pull Request mit Squash Merge, Synchronisation nach M/Text-Entwicklung und M/Text-Funktionstest sowie der Wechsel der führenden Releaselinie funktionieren im Mandanten-Repository. |
| ☐ | Mainframe-Lieferung abnehmen | FULL mit `.100`, kumulatives DELTA, Teillieferung, bewusst bestätigte Direktlieferung, Vier-Augen-Freigabe sowie erstmalige und erneute Ausführung über **Lieferung ausführen** laufen erfolgreich. Liefer-Tag, Mainframe-Übergabe und GitHub Release zeigen denselben Git-Stand. |
| ☐ | Produktiv umstellen | Der freigegebene SVN-Endstand ist importiert, die vorgesehenen Mandanten arbeiten mit den eingerichteten Workflows und GitHub ist für den Ablauf führend. |
