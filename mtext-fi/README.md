# `fi_lbs_entw_oms_fi`

Das Repository `FinanzInformatik/fi_lbs_entw_oms_fi` enthält die
M/Text-Briefressourcen der FI. Die ausführlichen Bedienabläufe stehen in der
zentralen Benutzeranleitung.

Der aktuelle Projektstand umfasst:

- `Configuration`
- `Fonts`
- `LOMS_Framework`
- `LOMS_Basis`
- `LOMS_PKA`

`LOMS_Testdaten` bleibt versioniert, ist aber in `.github/config.json` von
Synchronisation und Releasepaketen ausgeschlossen.

## Branches

| Branch | Verwendung |
|---|---|
| `main` | führende Releaselinie aus `.github/config.json` |
| `release/nnn` | parallel gepflegte Releaselinie |
| `feature/nnn/<Bezeichnung>` | einzelne fachliche Änderung |
| `bereitstellung/nnn.nnn` | Arbeitsbranch einer Teillieferung |

`main` und `release/nnn` sind geschützt. Änderungen werden über Pull Requests
geprüft und mit Squash Merge zusammengeführt.

## Änderung bearbeiten

1. Den geschützten Zielbranch aktualisieren.
2. Einen Feature-Branch der vorgesehenen Releaselinie erstellen.
3. M/Text-Ressourcen bearbeiten und committen.
4. Den Feature-Branch pushen.
5. Den automatischen Synchronisationslauf und anschließend die Änderung in
   M/Text-Entwicklung prüfen.
6. Einen Pull Request auf `main` oder `release/nnn` erstellen.
7. Nach Review mit Squash Merge zusammenführen.
8. Den automatischen Synchronisationslauf und den Stand in
   M/Text-Funktionstest prüfen.

## FULL oder DELTA auslösen

Eine Lieferung wird über den Workflow **Lieferung vorbereiten** auf dem
ausgewählten Branch vorbereitet. Die Vorprüfung hält SHA und Lieferumfang fest
und ordnet sie dem geplanten Liefer-Tag zu. Danach startet eine Person
**Lieferung ausführen** mit diesem Tag. Dieselbe Person bestätigt eine
Direktlieferung bewusst als Abweichung. Eine andere Person erfüllt das
empfohlene Vier-Augenprinzip.
Der zentrale Lauf setzt den Liefer-Tag auf der festgehaltenen SHA.

- `r261.100` entsteht auf `main` oder `release/261` und erzeugt ein FULL
- ein weiterer Tag wie `r261.108` erzeugt ein kumulatives DELTA gegen
  `r261.100`

Teillieferungen werden auf `bereitstellung/nnn.nnn` zusammengestellt. Der
Ausführungslauf startet die zentrale Mainframe-Lieferung in
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Ein Tag-Push allein startet
keine Mainframe-Übergabe. Das FTPS-Passwort liegt nicht in diesem Repository.

Wird **Lieferung ausführen** mit einem vorhandenen Liefer-Tag gestartet, wird
sein Stand ohne erneute Bestätigung noch einmal an den Mainframe übertragen.

## Mandantenkonfiguration

`.github/config.json` enthält unter anderem Mandantenkürzel, führende
`releaselinie`, Ausschlüsse und Hostprofile.
Eine Änderung der Datei startet die Konfigurationsprüfung.

## Weitere Informationen

- [Workflow-Vertrag und GitHub-Einrichtung](.github/workflows/README.md)
- [Zielbild](../docs/confluence/Zielbild_GitHub_Actions_Git.md)
- [Benutzeranleitung](../docs/confluence/Benutzeranleitung.md)
