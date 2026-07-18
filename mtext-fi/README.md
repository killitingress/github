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
  LOMS_Testdaten/        # Repositoryinhalt, nicht Teil der Projekt-Allowlist
  config/
    mandant.json
  .github/
    workflows/
      validate-config.yml
      sync-resources.yml
      release.yml
```

Die Projektverzeichnisse werden nicht mit leeren Platzhaltern angelegt. Sie
entstehen aus dem geprüften SVN-zu-Git-Import; ein leerer Projektpfad darf nicht
als gültiger Lieferstand erscheinen.

FI ist der Master-Mandant für diese unfragmentierten Projekte.
`LOMS_Testdaten` wird mit dem Repositoryinhalt migriert, bleibt aber wie bisher
außerhalb der Projekt-Allowlist in `config/mandant.json`.
Der redundante historische Sonderpfad `LOMS_Basis[FI]` wird nicht übernommen.

## Bedeutung der Mandantenkonfiguration

`config/mandant.json` ist kein allgemeiner Benutzerschalter. Sie gehört zum
versionierten Lieferstand und legt verbindlich fest, welche Projekte
synchronisiert und paketiert werden und welche mandantenspezifischen Werte für
die bestehende technische Übergabe gelten. Die historischen Lieferdateinamen
werden zentral aus dem Projektnamen abgeleitet und sind hier nicht
konfigurierbar. Repositoryinhalte, die nicht in der Projekt-Allowlist stehen,
werden nicht ausgeliefert.

Eine Änderung dieser Datei startet einen nebenwirkungsfreien Config-Check. Er
prüft Felder, Repository-Identität und fachliche Eindeutigkeit, greift aber
weder auf M/Text noch auf den Mainframe zu. Der Check liefert frühes Feedback
und ist kein technisch erzwungenes Gate; Sync und Release validieren die
Konfiguration erneut. Config-Änderungen werden mit den für den Mandanten
benannten Verantwortlichen abgestimmt.

## Branch- und Releasefluss

Für die gleichzeitig aktiven Linien existieren getrennte Branches für die drei
Stages, etwa
`R261/Entwicklung`, `R261/Abnahme` und `R261/Bereitstellung`. Änderungen können
bei Bedarf zunächst auf einem Feature-Branch entstehen; erst der direkte Push
nach `R261/Entwicklung` löst die M/Text-Synchronisation aus. Nach erfolgreicher
Prüfung kann ein fachlich freigegebener Commit direkt nach `R261/Abnahme`
per Cherry-Pick übernommen werden. Dabei entsteht auf dem Abnahmebranch ein
neuer Commit mit eigener SHA; seine Commit-Nachricht dokumentiert die
vollständige Quell-SHA. Die jeweiligen Pushes verteilen den exakten Stand ihres
Zielbranches zum Entwicklungs- beziehungsweise Abnahmesystem.

Ausgewählte abgenommene Änderungen werden mit dem zusätzlich bereitgestellten
Git-Client per Cherry-Pick nach `R261/Bereitstellung` übernommen und gepusht.
Dieser Push erzeugt noch keine Lieferung. Erst
ein vom Mandanten-Release-Team gesetzter Tag `Rnnn.nnn` prüft den
Bereitstellungsstand und startet eine FULL- oder DELTA-Lieferung. `.100` ist
FULL; andere gültige Tags derselben Linie sind kumulative DELTAs gegen `.100`.
Bestehende Release-Tags sind gegen Änderung und Löschung geschützt.

`R261/Entwicklung` ist zunächst als Default Branch vorgesehen. Beim
Linienwechsel wird der Entwicklungsbranch der führenden Linie als Default
Branch gesetzt. Ein zusätzlicher `main`-Branch ist nicht vorgesehen.

Eine neue Releaselinie wird zentral in `config/release_lines.json` der
technischen M/Text-Linie und einem vorhandenen Übergabeprofil zugeordnet. Ihre
drei Stage-Branches entstehen aus dem fachlich bestätigten letzten Release-Tag
der bisherigen Linie. Danach wird derselbe vollständige Stand über den
manuellen Sync-Workflow einmal nach Entwicklung und einmal nach Abnahme
übertragen.

## Stand des Entwicklungssystems

Die Workflows referenzieren `j520730/mtext-actions`, aber absichtlich noch
einen nicht auflösbaren Null-SHA als technischen Platzhalter. Vor dem ersten
Integrationslauf wird er durch den vollständigen Commit-SHA der vorgesehenen
zentralen Version ersetzt. Die erforderliche GitHub- und Runner-Einrichtung ist
im [Workflow-Vertrag](.github/workflows/README.md) dokumentiert.
