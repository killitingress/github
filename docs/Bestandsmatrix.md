# Read-only-Bestandsmatrix Jenkins/SVN zu GitHub Actions/Git

Stand: 15. Juli 2026

## Zweck und Quellenlage

Diese Bestandsmatrix erfüllt den ersten Arbeitsauftrag aus Abschnitt 19 des
Handoffs. Sie beschreibt ausschließlich den lokal belegten Bestand und einen
noch nicht freigegebenen Konfigurationsentwurf. Es wurden keine SVN-, Jenkins-,
M/Text-, NFS-, FTP-, JES- oder sonstigen externen Systeme aufgerufen.

Primärquellen:

- `LBS_SVN_Hook_v0.4.bash`, SHA-256
  `ac50916676fe92f7d5ec2ff063d39382dfea06b9cb5ee8aa312afd431324cb33`;
- `Handoff_Jenkins_SVN_zu_GitHub_Actions.md`, insbesondere Abschnitte 3, 10,
  16, 18 und 19;
- `BYAUTOND.tgz`, SHA-256
  `877045df9b942c7573d52abd9544e542da1691432af75c41602ed7e0aa8b2c9b`;
- `OSAUTONF.tgz`, SHA-256
  `c1d5026c84a5d8c348652b116da127b2cd9e1835e856f5af53a81dba8bbd6abc`;
- `_INFO_BY-LOMS_Autonom[BY]-DELTA-R260.234-R260.178.txt`, SHA-256
  `9470daf483c3a2349853585d346a96efaa1f760e34b9614dbfc4a573a86369b4`;
- `_INFO_OS-LOMS_Autonom[OS]-FULL-R260.100-R251.510.txt`, SHA-256
  `f12458507ce0c3470865db918c922ee19b230b90b3ff40421d0a69cf9165d77e`.

Statusbegriffe:

- **Belegt**: direkt aus einer der lokalen Quellen ableitbar.
- **Annahme/Entwurf**: notwendige Zielmodellierung, aber nicht als produktiver
  Wert freigegeben.
- **Offen**: aus den vorhandenen Quellen nicht vollständig ermittelbar.

## Belegte Erkenntnisse

### Repository-, Branch- und Tagbestand

| Mandant | Historisches Repository | Produktive SVN-Struktur/Refs | Bewusst nicht automatisch migrieren | Status und Beleg |
|---|---|---|---|---|
| FI | `/svn/mtext-fi/`; Zielname `mtext-fi` | `branches/Entwicklung/<Release>_MText`, `branches/Abnahme/...`, `branches/Bereitstellung/...`; im Screenshot unter Entwicklung sichtbar: `R200.100`, `R201.100`, weitere, `R251.100`, `R260.100`, `R261.100`; sichtbare Tags u. a. `R201.100`, `R201.136`, `R201.176`, `R201.220` | `R210.100_MText_BACKUP`, `R230.100_MText-Fusion_NordWest`; generell Sicherungs- und Sondernamen ohne Allowlist | **Belegt**, Handoff 3.1 |
| BY | getrenntes Repository `mtext-by` | Tag `R260.234` und direkter Vorrelease `R260.178` sind durch die Referenzlieferung belegt; die Paketbasis ist laut Skript `R260.100` | keine konkrete Sonderliste vorhanden; daher nur explizite Allowlist zulassen | **Teilweise belegt**, Handoff 3.1/3.2 und Skript 411–417 |
| LH | getrenntes Mandantenrepository ist Zielvorgabe; historischer Name/Refbestand fehlt | keine Branch- oder Tagliste vorhanden | alle nicht inventarisierten Refs | **Offen** |
| NW | getrenntes Mandantenrepository ist Zielvorgabe; historischer Name/Refbestand fehlt | keine Branch- oder Tagliste vorhanden | alle nicht inventarisierten Refs | **Offen** |
| OS | getrenntes Mandantenrepository ist Zielvorgabe; historischer Name fehlt | Tags `R260.100` und direkter Vorrelease `R251.510` sind durch die Referenzlieferung belegt | alle nicht inventarisierten Refs | **Teilweise belegt**, Handoff 3.2 |
| SA | getrenntes Mandantenrepository ist Zielvorgabe; historischer Name/Refbestand fehlt | keine Branch- oder Tagliste vorhanden | alle nicht inventarisierten Refs | **Offen** |
| IT | getrenntes Mandantenrepository ist Zielvorgabe; historischer Name/Refbestand fehlt | keine Branch- oder Tagliste vorhanden | alle nicht inventarisierten Refs | **Offen** |

Die physischen Git-Zielbranches `entwicklung`, `abnahme` und
`bereitstellung` sind nur für genau eine aktive Releaselinie direkt geeignet.
Die Anzahl gleichzeitig aktiver Linien ist noch nicht belegt; deshalb sind die
physischen Branchnamen noch kein freigegebener Implementierungsparameter.

### Releaselinien, Stage und Adapterziel

| Releasepräfix | Linie | Stage | Entwicklung | Abnahme | Status |
|---|---:|---|---|---|---|
| `R251` | W | JUR | `https://WA.fiv-mtext-do1.en4920.de/vMtextAdapter/sync` | `https://WA.fiv-mtext-do0.en4920.de/vMtextAdapter/sync` | **Belegt**, Skript 251–253 und 337–343 |
| `R260` | X | JUR | `https://XA.fiv-mtext-do1.en4920.de/vMtextAdapter/sync` | `https://XA.fiv-mtext-do0.en4920.de/vMtextAdapter/sync` | **Belegt**, Skript 242–244 und 337–343 |
| `R261` | Y | FKT | `https://YA.fiv-mtext-do1.en4920.de/vMtextAdapter/sync` | `https://YA.fiv-mtext-do0.en4920.de/vMtextAdapter/sync` | **Belegt**, Skript 245–247 und 337–343 |
| `R270` | Z | JUR | `https://ZA.fiv-mtext-do1.en4920.de/vMtextAdapter/sync` | `https://ZA.fiv-mtext-do0.en4920.de/vMtextAdapter/sync` | **Belegt**, Skript 248–250 und 337–343 |
| sonstige | A | FKT | per historischer Formel ableitbar | per historischer Formel ableitbar | **Historischer Fallback**, Skript 254–257; im Zielentwurf absichtlich nicht erlaubt |

Der Adapter wird historisch einmal per POST mit JSON und dem Pfad
`/vMtextAdapter/sync` angesprochen (Skript 386–392). Der Body enthält wörtlich
`{"mandant":"MAN", "institut":"INR"}`. Ob diese beiden Werte vom Adapter
wirklich wörtlich erwartet oder historisch unvollständig parametrisiert werden,
ist nicht belegt. Die Zielkonfiguration dokumentiert sie daher als
`unverified_legacy_payload` und nicht als freigegebenen produktiven Vertrag.

### Mandanten-, Projekt-, Assignment- und Paketmatrix

| Mandant | Subsystem | FKT Assignment / Level | JUR Assignment / Level | Projekte und Paketcode | Dateinamen je Projekt | Status |
|---|---|---|---|---|---|---|
| FI | `LOMS` | `LOMS000066` / `FKTE` | `LOMS000067` / `JURP` | `Configuration`/`CONFI`, `Fonts`/`FONTS`, `LOMS_Framework`/`FRAME`, `LOMS_Basis`/`BASIS`, `LOMS_PKA`/`PKA` | `FI<CODE>F.tgz`, `FI<CODE>D.tgz`, `FI<CODE>D.txt` | **Belegt**, Skript 263–270, 420–426, 446–452 |
| BY | `BYMT` | `BYMT000055` / `FKTE` | `BYMT000056` / `JURP` | `LOMS_Basis[BY]`/`BASIS`, `LOMS_Autonom[BY]`/`AUTON` | `BYBASISF/D.tgz`, `BYBASISD.txt`; `BYAUTONF/D.tgz`, `BYAUTOND.txt` | **Belegt**, Skript 272–279, 430–433; `BYAUTOND.tgz` |
| LH | `LHMT` | `LHMT000022` / `FKTE` | `LHMT000023` / `JURP` | `LOMS_Basis[LH]`/`BASIS`, `LOMS_Autonom[LH]`/`AUTON` | `LHBASISF/D.tgz`, `LHBASISD.txt`; `LHAUTONF/D.tgz`, `LHAUTOND.txt` | **Belegt aus Skript**, 281–288, 430–433 |
| NW | `NWMT` | `NWMT000073` / `FKTE` | `NWMT000074` / `JURP` | `LOMS_Basis[NW]`/`BASIS`, `LOMS_Autonom[NW]`/`AUTON` | `NWBASISF/D.tgz`, `NWBASISD.txt`; `NWAUTONF/D.tgz`, `NWAUTOND.txt` | **Belegt aus Skript**, 290–297, 430–433 |
| OS | `OSMT` | `OSMT000047` / `FKTE` | `OSMT000048` / `JURP` | `LOMS_Basis[OS]`/`BASIS`, `LOMS_Autonom[OS]`/`AUTON` | `OSBASISF/D.tgz`, `OSBASISD.txt`; `OSAUTONF/D.tgz`, `OSAUTOND.txt` | **Belegt**, Skript 299–306, 430–433; `OSAUTONF.tgz` |
| SA | `SAMT` | `SAMT000031` / `FKTE` | `SAMT000032` / `JURP` | `LOMS_Basis[SA]`/`BASIS`, `LOMS_Autonom[SA]`/`AUTON` | `SABASISF/D.tgz`, `SABASISD.txt`; `SAAUTONF/D.tgz`, `SAAUTOND.txt` | **Belegt aus Skript**, 308–315, 430–433 |
| IT | `ITMT` | `ITMT000031` / `FKTE` | `ITMT000032` / `JURP` | `LOMS_Autonom`/`AUTON` | `ITAUTONF.tgz`, `ITAUTOND.tgz`, `ITAUTOND.txt` | **Belegt aus Skript**, 317–324, 427–429 |

Für FI/R251/Entwicklung synchronisiert das Skript zusätzlich
`LOMS_Basis[FI]`, jedoch nicht in Abnahme und nicht als eigenes Releasepaket
(Skript 379–385). Dieser Sonderfall ist im FI-Konfigurationsentwurf explizit
als `sync_only` abgebildet.

### FULL-/DELTA- und Informationsdateien

| Referenz | Belegte Eigenschaften |
|---|---|
| `BYAUTOND.tgz` | DELTA `R260.100 -> R260.234`; 65 TAR-Einträge, davon 33 Dateien und 32 Verzeichnisse; kein `./`-Präfix; Wurzel `LOMS_Autonom[BY]/`; `BYAUTOND.txt` liegt in der Archivwurzel und enthält 12 nichtleere relative Löschpfade. |
| `_INFO_BY-...R260.234-R260.178.txt` | Direkter Informationsvergleich `R260.178 -> R260.234`; 14 Einträge (2 A, 12 M, 0 D). Diese Liste ist nicht die Quelle der 33 Archivdateien oder der Löschliste. |
| `OSAUTONF.tgz` | FULL für `R260.100`; 1017 TAR-Einträge, davon 835 Dateien und 182 Verzeichnisse; alle Einträge haben historisch ein `./`-Präfix; Wurzel `./LOMS_Autonom[OS]/`. |
| `_INFO_OS-...R260.100-R251.510.txt` | Direkter Informationsvergleich `R251.510 -> R260.100`; 15 Einträge (2 A, 3 M, 10 D); die Inhaltsliste beschreibt das vollständige FULL-Archiv. |

Allgemein belegt sind:

- FULL-Archiv: `<MANDANT><PAKETCODE>F.tgz`;
- DELTA-Archiv: `<MANDANT><PAKETCODE>D.tgz`;
- Löschliste: `<MANDANT><PAKETCODE>D.txt` in der DELTA-Archivwurzel;
- Information:
  `_INFO_<MANDANT>-<PROJEKT>-<FULL|DELTA>-<RELEASE>-<VORRELEASE>.txt`;
- DELTA-Paketbasis ist immer `<Releasepräfix>.100`, während der direkte
  Vorreleasevergleich ausschließlich der Information dient (Skript 165–176,
  207–229 und 411–417).

### JCL-Platzhalter und Übergabe

| Platzhalter | Historischer Wert | Beleg |
|---|---|---|
| `@@ISPW@@` | historisch `P`; Kommentar nennt `T` oder `P` | Skript 259, 102, 117 |
| `@@LEVEL@@` | `FKTE` oder `JURP` | Skript 264–324, 102, 128–129 |
| `@@SUBSYS@@` | `LOMS`, `ITMT` oder `<MANDANT>MT` | Skript 420–457, 123–124 |
| `@@MEMBER@@` | `<MANDANT><PAKETCODE>F` oder `...D` | Skript 105, 126 und Aufrufe 157/160/202 |
| `@@ASSIGNMENT@@` | stage- und mandantenabhängige Assignmentnummer | Skript 263–324, 127 |

Das Template unter `mtext-delivery-automation/templates/` ist eine direkte,
lesbare Extraktion der JCL-Zeilen 68–132. FTP-Host, Credentials und
Übertragungscode wurden nicht in das Template übernommen. Das historische
Quellmember ist `IEA.LOMS.TONICZ`; Ziel-Dataset, Code-Pipeline-Metadaten und
Membername verwenden die fünf Platzhalter.

## Annahmen und Entwurfsentscheidungen

1. `mtext-fi/config/mandant.yml` verwendet den Zielnamen `mtext-fi`, weil nur
   dieser repräsentative Repository-Entwurf beauftragt ist und dieser Name im
   Handoff ausdrücklich belegt ist.
2. Die `.yml`-Entwürfe sind absichtlich JSON-kompatibles YAML 1.2. Dadurch sind
   sie ohne unkontrollierten Paketdownload mit der Python-Standardbibliothek
   lesbar; die spätere Auswahl und Sperrung eines YAML-Parsers bleibt offen.
3. Der historische Default für unbekannte Releasepräfixe und unbekannte
   Mandanten wird nicht übernommen. Die Konfiguration enthält nur die vier
   belegten Releasepräfixe und das Schema nur die sieben belegten Mandantencodes.
4. `R251`/`LOMS_Basis[FI]` wird als zusätzlicher `sync_only`-Pfad modelliert.
   Die fachliche Beobachtung ist belegt, die konkrete Konfigurationsform ist ein
   Entwurf.
5. Der JCL-Renderer begrenzt Werte vorläufig auf den beobachteten
   Mainframe-Zeichensatz; `MEMBER` auf 8, `ISPW` auf 1, `LEVEL` und `SUBSYS` auf
   8 und `ASSIGNMENT` auf 12 Zeichen. Diese Grenzen sind sicherheitsorientierte
   Implementierungsannahmen und müssen mit Mainframe/Code Pipeline bestätigt
   werden.
6. Das JCL-Template entfernt ausschließlich historisches Padding am Zeilenende.
   Inhalt und Reihenfolge bleiben erhalten. Ob bytegenaue 80-Spalten-Zeilen
   erforderlich sind, ist noch fachlich zu bestätigen.
7. Die gerenderte JCL-Fixture nutzt die belegten FI/JUR-Werte und Member
   `FIBASISF`; sie ist ein technischer Entwurf, noch keine fachlich abgenommene
   Golden-Master-Datei.

## Noch festzulegende Implementierungsparameter

1. Vollständige Repository-Namen und SVN-Wurzelpfade für LH, NW, OS, SA und IT.
2. Vollständige Allowlist produktiver Branches, Releaseverzeichnisse und Tags je
   Mandant; ausdrücklich auch alle weiteren Sicherungs-/Sonderverzeichnisse.
3. Gleichzeitig aktive Releaselinien und daraus abgeleitete physische
   Git-Branchnamen sowie das genaue SVN-Pfad-zu-Git-Pfad-Mapping.
4. Projektmatrix je Mandant und Releaselinie gegen reale Repository-Inhalte;
   besonders die Abweichung zwischen Screenshot (`LOMS_Testdaten`) und
   Skript (`LOMS_PKA`).
5. Bedeutung und zulässige Werte des Adapter-Payloads `MAN`/`INR`, der genaue
   NFS/serverSync-Vertrag sowie die fachlich dokumentierten 2xx-Antworten.
6. Freigegebene Python-Minor-Version, YAML-/JSON-Schema-Bibliotheken, Lockdatei
   und internes Installationsverfahren.
7. Mainframe-Zeichensätze und Maximallängen der fünf JCL-Felder,
   80-Spalten-/Encoding-Anforderungen sowie abgenommene JCL-Fixtures.
8. Unmittelbares Erfolgskriterium für FTP und JES-Submit; Job-Polling bleibt
   weiterhin außerhalb der ersten Ausbaustufe.
9. Verträglichkeit normalisierter TAR-Metadaten und Vereinheitlichung oder
   Erhalt des historischen `./`-Präfixunterschieds.
10. Umfang der zu migrierenden Historie, SVN-Properties/Externals/Autoren/LFS,
    Runner, Environments, Secrets, Retention, Concurrency und
    Benachrichtigungskanal gemäß Handoff Abschnitt 16.
