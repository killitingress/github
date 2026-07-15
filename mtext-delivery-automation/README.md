# mtext-delivery-automation (Entwurf)

Dieser lokale Entwurf enthält nur die Artefakte aus dem ersten Arbeitsauftrag:

- Mandantenschema und gemeinsame Deployment-Konfiguration;
- extrahiertes JCL-Template und einen seiteneffektfreien strikten Renderer;
- Tests für Konfiguration, unveränderte Referenzdateien und JCL-Rendering.

Es sind keine Workflows, Credentials oder Aufrufe von NFS, M/Text, FTP, JES,
Jenkins oder SVN enthalten. Belegte Werte, Annahmen und offene Parameter stehen
getrennt in `../docs/Bestandsmatrix.md`.

Die `.yml`-Dateien verwenden für diesen Entwurf die JSON-kompatible Teilmenge
von YAML 1.2. Damit kann die Konfiguration lokal mit der Python-
Standardbibliothek geladen werden. Für die vollständige Schemaauswertung wird
die Testabhängigkeit `jsonschema` benötigt.

Testaufruf aus diesem Verzeichnis:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

Die produktive Python-Minor-Version, die Lockdatei und das interne
Installationsverfahren sind noch festzulegen.
