# Kurzanleitung

Dieses Repository enthält die M/Text-Briefressourcen der FI.
Diese Kurzanleitung fasst die häufigsten Abläufe zusammen. Die separate
Benutzeranleitung enthält zusätzlich Git-Grundlagen, Rücknahmen, Wiederanläufe
und Fehlerbilder.

Der aktuelle Projektstand dieses Mandanten umfasst folgende Projekte:

- `Configuration`
- `Fonts`
- `LOMS_Framework`
- `LOMS_Basis`
- `LOMS_PKA`

`LOMS_Testdaten` gehört zum Repository, ist aber von der Synchronisation
(mittels `excluded_projects` in `.github/config.json`) ausgeschlossen.
Reguläre Dateien in der Repositorywurzel werden nicht als Projekte verarbeitet.
Verzeichnisse, deren Namen mit einem Punkt beginnen, werden ebenfalls ignoriert.

## Branches

Es gibt normaler Weise immer drei aktive Releaselinien und jede Releaselinie
besitzt drei Branches:

| Branch | Verwendung |
|---|---|
| `<Releaselinie>/Entwicklung` | Branch für initiale Entwicklungen fachlicher Anforderungen |
| `<Releaselinie>/Abnahme` | Branch für Funktionstests und Abnahmen entwickelter Änderungen |
| `<Releaselinie>/Bereitstellung` | abgenommene Änderungen für eine Lieferung zusammenstellen |

Zusätzlich können Feature-Branches verwendet werden.
Der Default Branch ist üblicher Weise der Entwicklungsbranch der führenden
Releaselinie.

## Änderung nach Entwicklung bringen

1. Entwicklungsbranch der gewünschten Releaselinie auschecken / aktualisieren.
2. M/Text-Ressourcen bearbeiten und lokal prüfen.
3. Die Änderung committen und dann nach GitHub pushen.
4. Den Workflow **Sync M/Text resources** kontrollieren.

Der Workflow synchronisiert den Projektstand des gepushten Commits mit
M/Text-Entwicklung.

## Änderung zur Abnahme und Bereitstellung weitergeben

1. Den fachlich freigegebenen Commit per Cherry-Pick auf den Zielbranch
   übernehmen.
2. Den übernommenen Gesamtstand prüfen.
3. Den Zielbranch pushen. Bei der Abnahme anschließend den Workflow
   **Sync M/Text resources** kontrollieren.

Die Weitergabe erfolgt zuerst nach `<Releaselinie>/Abnahme` und danach nach
`<Releaselinie>/Bereitstellung`. Bei einer Push-Ablehnung oder einem Konflikt
wird der Zielstand zuerst aktualisiert und das fachlich richtige Ergebnis vor
dem nächsten Push geprüft.

## FULL- oder DELTA-Lieferung auslösen

Das Mandanten-Release-Team setzt einen Git-Tag auf den gewünschten Commit des
Bereitstellungsbranches:

- `<Releaselinie>.100`, beispielsweise `R261.100`, erzeugt ein FULL.
- Jeder weitere gültige Tag derselben Linie erzeugt ein kumulatives DELTA
  gegenüber `.100`.

Ein FULL enthält je Projekt das vollständige F-Paket und zusätzlich ein leeres
D-Paket mit leerem Projektverzeichnis und leerer Löschliste.

Der Release-Tag ist die fachliche Freigabe. Der Release-Workflow prüft den Tag,
baut die Lieferdateien und übergibt sie nach erfolgreicher Prüfung automatisch
an den Mainframe.

## Mandantenkonfiguration

.github/config.json legt für den Mandante relevante Parameter fest. Ein Push
der Datei startet den Config-Check.

## Weitere Informationen

- [Workflow-Vertrag und GitHub-Einrichtung](.github/workflows/README.md)
