# Fachlicher Vertrag

Maßgeblich sind der fachliche Lieferablauf, die GitHub-Workflows, die
betrieblich verwendete Konfiguration und die weiterhin benötigten
Kompatibilitätsregeln aus dem nur als Referenz gelesenen Jenkins-Hook
`LBS_SVN_Hook_v0.4.bash`.

## Konfiguration

- Ein Mandanten-Repository besitzt ein bekanntes Mandantenkürzel, ein
  Mainframe-Subsystem und mindestens ein Hostprofil.
- Sichtbare Projektverzeichnisse bilden den Lieferumfang; ausdrücklich
  ausgeschlossene Verzeichnisse werden ignoriert.
- Jedes Projekt muss einem historisch festgelegten Liefercode zugeordnet sein.
- Eine Releaselinie nennt M/Text-Linie und Hostprofil.

## Ressourcensynchronisation

- Synchronisiert wird genau der ausgecheckte, vollständig benannte Commit.
- Quellbranch und Zielumgebung müssen dieselbe Releaselinie und Stage benennen.
- Projektstände dürfen keine Symlinks enthalten.
- Erst nach vollständigem Staging werden die Projektverzeichnisse in
  `serverSync` ersetzt und der M/Text-Adapter aufgerufen.

## Release

- Ein Tag mit Endung `.100` erzeugt FULL, jeder weitere Tag der Releaselinie
  ein kumulatives DELTA gegen `.100`.
- Der Tag muss vom Bereitstellungsbranch erreichbar sein und dem Checkout
  entsprechen.
- Archivnamen, Mainframe-Member, Löschlisten und Informationsdateien folgen dem
  bestehenden Jenkins-Vertrag.
- Erkannte Dateikopien werden wie Hinzufügungen behandelt; Umbenennungen als
  Löschung und Hinzufügung.
- Gleiche Eingaben erzeugen bytegleiche Archive.

## Mainframe-Übergabe

- Das Publish-Kommando prüft jede manifestierte Datei unmittelbar vor der
  externen Wirkung anhand von Pfad, Größe und SHA-256.
- JCL-Werte werden genau beim Rendern geprüft.
- Erst danach werden Paket und JCL in einer FTP-Sitzung übertragen.
- `MAINFRAME_SUBMITTED` bezeichnet nur die unmittelbare technische Annahme.
