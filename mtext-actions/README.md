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
| `shared-sync-resources.yml` | Den ausgewählten Branchcommit mit M/Text synchronisieren |
| `shared-lieferung-check.yml` | Branchcommit und Lieferumfang prüfen und als Vorbereitung speichern |
| `shared-lieferung-ausfuehren.yml` | Lieferstand ermitteln, Lieferdateien bauen, an den Mainframe übertragen und das Freigabe-Issue abschließen |
| `ci.yml` | Python-Tests bei Pull Requests, Änderungen an `main` oder manuell ausführen |

Der Branch `main` lädt die Composite Action in den Shared Workflows mit
`@main`. Im Branch `test` zeigen diese statischen Referenzen auf `@test`,
damit Workflow-Datei und Python-Implementierung vom selben Commit kommen.

## Python-Anwendung

`src/mtext.py` stellt die von den Workflows verwendeten Kommandos bereit:

| Kommando | Aufgabe |
|---|---|
| `resources check` | Mandantenkonfiguration sowie konfigurierte JSON-, XML- und verfügbare JavaScript-Ressourcen prüfen |
| `resources sync` | Änderungen seit dem letzten erfolgreichen Branchcommit mit M/Text synchronisieren |
| `delivery check` | Liefer-Tag aus dem Branch ableiten und den Lieferstand vorbereiten |
| `delivery resolve` | die Freigabe aus dem Issue bestätigen oder den Wiederholungsstand ermitteln |
| `delivery complete` | Archivnamen und SHA-256-Prüfsummen im Freigabe-Issue festhalten und es schließen |
| `delivery incomplete` | einen nicht abgeschlossenen Lauf im Freigabe-Issue melden |
| `delivery tag` | den vom Mainframe angenommenen Commit mit einem annotierten Liefer-Tag und zugehöriger Issue-Nummer kennzeichnen |
| `release build` | FULL- oder DELTA-Lieferdateien erzeugen |
| `release mainframe` | Lieferdateien per FTPS und JES an den Mainframe übergeben |

Die Implementierung liegt in `src/lbs_delivery`. Das Repository verwendet
dabei folgende versionierte Daten:

| Pfad | Inhalt |
|---|---|
| `config/mandanten.json` | Zuordnung von Mandantenkürzeln zu GitHub-Repositories und Mainframe-Subsystemen |
| `config/releaselinien.json` | M/Text-Zielpräfixe sowie ETAPS-Linie und Hostprofil je Releaselinie |
| `config/ressourcenformate.json` | Zuordnung geprüfter Endungsmuster zu JSON, XML oder JavaScript |
| `templates/mainframe-upload.jcl` | JCL-Vorlage für die Mainframe-Übergabe |

Der Shared Workflow `shared-sync-resources.yml` nimmt `zielumgebung` mit den
Werten `Branchstandard` (Standard), `Entwicklung`, `Funktionstest` oder `Beide`
entgegen und reicht den Wert als `MTEXT_ZIELUMGEBUNG` weiter. Die Auswahl gilt
für manuelle Vollabgleiche. Feature-Pushes verwenden Entwicklung, PR-Merges nach
`main` oder `release/nnn` Funktionstest. Beim Merge wird der entstandene
Merge-Commit ausgecheckt. Die Prüfung erhält dieselbe Zielauswahl.

Ein automatisches DELTA benötigt einen erfolgreichen Zielnachweis desselben
Branches, derselben M/Text-Umgebung und derselben Releaselinie. Andernfalls
erfolgt FULL. `hostprofil` gehört zur Mainframe-Übergabe und beeinflusst diese
Basis nicht. Dry Runs bauen FULL und erzeugen keinen Übertragungsnachweis.

Nach einer echten Übertragung speichert der Workflow `mtext-stand.json` als
lesbares Artefakt, etwa `mtext-stand-feature%2F261%2Ftest`. Der Branchname wird
URL-kodiert. Die Datei nennt `commit`, `releaselinie` und die
übertragenen `umgebungen`. Der Commit stammt aus dem Nachweis, weil der
übertragene Merge-Commit vom `head_sha` eines PR-Laufs abweichen kann.

Die Abfrage filtert auf diesen Namen und nimmt das neueste nicht abgelaufene
Artefakt, das die Zielumgebung enthält. Eine andere Releaselinie verlangt FULL,
ebenso ein fehlender Nachweis. Ein Dry Run erzeugt keinen Vergleichscommit.

Die Concurrency-Gruppe `mtext-synchronisierung` mit
`cancel-in-progress: false` umfasst den gesamten Ablauf. GHES 3.20 ersetzt
einen wartenden Lauf, wenn ein weiterer hinzukommt.

## Laufzeit und Tests

Die Mandantenquelle liegt unter `GITHUB_WORKSPACE/source`. Der Paketbau schreibt
nach `RUNNER_TEMP/dist`, Übergabe und Abschlussjob lesen das heruntergeladene
Artefakt aus `RUNNER_TEMP/release`. Das temporäre Basisverzeichnis wird vom
Runner je Job bereinigt.

Die manuell gestartete Ressourcenprüfung prüft den vollständigen ausgewählten
Branchcommit. Vor einer DELTA-Lieferung verwendet sie die Änderungen seit dem
`.100`-Tag der Releaselinie. Vor einer DELTA-Synchronisierung verwendet sie
denselben Vergleichscommit wie der anschließende Paketbau. FULL-Läufe prüfen den
vollständigen Commit. Projektverzeichnisse aus `excluded_projects` bleiben
dabei unberücksichtigt. Die Actions-Zusammenfassung schlüsselt die geprüften
Dateien nach JSON, XML und JavaScript auf. Syntaxbefunde werden als Warnungen
ausgegeben und beenden den Job erfolgreich.

Die Mindestversion in `.python-version` ist Python 3.12. Die Runner-Prüfung in
`scripts/runner-preflight.sh` erwartet außerdem Git, `tar` und `curl`.
Die Lieferung liest den Liefer-Tag aus dem Titel des Freigabe-Issues und den
vorbereiteten Commit aus dessen Text.

Ist Node.js auf dem Runner verfügbar, zeigt die Runner-Prüfung seine Version an
und `resources check` prüft zusätzlich JavaScript-Dateien mit `node --check`.
