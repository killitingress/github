# CI/CD-Workflows des Mandanten-Repositories

Die Workflowdateien starten die Läufe dieses Mandanten-Repositories. Die
eigentliche CI/CD-Implementierung kommt aus
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` (`mtext_actions`) über eine
Commit-SHA.

## Voraussetzungen

`MTEXT_ACTIONS_TOKEN` ist ein Fine-grained PAT eines technischen
GitHub-Benutzers für `mtext_actions` mit:

- `Contents: read` zum Laden der CI/CD-Version
- `Actions: write` zum Starten der zentralen Lieferworkflows

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
| `feature/nnn/<Bezeichnung>` | M/Text-Entwicklung der Releaselinie |
| `release/nnn` | M/Text-Funktionstest der Releaselinie |
| `main` | M/Text-Funktionstest der in `.github/config.json` genannten Releaselinie |

Ein Push übergibt die geänderten Projekte über CIFS an den Adapter. Der
manuelle Start gleicht die angegebene Commit-SHA vollständig mit dem Ziel des
ausgewählten Branches ab. Ändert ein Push nach `main` die Releaselinie, folgt
ein vollständiger Abgleich mit M/Text-Entwicklung und M/Text-Funktionstest.

## `lieferung-vorbereiten.yml`

Der manuelle Start verwendet den in GitHub ausgewählten Branch. Die Vorprüfung
hält SHA und Lieferumfang fest und zeigt die Vorbereitungs-ID. `.100` entsteht
auf `main` oder `release/nnn` und erzeugt ein FULL des vollständigen Stands.
Jede spätere Version derselben Releaselinie erzeugt ein kumulatives DELTA gegen
`.100`. Teillieferungen werden auf `bereitstellung/nnn.nnn` zusammengestellt.

Nach der Prüfung startet eine Person **Vorbereitete Lieferung ausführen** mit
der angezeigten Vorbereitungs-ID. Dieselbe Person bestätigt eine
Direktlieferung. Eine andere Person erfüllt das empfohlene Vier-Augenprinzip.

## `lieferung-ausfuehren.yml`

Die ausführende Person nennt die Vorbereitungs-ID. Der Lauf lädt die
festgehaltenen Angaben, nennt den ermittelten Lieferweg und startet den
zentralen Workflow `lieferung.yml`. Dort entsteht der Liefer-Tag. Anschließend
startet `release.yml`. Ein Tag-Push allein startet keine
Mainframe-Übergabe. Paketbau und Mainframe-Übergabe laufen in
`mtext_actions`.

## `lieferung-erneut-uebergeben.yml`

Der manuelle Start nennt einen vorhandenen Liefer-Tag. Der zentrale Workflow
`release.yml` überträgt denselben Stand erneut. Eine erneute Bestätigung
entsteht nicht.

## Aktualisierung

Der zentrale Workflow **Mandanten-Workflows aktualisieren** schreibt die
Verweise auf `mtext_actions` direkt in `main` und die vorhandenen
Release-Branches. Workflows ohne Aufruf von `mtext_actions` bleiben
unverändert.
