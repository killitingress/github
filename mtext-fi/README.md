# mtext-fi

Dieses Repository ist der repräsentative Entwurf für die künftige
Git-Quelle der FI-M/Text-Ressourcen. Nach der Migration enthält es die
tatsächlichen Ressourcen und die mandantenspezifische Konfiguration. Gemeinsame
Automatisierungslogik wird nicht in dieses Repository kopiert, sondern über
unveränderlich gepinnte wiederverwendbare Workflows aus `mtext-actions`
verwendet.

Für die tägliche Bedienung siehe
[Benutzeranleitung](../docs/confluence/Benutzeranleitung.md), für den
End-to-End-Ablauf die
[Soll-Grafik](../Architektur_Soll_GitHub_Actions_Git.drawio).

## Ressourcenstruktur

Die FI-Ressourcen liegen nach der Migration entsprechend
`config/mandant.json` direkt unter ihren fachlichen Projektwurzeln:

```text
mtext-fi/
  Configuration/
  Fonts/
  LOMS_Framework/
  LOMS_Basis/
  LOMS_PKA/
  LOMS_Testdaten/        # Repositoryinhalt, nicht Teil der Delivery-Allowlist
  config/
    mandant.json
  .github/
    workflows/
      sync-resources.yml
      release.yml
```

Die Projektverzeichnisse werden nicht mit leeren Platzhaltern angelegt. Sie
entstehen aus dem geprüften SVN-zu-Git-Import; ein leerer Projektpfad darf nicht
als gültiger Lieferstand erscheinen.

FI ist der Master-Mandant für diese unfragmentierten Projekte.
`LOMS_Testdaten` wird mit dem Repositoryinhalt migriert, bleibt aber wie bisher
außerhalb der Synchronisations- und Paket-Allowlist in `config/mandant.json`.
Der redundante historische Sonderpfad `LOMS_Basis[FI]` wird nicht übernommen.

## Branch- und Releasefluss

Für die gleichzeitig aktiven Linien existieren getrennte Stufenbranches, etwa
`R261/Entwicklung`, `R261/Abnahme` und `R261/Bereitstellung`. Änderungen können
bei Bedarf zunächst auf einem lokalen Feature-Branch entstehen; erst der direkte
Push nach `R261/Entwicklung` löst die Automatisierung aus. Nach erfolgreicher
Prüfung kann ein fachlich freigegebener Commit direkt nach `R261/Abnahme`
promoviert werden. Die jeweiligen Pushes verteilen ihren exakten Commit zum
Entwicklungs- beziehungsweise Abnahmesystem.

Ausgewählte abgenommene Änderungen werden direkt nach
`R261/Bereitstellung` gepusht. Dieser Push erzeugt noch keine Lieferung. Erst
ein vom Benutzer gesetzter Tag `Rnnn.nnn` prüft den Bereitstellungsstand und
startet FULL oder DELTA. `.100` ist FULL; spätere Tags derselben Linie sind
kumulative DELTAs gegen `.100`.

Aktuell ist `R261/Entwicklung` als Default Branch vorgesehen. Beim rollierenden
Linienwechsel wird der Default Branch manuell auf den Entwicklungsbranch der
neuen führenden Linie umgestellt. Ein zusätzlicher `main`-Branch ist nicht
vorgesehen.

## Stand des Entwicklungssystems

Die Workflows referenzieren `j520730/mtext-actions`, aber absichtlich noch
einen nicht auflösbaren Null-SHA als technischen Platzhalter. Vor dem ersten
Integrationslauf wird er durch den vollständigen Commit-SHA der vorgesehenen
zentralen Version ersetzt. Die erforderliche GitHub- und Runner-Einrichtung ist in
`.github/workflows/README.md` dokumentiert.
