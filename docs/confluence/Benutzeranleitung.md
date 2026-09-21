# Einstieg von SVN zu Git

Diese Anleitung beschreibt die tägliche Arbeit mit M/Text-Ressourcen in Git
für Entwickler und Repository-Verantwortliche, die bisher mit SVN gearbeitet
haben.

## Grundprinzipien

In SVN ist ein Commit eine Aktion, durch die Änderungen an das zentrale
Repository übertragen werden. Dabei entsteht eine neue Revision als
aufsteigende Nummer. In Git hingegen werden Commits in einer lokalen Kopie
eines Repositories getätigt und per Push an ein zentrales Repository
übertragen. Zu jedem Commit gehört eine 40-stellige Commit-SHA, die den
zugehörigen Entwicklungsstand samt Historie zu einem bestimmten Zeitpunkt
eindeutig identifiziert und damit am ehesten einer SVN-Revision entspricht.
Technisch ist ein Branch in Git ein Zeiger auf einen Commit. Beim Push eines
Branches nach GitHub werden sämtliche fehlenden Commits dorthin übertragen und
der Branch in GitHub auf den dann aktuellsten Commit *verschoben*.

Jeder Entwicklungsauftrag (Änderung, Erweiterung, Korrektur, ...) wird als
Feature in einem eigenen temporären Feature-Branch umgesetzt. Wenn ein Feature
fertig entwickelt und getestet wurde, kann ein PR (Pull Request) angelegt
werden, um es in einen Zielbranch wie z.B. `main` zu übernehmen. Der Pull
Request muss dazu in GitHub nach dem 4-Augenprinzip geprüft und freigegeben
werden, da Release-Branches und main generell geschützte Branches sind. Wenn
das passiert ist, werden die Änderungen des Feature-Branches per Squash Merge
in den Zielbranch übernommen. Dabei entsteht ein neuer Commit.

Wird ein Feature-Branch nach GitHub gepusht, werden seine M/Text-Projekte
automatisch mit der M/Text-Entwicklungsumgebung synchronisiert, damit das
Feature vom Entwickler dort vorab getestet werden kann. Ein Merge nach `main`
oder `release/nnn` synchronisiert in der Folge automatisch die entsprechende
M/Text-Funktionstestumgebung. Dort soll das Feature dann von der LBS getestet
und fachlich freigegeben werden. Danach kann der Feature-Branch wieder gelöscht
werden.

Eine Mainframe-Lieferung kann entweder auf `main` oder `release/nnn`
durchgeführt werden und verwendet dann dessen vollständigen Commit, oder auf
einer in `bereitstellung/nnn.nnn` zusammengestellten Teillieferung. Ein
Vorbereitungs-Workflow hält Branch, Commit-SHA und Lieferumfang fest und
zeigt sie in einem Freigabe-Issue. Der Freigabekommentar startet anschließend
Paketbau und Mainframe-Übergabe. Nach erfolgreicher Übergabe entsteht der
Liefer-Tag.

Die **M/Workbench** ist dabei das zentrale Arbeitsmittel für die Bearbeitung
der M/Text-Ressourcen und die Arbeit mit Git über das Eclipse-Plugin `EGit`.
Dieses Plugin erlaubt dem Anwender lokale Branches und Commits zu verwalten und
mit GitHub bzw. M/Text zu synchronisieren.

## Grundablauf einer Änderung

```text
Ressourcen in M/Workbench auf lokalem Feature-Branch bearbeiten (feature/nnn/<Bezeichnung>)
    │ Push
    ▼
Synchronisierung mit M/Text-Entwicklung
    │ Entwicklung testen
    ▼
Pull Request nach main (oder release/nnn)
    │ Review und Merge
    ▼
Synchronisierung mit M/Text-Funktionstest
    │ fachlich freigeben lassen
    ▼
Branchcommit ist für eine Lieferung bereit
```

## Grundablauf einer Mainframe-Lieferung

```text
Lieferung vorbereiten
    │ Branch auswählen (bereitstellung/nnn.nnn, release/nnn oder main)
    ▼
Freigabe-Issue prüfen
    │ /freigabe
    ▼
Paketbau, Mainframe-Übergabe und Liefer-Tag
```

## Verwendete Namen

| Gegenstand | Namensschema | Beispiel |
|---|---|---|
| Produktive Releaselinie | `main` | `main` führt 270 |
| Parallel gepflegte Releaselinie | `release/nnn` | `release/261`, `release/271` |
| Einzelne Änderung | `feature/nnn/<Bezeichnung>` | `feature/261/issue-5678` |
| Arbeitsbranch einer Teillieferung | `bereitstellung/nnn.nnn` | `bereitstellung/261.108` |
| Liefer-Tag | `rnnn.nnn` | `r261.108` |

## Arbeitsmittel und Voraussetzungen

Benötigt werden:

- Zugriff auf das Mandanten-Repository in GitHub
- ein lokaler Klon des Mandanten-Repositorys
- die Einbindung des Klons in den Arbeitsbereich der M/Workbench
- ein im Git-Client hinterlegter Benutzername und eine E-Mail-Adresse
- die Releaselinie der vorgesehenen Änderung

| Anwendung | Aufgabe |
|---|---|
| M/Workbench mit Eclipse Git-Plugin (EGit) | Ressourcen bearbeiten, Branches verwalten, Änderungen prüfen, committen, cherry-picken und pushen |
| GitHub im Browser | Pull Requests bearbeiten, Workflow-Läufe prüfen, Lieferungen starten, Tags und Lieferinformationen ansehen |

In einem Git-Arbeitsbaum kann ein Branch ausgecheckt sein. Für gleichzeitig
geöffnete Arbeiten an mehreren Releaselinien sind getrennte lokale Klone und
Eclipse-Arbeitsbereiche sinnvoll. So bleiben Projektbaum, Releaselinie und
lokale Änderungen eindeutig zugeordnet.

Beispiel:

```text
Arbeitsbereich 270  → main oder feature/270/...
Arbeitsbereich 261  → release/261 oder feature/261/...
Arbeitsbereich 271  → release/271 oder feature/271/...
```

# Feature entwickeln und in M/Text-Entwicklung testen

## Feature-Branch erstellen

1. Im passenden lokalen Klon den Branch der Releaselinie auswählen.
2. Diesen Branch auf den aktuellen GitHub-Commit bringen.
3. Einen neuen Branch `feature/nnn/<Bezeichnung>` erstellen.
4. Den Feature-Branch auschecken.

Die Bezeichnung soll den fachlichen Auftrag erkennen lassen. Beispiele sind:

```text
feature/270/neuer-brief
feature/261/issue-5678
feature/271/adresse-korrigieren
```

## Änderung bearbeiten und committen

1. Die Ressourcen in der M/Workbench bearbeiten.
2. In der Git-Ansicht die geänderten, neuen und gelöschten Dateien prüfen.
3. Änderungen, die nicht zum Auftrag gehören, aus dem Commit ausschließen oder
   in den betroffenen Dateien rückgängig machen.
4. Die fachlich zusammengehörigen Änderungen zum Commit hinzufügen.
5. Eine verständliche Commit-Nachricht eingeben.
6. Den Commit erstellen.

Bei Bedarf können auf dem Feature-Branch mehrere Zwischen-Commits entstehen.
Sie werden beim späteren Squash Merge auf dem Zielbranch zusammengefasst.

## Nach M/Text-Entwicklung übertragen

1. Den Feature-Branch nach GitHub pushen.
2. Im Mandanten-Repository unter **Actions** den Lauf **M/Text-Ressourcen
   synchronisieren** öffnen.
3. Kontrollieren, dass der Lauf den eigenen Feature-Branch und dessen aktuellen
   Commit verarbeitet.
4. Nach erfolgreichem Lauf die Änderung in M/Text-Entwicklung testen.
5. Erforderliche Korrekturen erneut committen und pushen.

Mit dem erfolgreichen Workflow ist die technische Übertragung bestätigt,
anschließend wird die fachliche Richtigkeit in M/Text geprüft. Hat M/Text eine
Ausgabe geliefert, verweist die Laufzusammenfassung auf das zehn Tage
verfügbare Laufartefakt `mtext-ergebnis`.

## Gemeinsame M/Text-Entwicklungsumgebung beachten

Da alle Feature-Branches einer Releaselinie dieselbe
M/Text-Entwicklungsumgebung verwenden, ist bei konkurrierenden Änderungen an
einer Ressource der zuletzt synchronisierte Commit sichtbar. Die beteiligten
Entwickler stimmen deshalb ab, wann sie diese Ressource übertragen und testen.

# Pull Request und M/Text-Funktionstest

Wenn die Änderung in M/Text-Entwicklung erfolgreich geprüft wurde:

1. Das Mandanten-Repository in GitHub öffnen.
2. Einen Pull Request vom Feature-Branch auf den zugehörigen Zielbranch
   erstellen.
3. Prüfen, dass Feature-Branch und Zielbranch zur selben Releaselinie gehören.
4. Die Änderung und das Ergebnis des Tests in M/Text-Entwicklung verständlich
   beschreiben.
5. Eine zweite Person für das Review zuordnen.

Beispiele:

```text
feature/270/neuer-brief  → main, wenn main die Releaselinie 270 führt
feature/261/issue-5678   → release/261
feature/271/neuer-brief  → release/271
```

## Feature-Branch vor dem Merge aktualisieren

Hat sich der Zielbranch geändert, kann GitHub im Pull Request **Update branch**
anbieten. Damit wird der aktuelle Commit des Zielbranches in den Feature-Branch
übernommen und anschließend erneut in M/Text-Entwicklung getestet. Hinweise zu
Konflikten und abgelehnten Pushes stehen in Kapitel 7.

## Prüfen und zusammenführen

1. Die zweite Person prüft geänderte und gelöschte Ressourcen sowie die
   Testbeschreibung.
2. Rückfragen und Änderungswünsche werden im Pull Request geklärt.
3. Korrekturen werden in denselben Feature-Branch gepusht und erneut getestet.
4. Das Ergebnis von **Mandantenkonfiguration und Ressourcen prüfen** wird
   kontrolliert. Fehler in der Konfiguration werden vor dem Merge korrigiert.
   Hinweise zur JSON- oder XML-Syntax werden geprüft und bei Bedarf
   korrigiert.
5. Nach erfolgreichem Review wird **Squash and merge** gewählt.
6. Die endgültige Commit-Nachricht wird kontrolliert.
7. Der Feature-Branch wird nach dem Merge gelöscht.

Der beim Squash Merge auf `main` oder `release/nnn` erzeugte Commit startet die
Synchronisierung mit M/Text-Funktionstest.

## Änderung in M/Text-Funktionstest abnehmen

1. Unter **Actions** den Synchronisierungslauf des Zielbranches öffnen.
2. Prüfen, dass der Lauf den Squash-Commit des Pull Requests verarbeitet.
3. Nach erfolgreicher Synchronisierung den M/Text-Stand in Funktionstest prüfen.
4. Einen festgestellten Fehler über einen neuen Feature-Branch korrigieren.

Auf `main` und `release/nnn` werden fachliche Änderungen nicht direkt
committet.

# Änderung auf eine weitere Releaselinie übernehmen

Durch den Squash Merge liegt die zusammengeführte Änderung als ein Commit vor.
Soll die Änderung auch in eine weitere Releaselinie gelangen, wird dieser
Commit in einen neuen Feature-Branch der weiteren Releaselinie übernommen.
Damit kann die Änderung auf deren aktuellem Commit geprüft werden.

1. Im ursprünglichen Pull Request die Commit-SHA des Squash-Commits kopieren.
2. Vom aktuellen Branch der weiteren Releaselinie einen neuen Feature-Branch
   erstellen.
3. Den Squash-Commit mit EGit per Cherry-Pick übernehmen. Konflikte auflösen
   und die übernommene Änderung prüfen.
4. Den Feature-Branch pushen und die Änderung in M/Text-Entwicklung testen.
5. Einen Pull Request auf den Branch der weiteren Releaselinie erstellen und
   wie in Kapitel 3 fortfahren.

Im folgenden Beispiel wurde die Änderung bereits nach `release/261`
zusammengeführt. Nun soll sie zusätzlich in die von `main` geführte
Releaselinie 270 übernommen werden:

```text
main (Releaselinie 270) ── Feature-Branch erstellen ──▶ feature/270/issue-5678
                                                                ▲
release/261 ── Squash-Commit per Cherry-Pick übernehmen ────────┘

feature/270/issue-5678 ── Pull Request nach Kapitel 3 ──▶ main
```

# Mainframe-Lieferung ausführen

## Kurzfassung

Lieferzweig wählen → **Lieferung vorbereiten** → Freigabe-Issue prüfen →
`/freigabe` kommentieren → Mainframe-Übergabe, Liefer-Tag und
Abschlussprotokoll kontrollieren.

## Lieferstand und Liefer-Tag bestimmen

Aus dem ausgewählten Branch leitet der Workflow den Liefer-Tag ab, sodass er
weder bei der Vorbereitung noch bei der Freigabe eingegeben wird.

| Ausgewählter Branch | Lieferart | Liefer-Tag |
|---|---|---|
| `main` | FULL | `r<Releaselinie von main>.100` |
| `release/nnn` | FULL | `rnnn.100` |
| `bereitstellung/nnn.nnn` | DELTA | `rnnn.nnn` |

Beispiele:

```text
r261.100   FULL-Basis der Releaselinie 261
r261.108   kumulatives DELTA gegen r261.100
```

Das Zwischenrelease `.100` bezeichnet die FULL-Basis einer Releaselinie. Ein
Bereitstellungsbranch mit `.100` ist nicht zulässig. Spätere Liefer-Tags
derselben Releaselinie erzeugen ein kumulatives DELTA gegen den `.100`-Tag.

Entspricht der gewünschte Lieferstand dem aktuellen Commit von `main` oder
`release/nnn`, kann dieser Branch direkt verwendet werden. Sollen ausgewählte,
bereits in M/Text-Funktionstest abgenommene Änderungen geliefert werden, wird
ein Bereitstellungsbranch erstellt.

## Teillieferung zusammenstellen

1. Branches und Tags mit EGit aus GitHub abrufen und den vorherigen Liefer-Tag
   auswählen, beispielsweise `r261.107`.
2. Von diesem Tag `bereitstellung/261.108` erstellen und auschecken.
3. Die vorgesehenen Squash-Commits in der gewünschten Reihenfolge per
   Cherry-Pick übernehmen.
4. Konflikte auflösen und den zusammengestellten Commit prüfen.
5. Den Bereitstellungsbranch nach GitHub pushen.

Der Bereitstellungsbranch wird nicht nach M/Text synchronisiert. Vor der
Lieferung wird deshalb der im Freigabe-Issue angezeigte Lieferumfang geprüft,
nach erfolgreichem Abschluss kann der Branch gelöscht werden.

## Lieferung vorbereiten

1. Im Mandanten-Repository **Actions** öffnen.
2. **Lieferung vorbereiten** auswählen.
3. **Run workflow** öffnen.
4. `main`, den passenden `release/nnn` oder den Bereitstellungsbranch
   auswählen.
5. Den Workflow starten.
6. Nach erfolgreichem Lauf den Link zum neu angelegten Freigabe-Issue in der
   Laufzusammenfassung öffnen.

Die Commit-SHA stammt aus dem ausgewählten Branch und muss nicht eingegeben
werden. Bevor das Freigabe-Issue entsteht, prüft der Workflow die
Mandantenkonfiguration und die Ressourcen im Lieferumfang. Syntaxbefunde
erscheinen als Warnungen und werden vor der Freigabe fachlich bewertet.

Das Freigabe-Issue trägt das Label `lieferung:freigabe` und zeigt:

- den aus dem Branch abgeleiteten Liefer-Tag
- Lieferart, Branch und festgehaltene Commit-SHA
- Abweichungen gegenüber dem vorherigen Liefer-Tag
- den vorgesehenen Inhalt der FULL- oder DELTA-Archive
- die vorbereitende Person und den Vorbereitungslauf

Die festgehaltene Commit-SHA bleibt die Grundlage der Lieferung, wenn der
Branch nach der Vorbereitung weitere Commits erhält. Ist der angezeigte Commit
nicht freigabefähig, wird der Branch korrigiert und **Lieferung vorbereiten**
erneut gestartet. Dabei entsteht ein neues Freigabe-Issue.

## Lieferung freigeben

1. Liefer-Tag, Branch, Commit-SHA und Lieferumfang im Freigabe-Issue prüfen.
2. Sicherstellen, dass der Liefer-Tag noch nicht im Repository vorhanden ist.
3. Als Person mit der Repository-Berechtigung `maintain` oder `admin` einen
   Kommentar schreiben, der ausschließlich `/freigabe` enthält.
4. Den vom Bot im Issue verlinkten Actions-Lauf öffnen und seinen Abschluss
   kontrollieren.

Auch die vorbereitende Person darf die Lieferung freigeben. Mit einer gültigen
Freigabe wechselt das Label von `lieferung:freigabe` zu
`lieferung:gestartet` und weitere `/freigabe`-Kommentare starten aus diesem
Issue keine zweite Lieferung.

Zum Lieferlauf gehören der Bau der FULL- oder DELTA-Archive mit ihrer JCL, die
Mainframe-Übergabe und das Einreichen der JCL-Aufträge. Alle Lieferdateien
stehen danach 30 Tage im Laufartefakt `release` bereit. Abschließend entsteht
der Liefer-Tag auf der im Issue festgehaltenen Commit-SHA.

## Ergebnis kontrollieren

Nach Abschluss wird geprüft:

1. Der Lieferlauf ist erfolgreich beendet.
2. Das Freigabe-Issue trägt das Label `lieferung:abgeschlossen` und ist
   geschlossen.
3. Der Liefer-Tag zeigt auf die im Issue festgehaltene Commit-SHA.
4. Der Abschlusskommentar nennt den Lieferlauf, die Archivnamen und ihre
   SHA-256-Prüfsummen.
5. Das Laufartefakt `release` enthält zu jedem `.tgz`-Archiv die zugehörige
   `.jcl`-Datei.

## Vorhandene Lieferung erneut ausführen

Eine abgeschlossene oder bereits gestartete Lieferung mit vorhandenem
Liefer-Tag kann aus ihrem Freigabe-Issue erneut ausgeführt werden:

1. Das zum Liefer-Tag gehörende Freigabe-Issue öffnen.
2. Als Person mit `maintain` oder `admin` einen Kommentar schreiben, der
   ausschließlich `/wiederholung` enthält.
3. Den neuen, im Issue verlinkten Actions-Lauf kontrollieren.

Für die Wiederholung liest der Workflow den Lieferstand aus dem annotierten
Tag und prüft dessen Zuordnung zum Freigabe-Issue. Dabei bleibt der Liefer-Tag
unverändert, während die Lieferdateien neu gebaut und erneut an den Mainframe
übergeben werden.

# Sonderabläufe für Repository-Verantwortliche

## Mandantenkonfiguration ändern

Die Mandantenkonfiguration steht in `.github/config.json` und wird über einen
Feature-Branch mit Pull Request geändert. Beim Wechsel der produktiven
Releaselinie erhält das Feld `releaselinie` den neuen Wert.

Der Workflow **Mandantenkonfiguration und Ressourcen prüfen** kontrolliert die
Konfiguration, damit Fehler vor dem Merge korrigiert werden können.

Als M/Text-Projekt gilt jedes nicht versteckte Verzeichnis direkt in der
Repositorywurzel, sofern es nicht in `excluded_projects` ausgeschlossen ist.
Für den Projektcode werden `LOMS_` und ein Zusatz wie `[BY]` aus dem
Verzeichnisnamen entfernt. Vom verbleibenden Namen werden die ersten fünf
Zeichen in Großschreibung verwendet. Beispielsweise erhält
`LOMS_Basis[BY]` den Projektcode `BASIS`. Vor dem Hinzufügen oder Umbenennen
eines Projektverzeichnisses ist zu prüfen, ob es verarbeitet werden soll und ob
sein Projektcode eindeutig bleibt.

## Manuellen Vollabgleich starten

Ein manueller Vollabgleich ersetzt die einbezogenen Projekte in den
gewählten M/Text-Umgebungen durch den Commit des ausgewählten Branches.
Den Abgleich deshalb mit anderen Arbeiten an diesen Umgebungen abstimmen.

1. Im Mandanten-Repository **Actions → Ressourcen synchronisieren** öffnen.
2. **Run workflow** öffnen und den gewünschten Branch auswählen.
3. Die **Zielumgebung** auswählen:
   - **Branchstandard**: Entwicklung für Feature-Branches, Funktionstest für
     `main` und `release/nnn`.
   - **Entwicklung** oder **Funktionstest**: den Branchcommit in die angegebene
     Umgebung übertragen.
   - **Beide**: zuerst Entwicklung, anschließend Funktionstest befüllen.
4. Den Workflow starten und die Ressourcenprüfung kontrollieren.
5. In der Laufzusammenfassung Commit, FULL-Umfang und Zielumgebungen prüfen.
   Die M/Text-Ausgaben im Laufartefakt und die M/Text-Stände in den Umgebungen
   kontrollieren.

Automatische Läufe verwenden DELTA, wenn ein erfolgreicher Abgleich desselben
Branches mit derselben Zielumgebung und derselben Releaselinie
belegt ist. Fehlt diese Basis, erfolgt FULL. Ein manueller Abgleich nur nach
Entwicklung verändert die Vergleichsbasis für Funktionstest nicht.

Läufe werden im Repository nacheinander ausgeführt. GHES 3.20 hält einen
wartenden Lauf vor, den ein weiterer Start ersetzen kann. Mehrere manuelle
Abgleiche deshalb nacheinander starten und ihren Abschluss kontrollieren.
Ein verdrängter Lauf erscheint in Actions als abgebrochen.

## Die produktive Releaselinie wechseln

Branches, Mandantenkonfiguration und Zielzuordnungen werden manuell
vorbereitet. Zur Übertragung dient der normale Workflow **Ressourcen
synchronisieren**. Vor dem Wechsel bestehen beispielsweise diese Branches:

```text
release/260   vorherige Releaselinie
main          produktive Releaselinie 261
release/270   kommende Releaselinie
```

### Zielzuordnungen vorbereiten

1. Im Repository `mtext_actions` die Datei `config/releaselinien.json` öffnen.
2. Die nächste Linie, beispielsweise `271`, ergänzen. Für die weiter
   verwendeten Linien `etaps_linie` und `hostprofil` prüfen und bei Bedarf
   anpassen.
3. Die Entwicklungs- und Funktionstestumgebungen anhand von `mtext_ziele` und
   `etaps_linie` kontrollieren. In `.github/config.json` des Mandanten müssen
   die zugeordneten Hostprofile mit Stage und Assignment vorhanden sein.
4. Änderungen in dem von den Workflows verwendeten Commit von `mtext_actions`
   bereitstellen, bevor die ersten Feature-Pushes und PR-Merges erfolgen.

Bereits der Push des vorbereitenden Feature-Branches synchronisiert
Entwicklung. Der spätere Merge nach `main` synchronisiert Funktionstest.
Diese automatischen Übertragungen gehören auch beim Releasewechsel zum
Ablauf. Der abschließende manuelle Abgleich ist daher eine Ergänzung und
nicht zwingend die erste Übertragung.

### Bisherige und kommende Linie vorbereiten

1. Prüfen, dass `release/270` den vorgesehenen vollständigen Commit enthält und
   in M/Text-Funktionstest abgenommen wurde.
2. Den aktuellen `main`-Commit und den letzten Liefertag der produktiven Linie
   261 feststellen. Änderungen auf `main` nach diesem Tag prüfen und
   entscheiden, welche in die neue produktive Linie übernommen werden.
3. Falls 261 weiter gepflegt wird, `release/261` auf dem bisherigen
   `main`-Commit erstellen und nach GitHub pushen. Prüfen, dass beide Branches
   denselben Commit bezeichnen.
4. `release/260` erhalten, solange die Linie weiter gepflegt wird, andernfalls
   den Branch löschen.

Das Anlegen oder direkte Pushen eines Release-Branches löst keine
Synchronisierung aus. Der Branchname bleibt seiner Releaselinie zugeordnet.

### Kommende Linie nach main übernehmen

1. Die aktuellen Commits von `main` und `release/270` sowie die Liefer-Tags
   abrufen.
2. Vom festgestellten letzten Liefertag der Linie 261 den Branch
   `feature/270/releasewechsel` erstellen und auschecken.
3. `release/270` in diesen Branch mergen. Die vorgesehenen Änderungen nach dem
   Liefertag übernehmen und Konflikte zum gewünschten vollständigen Commit
   auflösen.
4. In `.github/config.json` das Feld `releaselinie` auf `270` setzen.
5. Den vollständigen Dateiinhalt mit dem vorgesehenen Commit vergleichen.
   Insbesondere Löschungen und Abweichungen zu `release/270` kontrollieren.
6. Die Änderungen committen und den Feature-Branch pushen. Den automatisch
   gestarteten Abgleich nach Entwicklung kontrollieren.
7. Einen Pull Request nach `main` erstellen. Im Review auch prüfen, ob die
   Zusammenführung unbeabsichtigt Inhalte des bisherigen `main` beibehält.
8. Den Pull Request mit Squash Merge zusammenführen. Der entstandene Commit
   startet automatisch die Synchronisierung nach Funktionstest. Bei
   geänderter Zielzuordnung oder fehlendem passenden Vergleichscommit erfolgt
   FULL.
9. Prüfen, dass `main` dem vorgesehenen Commit von 270 entspricht und die
   Mandantenkonfiguration `270` nennt. Den automatischen Lauf und den M/Text-Stand
   in Funktionstest kontrollieren.

### Weitere Branchcommits manuell abgleichen

1. `release/271` auf Basis des neuen `main` erstellen und dort die nächste
   Releaselinie vorbereiten.
2. Für die gewünschten Branches, üblicherweise `main`, `release/261` und
   `release/271`, jeweils **Ressourcen synchronisieren → Run workflow** öffnen.
3. Branch und Zielumgebung auswählen. **Beide** verwenden, wenn Entwicklung
   und Funktionstest denselben Vollstand erhalten sollen.
4. Jeden Lauf abschließen lassen und Commit, Zielumgebungen und M/Text-Stand
   kontrollieren, bevor der nächste Abgleich gestartet wird.

Bei einem Fehler die Meldung und eine dort genannte bereits erfolgreich
verarbeitete Umgebung prüfen. Nach Behebung der Ursache den fehlgeschlagenen
Job im selben Lauf erneut ausführen, wenn derselbe Commit verarbeitet werden
soll. Bereits abgeschlossene und entfernte Adapteraufträge werden dabei
erneut übertragen.

Die bisherige Linie 261 wird anschließend über `release/261` gepflegt, `main`
führt 270 und `release/271` die kommende Linie. Neue Features für 270 entstehen
aus `main`.

# Fehler beheben und Workflow-Läufe kontrollieren

## Kurzfassung

Erwarteten Branch, Commit oder Liefer-Tag feststellen → erste aussagekräftige
Fehlermeldung prüfen → Ursache im Feature-Branch oder in der technischen
Einrichtung beheben → aktuellen gewünschten Commit erneut verarbeiten. Alte
Synchronisierungsläufe nicht unkontrolliert wiederholen.

## Eigene Änderungen korrigieren

Solange der Pull Request noch nicht zusammengeführt wurde, wird die Korrektur
im selben Feature-Branch bearbeitet, committet und erneut getestet. Ist eine
noch nicht committete Änderung zu verwerfen, werden die betroffenen Dateien
vorher geprüft und gezielt mit **Restore** zurückgesetzt.

Nach dem Squash Merge wird die Korrektur in einem neuen Feature-Branch
bearbeitet und über einen neuen Pull Request übernommen.

## Konflikte und abgelehnte Pushes behandeln

Entsteht beim Aktualisieren oder bei einem Cherry-Pick ein Konflikt:

1. Die betroffenen Dateien prüfen und den fachlich richtigen Inhalt
   herstellen.
2. Die aufgelösten Dateien in EGit bestätigen und die unterbrochene
   Git-Operation fortsetzen.
3. Ist die richtige Auflösung unklar, die Git-Operation abbrechen und die
   Abweichung mit den Beteiligten klären.
4. Nach der Auflösung die Änderung prüfen und erneut in M/Text-Entwicklung
   testen.

Wird ein Push abgelehnt, weil der Feature-Branch in GitHub seit dem letzten
Abruf geändert wurde, wird der GitHub-Commit abgerufen und mit dem lokalen Commit
verglichen. Die Änderungen werden erst danach zusammengeführt und erneut
gepusht.

## Workflow-Lauf prüfen

1. Im Mandanten-Repository **Actions** öffnen.
2. Den Workflow und den betroffenen Lauf auswählen.
3. Branch oder Liefer-Tag und verarbeiteten Commit mit dem erwarteten Commit
   vergleichen.
4. Die Jobs öffnen und die erste aussagekräftige Fehlermeldung prüfen.
5. Zugangsdaten nicht in Kommentare, Workflow-Eingaben oder Support-Tickets
   kopieren.

Paketbau und Mainframe-Übergabe bleiben Bestandteil des Mandantenlaufs, dessen
gemeinsame Implementierung aus
`FinanzInformatik/fi_lbs_entw_oms_mtext_actions` geladen wird. Liefer-Tag und
Freigabe-Issue entstehen dagegen im Mandanten-Repository.

## Fehlgeschlagene Ressourcenprüfung

- Fehler in `.github/config.json` werden im Feature-Branch korrigiert.
- Bei Hinweisen zu JSON-, XML- oder JavaScript-Ressourcen werden die genannte
  Datei und Fundstelle geprüft und bei Bedarf korrigiert.
- Nach einer Korrektur wird derselbe Feature-Branch erneut gepusht.

## Fehlgeschlagene M/Text-Synchronisierung

Fehler beim Ermitteln des Vergleichscommits, beim Paketbau, Upload oder bei der
Adapterverarbeitung erscheinen im Schritt **Ressourcen synchronisieren**.

1. Im Repository unter **Actions** den betroffenen Lauf öffnen und die
   Fehlerursache prüfen und beheben.
2. Den jüngsten fehlgeschlagenen Lauf des Branches über **Re-run jobs** erneut
   ausführen oder die Korrektur pushen. Die Synchronisierung holt dabei die noch
   fehlenden Änderungen früherer Pushes nach.
3. Das erfolgreiche Ende abwarten. Meldet der Lauf einen überholten
   Branchcommit, den neueren Lauf prüfen und diesen bei Bedarf wiederholen.

GitHub erlaubt Wiederholungen innerhalb von 30 Tagen und mit Schreibrechten auf
das Repository.

Ist der M/Text-Stand unklar oder ein vollständiger Abgleich erforderlich,
startet ein Repository-Verantwortlicher nach Abstimmung den manuellen Vollabgleich.

## Fehlerhafte oder fehlgeschlagene Mainframe-Lieferung

Ein nicht abgeschlossener Lieferlauf wird im Freigabe-Issue mit einem Link zum
betroffenen Actions-Lauf dokumentiert. Dort wird zuerst festgestellt, ob der
Liefer-Tag bereits erzeugt wurde.

Ist der Liefer-Tag noch nicht vorhanden:

1. Den verlinkten Actions-Lauf öffnen und den fehlgeschlagenen Job prüfen.
2. Die Ursache beheben oder mit den technisch Verantwortlichen klären.
3. Im selben Lauf **Re-run failed jobs** verwenden, damit die bereits bestätigte
   Freigabe und der festgehaltene Lieferstand erhalten bleiben.
4. Danach Issue, Liefer-Tag und Abschlusskommentar erneut kontrollieren.

Ist der Liefer-Tag vorhanden und soll derselbe Commit erneut übergeben werden,
wird im zugehörigen Freigabe-Issue `/wiederholung` kommentiert. Mit dem
unveränderten Tag baut der neue Lauf die Lieferdateien erneut.

Zeigt ein Liefer-Tag auf einen fachlich falschen Commit, darf er nicht
wiederholt werden. Vor seiner Löschung ist bei einem `.100`-Tag zu prüfen, ob
spätere DELTA-Lieferungen ihn bereits als Bezugscommit verwenden. Nach der
Löschung wird der Branch korrigiert und die Lieferung neu vorbereitet.
