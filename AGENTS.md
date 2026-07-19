# Arbeitsregeln

## Word-Dokumente

- `.docx`-Dateien nicht erzeugen, aktualisieren, rendern oder visuell prüfen.
- Bei Änderungen an der Dokumentation nur die Markdown-Quelldateien bearbeiten.
- Die Erzeugung und Prüfung der Word-Dokumente übernimmt der Benutzer selbst.
- Von dieser Regel nur abweichen, wenn der Benutzer dies ausdrücklich für eine konkrete Aufgabe verlangt.

## Formulierungen

- Kommentare oder Dokumentation darf nicht von Dingen sprechen die im Rahmen
  dieser Implementierung mal anders gemacht wurden - das ist irrelevant und
  verwirrt nur. Abgrenzungen zu früheren Überlegungen oder Erklärungen warum
  etwas jetzt auf eine bestimmte Weise, und nicht wie anders ggf. mal überlegt
  wurde, gemacht wird sollen nicht enthalten sein, es sei denn wichtige für den
  Leser zur Nachvollziehbarkeit der Entscheidungsfindung interessante Fakten
  sind enthalten.
- z.B. wenn etwas in früheren Überlegungen als "vielfältig möglich" vor kam
  aber sich herauskristalisiert hat, dass es nur "einzigartig" sein kann, dann
  muss dieses Einzigartigkeit nicht extra hervorgehoben werden, da sie sowieso
  klar ist.

## Kommentare

- **jede** Python-Funktion muss einen Kommentar oder eine Docstring bekommen,
  der ihren Zweck beschreibt und sie bei Bedarf in den Ablauf einordnet.
- **jede** Konstante muss eine aussagekräftige Beschreibung erhalten. Der
  Kommentar muss ihre fachliche Bedeutung, Randbedingung oder Rolle im Ablauf
  erklären und darf nicht lediglich den Namen der Konstante umformulieren.
- Vor einem zusammengehörigen Block regulärer Ausdrücke muss ein Kommentar den
  Block als reguläre Ausdrücke einordnen. Zusätzlich muss unmittelbar vor jedem
  einzelnen Ausdruck stehen, welchen konkreten Wert und welche reale Regel er
  prüft.
- Nicht-triviale Codeblöcke müssen kommentiert werden, wenn der fachliche Grund,
  eine Sicherheitsgrenze oder die Rolle im Ablauf nicht unmittelbar erkennbar
  ist.
- Jeder YAML-Workflow muss ausreichend viele Kommentare enthalten, die seine
  Jobs, Sicherheitsgrenzen und betrieblichen Regeln verständlich machen.
- Kommentare sollen Dritten Orientierung geben. Sie dürfen Namen, Typen oder
  unmittelbar lesbaren Code nicht bloß wiederholen und dieselbe Regel nicht an
  mehreren direkt aufeinanderfolgenden Stellen erneut erzählen.

## Fachsprache und Namen

- Für fachliche Begriffe sind die in Dokumentation und Betrieb verwendeten
  deutschen Bezeichnungen zu übernehmen. Keine neuen englischen Übersetzungen
  für bereits eindeutig benannte Fachbegriffe erfinden.
- Insbesondere heißt es `Releaselinie`, nicht `Release-Line` oder
  `release_line`, und `Mandantenkürzel`, nicht `Mandant-Code`.
- Die zugehörigen JSON-Felder heißen `kuerzel`, `releaselinie`,
  `etaps_linie`, `hostprofil` und `hostprofile`. Bei Feldnamen werden
  Umlaute als `ae`, `oe` und `ue` geschrieben.
- Namen in Code, Fehlermeldungen, Kommentaren und Dokumentation müssen dieselbe
  Fachsprache verwenden. Unveränderliche technische Namen externer Verträge
  wie Git, JCL, SHA oder CodePipeline bleiben unverändert.

## Einfachheit zuerst

- Bevorzugt wird der kleinste Code, der die aktuelle Aufgabe vollständig löst.
  Eine etwas umfangreichere Lösung ist nur dann vorzuziehen, wenn sie deutlich
  klarer und angenehmer zu verstehen ist. Nichts Spekulatives implementieren.
- Klarheit geht vor Cleverness. Direkte, naheliegende Kontrollflüsse verwenden
  und Sprachmittel nur einsetzen, wenn sie das Lesen tatsächlich erleichtern.
- Keine vorzeitigen Abstraktionen, Framework-Konstrukte oder allgemeinen
  Mechanismen für einmalige Fälle einführen.
- Keine unaufgeforderte Konfigurierbarkeit und kein Future-Proofing ergänzen.
- Den erfolgreichen Hauptablauf linear halten. Frühe Prüfungen und Rückgaben
  verwenden, statt tiefe Verschachtelungen aufzubauen.
- Keine Fehlerbehandlung für Fälle ergänzen, die nach dem geltenden Vertrag
  nicht auftreten können. Fehler an echten I/O-, Sicherheits- und
  Systemgrenzen weiterhin klar behandeln.
- Wenn eine Implementierung 200 Zeilen umfasst, obwohl 50 verständliche Zeilen
  genügen würden, ist sie neu und kompakter zu schreiben.
- Oberstes Ziel ist insgesamt kompakter, linear lesbarer Code mit möglichst
  wenigen Konzepten, Abstraktionsebenen, Sprüngen zwischen Funktionen und
  Verzweigungen. Nicht einzelne Funktionen isoliert optimieren, sondern die
  Verständlichkeit und Größe des gesamten Ablaufs bewerten.

### Validierung

- Nur Regeln prüfen, die im aktuellen fachlichen oder technischen Vertrag
  tatsächlich existieren. Keine regulären Ausdrücke, Grenzwerte, Allowlists
  oder Sonderfälle aus vermutetem Future-Proofing erfinden.
- Werte einer kleinen zentralen und versionierten Zuordnung nicht zusätzlich
  durch eine abgeleitete Namenskonvention einschränken. Beispielsweise legt
  `releaselinien.json` die `etaps_linie` selbst verbindlich fest; dafür gibt es
  keine zusätzliche Regex-Regel.
- Jede Formatregel hat genau einen Eigentümer. Andere Module importieren diese
  Regel oder leiten ihre Prüfung daraus ab, statt dieselbe Regel erneut zu
  formulieren.
- Für Hostprofile werden keine erlaubten Profilnamen fest verdrahtet. Die
  vorhandenen Profile stehen unter `hostprofile`; fachlich erlaubt sind
  ausschließlich die sechs CodePipeline-Stages `FKTE`, `FKTF`, `JURJ`, `JURP`,
  `SVTS` und `VPTV`.

### Helferfunktionen

- Vor dem Anlegen oder Beibehalten einer Helferfunktion müssen ihre produktiven
  Aufrufstellen mit der Textsuche geprüft werden. Aufrufe aus Tests zählen nicht
  als Wiederverwendung der Produktionslogik.
- Eine Helferfunktion mit nur einer produktiven Aufrufstelle ist ein deutliches
  Warnsignal. Sie wird eingebettet, wenn dadurch insgesamt Code, Begriffe oder
  Lesesprünge entfallen.
- Insbesondere keine Einmal-Helfer anlegen, die lediglich eine Bedingung, einen
  Dictionary-Zugriff, eine einzelne Validierung, eine Stringformatierung oder
  einen direkten Funktionsaufruf weiterreichen.
- Dünne Durchreichungshelfer, deren Rumpf nur auf verschachtelte Felder zugreift,
  sind direkt am Aufrufort einzubetten. Ein Helfer muss über das bloße
  Projizieren oder Weiterreichen von Feldern hinaus eigene Logik enthalten.
- Ein Einmal-Helfer darf bleiben, wenn er eine eigenständige, nicht-triviale
  I/O-, Sicherheits- oder fachliche Grenze kapselt oder einen langen Ablauf am
  Aufrufort deutlich verständlicher macht. Er darf dabei nicht lediglich Code
  und Begriffe an eine andere Stelle verschieben. Der Grund muss an der Funktion
  kommentiert sein.
- Ein sprechender Funktionsname allein rechtfertigt keine zusätzliche
  Abstraktion. Ein kurzer Kommentar über wenigen direkten Zeilen ist dann zu
  bevorzugen.
- Keine Abstraktion allein für mögliche spätere Wiederverwendung einführen.
  Wenige direkte, gut kommentierte Zeilen am tatsächlichen Aufrufort sind zu
  bevorzugen.
- Bei der Entscheidung den Gesamtunterschied vergleichen: Zeilenanzahl,
  zusätzliche Namen und Typen, Verzweigungen sowie notwendige Lesesprünge. Die
  Variante mit der geringeren Gesamtkomplexität ist zu bevorzugen.
- Bei jeder KISS-Überarbeitung bestehende Helfer mitzählen und triviale
  Einmal-Helfer entfernen; nicht nur neu hinzukommende Helfer bewerten.

## Sonstiges

- der alte Bash Hook ist read-only und darf nie verändert werden - ist nur
  Referenzmaterial
