# M/Text-Mandanten-Repository

Das Repository enthält die M/Text-Projekte eines Mandanten sowie dessen
GitHub-Konfiguration und Trigger-Workflows. Die Projektverzeichnisse liegen
direkt in der Repositorywurzel. Verzeichnisse, die nicht synchronisiert oder
geliefert werden sollen, können in der Mandantenkonfiguration ausgeschlossen
werden.

## Mandantenkonfiguration

`.github/config.json` ordnet das Repository einem Mandanten und seinen
technischen Zielen zu:

| Feld | Inhalt |
|---|---|
| `kuerzel` | Mandantenkürzel |
| `releaselinie` | von `main` geführte Releaselinie |
| `ispw` | CodePipeline-Umgebung |
| `excluded_projects` | von Synchronisation und Lieferung ausgeschlossene Projektverzeichnisse |
| `hostprofile` | Assignment und CodePipeline-Stage der verwendeten Hostprofile |

## Voraussetzungen

Für die Bearbeitung werden Zugriff auf das GitHub-Repository, ein lokaler Klon
im Arbeitsbereich der M/Workbench, eine konfigurierte Git-Identität und die
Releaselinie der Änderung benötigt.

## Ressourcen ändern

Eine Änderung wird auf einem Feature-Branch der betroffenen Releaselinie
bearbeitet:

1. `main` oder den passenden Branch `release/nnn` aktualisieren.
2. Davon einen Branch `feature/nnn/<Bezeichnung>` erstellen.
3. Die M/Text-Ressourcen bearbeiten, committen und den Feature-Branch nach
   GitHub pushen.
4. Unter **Actions** den Lauf **M/Text-Ressourcen synchronisieren** prüfen und
   die Änderung anschließend in M/Text-Entwicklung testen.
5. Einen Pull Request auf `main` oder `release/nnn` erstellen. Ziel- und
   Feature-Branch gehören dabei zur selben Releaselinie.
6. Die Ressourcenprüfung und das Review abschließen und die Änderung mit
   **Squash and merge** zusammenführen.
7. Den Synchronisationslauf des Zielbranches prüfen und den Stand in
   M/Text-Funktionstest abnehmen.

Korrekturen werden auf demselben Feature-Branch ergänzt und erneut nach
M/Text-Entwicklung übertragen. Soll eine zusammengeführte Änderung in eine
weitere Releaselinie übernommen werden, wird ihr Squash-Commit in einen neuen
Feature-Branch dieser Releaselinie übernommen.

## Mainframe-Lieferung

Liefer-Tags folgen dem Schema `rnnn.nnn`. Die Version `.100` erzeugt das FULL
einer Releaselinie. Spätere Versionen erzeugen ein kumulatives DELTA gegen
diesen `.100`-Tag.

1. In GitHub unter **Actions** den Workflow **Lieferung vorbereiten** öffnen.
2. `main`, den passenden Branch `release/nnn` oder einen vorbereiteten Branch
   `bereitstellung/nnn.nnn` auswählen und den geplanten Liefer-Tag eingeben.
3. In der Zusammenfassung Branch, Commit, Lieferart, Bezugsstand und
   Lieferumfang prüfen.
4. Den Workflow **Lieferung ausführen** öffnen und denselben Liefer-Tag
   eingeben.
5. Hat dieselbe Person die Lieferung vorbereitet, die Direktlieferung im
   Eingabefeld bewusst bestätigen.
6. Nach dem Lauf die Mainframe-Übergabe und das GitHub Release zum Liefer-Tag
   kontrollieren.

Ein vorhandener Liefer-Tag kann mit **Lieferung ausführen** erneut verarbeitet
werden. Dafür ist keine neue Vorbereitung erforderlich.

## Workflows

Die Dateien unter `.github/workflows` stellen die manuellen und automatischen
Einstiege des Repositories bereit. Die Verarbeitungsschritte werden aus
`FI-Actions/fi_lbs_entw_oms_mtext_actions` geladen.

| Datei | Auslöser | Aufgerufener Shared Workflow |
|---|---|---|
| `check-resources.yml` | Pull Request oder manueller Start | `shared-check-resources.yml` |
| `sync-resources.yml` | Push auf `main`, `release/nnn` oder `feature/nnn/**` sowie manueller Start | `shared-sync-resources.yml` |
| `lieferung-vorbereiten.yml` | manueller Start mit einem Liefer-Tag | `shared-lieferung-check.yml` |
| `lieferung-ausfuehren.yml` | manueller Start mit einem Liefer-Tag und optionaler Bestätigung der Direktlieferung | `shared-lieferung-ausfuehren.yml` |

Die Workflow-Aufrufe verwenden jeweils `@main` aus dem Repository
`FI-Actions/fi_lbs_entw_oms_mtext_actions`.

Für die Mainframe-Übergabe verwendet der Lieferworkflow dieses für das
Mandanten-Repository freigegebene organisationsweite Secret:

| Name | Art |
|---|---|
| `MAINFRAME_FTPS_PASSWORD` | organisationsweites Secret |

Das Secret wird nicht in den Einstellungen dieses Mandanten-Repositories
gepflegt. Der Trigger-Workflow reicht es an den Shared
Workflow für die Lieferung weiter.
