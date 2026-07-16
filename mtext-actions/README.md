# mtext-actions

`mtext-actions` ist die zentrale, mandantenunabhängige Automatisierung für die
Verteilung von M/Text-Ressourcen und die technische Übergabe von FULL-/DELTA-
Lieferungen an den bestehenden Mainframe-Prozess.

Mandantenspezifische Ressourcen und Mappings bleiben in Repositories wie
`mtext-fi`. Diese Repositories rufen die hier enthaltenen wiederverwendbaren
Workflows über einen unveränderlichen Commit-SHA auf.

Übergreifende Dokumentation: [Technisches Zielbild](../docs/confluence/Zielbild_GitHub_Actions_Git.md),
[Benutzeranleitung](../docs/confluence/Benutzeranleitung.md),
[Nächste Schritte](../docs/confluence/Naechste_Schritte.md) und
[Soll-Grafik](../Architektur_Soll_GitHub_Actions_Git.drawio).

## Struktur

```text
mtext-actions/
  .github/workflows/
    ci.yml
    reusable-sync-resources.yml
    reusable-release.yml
  config/
    mandant.schema.json
    deployments.schema.json
    deployments.json
  scripts/
    runner-preflight.sh
  src/lbs_delivery/
    __main__.py
    cli.py
    config.py
    errors.py
    git_refs.py
    jcl.py
    mainframe.py
    manifest.py
    mtext_adapter.py
    paths.py
    release.py
    resources.py
    schemas/
      manifest.schema.json
  templates/
    mainframe-upload.jcl
  tests/
    integration/
    unit/
  .python-version
  requirements.lock
  pyproject.toml
```

## Wiederverwendbare Workflows

`reusable-sync-resources.yml` checkt einen exakten Commit aus, stellt die
konfigurierten Projekte in einem laufbezogenen Verzeichnis bereit, veröffentlicht
sie nach serverSync und ruft den bestehenden Adapter einmal synchron auf.

`reusable-release.yml` enthält zwei getrennte Jobs. `build` validiert Tag und
Erreichbarkeit aus `<Releaselinie>/Bereitstellung`, erzeugt FULL oder
kumulatives DELTA und lädt Pakete, Informationsdateien und Manifest genau
einmal unter einem eindeutigen Namen hoch. `publish` wartet im Environment
`Bereitstellung` auf Freigabe, lädt dieses Artefakt, verifiziert alle SHA-256-
Prüfsummen, rendert JCL je Paket und führt die bestehende FTP-/JES-Übergabe
aus. Der gemeldete Status `MAINFRAME_SUBMITTED` ist kein fachlicher Endstatus
des Mainframe-Jobs.

`ci.yml` führt die zentrale Testsuite nur bei Änderungen an `mtext-actions`
aus.

Alle verwendeten `actions/*`-Actions sind auf vollständige Commit-SHAs
festgelegt. Fachlogik liegt ausschließlich in Python.

## CLI

Die drei vorgesehenen Kommandos sind implementiert:

```bash
python -m lbs_delivery sync-resources ...
python -m lbs_delivery build-release ...
python -m lbs_delivery publish-mainframe ...
```

Die vollständigen Pflichtargumente der installierten Version liefert
`python -m lbs_delivery <kommando> --help`. In GitHub Actions werden diese
Argumente durch die wiederverwendbaren Workflows gesetzt; Benutzer müssen die
CLI für den normalen Promotions- und Releaseablauf nicht direkt aufrufen.

`sync-resources` führt ohne `--execute` nur das lokale Staging aus.
`publish-mainframe` verifiziert ohne `--execute` das Manifest und alle
Prüfsummen und rendert das JCL lokal, führt aber keine FTP-/JES-Übergabe aus.

## Stand des Entwicklungssystems

Das Beispiel-Repository `j517120/mtext-fi` verweist bereits auf
`j520730/mtext-actions`, verwendet aber weiterhin den nicht auflösbaren
Null-SHA als technischen Platzhalter. Vor dem ersten Integrationslauf wird er
in beiden aufrufenden Workflows durch den vollständigen Commit-SHA der
vorgesehenen zentralen Version ersetzt. Zusätzliche versionierte
Freigabeschalter für serverSync, Adapter oder Mainframe gibt es nicht; die
Schnittstellen werden auf dem Entwicklungssystem praktisch geprüft.

## Runner-Vertrag

Der Zielrunner ist ein gehärteter Linux-self-hosted-Runner mit den Labels
`self-hosted`, `linux` und standardmäßig `mtext-delivery`. Benötigt werden Git,
Python 3.14, ein frischer `RUNNER_TEMP`, Node.js-20-Action-Unterstützung und
ein internes Wheelhouse.

`LBS_WHEELHOUSE` verweist auf dieses freigegebene Wheelhouse. Der Preflight
erzeugt für jeden Lauf eine neue virtuelle Umgebung und installiert
ausschließlich mit `--no-index` aus `requirements.lock`. Ein Download aus
öffentlichen Paketquellen findet im Workflow nicht statt.

Für Validierung und Releasebau sind keine internen Zielzugriffe erforderlich.
Die Sync- und Publish-Jobs benötigen die fachlich freigegebenen NFS-, Adapter-
beziehungsweise FTP/JES-Netzwerkpfade.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Für den
Artefakttransport sind deshalb die von GitHub für GHES vorgesehenen
Node-20-Varianten von `upload-artifact` v3 und `download-artifact` v3 jeweils
auf einen vollständigen Commit-SHA gepinnt. Die v4-Varianten verwenden einen
auf GHES nicht verfügbaren Artefaktdienst. Vor Aktivierung wird auf der
konkreten Instanz geprüft, dass die beiden gepinnten SHAs im dortigen
`actions`-Namespace verfügbar sind und der vorgesehene Runner Node-20-Actions
ausführen kann.

## GitHub Environments und Secrets

Die wiederverwendbaren Workflows erwarten die drei gemeinsamen GitHub
Environments `Entwicklung`, `Abnahme` und `Bereitstellung`. Entwicklung und
Abnahme laufen nach einem direkten Push ohne zusätzliche manuelle
Environment-Freigabe. Die Mainframe-Übergabe im Environment `Bereitstellung`
wartet auf eine manuelle Freigabe.

Der Publish-Job liest im Environment `Bereitstellung`:

- Secrets: `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER`,
  `MAINFRAME_FTP_PASSWORD`;
- Variablen: `MAINFRAME_DATASET`, `MAINFRAME_JES_TARGET`,
  `MAINFRAME_FTP_TIMEOUT`.

`LBS_WHEELHOUSE` wird bereits von Validate-, Sync- und Build-Jobs benötigt und
muss daher als Repository- oder Organisationsvariable verfügbar sein; eine
ausschließlich im Environment `Bereitstellung` hinterlegte Variable reicht
nicht aus.

Leere optionale Mainframe-Variablen fallen auf die historischen Dataset- und
JES-Namen sowie 60 Sekunden Timeout zurück. Zugangsdaten werden weder in
Manifest, JCL noch Logausgaben geschrieben.

Da aufrufendes und zentrales Repository in unterschiedlichen Namespaces
liegen, muss `j520730/mtext-actions` in den GitHub-Enterprise-Actions-
Einstellungen für `j517120/mtext-fi` und die späteren Mandanten-Repositories
freigegeben werden. Der lesende Checkout des zentralen Codes wird auf dem
echten Enterprise-System verifiziert; ein gegebenenfalls erforderlicher
kurzlebiger Installation-Token ist ein Betriebsparameter und wird nicht im
Repository hinterlegt.

## Linien und Adapterziele

Die aktuell aktiven Linien sind `R261 -> en01`, `R270 -> en02` und
`R260 -> en03`. Entwicklung und Abnahme verwenden je Linie getrennte Hosts,
beispielsweise `en01e.ltoma.intern` und `en01a.ltoma.intern`; der vollständige
Endpunkt endet auf `/vMtextAdapter/sync`. Der bestätigte Payload ist
`{"mandant":"MAN","institut":"INR"}` und jeder 2xx-Status gilt als
unmittelbare Annahme. Authentifizierung und nachgelagertes Status-Polling sind
in der ersten Ausbaustufe nicht vorgesehen.

Der `serverSync`-Sharepfad ist noch nicht bestätigt und wird beim
nichtproduktiven Integrationslauf auf dem vorgesehenen Runner praktisch
geprüft.

## Releaseverhalten

`Rnnn.100` erzeugt FULL. Ein anderer gültiger Tag derselben Linie erzeugt ein
kumulatives DELTA zwischen `Rnnn.100` und dem Zieltag. Umbenennungen werden als
Löschung des alten und Aufnahme des neuen Pfads behandelt. Archive setzen
Dateireihenfolge, Modus, UID/GID und Zeitstempel reproduzierbar.

Das Manifest enthält Repository, Mandant, Release- und Commitidentität,
Paketmember sowie Größe und SHA-256 jedes Pakets und jeder Informationsdatei.
Vor FTP/JES werden sämtliche Dateien erneut gegen dieses Manifest geprüft.
Das Manifest wird beim Schreiben und Lesen vollständig gegen das mit dem
Python-Paket ausgelieferte Schema validiert. Konfigurationen und Manifest
bleiben danach bewusst einfache JSON-Dokumente. Kleine Hilfsfunktionen bilden
nur diejenigen fachlichen Querverweise ab, die JSON Schema nicht ausdrücken
kann; eine zweite Dataclass- und Immutability-Schicht gibt es nicht.
Mainframe-Übergaben werden innerhalb eines Mandanten-Repositories
standardmäßig serialisiert; unterschiedliche Mandanten können parallel
publizieren. Die Serialisierung ist als Workflowinput abschaltbar.

## Tests

Die Tests sind vollständig lokal und führen keine externen Aufrufe aus:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --no-index \
  --find-links "$LBS_WHEELHOUSE" --requirement requirements.lock
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Eine vorhandene `.venv` wird wiederverwendet und ist über `.gitignore` vom
Repository ausgeschlossen.

Abgedeckt sind Konfiguration und Schemas, Promotionen, Git-Diffs,
reproduzierbarer FULL-/DELTA-Bau, kumulative Löschlisten, Manifestprüfung,
JCL-Rendering, Ressourcen-Staging, Adapterstatus und der unmittelbare FTP-/JES-
Vertrag. Historische Referenzdateien gehören nicht zur Testsuite.

Nichtproduktive Integrationsläufe gegen die vorgesehenen Entwicklungsziele
und fachliche Abnahmen bleiben vor dem regulären Betrieb erforderlich. Ein M/Text- oder
Mainframe-Job-Polling ist bewusst nicht implementiert.

Die Git-Prüfungen erwarten den von `actions/checkout` angelegten Remote
`origin`. Ein abweichend benannter Remote ist für die Runner-Ausführung nicht
Teil des Vertrags.
