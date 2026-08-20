# CI/CD-Workflows des Mandanten-Repositories

Die Workflowdateien starten die Läufe dieses Mandanten-Repositories. Die
eigentliche CI/CD-Implementierung kommt aus
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` (`mtext_actions`) über eine
Commit-SHA.

## Voraussetzungen

`MTEXT_ACTIONS_TOKEN` ist ein Fine-grained PAT eines technischen
GitHub-Benutzers für `mtext_actions` mit:

- `Contents: read` zum Laden der CI/CD-Version
- `Actions: write` zum Starten des zentralen Release-Workflows

Mainframe-Zugangsdaten liegen nicht im Mandanten-Repository.

Die Organisationsvariable `MTEXT_CIFS_ROOT` bezeichnet den auf dem Runner
eingehängten CIFS-Basispfad für die Adapterübergabe.

## `check-resources.yml`

Bei jedem Pull Request prüft der Lauf die Mandantenkonfiguration und nur die
geänderten Ressourcen. Manuell prüft der Lauf standardmäßig den gesamten Stand;
die Ressourcenprüfung lässt sich dabei abwählen. Dateiendungen und Formate
stehen in `config/ressourcenformate.json` in `mtext_actions`. Syntaxbefunde
erscheinen als Warnungen und blockieren den Merge nicht.

## `sync-resources.yml`

| Branch | Ziel |
|---|---|
| `feature/Rnnn/<Bezeichnung>` | M/Text-Entwicklung der Releaselinie |
| `release/Rnnn` | M/Text-Funktionstest der Releaselinie |
| `main` | M/Text-Funktionstest der in `.github/config.json` genannten Releaselinie |

Ein Push übergibt die geänderten Projekte über CIFS an den Adapter. Der
manuelle Start gleicht die angegebene Commit-SHA vollständig mit dem Ziel des
ausgewählten Branches ab. Ändert ein Push nach `main` die Releaselinie, folgt
ein vollständiger Abgleich mit M/Text-Entwicklung und M/Text-Funktionstest.

## `release-approval.yml`

Der manuelle Start trägt die Release-Version aus dem Wartungstool als
`letztes_release` in `.github/config.json` auf einem Branch
`release-approval/...` ein. Die anfordernde Person eröffnet den Pull Request
auf den Lieferbranch selbst. Ein Check zeigt Branchstand und Lieferumfang.
Nach Merge entsteht der Release-Tag auf dem Merge-Commit.

Ein Push eines Tags (`v261.100`, `v261.108`, `v261.108a`) startet den zentralen
Workflow `release.yml`. Beta-Tags brauchen keinen Freigabe-Pull-Request.
Paketbau und Mainframe-Übergabe laufen in `mtext_actions`.

## Aktualisierung

Der zentrale Workflow **Mandanten-Workflows aktualisieren** schreibt die
Verweise auf `mtext_actions` direkt in `main` und die vorhandenen
Release-Branches. Workflows ohne Aufruf von `mtext_actions` bleiben
unverändert.
