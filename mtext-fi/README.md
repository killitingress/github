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
| `dry_run` | überspringt bei `true` die noch nicht verfügbare Adapter- und Mainframe-Übergabe |
| `excluded_projects` | von Prüfung, Synchronisierung und Lieferung ausgeschlossene Projektverzeichnisse |
| `hostprofile` | Assignment und CodePipeline-Stage der verwendeten Hostprofile |

Mit aktiviertem Dry Run bleiben Adapter-Versionsabfrage, Ressourcenprüfung und
Paketbau erhalten. Adapterauftrag, Archivupload sowie FTPS- und JES-Übergabe
werden simuliert. Der Liefer-Tag entsteht weiterhin. Das Freigabe-Issue erhält
das Label `dry_run` und vermerkt, dass keine Mainframe-Übergabe stattfand.

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
4. Unter **Actions** die Ressourcenprüfung und Synchronisierung im Lauf
   **Ressourcen synchronisieren** prüfen und die Änderung anschließend
   in M/Text-Entwicklung testen.
5. Einen Pull Request auf `main` oder `release/nnn` erstellen. Ziel- und
   Feature-Branch gehören dabei zur selben Releaselinie.
6. Das Review abschließen und die Änderung mit **Squash and merge**
   zusammenführen.
7. Den Synchronisierungslauf des Zielbranches prüfen und den M/Text-Stand in
   Funktionstest abnehmen.

Korrekturen werden auf demselben Feature-Branch ergänzt und erneut nach
M/Text-Entwicklung übertragen. Soll eine zusammengeführte Änderung in eine
weitere Releaselinie übernommen werden, wird ihr Squash-Commit in einen neuen
Feature-Branch dieser Releaselinie übernommen.

## Manuelle Synchronisierung und Releasewechsel

Unter **Actions → Ressourcen synchronisieren → Run workflow** den Branch und
die Zielumgebung auswählen. `Branchstandard` bedeutet Entwicklung für
Feature-Branches und Funktionstest für `main` und `release/nnn`. Alternativ
`Entwicklung`, `Funktionstest` oder `Beide` wählen. Ein manueller Lauf überträgt
FULL, bei `Beide` zuerst nach Entwicklung und dann nach Funktionstest.

Beim Releasewechsel werden Branches, `.github/config.json` und die zentrale
`config/releaselinien.json` manuell vorbereitet. Die Zielzuordnungen müssen
vor den ersten Feature-Pushes und vor dem Merge nach `main` bereitstehen:
Feature-Pushes übertragen automatisch nach Entwicklung, PR-Merges nach
`main` oder `release/nnn` nach Funktionstest. Das gilt auch für den
Vorbereitungs-Merge. Bei fehlender passender DELTA-Basis erfolgt FULL.
Das Anlegen oder direkte Pushen eines Release-Branches startet keinen Abgleich.

Anschließend die gewünschten Branches, etwa `main`, `release/261` und
`release/271`, mit ihrer Zielauswahl manuell synchronisieren. Commit,
Zielumgebungen und Ergebnisse je Lauf kontrollieren. Branches und Zuordnungen
werden durch die Synchronisierung nicht verändert.

Läufe werden im Repository nacheinander ausgeführt. GHES 3.20 hält einen
wartenden Lauf vor, der durch einen weiteren Start ersetzt werden kann.
Der letzte erfolgreiche Stand wird je Umgebungsart, Releaselinie und Branch
unter `refs/mtext/synchronisierungen/<Präfix>/<Releaselinie>/<Branch>`
festgehalten. Das Präfix liefert `mtext_umgebung_prefixe` aus
`config/releaselinien.json`. Diese technischen Referenzen verändern die
Arbeitsbranches nicht.
Deshalb die manuellen Abgleiche nacheinander starten und ihren Abschluss
kontrollieren. Bei einem Fehler nennt die Meldung eine bereits erfolgreich
verarbeitete Umgebung. Eine Wiederholung kann diese erneut übertragen.

## Mainframe-Lieferung

Liefer-Tags folgen dem Schema `rnnn.nnn`. Die Version `.100` erzeugt das FULL
einer Releaselinie. Spätere Versionen erzeugen ein kumulatives DELTA gegen
diesen `.100`-Tag. `main` und `release/nnn` ergeben `rnnn.100`. Ein Branch
`bereitstellung/nnn.nnn` ergibt den gleichnamigen Liefer-Tag mit Präfix `r`.

1. In GitHub unter **Actions** den Workflow **Lieferung vorbereiten** öffnen.
2. `main`, den passenden Branch `release/nnn` oder einen vorbereiteten Branch
   `bereitstellung/nnn.nnn` auswählen.
3. Die Warnungen der Ressourcenprüfung prüfen und das in der Zusammenfassung
   verlinkte Freigabe-Issue öffnen.
4. Im mit `lieferung:vorbereitet` gekennzeichneten Issue Branch, Commit,
   Lieferart, Bezugscommit und Lieferumfang prüfen.
5. Mit Repository-Berechtigung `maintain` oder `admin` den Kommentar
   `/freigabe` eintragen. Die vorbereitende Person darf selbst freigeben.
6. Nach dem ausgelösten Lauf die Mainframe-Übergabe und den Abschlusskommentar
   mit Archivnamen und SHA-256-Prüfsummen im Issue kontrollieren.

Das Freigabe-Issue erhält nach erfolgreicher Lieferung Links zum Lauf und zum
Liefer-Tag sowie eine Tabelle der übertragenen Archivdateien mit
SHA-256-Prüfsummen. Danach wird es geschlossen. Der annotierte Liefer-Tag
enthält die Nummer des Freigabe-Issues. Für einen Wiederanlauf im zugehörigen
Issue `/wiederholung` kommentieren. Eine neue Vorbereitung ist nicht
erforderlich. Die kommentierende Person benötigt `maintain` oder `admin`.
Vor dem Paketbau wird der Tag aus dem Issue-Titel gelesen und geprüft, ob
seine Annotation auf dieses Issue verweist. Das Issue erhält danach einen weiteren
Abschlusskommentar.

Bis zum Tagging hält
`refs/mtext/lieferungen/<Liefer-Tag>` den vorbereiteten Commit fest. Ein offenes
Issue mit `lieferung:vorbereitet` oder `lieferung:gestartet` sperrt eine neue
Vorbereitung dieses Tags. Soll stattdessen ein neuer Stand vorbereitet werden,
muss ein Maintainer das bisherige Issue zuvor schließen. Nach erfolgreichem
Tagging wird die technische Referenz entfernt. Ein Fehler bei dieser
Bereinigung erscheint als Warnung und ändert den Liefer-Tag nicht.

## Workflows

Die Dateien unter `.github/workflows` stellen die manuellen und automatischen
Einstiege des Repositories bereit. Die Verarbeitungsschritte werden aus
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` geladen.

Die eigenständige Ressourcenprüfung umfasst den ausgewählten Branchcommit. In
der Synchronisierung und Liefervorbereitung folgt ihr Umfang der jeweiligen
FULL- oder DELTA-Verarbeitung. Bei einem DELTA werden die seit dem fachlichen
Vergleichscommit geänderten Ressourcen geprüft.

| Datei | Auslöser | Aufgerufener Shared Workflow |
|---|---|---|
| `check-resources.yml` | manueller Start auf einem ausgewählten Branch | `shared-check-resources.yml` |
| `sync-resources.yml` | Push auf `feature/nnn/**`, PR-Merge nach `main` oder `release/nnn` sowie manueller Start | zuerst `shared-check-resources.yml`, danach `shared-sync-resources.yml` |
| `lieferung-vorbereiten.yml` | manueller Start auf einem Lieferzweig | zuerst `shared-check-resources.yml`, danach `shared-lieferung-check.yml` |
| `lieferung-ausfuehren.yml` | `/freigabe` oder `/wiederholung` im Freigabe-Issue | `shared-lieferung-ausfuehren.yml` |

Die Workflow-Aufrufe verwenden `@test` aus dem Repository
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Die dort geladene Workflow-Datei
lädt die Python-Implementierung vom selben Branch.

Für die Mainframe-Übergabe verwendet der Lieferworkflow dieses für das
Mandanten-Repository freigegebene organisationsweite Secret:

| Name | Art |
|---|---|
| `IZE9_FTPS_PASSWORD_MTEXT` | organisationsweites Secret |

Das Secret wird nicht in den Einstellungen dieses Mandanten-Repositories
gepflegt. Der Trigger-Workflow reicht es an den Shared
Workflow für die Lieferung weiter.
