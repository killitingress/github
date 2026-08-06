# CI/CD-Workflow-Vertrag des Mandanten-Repositories

Die Workflowdateien enthalten die Git-Auslöser des Mandanten. Die
CI/CD-Implementierung wird über eine vollständige Commit-SHA aus
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, kurz `mtext_actions`, geladen.

## Benötigtes Repository-Secret

`MTEXT_ACTIONS_TOKEN` ist ein Fine-grained PAT eines technischen
GitHub-Benutzers. Es ist auf das zentrale CI/CD-Repository begrenzt
und besitzt:

- `Contents: read` zum Laden der freigegebenen CI/CD-Version,
- `Actions: write` zum Starten des zentralen Release-Workflows.

Mainframe-Zugangsdaten liegen nicht im Mandanten-Repository.

## `validate-config.yml`

Ein Push mit einer Änderung an `.github/config.json` startet die zentrale
Konfigurationsprüfung. Der Lauf überträgt keine Ressourcen und liest keine
Mainframe-Secrets.

## `sync-resources.yml`

Automatische Auslöser:

| Branch | Ziel |
|---|---|
| `feature/Rnnn/<Bezeichnung>` | M/Text-Entwicklung der Releaselinie |
| `release/Rnnn` | M/Text-Abnahme der Releaselinie |
| `main` | M/Text-Abnahme der in `.github/config.json` genannten Releaselinie |

Der manuelle Start erhält eine vollständige Commit-SHA. Er gleicht den Commit
vollständig mit dem Ziel des ausgewählten Branches ab. Feature-Branches führen
nach Entwicklung, `main` und Release-Branches nach Abnahme. Die Releaselinie
stammt aus dem ausgewählten Branch und bei `main` aus der Mandantenkonfiguration
des Commits. Normale Läufe verwenden den zuletzt von LTOMA angenommenen Commit
als Vergleichsstand und übertragen die geänderten Ressourcen.

Ändert ein Push nach `main` die konfigurierte Releaselinie, wird dieser erste
Stand automatisch vollständig nach Entwicklung und Abnahme synchronisiert.

## `release.yml`

Ein Push eines Tags wie `v261.100` oder `v261.108` ruft den Dispatch-Workflow
der freigegebenen CI/CD-Version auf. Dieser startet `release.yml` in
`mtext_actions` mit Repository, Tag, auslösender Commit-SHA und der
CI/CD-Version.

Paketbau und Mainframe-Übergabe laufen anschließend in `mtext_actions`. Der
Mandantenlauf erhält keinen FTP-Zugang.

## Aktualisierung

Der zentrale Aktualisierungsworkflow erstellt für `main` und vorhandene
Release-Branches einen technischen Aktualisierungsbranch und einen Pull
Request. Nach Review wird dieser mit Squash Merge zusammengeführt.
