# CI/CD-Workflows des Mandanten-Repositories

Die Workflowdateien enthalten die Git-Auslöser des Mandanten. Die
CI/CD-Implementierung wird über eine vollständige Commit-SHA aus
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, kurz `mtext_actions`, geladen.

## Benötigtes Repository-Secret

`MTEXT_ACTIONS_TOKEN` ist ein Fine-grained PAT eines technischen
GitHub-Benutzers. Es ist auf das zentrale CI/CD-Repository begrenzt
und besitzt:

- `Contents: read` zum Laden der angegebenen CI/CD-Version,
- `Actions: write` zum Starten des zentralen Release-Workflows.

Mainframe-Zugangsdaten liegen nicht im Mandanten-Repository.

## `validate-config.yml`

Ein Push mit einer Änderung an `.github/config.json` startet die zentrale
Konfigurationsprüfung. Der Lauf überträgt keine Ressourcen und liest keine
Mainframe-Secrets.

## `check-resources.yml`

Jeder Pull Request startet die zentrale technische Prüfung seiner
hinzugefügten, geänderten und umbenannten Ressourcen. Welche Dateiendungen als
JSON oder XML gelesen werden, legt `config/ressourcenformate.json` in
`mtext_actions` fest. Über **Run workflow** kann für den gewählten Branch eine
Vollprüfung gestartet werden.

Ungültige JSON-Syntax und nicht wohlgeformtes XML erscheinen mit Datei und
Fundstelle als Warnungen. Diese Befunde lassen den Lauf erfolgreich enden und
verhindern den Merge nicht.

Eine spätere XSD-Prüfung der Tonic-XMLs benötigt zunächst das verbindliche XSD
und seine Zuordnung zu den Ressourcen.

## `sync-resources.yml`

Automatische Auslöser:

| Branch | Ziel |
|---|---|
| `feature/Rnnn/<Bezeichnung>` | M/Text-Entwicklung der Releaselinie |
| `release/Rnnn` | M/Text-Funktionstest der Releaselinie |
| `main` | M/Text-Funktionstest der in `.github/config.json` genannten Releaselinie |

Der manuelle Start erhält eine vollständige Commit-SHA. Er gleicht den Commit
vollständig mit dem Ziel des ausgewählten Branches ab. Feature-Branches führen
zum Ziel M/Text-Entwicklung, `main` und Release-Branches zum Ziel
M/Text-Funktionstest. Die Releaselinie stammt aus dem ausgewählten Branch und
bei `main` aus der Mandantenkonfiguration des Commits. Normale Läufe verwenden
den zuletzt von LTOMA angenommenen Commit als Vergleichsstand und übertragen
die geänderten Ressourcen.

Ändert ein Push nach `main` die konfigurierte Releaselinie, wird dieser erste
Stand automatisch vollständig mit M/Text-Entwicklung und M/Text-Funktionstest
synchronisiert.

## `release.yml`

Ein Push eines Tags wie `v261.100`, `v261.108` oder `v261.108a` ruft den
Dispatch-Workflow der angegebenen CI/CD-Version auf. Dieser startet
`release.yml` in `mtext_actions` mit Repository, Tag, auslösender Commit-SHA
und der CI/CD-Version.

Paketbau und Mainframe-Übergabe laufen anschließend in `mtext_actions`. Der
Mandantenlauf erhält keinen FTPS-Zugang.

## Aktualisierung

Der zentrale Workflow **Mandanten-Workflows aktualisieren** aktualisiert die
Verweise auf `mtext_actions` in `main` und den vorhandenen Release-Branches. Er
schreibt die Änderung direkt in den jeweiligen Branch. Eigene Workflows ohne
einen Aufruf von `mtext_actions` bleiben unverändert.
