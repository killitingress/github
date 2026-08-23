# CI/CD-Workflows des Mandanten-Repositories

Die Workflowdateien starten die Läufe dieses Mandanten-Repositories. Die
eigentliche CI/CD-Implementierung kommt aus
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` (`mtext_actions`). Dessen
`main` enthält die freigegebene Version und wird von den Mandanten-Workflows
direkt verwendet.

## Voraussetzungen

Der aktuelle Workflowvertrag erwartet `MTEXT_ACTIONS_TOKEN` als Fine-grained
PAT für `mtext_actions` mit:

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
hält SHA und Lieferumfang unter dem geplanten Liefer-Tag fest. `.100` entsteht
auf `main` oder `release/nnn` und erzeugt ein FULL des vollständigen Stands.
Jede spätere Version derselben Releaselinie erzeugt ein kumulatives DELTA gegen
`.100`. Teillieferungen werden auf `bereitstellung/nnn.nnn` zusammengestellt.

Bestehen mehrere Vorbereitungen desselben Tags, verwendet **Lieferung
ausführen** die neueste noch verfügbare Vorbereitung. Eine andere Person
erfüllt das empfohlene Vier-Augenprinzip. Dieselbe Person muss die
Direktlieferung im manuellen Start bewusst bestätigen.

## `lieferung-ausfuehren.yml`

Die ausführende Person nennt den Liefer-Tag. Fehlt der Git-Tag, lädt der Lauf
die neueste Vorbereitung und nennt den ermittelten Lieferweg. Anschließend
startet der zentrale Ablauf `lieferung.yml`. Dieser erstellt bei einer
erstmaligen Lieferung den Tag und baut und überträgt anschließend die
Lieferung. Bei einem vorhandenen Git-Tag entfällt die erneute Bestätigung und
`lieferung.yml` verarbeitet den Lieferstand erneut. Ein Tag-Push allein startet
keine Mainframe-Übergabe. Paketbau und Mainframe-Übergabe laufen in
`mtext_actions`.

## Zentrale CI/CD-Version

Die Mandanten-Workflows verweisen auf `mtext_actions@main`. Eine neue
freigegebene Version steht nach ihrer Zusammenführung in `main` bei den
nächsten Workflow-Läufen zur Verfügung.
