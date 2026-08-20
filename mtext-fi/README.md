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

Ein Release ohne Buchstabensuffix wird über den Workflow **Release
vorbereiten** und einen von der anfordernden Person eröffneten
Freigabe-Pull-Request erstellt. Nach Review und Merge setzt der Workflow den
Release-Tag. Für die Tags gilt:

- `v261.100` erzeugt ein FULL,
- ein weiterer Tag wie `v261.108` erzeugt ein kumulatives DELTA gegen
  `v261.100`,
- ein Tag mit einem Buchstabensuffix wie `v261.108a` kennzeichnet einen
  Beta-Lieferstand und erzeugt dasselbe kumulative DELTA.

Der Mandanten-Workflow startet automatisch den zentralen CI/CD-Releaseweg in
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Das FTPS-Passwort liegt nicht
in diesem Repository.

## Mandantenkonfiguration

`.github/config.json` enthält unter anderem Mandantenkürzel, führende
`releaselinie`, das zuletzt freigegebene Release, Ausschlüsse und Hostprofile.
Eine Änderung der Datei startet die Konfigurationsprüfung.

## Weitere Informationen

- [Workflow-Vertrag und GitHub-Einrichtung](.github/workflows/README.md)
- [Zielbild](../docs/confluence/Zielbild_GitHub_Actions_Git.md)
- [Benutzeranleitung](../docs/confluence/Benutzeranleitung.md)
