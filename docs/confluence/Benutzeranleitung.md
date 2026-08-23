# Benutzeranleitung für M/Text-Ressourcen mit Git

## 1. Einstieg von SVN zu Git

Diese Anleitung beschreibt die tägliche Arbeit mit M/Text-Ressourcen in Git.
Sie richtet sich an Entwickler und Repository-Verantwortliche, die bisher mit
SVN gearbeitet haben.

### Grundprinzipien

In SVN ist ein Commit eine Aktion, durch die Änderungen an das zentrale
Repository übertragen werden. Dabei entsteht eine neue Revision. In Git
hingegen hält ein Commit einen Entwicklungsstand samt Historie zu einem
bestimmten Zeitpunkt fest und entspricht damit am ehesten einer SVN-Revision.
Seine Commit-SHA kennzeichnet ihn eindeutig. Diese besteht aus 40 hexadezimalen
Zeichen, während eine SVN-Revision eine aufsteigende Nummer ist. Git-Commits
werden normalerweise lokal erstellt und erst durch einen Push nach GitHub
übertragen. Technisch ist ein Branch in Git ein Zeiger auf einen Commit. Beim
Push eines Branches nach GitHub werden sämtliche fehlenden Commits dorthin
übertragen und der Branch in GitHub auf den dann aktuellsten Commit
*verschoben*.

Jeder Entwicklungsauftrag wie eine Änderung, Erweiterung oder Korrektur wird
als Feature in einem eigenen temporären Feature-Branch umgesetzt. Wenn ein
Feature fertig entwickelt und getestet wurde, kann ein Pull Request angelegt
werden, um es in `main` oder `release/nnn` zu übernehmen. Der Pull Request muss
dazu im Vier-Augen-Prinzip geprüft und freigegeben werden. Danach werden die
Änderungen des Feature-Branches per Squash Merge in den Zielbranch
übernommen. Dabei entsteht ein neuer Stand und somit auch ein neuer Commit.

Wird ein Feature-Branch nach GitHub gepusht, werden die von ihm geänderten
M/Text-Ressourcen automatisch mit der M/Text-Entwicklungsumgebung
synchronisiert. Dort kann der Entwickler das Feature testen. Ein Merge nach
`main` oder `release/nnn` synchronisiert automatisch die
M/Text-Funktionstestumgebung. Dort soll das Feature von der LBS getestet und
fachlich freigegeben werden.

Eine Mainframe-Lieferung wird aus einem fachlich freigegebenen Stand auf
`main`, `release/nnn` oder `bereitstellung/nnn.nnn` vorbereitet. Die
Vorbereitung hält den gewählten Commit, den Liefer-Tag und den Lieferumfang
fest. Anschließend führt dieselbe oder eine zweite Person die vorbereitete
Lieferung aus. Der zentrale Workflow erzeugt den Liefer-Tag und startet
Paketbau sowie Mainframe-Übergabe.

### Grundablauf einer Änderung

```text
Feature-Branch erstellen und Änderung committen
    │ Push
    ▼
Änderung in M/Text-Entwicklung testen
    │ Pull Request und Review
    ▼
Squash Merge nach main oder release/nnn
    │ automatische Synchronisation
    ▼
Änderung in M/Text-Funktionstest abnehmen
```

### Grundablauf einer Mainframe-Lieferung

```text
Branch und Liefer-Tag auswählen
    │ Lieferung vorbereiten
    ▼
Lieferumfang prüfen
    │ Lieferung mit demselben geplanten Liefer-Tag ausführen
    ▼
Liefer-Tag, Paketbau und Mainframe-Übergabe
```

### Verwendete Namen

| Gegenstand | Namensschema | Beispiel |
|---|---|---|
| Produktive Releaselinie | `main` | `main` führt 270 |
| Parallel gepflegte Releaselinie | `release/nnn` | `release/261`, `release/271` |
| Einzelne Änderung | `feature/nnn/<Bezeichnung>` | `feature/261/issue-5678` |
| Arbeitsbranch einer Teillieferung | `bereitstellung/nnn.nnn` | `bereitstellung/261.108` |
| Liefer-Tag | `rnnn.nnn` | `r261.108` |

### Arbeitsmittel und Voraussetzungen

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

## 2. Feature entwickeln und in M/Text-Entwicklung testen

### Feature-Branch erstellen

1. Im passenden lokalen Klon den Branch der Releaselinie auswählen.
2. Diesen Branch auf den aktuellen GitHub-Stand bringen.
3. Einen neuen Branch `feature/nnn/<Bezeichnung>` erstellen.
4. Den Feature-Branch auschecken.

Die Bezeichnung soll den fachlichen Auftrag erkennen lassen. Beispiele sind:

```text
feature/270/neuer-brief
feature/261/issue-5678
feature/271/adresse-korrigieren
```

### Änderung bearbeiten und committen

1. Die Ressourcen in der M/Workbench bearbeiten.
2. In der Git-Ansicht die geänderten, neuen und gelöschten Dateien prüfen.
3. Änderungen, die nicht zum Auftrag gehören, aus dem Commit ausschließen oder
   in den betroffenen Dateien rückgängig machen.
4. Die fachlich zusammengehörigen Änderungen zum Commit hinzufügen.
5. Eine verständliche Commit-Nachricht eingeben.
6. Den Commit erstellen.

Bei Bedarf können auf dem Feature-Branch mehrere Zwischen-Commits entstehen.
Sie werden beim späteren Squash Merge auf dem Zielbranch zusammengefasst.

### Nach M/Text-Entwicklung übertragen

1. Den Feature-Branch nach GitHub pushen.
2. Im Mandanten-Repository unter **Actions** den Lauf **M/Text-Ressourcen
   synchronisieren** öffnen.
3. Kontrollieren, dass der Lauf den eigenen Feature-Branch und dessen aktuellen
   Commit verarbeitet.
4. Nach erfolgreichem Lauf die Änderung in M/Text-Entwicklung testen.
5. Erforderliche Korrekturen erneut committen und pushen.

Der erfolgreiche Workflow bestätigt die technische Übertragung. Die fachliche
Richtigkeit wird anschließend in M/Text geprüft.

### Gemeinsame M/Text-Entwicklungsumgebung beachten

Alle Feature-Branches einer Releaselinie verwenden dieselbe
M/Text-Entwicklungsumgebung. Ändern mehrere Feature-Branches dieselbe
Ressource, ist dort die zuletzt synchronisierte Änderung sichtbar. Die
beteiligten Entwickler stimmen deshalb ab, wann sie diese Ressource übertragen
und testen.

## 3. Pull Request und M/Text-Funktionstest

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

### Feature-Branch vor dem Merge aktualisieren

Hat sich der Zielbranch geändert, kann GitHub im Pull Request **Update branch**
anbieten. Damit wird der aktuelle Stand des Zielbranches in den Feature-Branch
übernommen. Anschließend wird die Änderung erneut in M/Text-Entwicklung
getestet. Hinweise zu Konflikten und abgelehnten Pushes stehen in Kapitel 7.

### Prüfen und zusammenführen

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

Der Squash Merge erzeugt einen Commit auf `main` oder `release/nnn`. Dieser
Push startet die Synchronisation mit M/Text-Funktionstest.

### Stand in M/Text-Funktionstest abnehmen

1. Unter **Actions** den Synchronisationslauf des Zielbranches öffnen.
2. Prüfen, dass der Lauf den Squash-Commit des Pull Requests verarbeitet.
3. Nach erfolgreicher Übertragung den Stand in M/Text-Funktionstest prüfen.
4. Einen festgestellten Fehler über einen neuen Feature-Branch korrigieren.

Auf `main` und `release/nnn` werden fachliche Änderungen nicht direkt
committet.

## 4. Änderung auf eine weitere Releaselinie übernehmen

Durch den Squash Merge liegt die zusammengeführte Änderung als ein Commit vor.
Soll die Änderung auch in eine weitere Releaselinie gelangen, wird dieser
Commit in einen neuen Feature-Branch der weiteren Releaselinie übernommen.
Damit kann die Änderung auf deren aktuellem Stand geprüft werden.

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

## 5. Mainframe-Lieferung ausführen

### Kurzfassung

Branch und Liefer-Tag wählen → **Lieferung vorbereiten** → Lieferumfang prüfen
→ **Lieferung ausführen** mit demselben Liefer-Tag → Mainframe-Übergabe und
GitHub Release kontrollieren.

### Lieferstand und Liefer-Tag bestimmen

Liefer-Tags heißen beispielsweise:

```text
r261.100   FULL-Basis der Releaselinie 261
r261.108   kumulatives DELTA gegen r261.100
```

`r261.100` bezeichnet den vollständigen Stand von `main` oder `release/261`.
Diese FULL-Lieferung enthält die vollständigen Projektstände. Eine
Teillieferung mit der Versionsnummer `.100` ist nicht vorgesehen. Spätere
Liefer-Tags derselben Releaselinie erzeugen ein kumulatives DELTA gegen den
`.100`-Tag.

Entspricht der gewünschte Lieferstand dem aktuellen Stand von `main` oder
`release/nnn`, kann dieser Branch direkt verwendet werden. Sollen ausgewählte,
bereits in M/Text-Funktionstest abgenommene Änderungen geliefert werden, wird
ein Bereitstellungsbranch erstellt.

### Teillieferung zusammenstellen

1. Branches und Tags mit EGit aus GitHub abrufen und den vorherigen Liefer-Tag
   auswählen, beispielsweise `r261.107`.
2. Von diesem Tag `bereitstellung/261.108` erstellen und auschecken.
3. Die vorgesehenen Squash-Commits in der gewünschten Reihenfolge per
   Cherry-Pick übernehmen.
4. Konflikte auflösen und den zusammengestellten Stand prüfen.
5. Den Bereitstellungsbranch nach GitHub pushen.

Der Bereitstellungsbranch wird nicht nach M/Text synchronisiert. Vor der
Lieferung wird deshalb der in der Zusammenfassung angezeigte Lieferumfang
geprüft. Nach erfolgreicher Lieferung kann der Bereitstellungsbranch gelöscht
werden.

### Lieferung vorbereiten

1. Im Mandanten-Repository **Actions** öffnen.
2. **Lieferung vorbereiten** auswählen.
3. **Run workflow** öffnen.
4. `main`, den passenden `release/nnn` oder den Bereitstellungsbranch
   auswählen.
5. Den Liefer-Tag `rnnn.nnn` eingeben und den Workflow starten.
6. In der Zusammenfassung Branch, Commit, FULL oder DELTA, Bezugsstand und
   projektbezogenen Lieferumfang prüfen.

Die Commit-SHA wird aus dem ausgewählten Branch ermittelt. Sie wird nicht
eingegeben. Die Vorbereitung hält diesen Stand fest, damit spätere Änderungen
am Branch die vorbereitete Lieferung nicht verändern.

Wird derselbe Liefer-Tag mehrmals vorbereitet, verwendet **Lieferung
ausführen** die neueste Vorbereitung.

### Lieferung ausführen

1. Nach der Prüfung unter **Actions** den Workflow **Lieferung ausführen**
   öffnen.
2. Den geplanten Liefer-Tag eingeben.
3. Wenn dieselbe Person die Lieferung vorbereitet hat, **Direktlieferung als
   Abweichung vom empfohlenen Vier-Augenprinzip und das damit verbundene Risiko
   bewusst bestätigen** auswählen.
4. Den Workflow starten.
5. Den angezeigten Lieferweg und den Start des zentralen Lieferlaufs prüfen.

Führt die vorbereitende Person auch diesen Workflow aus, ist die bewusste
Bestätigung erforderlich und die Zusammenfassung zeigt **Direktlieferung**.
Bei einer anderen Person zeigt sie **Vier-Augen-Freigabe**.

Der zentrale Lauf erstellt den Liefer-Tag auf dem vorbereiteten Commit, baut
die Pakete und startet die Mainframe-Übergabe.

### Ergebnis kontrollieren

Nach Abschluss wird geprüft:

1. Der zentrale Lieferlauf ist erfolgreich beendet.
2. Die Pakete wurden an den Mainframe übergeben.
3. Im Mandanten-Repository besteht zum Liefer-Tag ein GitHub Release.
4. Das GitHub Release nennt den gelieferten Commit und enthält die
   JSON-Informationsdateien der Projekte.

### Vorhandene Lieferung erneut ausführen

Eine vorhandene Lieferung kann erneut an den Mainframe übergeben werden:

1. Im Mandanten-Repository **Actions** öffnen.
2. **Lieferung ausführen** auswählen.
3. Den vorhandenen Liefer-Tag eingeben.
4. Den Workflow starten und den zentralen Lieferlauf kontrollieren.

Der vorhandene Liefer-Tag bleibt unverändert. Eine neue Vorbereitung ist nicht
erforderlich.

## 6. Sonderabläufe für Repository-Verantwortliche

### Mandantenkonfiguration ändern

Die Mandantenkonfiguration steht in `.github/config.json`. Änderungen werden
in einem Feature-Branch bearbeitet und über einen Pull Request übernommen. Das
Feld `releaselinie` wird beim Wechsel der produktiven Releaselinie geändert.

Der Workflow **Mandantenkonfiguration und Ressourcen prüfen** kontrolliert die
Konfiguration. Fehler werden vor dem Merge korrigiert.

Als M/Text-Projekt gilt jedes nicht versteckte Verzeichnis direkt in der
Repositorywurzel, sofern es nicht in `excluded_projects` ausgeschlossen ist.
Für den Projektcode werden `LOMS_` und ein Zusatz wie `[BY]` aus dem
Verzeichnisnamen entfernt. Vom verbleibenden Namen werden die ersten fünf
Zeichen in Großschreibung verwendet. Beispielsweise erhält
`LOMS_Basis[BY]` den Projektcode `BASIS`. Vor dem Hinzufügen oder Umbenennen
eines Projektverzeichnisses ist zu prüfen, ob es verarbeitet werden soll und ob
sein Projektcode eindeutig bleibt.

### Manuellen Vollabgleich starten

Ein manueller Vollabgleich ersetzt die einbezogenen Projekte in der
M/Text-Zielumgebung durch den ausgewählten Git-Stand. Der Lauf wird deshalb mit
anderen Arbeiten auf derselben Releaselinie abgestimmt.

1. Den gewünschten Commit in GitHub öffnen und seine vollständige SHA kopieren.
2. Im Mandanten-Repository **Actions** öffnen.
3. **M/Text-Ressourcen synchronisieren** auswählen.
4. **Run workflow** öffnen.
5. Den Branch auswählen, zu dem der Commit gehört.
6. Die vollständige Commit-SHA eingeben.
7. Den Workflow starten und den Lauf kontrollieren.
8. Den Stand in der zugeordneten M/Text-Umgebung prüfen.

Der ausgewählte Commit muss zum ausgewählten Branch gehören. `main` und
`release/nnn` werden mit M/Text-Funktionstest synchronisiert. Ein
Feature-Branch wird mit M/Text-Entwicklung synchronisiert.

### Die produktive Releaselinie wechseln

Vor dem Wechsel bestehen beispielsweise diese Stände:

```text
release/260   vorherige Releaselinie
main          produktive Releaselinie 261
release/270   kommende Releaselinie
```

#### Bisherige und kommende Linie abschließen

1. Prüfen, dass `release/270` den vollständigen neuen Stand enthält und in
   M/Text-Funktionstest abgenommen wurde.
2. `main` aktualisieren und prüfen, dass dieser Stand die bisher produktive
   Releaselinie 261 abschließt.
3. Falls 261 weiter gepflegt wird, `release/261` auf dem aktuellen
   `main`-Commit erstellen und nach GitHub pushen.
4. Prüfen, dass `release/261` und der bisherige `main` denselben Commit
   bezeichnen.

Beim Erstellen von `release/261` entsteht kein neuer Commit.

#### Kommende Linie nach main übernehmen

1. Die aktuellen Stände von `main` und `release/270` abrufen.
2. Vom aktuellen `main` den Branch
   `feature/270/releaselinienwechsel` erstellen und auschecken.
3. `release/270` in diesen Branch mergen.
4. Konflikte so auflösen, dass der fachliche Inhalt dem Stand von
   `release/270` entspricht.
5. In `.github/config.json` das Feld `releaselinie` auf `270` setzen.
6. Den Feature-Branch mit `release/270` vergleichen. Abgesehen von der für
   `main` benötigten Mandantenkonfiguration dürfen keine unbeabsichtigten
   Unterschiede bestehen.
7. Die Änderungen committen und den Feature-Branch pushen.
8. Einen Pull Request von `feature/270/releaselinienwechsel` nach `main`
   erstellen.
9. Den vollständigen Dateiinhalt und insbesondere Löschungen prüfen. Das
   Review durchführen und den Pull Request mit Squash Merge
   zusammenführen.
10. Prüfen, dass `main` dem vorgesehenen Stand von 270 entspricht und die
    Mandantenkonfiguration `270` nennt.

Der vollständige Vergleich ist erforderlich, weil ein Merge konfliktfreie
Änderungen des bisherigen `main` beibehalten kann.

#### Synchronisation und nächste Linie

1. Den automatisch gestarteten Synchronisationslauf von `main` kontrollieren.
2. Prüfen, dass der vollständige Stand zuerst nach M/Text-Entwicklung und
   anschließend nach M/Text-Funktionstest übertragen wurde.
3. Den Stand in beiden Umgebungen kontrollieren.
4. Neue Features für 270 auf Basis von `main` erstellen.
5. `release/271` auf Basis des neuen `main` erstellen und dort die kommende
   Releaselinie vorbereiten.

Die bisherige Linie 261 wird anschließend über `release/261` gepflegt. `main`
führt jetzt 270.

## 7. Fehler beheben und Workflow-Läufe kontrollieren

### Kurzfassung

Erwarteten Branch, Commit oder Liefer-Tag feststellen → erste aussagekräftige
Fehlermeldung prüfen → Ursache im Feature-Branch oder in der technischen
Einrichtung beheben → aktuellen gewünschten Stand erneut verarbeiten. Alte
Synchronisationsläufe nicht unkontrolliert wiederholen.

### Eigene Änderungen korrigieren

Solange der Pull Request noch nicht zusammengeführt wurde, wird die Korrektur
im selben Feature-Branch bearbeitet, committet und erneut getestet. Ist eine
noch nicht committete Änderung zu verwerfen, werden die betroffenen Dateien
vorher geprüft und gezielt mit **Restore** zurückgesetzt.

Nach dem Squash Merge wird die Korrektur in einem neuen Feature-Branch
bearbeitet und über einen neuen Pull Request übernommen.

### Konflikte und abgelehnte Pushes behandeln

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
Abruf geändert wurde, wird der GitHub-Stand abgerufen und mit dem lokalen Stand
verglichen. Die Änderungen werden erst danach zusammengeführt und erneut
gepusht.

### Workflow-Lauf prüfen

1. Im Mandanten-Repository **Actions** öffnen.
2. Den Workflow und den betroffenen Lauf auswählen.
3. Branch oder Liefer-Tag und verarbeiteten Commit mit dem erwarteten Stand
   vergleichen.
4. Die Jobs öffnen und die erste aussagekräftige Fehlermeldung prüfen.
5. Zugangsdaten nicht in Kommentare, Workflow-Eingaben oder Support-Tickets
   kopieren.

Für Paketbau und Mainframe-Übergabe führt der Mandantenlauf zu einem zentralen
Lauf in `FinanzInformatik/fi_lbs_entw_oms_mtext_actions`. Das abschließende
GitHub Release steht wieder im Mandanten-Repository.

### Fehlgeschlagene Ressourcenprüfung

- Fehler in `.github/config.json` werden im Feature-Branch korrigiert.
- Bei Hinweisen zu JSON- oder XML-Ressourcen werden die genannte Datei und
  Fundstelle geprüft und bei Bedarf korrigiert.
- Nach einer Korrektur wird derselbe Feature-Branch erneut gepusht.

### Fehlgeschlagene M/Text-Synchronisation

Vor einem erneuten Start wird der Commit des fehlgeschlagenen Laufs mit dem
aktuellen Branchstand verglichen. Ein älterer Lauf darf keinen inzwischen
überholten Stand nach M/Text übertragen.

- Verarbeitet der Lauf weiterhin den gewünschten Branchstand, wird die Ursache
  behoben und der Lauf erneut gestartet.
- Ist der M/Text-Stand unklar oder ein vollständiger Abgleich erforderlich,
  startet ein Repository-Verantwortlicher nach Abstimmung den manuellen
  Vollabgleich.

### Fehlerhafte oder fehlgeschlagene Mainframe-Lieferung

Zeigt ein Liefer-Tag auf den falschen Stand, wird er nicht erneut ausgeführt.
Nach seiner Löschung kann die Lieferung unter demselben geplanten Liefer-Tag
neu vorbereitet werden. Bei `.100` ist vor der Löschung zu prüfen, ob spätere
DELTA-Lieferungen diesen Tag bereits als Bezugsstand verwenden.

Im zentralen Lieferlauf wird geprüft, ob Paketbau oder Mainframe-Übergabe
fehlgeschlagen sind. In diesem Fall wird **Lieferung ausführen** mit dem
vorhandenen Liefer-Tag gestartet. Ein neuer Tag und eine neue Vorbereitung
sind nicht erforderlich.

Ist ausschließlich das Bereitstellen der Lieferinformationen in GitHub
fehlgeschlagen, wird im zentralen Lauf der fehlgeschlagene Job
**Bereitstellungsbericht im Mandanten-Repository veröffentlichen** erneut
ausgeführt. Das Paket wird dabei nicht noch einmal an den Mainframe übertragen.
