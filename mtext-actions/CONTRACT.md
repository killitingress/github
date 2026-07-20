# Fachlicher Vertrag

Dieses Dokument fasst die Regeln zusammen, die Automatisierung, Workflows und
versionierte Konfiguration technisch durchsetzen. Der Jenkins-Hook
`LBS_SVN_Hook_v0.4.bash` dient ausschließlich als schreibgeschützte Referenz
für weiterhin benötigte Kompatibilitätsregeln.

## Konfiguration

- Die versionierte Mandantenkonfiguration liegt im Mandanten-Repository unter
  `.github/config.json`.
- Ein Mandanten-Repository besitzt ein bekanntes Mandantenkürzel, eine
  ISPW-Instanz `T` oder `P`, ein Mainframe-Subsystem und mindestens ein
  Hostprofil.
- Mandanten-, Hostprofil- und Releaselinienkonfiguration enthalten nur die
  festgelegten Felder.
- Sichtbare Projektverzeichnisse bilden den Lieferumfang. Ausdrücklich
  ausgeschlossene Verzeichnisse werden ignoriert.
- Der Projektcode für Archiv und Mainframe-Member wird aus dem Projektnamen
  abgeleitet: Mandantensuffix und Präfix `LOMS_` entfallen, anschließend werden
  höchstens die ersten fünf Zeichen in Großschreibung verwendet. Die
  abgeleiteten Projektcodes müssen innerhalb eines Repositorys eindeutig sein.
- Die aktuelle Projektmatrix ordnet `mtext-fi` die fünf unfragmentierten
  Projekte, `mtext-autonom` das Projekt `LOMS_Autonom` mit dem Mandantenkürzel
  `IT` und den übrigen Mandanten jeweils `LOMS_Basis[<Kürzel>]` und
  `LOMS_Autonom[<Kürzel>]` zu. Sie ist ein Referenzstand und schreibt den
  Lieferumfang technisch nicht fest.
- Ein abweichendes Mandantenkürzel sowie gegenüber dem Referenzstand fehlende
  oder zusätzliche Projekte erzeugen Warnungen, aber keinen Fehler.
- Eine Releaselinie nennt ETAPS-Linie und Hostprofil.

## Ressourcensynchronisation

- Synchronisiert wird genau der ausgecheckte, vollständig benannte Commit.
- Der Quellbranch muss eine bekannte Releaselinie benennen. Seine Stage muss
  zur Zielumgebung `Entwicklung` oder `Abnahme` passen.
- Projektstände dürfen keine Symlinks enthalten.
- Jede Synchronisation veröffentlicht den vollständigen Stand jedes
  verarbeiteten Projekts. Dies ist unabhängig von FULL und DELTA bei einer
  Mainframe-Lieferung.
- Erst nach vollständigem Staging werden die Projektverzeichnisse in
  `serverSync` ersetzt und der M/Text-Adapter aufgerufen.
- `ADAPTER_ACCEPTED` bestätigt nur die unmittelbare technische Annahme des
  Adapteraufrufs und keinen fachlichen M/Text-Endstatus.

## Release

- Ein Tag mit Endung `.100` erzeugt je Projekt ein vollständiges F-Paket und
  ein zusätzliches leeres D-Paket mit leerer Löschliste. Jeder weitere Tag der
  Releaselinie erzeugt ein kumulatives D-Paket gegen `.100`.
- Die `.100`-Basis eines DELTA ist ein Vorgänger des Ziel-Tags in der
  Git-Historie.
- Der Tag muss vom Bereitstellungsbranch erreichbar sein und dem Checkout
  entsprechen.
- Das Mandanten-Release-Team kann einen irrtümlichen Tag nach Abbruch des zugehörigen
  Workflow-Laufs löschen und neu anlegen.
- Die manuelle Freigabe im Environment `Bereitstellung` gilt für die
  Mainframe-Übergabe, nicht für den Tag. Das Löschen eines Tags nimmt eine
  bereits erfolgte Lieferung nicht zurück.
- Archivnamen, Mainframe-Member, Löschlisten und Informationsdateien folgen dem
  bestehenden Jenkins-Vertrag.
- Erkannte Dateikopien werden wie Hinzufügungen behandelt. Umbenennungen gelten
  als Löschung und Hinzufügung.
- Gleiche Eingaben erzeugen bytegleiche Archive.

## Mainframe-Übergabe

- Das Publish-Kommando prüft jede manifestierte Datei unmittelbar vor der
  externen Wirkung anhand von Pfad, Größe und SHA-256.
- JCL-Werte werden genau beim Rendern geprüft.
- Erst danach werden Paket und JCL in einer FTP-Sitzung übertragen.
- `MAINFRAME_SUBMITTED` bezeichnet nur die unmittelbare technische Annahme.
