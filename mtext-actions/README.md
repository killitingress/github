# mtext-actions

`mtext-actions` ist die zentrale, mandantenunabhängige Automatisierung für die
Verteilung von M/Text-Ressourcen und die technische Übergabe von FULL- und
DELTA-Lieferungen an den bestehenden Mainframe-Prozess.

Mandantenspezifische Ressourcen und Mappings bleiben in Repositories wie
`mtext-fi`. Diese Repositories rufen die hier enthaltenen wiederverwendbaren
Workflows über einen unveränderlichen Commit-SHA auf.

Das Zielrepository ist privat. Nur das zentrale Automatisierungsteam erhält
direkten Lese- oder Schreibzugriff. Text-Entwickler der Mandanten arbeiten
ausschließlich in ihrem Mandanten-Repository. Dessen Workflows dürfen die freigegebenen
wiederverwendbaren Workflows über die GitHub-Actions-Zugriffsrichtlinie
aufrufen; dafür werden die Text-Entwickler nicht als Mitglieder von
`mtext-actions` berechtigt. Jobausgaben sind im aufrufenden Repository
sichtbar und dürfen daher keine Secrets oder unnötigen internen Details
enthalten.

Auf GitHub Enterprise Server 3.20 kann ein privates aufrufendes Repository
Workflows aus einem freigegebenen privaten Repository verwenden. Die
Mandanten-Repositories werden deshalb ebenfalls privat angelegt; die konkrete
repositoryübergreifende Freigabe über beide Namespaces wird vor Aktivierung
praktisch bestätigt.

In jedem Mandanten-Repository schützt ein Push-Ruleset den vollständigen Pfad
`.github/workflows/**/*`. Text-Entwickler der Mandanten können dadurch weder die
zentralen Aufrufe verändern noch einen neuen Workflow anlegen, der die
technische Freigabe zweckentfremdet. Nur die zentralen
Automatisierungsverantwortlichen erhalten einen kontrollierten Bypass.

Übergreifende Dokumentation: [Technisches Zielbild](../docs/confluence/Zielbild_GitHub_Actions_Git.md),
[Benutzeranleitung](../docs/confluence/Benutzeranleitung.md),
[Nächste Schritte](../docs/confluence/Naechste_Schritte.md) und
[Soll-Grafik](../Architektur_Soll_GitHub_Actions_Git.drawio).

## Struktur

```text
mtext-actions/
  .github/workflows/
    ci.yml
    reusable-validate-config.yml
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
    delivery_names.py
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

`reusable-validate-config.yml` prüft die Mandantenkonfiguration, das Schema,
die Repository-Identität und die gemeinsame Deploymentkonfiguration. Der Job
verwendet keine Secrets, kein GitHub Environment und keine externen
Zielzugriffe. Er liefert frühes Feedback, ist aber kein technisch erzwungenes
Gate; Sync und Release validieren die Konfiguration auf ihren
Ausführungspfaden erneut.

`reusable-sync-resources.yml` checkt einen exakten Commit aus und stellt die
konfigurierten Projekte in einem laufbezogenen Verzeichnis bereit. Im aktuellen
Implementierungsstand veröffentlicht der Workflow sie anschließend nach
`serverSync` und ruft den bestehenden Adapter einmal synchron auf. Der Ablauf
überträgt bei jedem Start den vollständigen Stand der Projekt-Allowlist. Er
wird deshalb unverändert auch für die initiale Vollsynchronisation einer neuen
Releaselinie verwendet; einen M/Text-DELTA-Modus gibt es nicht.

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

Alle verwendeten externen Actions sind auf vollständige Commit-SHAs
festgelegt. Fachlogik liegt ausschließlich in Python.

## CLI

Die vier vorgesehenen Kommandos sind implementiert:

```bash
python -m lbs_delivery validate-config ...
python -m lbs_delivery sync-resources ...
python -m lbs_delivery build-release ...
python -m lbs_delivery publish-mainframe ...
```

Die vollständigen Pflichtargumente der installierten Version liefert
`python -m lbs_delivery <kommando> --help`. In GitHub Actions werden diese
Argumente durch die wiederverwendbaren Workflows gesetzt; Benutzer müssen die
CLI für den normalen Weitergabe- und Releaseablauf nicht direkt aufrufen.

`sync-resources` führt ohne `--execute` nur das lokale Staging aus.
`publish-mainframe` verifiziert ohne `--execute` das Manifest und alle
Prüfsummen und rendert das JCL lokal, führt aber keine FTP-/JES-Übergabe aus.

## Stand des Entwicklungssystems

Das Beispiel-Repository `j517120/mtext-fi` verweist bereits auf
`j520730/mtext-actions`, verwendet aber weiterhin den nicht auflösbaren
Null-SHA als technischen Platzhalter. Vor dem ersten Integrationslauf wird er
in allen aufrufenden Workflows durch den vollständigen Commit-SHA der
vorgesehenen zentralen Version ersetzt. Zusätzliche versionierte
Freigabeschalter für serverSync, Adapter oder Mainframe gibt es nicht; die
Schnittstellen werden auf dem Entwicklungssystem praktisch geprüft.

## Runner-Vertrag

Der Zielrunner ist ein gehärteter Self-hosted Linux-Runner mit den Labels
`self-hosted`, `linux` und standardmäßig `mtext-delivery`. Benötigt werden Git,
Python 3.14, ein frischer `RUNNER_TEMP`, Node.js-20-Action-Unterstützung und
ein internes Wheelhouse.

`LBS_WHEELHOUSE` verweist auf dieses freigegebene Wheelhouse. Der Preflight
erzeugt für jeden Lauf eine neue virtuelle Umgebung und installiert
ausschließlich mit `--no-index` aus `requirements.lock`. Ein Download aus
öffentlichen Paketquellen findet im Workflow nicht statt.

Für Validierung und Releasebau sind keine internen Zielzugriffe erforderlich.
Der Sync-Job bildet bis zur offenen Transportentscheidung den aktuellen
Implementierungsstand ab: Er veröffentlicht über einen Filesystem-/NFS-Pfad
nach `serverSync` und ruft danach den Adapter per POST auf. Diese vorläufige
Implementierung ist keine Festlegung des Zieltransports; PUT an den Adapter
und Download eines Actions-Artefakts durch Adapter beziehungsweise M/Text
bleiben ebenfalls zu prüfen. Der Publish-Job benötigt weiterhin die fachlich
freigegebenen FTP-/JES-Netzwerkpfade.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Für den
Artefakttransport sind deshalb die von GitHub für GHES vorgesehenen
Node-20-Varianten von `upload-artifact` v3 und `download-artifact` v3 jeweils
auf einen vollständigen Commit-SHA gepinnt. Die v4-Varianten verwenden einen
auf GHES nicht verfügbaren Artefaktdienst. Vor Aktivierung wird auf der
konkreten Instanz geprüft, dass die beiden gepinnten SHAs im dortigen
`actions`-Namespace verfügbar sind und der vorgesehene Runner Node-20-Actions
ausführen kann.

## GitHub Environments und Secrets

Die Sync- und Release-Workflows erwarten die drei gemeinsamen GitHub
Environments `Entwicklung`, `Abnahme` und `Bereitstellung`. Entwicklung und
Abnahme laufen nach einem direkten Push ohne zusätzliche manuelle
Environment-Freigabe. Die Mainframe-Übergabe im Environment `Bereitstellung`
wartet auf eine manuelle Freigabe.

Der Publish-Job liest im Environment `Bereitstellung`:

- Secrets: `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER`,
  `MAINFRAME_FTP_PASSWORD`;
- Variablen: `MAINFRAME_DATASET`, `MAINFRAME_JES_TARGET`,
  `MAINFRAME_FTP_TIMEOUT`.

`LBS_WHEELHOUSE` wird bereits für Config-Check, Sync und Build benötigt und
muss daher als Repository- oder Organisationsvariable verfügbar sein; eine
ausschließlich im Environment `Bereitstellung` hinterlegte Variable reicht
nicht aus.

Leere optionale Mainframe-Variablen fallen auf die historischen Dataset- und
JES-Namen sowie 60 Sekunden Timeout zurück. Zugangsdaten werden weder in
Manifest, JCL noch Logausgaben geschrieben.

Da aufrufendes und zentrales Repository in unterschiedlichen Namespaces
liegen, muss `j520730/mtext-actions` in den GitHub-Enterprise-Actions-
Einstellungen für `j517120/mtext-fi` und die späteren Mandanten-Repositories
mit dem kleinstmöglichen unterstützten Geltungsbereich freigegeben werden.
Diese Actions-Freigabe ersetzt keine direkte Benutzerberechtigung. Der lesende
Checkout des zentralen Codes wird auf dem
echten Enterprise-System verifiziert. Falls dafür ein kurzlebiger
Installation-Token erforderlich ist, muss der Workflowvertrag vor Aktivierung
um dessen sichere Übergabe erweitert werden; der Token wird nicht im
Repository hinterlegt.

## Linien und Adapterziele

Die aktuell aktiven Linien sind `R260 -> en03`, `R261 -> en01` und
`R270 -> en02`. Entwicklung und Abnahme verwenden je Linie getrennte Hosts,
beispielsweise `en01e.ltoma.intern` und `en01a.ltoma.intern`. Im aktuellen
Implementierungsstand endet der Adapterendpunkt auf `/vMtextAdapter/sync`; der
Payload ist `{"mandant":"MAN","institut":"INR"}` und jeder 2xx-Status gilt
als unmittelbare Annahme. Dieser POST-Vertrag ist die dokumentierte
Ausgangslage und sendet derzeit keinen Authentifizierungsheader. Er wird nach
der Transportentscheidung entweder bestätigt oder gezielt ersetzt.
Nachgelagertes Status-Polling ist in der ersten Ausbaustufe nicht vorgesehen.

Der konfigurierte `serverSync`-Sharepfad gehört zum vorläufig implementierten
Filesystem-/NFS-Weg. Er wird nur dann als Zielkonfiguration bestätigt und auf
dem vorgesehenen Runner praktisch geprüft, wenn diese Transportvariante
ausgewählt wird. Andernfalls werden Konfiguration und Implementierung nach der
Transportentscheidung gezielt auf die gewählte Variante umgestellt.

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
bleiben bewusst einfache JSON-Dokumente; kleine Hilfsfunktionen prüfen
diejenigen fachlichen Querverweise, die JSON Schema nicht ausdrücken kann.
Mainframe-Übergaben werden innerhalb eines Mandanten-Repositories
serialisiert; unterschiedliche Mandanten können parallel publizieren.

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

Abgedeckt sind Konfiguration und Schemas, Branch- und Tagzuordnungen, Git-Diffs,
reproduzierbarer Bau von FULL und DELTA, kumulative Löschlisten, Manifestprüfung,
JCL-Rendering, Ressourcen-Staging, Adapterstatus und der unmittelbare FTP-/JES-
Vertrag. Historische Referenzdateien gehören nicht zur Testsuite.

Nichtproduktive Integrationsläufe gegen die vorgesehenen Entwicklungsziele
und fachliche Abnahmen bleiben vor dem regulären Betrieb erforderlich. Ein
M/Text- oder Mainframe-Job-Polling ist bewusst nicht implementiert.

Die Git-Prüfungen erwarten den von `actions/checkout` angelegten Remote
`origin`. Ein abweichend benannter Remote ist für die Runner-Ausführung nicht
Teil des Vertrags.
