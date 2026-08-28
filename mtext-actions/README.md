# `fi_lbs_entw_oms_mtext_actions`

Das Repository enthält wiederverwendbare GitHub-Workflows und eine
Python-Anwendung für M/Text-Mandanten-Repositories. Die vorhandenen Abläufe
prüfen Mandantenkonfigurationen und Ressourcen, synchronisieren Projekte mit
M/Text und erstellen Mainframe-Lieferungen.

## Schnittstellen

`action.yml` ist eine Composite Action. Sie prüft die Programme auf dem Runner
und stellt den Pfad der Python-Runtime sowie den Pfad dieses Repositories als
Outputs bereit.

Die wiederverwendbaren Workflows unter `.github/workflows` sind:

| Datei | Aufgabe |
|---|---|
| `shared-check-resources.yml` | Mandantenkonfiguration und konfigurierte Ressourcen prüfen |
| `shared-sync-resources.yml` | Den ausgewählten Branchstand mit M/Text synchronisieren |
| `shared-lieferung-check.yml` | Branchstand und Lieferumfang prüfen und als Vorbereitung speichern |
| `shared-lieferung-ausfuehren.yml` | Lieferstand ermitteln, Lieferdateien bauen, an den Mainframe übertragen und ein GitHub Release veröffentlichen |
| `ci.yml` | Python-Tests bei Pull Requests, Änderungen an `main` oder manuell ausführen |

## Python-Anwendung

`src/mtext.py` stellt die von den Workflows verwendeten Kommandos bereit:

| Kommando | Aufgabe |
|---|---|
| `config validate` | Mandantenkonfiguration prüfen |
| `resources check` | konfigurierte JSON-, XML- und verfügbare JavaScript-Ressourcen prüfen |
| `resources sync` | Änderungen seit dem letzten erfolgreichen Branchstand mit M/Text synchronisieren |
| `delivery check` | einen Lieferstand vorbereiten |
| `delivery resolve` | eine Vorbereitung oder einen vorhandenen Liefer-Tag ermitteln |
| `delivery confirm` | eine Vorbereitung bestätigen |
| `delivery tag` | den Liefer-Tag auf der vorbereiteten SHA erstellen |
| `release build` | FULL- oder DELTA-Lieferdateien erzeugen |
| `release mainframe` | Lieferdateien per FTPS und JES an den Mainframe übergeben |
| `release github` | Lieferinformationen als GitHub Release veröffentlichen |

Die Implementierung liegt in `src/lbs_delivery`. Das Repository verwendet
dabei folgende versionierte Daten:

| Pfad | Inhalt |
|---|---|
| `config/mandanten.json` | Zuordnung von Mandantenkürzeln zu GitHub-Repositories und Mainframe-Subsystemen |
| `config/releaselinien.json` | M/Text-Zielpräfixe sowie ETAPS-Linie und Hostprofil je Releaselinie |
| `config/ressourcenformate.json` | Zuordnung geprüfter Endungsmuster zu JSON, XML oder JavaScript |
| `templates/mainframe-upload.jcl` | JCL-Vorlage für die Mainframe-Übergabe |

## Laufzeit und Tests

Die Mandantenquelle liegt unter `GITHUB_WORKSPACE/source`. Der Paketbau schreibt
nach `RUNNER_TEMP/dist`, Übergabe und Berichtsjob lesen das heruntergeladene
Artefakt aus `RUNNER_TEMP/release`. Das temporäre Basisverzeichnis wird vom
Runner je Job bereinigt.

Die Ressourcenprüfung leitet ihren Umfang aus `GITHUB_EVENT_NAME` ab. Bei
`pull_request` prüft sie geänderte Ressourcen, beim manuellen Start den gesamten
Stand.

Die Mindestversion in `.python-version` ist Python 3.11. Die Runner-Prüfung in
`scripts/runner-preflight.sh` erwartet außerdem Git und `tar`.
Ist Node.js auf dem Runner verfügbar, prüft `resources check` zusätzlich
JavaScript-Dateien mit `node --check`.

Die Tests lassen sich aus der Repositorywurzel ausführen:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```
