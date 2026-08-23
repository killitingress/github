# `fi_lbs_entw_oms_mtext_actions`

Das Repository `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`, kurz
`mtext_actions`, enthält die zentrale CI/CD-Automatisierung für
Mandantenkonfiguration, M/Text-Synchronisation, Paketbau und
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
| `WORKFLOW_CONFIGURATION_TOKEN` | Repository-Secret | Liefer-Tags erstellen und Lieferinformationen veröffentlichen |

`WORKFLOW_CONFIGURATION_TOKEN` gilt für die zugeordneten
Mandanten-Repositories und benötigt dort `Contents: read and write`. Die
Liefer-Tags `rnnn.nnn` fallen nicht unter die Schutzregeln für Release-Tags aus
dem Git-Leitfaden.

Jedes Mandanten-Repository erhält `MTEXT_ACTIONS_TOKEN` als Repository-Secret.
Der Fine-grained PAT ist auf `mtext_actions` begrenzt und besitzt dort
`Contents: read` sowie `Actions: write`.

Die Organisationsvariable `MTEXT_CIFS_ROOT` enthält den auf dem Runner
eingehängten CIFS-Basispfad für die Adapterübergabe.

GitHub Environments werden nicht verwendet.

## Mainframe-Lieferung

Eine Lieferung wird im Mandanten-Repository in zwei Schritten gestartet:

1. **Lieferung vorbereiten** prüft den ausgewählten Branchstand, hält seine
   SHA und den Lieferumfang unter dem geplanten Liefer-Tag fest.
2. **Lieferung ausführen** erhält diesen Liefer-Tag und lädt die neueste
   festgehaltene Vorbereitung. Eine andere Person erfüllt das empfohlene
   Vier-Augenprinzip. Dieselbe Person muss die Direktlieferung als Abweichung
   davon bewusst bestätigen.

Der zentrale Workflow erstellt den Liefer-Tag `rnnn.nnn` auf der
festgehaltenen SHA und ruft anschließend Paketbau und Mainframe-Übergabe auf.
Ein Tag-Push allein löst keine Übergabe aus. Wird **Lieferung ausführen** mit
einem vorhandenen Liefer-Tag gestartet, verarbeitet der Workflow diesen Stand
ein weiteres Mal.

Die `.100`-Lieferung einer Releaselinie ist ein FULL. Spätere Lieferungen sind
kumulative DELTAs gegen diesen `.100`-Tag. Teillieferungen werden im
Mandanten-Repository auf `bereitstellung/nnn.nnn` zusammengestellt.

## Zentrale CI/CD-Version

`main` enthält die freigegebene Version von `mtext_actions`. Die
Mandanten-Workflows rufen diese Version über `@main` auf. Eine Änderung an
`main` steht damit allen Mandanten bei ihrem nächsten Workflow-Lauf zur
Verfügung. Änderungen werden nach erfolgreicher **Zentraler Testsuite** über
einen Pull Request in `main` zusammengeführt.

## Tests

Jeder Pull Request und jede Änderung an `main` startet die **Zentrale
Testsuite**. Der Job **Zentrale CI/CD-Implementierung testen** muss vor dem
Merge erfolgreich sein. Die Tests sprechen weder M/Text noch den Mainframe an.

Benötigt werden Python ab Version 3.11, Git und `tar`. Die Produktivlogik
nutzt die Standardbibliothek.
