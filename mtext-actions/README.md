# `fi_lbs_entw_oms_mtext_actions`

Das Repository `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, kurz
`mtext_actions`, enthält die zentrale CI/CD-Automatisierung für
Mandantenkonfiguration, M/Text-Synchronisation, Releasebau und
Mainframe-Übergabe.

## Aufbau

- `src/mtext.py`: Kommandozeileneinstieg für die Workflow-Schritte
- `src/lbs_delivery/`: Implementierung der einzelnen Arbeitsschritte
- `config/mandanten.json`: Mandantenkürzel, Repositories und Subsysteme
- `config/releaselinien.json`: M/Text-Zielpräfixe, aktive Releaselinien,
  ETAPS-Linien und Hostprofile
- `config/ressourcenformate.json`: Dateiendungen und ihr technisches Format
- `templates/mainframe-upload.jcl`: JCL-Vorlage für die Mainframe-Übergabe

## GitHub-Konfiguration

| Name | Art | Verwendung |
|---|---|---|
| `MAINFRAME_FTPS_HOST` | Repositoryvariable | FTPS-Ziel |
| `MAINFRAME_FTPS_PORT` | Repositoryvariable | Steuerungsport des expliziten FTPS-Zugangs |
| `MAINFRAME_FTPS_USER` | Repositoryvariable | zentraler technischer FTPS-Benutzer |
| `MAINFRAME_FTPS_PASSWORD` | Repository-Secret | FTPS-Passwort für den zentralen Übergabejob |
| `WORKFLOW_CONFIGURATION_TOKEN` | Repository-Secret | Mandanten-Workflows ausrollen, Freigabe-Branches und Release-Tags erstellen sowie Lieferinformationen veröffentlichen |

`WORKFLOW_CONFIGURATION_TOKEN` gilt für die zugeordneten
Mandanten-Repositories. Es benötigt dort `Contents: read and write`,
`Workflows: read and write` und `Pull requests: read`. Der technische Benutzer
ist in den Schutzregeln als Ausnahme von der Pull-Request-Pflicht für den
administrativen Rollout hinterlegt. Die organisationsweit vorgegebenen
Tag-Regeln gelten auch für diesen Zugriff.

Jedes Mandanten-Repository erhält `MTEXT_ACTIONS_TOKEN` als Repository-Secret.
Der Fine-grained PAT ist auf `mtext_actions` begrenzt und besitzt dort
`Contents: read` sowie `Actions: write`.

Die Organisationsvariable `MTEXT_CIFS_ROOT` enthält den auf dem Runner
eingehängten CIFS-Basispfad für die Adapterübergabe.

GitHub Environments werden nicht verwendet.

## Mandanten-Workflows aktualisieren

Der manuell gestartete Workflow erhält die Commit-SHA der gewünschten
CI/CD-Version. Er aktualisiert in `main` und den vorhandenen `release/Rnnn`
jedes Mandanten die Workflowdateien, die einen wiederverwendbaren Workflow aus
`mtext_actions` aufrufen, und pusht den Commit direkt. Nicht vorhandene
Repositories und Branches werden mit einer Warnung übersprungen.
Feature-Branches sind keine Ziele. Der Rollout startet keine
M/Text-Synchronisation.

## Tests

Jeder Pull Request und jede Änderung an `main` startet die **Zentrale
Testsuite**. Der Job **Zentrale CI/CD-Implementierung testen** muss vor dem
Merge erfolgreich sein. Die Tests sprechen weder M/Text noch den Mainframe an.

Benötigt werden Python ab Version 3.11, Git und `tar`. Die Produktivlogik
nutzt die Standardbibliothek.
