# Bedienungsanleitung für `mtext-fi`

Dieses Repository enthält die M/Text Brief-Ressourcen des Mandanten.
FI ist der Master-Mandant, verantwortlich für die Projekte:

- `Configuration`
- `Fonts`
- `LOMS_Framework`
- `LOMS_Basis`
- `LOMS_PKA`

`LOMS_Testdaten` gehört zum Repository, ist aber von der Synchronisierung
mittels `excluded_projects` in `.github/config.json` ausgeschlossen.
Reguläre Dateien in der Repositorywurzel werden nicht als Projekte verarbeitet.
Verzeichnisse, deren Namen mit einem Punkt beginnen, werden ebenfalls ignoriert.

## Branches

Jede aktive Releaselinie besitzt drei Branches:

| Branch | Verwendung |
|---|---|
| `<Releaselinie>/Entwicklung` | Änderungen entwickeln und nach M/Text-Entwicklung synchronisieren |
| `<Releaselinie>/Abnahme` | freigegebene Änderungen nach M/Text-Abnahme synchronisieren |
| `<Releaselinie>/Bereitstellung` | abgenommene Änderungen für eine Lieferung zusammenstellen |

Zusätzlich können Feature-Branches verwendet werden.
Der Default Branch ist der Entwicklungsbranch der führenden Releaselinie,
beispielsweise `R261/Entwicklung`.

## Änderung nach Entwicklung bringen

1. Entwicklungsbranch der gewünschten Releaselinie auschecken / aktualisieren.
2. M/Text-Ressourcen bearbeiten und lokal prüfen.
3. Die Änderung committen und dann nach GitHub pushen.
4. Den Workflow **Sync M/Text resources** kontrollieren.

Der Workflow synchronisiert den Projektstand des gepushten Commits mit
M/Text-Entwicklung.

## Änderung zur Abnahme und Bereitstellung weitergeben

1. Den fachlich freigegebenen Commit mit dem bereitgestellten Git-Client per
   Cherry-Pick auf den Zielbranch übernehmen.
2. Die vollständige SHA des Quell-Commits mit `cherry-pick -x` oder einer
   gleichwertigen festen Herkunftszeile in der Commit-Nachricht speichern.
3. Den übernommenen Gesamtstand prüfen.
4. Den Zielbranch pushen. Bei der Abnahme anschließend den Workflow
   **Sync M/Text resources** kontrollieren.

Die Weitergabe erfolgt zuerst nach `<Releaselinie>/Abnahme` und danach nach
`<Releaselinie>/Bereitstellung`. Bei einer Push-Ablehnung oder einem Konflikt
wird der Zielstand zuerst aktualisiert und das fachlich richtige Ergebnis vor
dem nächsten Push geprüft. Force-Pushes sind nicht zulässig.

## FULL- oder DELTA-Lieferung auslösen

Das Mandanten-Release-Team setzt mit dem freigegebenen zusätzlichen Git-Client
einen Git-Tag auf den gewünschten Commit des Bereitstellungsbranches. Ein
zusätzliches GitHub Release wird nicht angelegt:

- `<Releaselinie>.100`, beispielsweise `R261.100`, erzeugt ein FULL.
- Jeder weitere gültige Tag derselben Linie erzeugt ein kumulatives DELTA
  gegenüber `.100`.

Der Release-Workflow prüft den Tag, baut die Lieferdateien und wartet vor der
Mainframe-Übergabe auf die Freigabe im GitHub Environment `Bereitstellung`.
Bis zu dieser Freigabe kann das Release-Team einen irrtümlich angelegten Tag
nach Abbruch des zugehörigen Workflow-Laufs löschen und bei Bedarf neu
anlegen. Mit der Freigabe werden Tagname und Ziel-Commit zur unveränderlichen
Release-Identität; danach darf der Tag weder verschoben noch gelöscht werden.
Eine fachliche Korrektur erfolgt mit einem neuen Commit und einem neuen
Release-Tag.

## Mandantenkonfiguration

[`.github/config.json`](.github/config.json) legt das Mandantenkürzel, das Repository, das
Mainframe-Subsystem, die ISPW-Instanz `T` oder `P`, die Hostprofile und
optionale Projektausschlüsse fest.
Alle anderen sichtbaren Verzeichnisse in der Repositorywurzel werden als
Projekte verarbeitet. Änderungen werden mit den benannten Mandanten- und
Betriebsverantwortlichen abgestimmt. Ein Push der Datei startet den
Config-Check.

## Weitere Informationen

- [Workflow-Vertrag und GitHub-Einrichtung](.github/workflows/README.md)
