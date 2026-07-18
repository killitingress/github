# Bedienungsanleitung für `mtext-fi`

Dieses Repository enthält die FI-Ressourcen für M/Text. FI ist der
Master-Mandant für die unfragmentierten Projekte:

- `Configuration`
- `Fonts`
- `LOMS_Framework`
- `LOMS_Basis`
- `LOMS_PKA`

`LOMS_Testdaten` gehört zum Repository, wird aber nicht synchronisiert oder
ausgeliefert. Ein Fragmentprojekt `LOMS_Basis[FI]` wird nicht verwendet.

## Branches

Jede aktive Releaselinie besitzt drei Branches:

| Branch | Verwendung |
|---|---|
| `<Releaselinie>/Entwicklung` | Änderungen entwickeln und nach M/Text-Entwicklung synchronisieren |
| `<Releaselinie>/Abnahme` | freigegebene Änderungen nach M/Text-Abnahme synchronisieren |
| `<Releaselinie>/Bereitstellung` | abgenommene Änderungen für eine Lieferung zusammenstellen |

Zusätzliche Feature-Branches können für länger laufende Arbeiten verwendet
werden. Die führende Releaselinie, beispielsweise `R261/Entwicklung`, ist der
Default Branch.

## Änderung nach Entwicklung bringen

1. Den Entwicklungsbranch der richtigen Releaselinie auschecken und
   aktualisieren.
2. Die M/Text-Ressourcen bearbeiten und lokal prüfen.
3. Die Änderung committen und nach GitHub pushen.
4. Den Workflow **Sync M/Text resources** kontrollieren.

Der Workflow synchronisiert den vollständigen konfigurierten Projektstand des
gepushten Commits nach M/Text-Entwicklung.

## Änderung zur Abnahme und Bereitstellung weitergeben

1. Den fachlich freigegebenen Commit mit dem bereitgestellten Git-Client per
   Cherry-Pick auf den Zielbranch übernehmen.
2. Die vollständige SHA des Quell-Commits mit `cherry-pick -x` in der
   Commit-Nachricht dokumentieren.
3. Den übernommenen Gesamtstand prüfen.
4. Den Zielbranch pushen. Bei der Abnahme anschließend den Workflow
   **Sync M/Text resources** kontrollieren.

Die Weitergabe erfolgt zuerst nach `<Releaselinie>/Abnahme` und danach nach
`<Releaselinie>/Bereitstellung`. Bei einer Push-Ablehnung oder einem Konflikt
wird der Zielstand zuerst aktualisiert und das fachlich richtige Ergebnis vor
dem nächsten Push geprüft. Force-Pushes sind nicht zulässig.

## FULL- oder DELTA-Lieferung auslösen

Das Mandanten-Release-Team setzt den Release-Tag auf den gewünschten Commit des
Bereitstellungsbranches:

- `<Releaselinie>.100`, beispielsweise `R261.100`, erzeugt ein FULL.
- Jeder weitere gültige Tag derselben Linie erzeugt ein kumulatives DELTA
  gegenüber `.100`.

Der Release-Workflow prüft den Tag, baut die Lieferdateien und wartet vor der
Mainframe-Übergabe auf die Freigabe im GitHub Environment `Bereitstellung`.
Bestehende Release-Tags dürfen nicht verändert oder gelöscht werden.

## Mandantenkonfiguration

[`config/mandant.json`](config/mandant.json) legt die ausgelieferten Projekte,
das Mandantenkürzel, das Repository, das Mainframe-Subsystem und die
Übergabeprofile fest. Änderungen werden mit den benannten Mandanten- und
Betriebsverantwortlichen abgestimmt. Ein Push der Datei startet den
Config-Check.

## Weitere Informationen

- [Workflow-Vertrag und GitHub-Einrichtung](.github/workflows/README.md)
