# Arbeitsregeln

## Formulierungen

- Kommentare und Dokumentation beschreiben den geltenden Stand. Frühere Varianten und
  verworfene Überlegungen entfallen, außer sie sind für eine Entscheidung wichtig.
- Einfach und auch für technisch unbedarfte Leser schreiben. Keine Semikolons zur
  Satztrennung verwenden.
- Aussagen nicht über bestätigte fachliche oder technische Sachverhalte hinaus erweitern.
  Ungeklärte Komponenten, Abläufe, Rollen oder Schutzmaßnahmen als offene Frage benennen.
- Verstärkungen und Einschränkungen wie `genau`, `nur`, `immer`, `vollständig` oder
  `zwingend` nur verwenden, wenn sie bestätigt und inhaltlich wichtig sind.
- Positive Aussagen unbegründeten Ausschlüssen vorziehen, etwa `Repository X darf
  zugreifen` statt `Nur Repository X darf zugreifen`.

## Dokumentation

- `docs/confluence/Naechste_Schritte.md` und `docs/confluence/Benutzeranleitung.md` nur
  ändern, wenn der Benutzer die jeweilige Datei ausdrücklich nennt.
- Informationen aufnehmen, die Leser zum Verständnis, für Entscheidungen oder zur
  Ausführung benötigen. Verbindliche Verträge technisch vollständig beschreiben.
  Herleitungen, vorsorgliche Absicherungen und hypothetische Betriebsabläufe entfallen,
  wenn sie dem Zweck der Seite nicht direkt dienen.
- Ein Zielbild beschreibt Sollzustand, Hauptablauf und verbindliche Schnittstellen.
  Implementierungs- oder Bedienhinweise gehören hinein, wenn sie den Sollzustand bestimmen.
- Eine Benutzeranleitung beschreibt Voraussetzungen, Handlungen, erwartete Ergebnisse und
  notwendige Kontrollen, nicht interne Implementierung oder technische Einrichtung.
- Eine Arbeitsliste nennt je Punkt Tätigkeit, Status und prüfbares Ergebnis, ohne
  Meta-Erklärungen, wiederholte Begründungen oder vorweggenommene Detailkonzepte.
- Rollen nur in der benötigten Granularität nennen. Beispiele, technische Namen, Eingaben
  und Statuswerte erhalten, wenn sie einen Vertrag oder Bedienweg eindeutig machen.
- Nach dem Entwurf Wiederholungen, entbehrliche Nebensätze, Meta-Navigation und folgenlose
  Details entfernen.

## Kommentare: Der Code liest sich wie ein Comic

- Docstring und Blockkommentare sollen Zweck, Schritte und Ergebnis einer Funktion in
  Ausführungsreihenfolge verständlich machen, ohne dass jede Codezeile gelesen werden muss.
- Jede Python-Funktion erhält einen Docstring oder Kommentar zu Zweck und Einordnung.
  Mehrschrittige Funktionen werden in Codeabschnitte gegliedert, vor denen unmittelbar ein
  kurzer narrativer Kommentar steht. Der Funktionskommentar ersetzt diese Gliederung nicht.
- Eigene Abschnitte bilden insbesondere Eingaben, Prüfungen, Vorbereitungen, externe
  Aufrufe, Zustandsänderungen, Ergebnisaufbau und Bereinigung. Ein kurzer, unmittelbar
  verständlicher Einzelschritt benötigt keinen künstlichen Blockkommentar.
- Kommentare benennen den Schritt und bei Bedarf Grund, Sicherheitsgrenze oder Bedeutung
  für den weiteren Ablauf. Lokale Detailkommentare erklären unerwartete Formate,
  Randbedingungen oder technische Eigenschaften.
- Jede Konstante erhält einen Kommentar zu ihrer fachlichen Bedeutung, Randbedingung oder
  Rolle. Nicht offensichtliche Zustandswechsel, Wiederholungsregeln, I/O-Grenzen,
  Sicherheitsprüfungen und mögliche Teilzustände werden an ihrer Wirkungsstelle erklärt.
- Längere Tests werden nach Vorbereitung, Ausführung und geprüftem Zusammenhang narrativ
  gegliedert. Kommentare wiederholen weder Mock, Assert noch unmittelbar lesbaren Code.
- Kurze Stichpunkte, Kleinschreibung und fehlende Satzzeichen sind gegenüber
  grammatikalisch korrekten Voll-Sätzen zu bevorzugen. Kommentare bleiben
  konkret, beschreiben den aktuellen Code und wiederholen weder Namen, Typen
  noch dieselbe Regel an direkt aufeinanderfolgenden Stellen.
- Betroffene Kommentare bei jeder Codeänderung mitprüfen. Falsche oder überholte
  Kommentare gelten als Codefehler.

```python
def upload_archive(path: Path) -> Response:
    """Überträgt ein Archiv und gibt die geprüfte Adapterantwort zurück."""

    # Dateigröße ankündigen, damit der Empfänger die erwarteten Bytes kennt
    headers = {"Content-Length": str(path.stat().st_size)}

    # großes FULL blockweise übertragen, statt den Arbeitsspeicher zu belegen
    with path.open("rb") as archive:
        response = send(archive, headers)

    # geprüfte Antwort an den weiteren Ablauf übergeben
    return validate_response(response)
```

## Python

- Fachlich getrennte `if`-Blöcke durch eine Leerzeile davor und durch Kommentare absetzen.
  Ist auch der nächste Abschnitt getrennt, folgt eine Leerzeile nach dem Block.
- Eine unmittelbar verwendete Vorberechnung bleibt ohne Leerzeile bei ihrem `if`.
- `if`-/`elif`-/`else`-Ketten bleiben zusammen. Erst danach folgt die Trennung zum nächsten
  Abschnitt.

## YAML-Workflows

- Anzeigenamen von Workflows, Jobs und Schritten kurz und auf Deutsch formulieren.
  Unveränderliche technische Namen externer Komponenten bleiben erhalten.
- Kommentare beschreiben Ablauf, Sicherheitsgrenzen und betriebliche Regeln an ihrer
  Wirkungsstelle. Aus dem YAML erkennbare oder für den Ablauf unwichtige Details entfallen.

## Fachsprache und Namen

- In Dokumentation und Betrieb verwendete deutsche Fachbegriffe übernehmen. Keine neuen
  englischen Übersetzungen für bestehende Begriffe einführen.
- Es heißt `Releaselinie` und `Mandantenkürzel`, nicht `Release-Line`, `release_line` oder
  `Mandant-Code`. Die JSON-Felder heißen `kuerzel`, `releaselinie`, `etaps_linie`,
  `hostprofil` und `hostprofile`. Umlaute in Feldnamen als `ae`, `oe` und `ue` schreiben.
- Code, Fehlermeldungen, Kommentare und Dokumentation verwenden dieselbe Fachsprache.
  Unveränderliche Namen externer Verträge wie Git, JCL, SHA oder CodePipeline bleiben.

## Einfachheit zuerst

- Den kleinsten Code wählen, der die Aufgabe vollständig löst. Eine umfangreichere Lösung
  ist vorzuziehen, wenn sie deutlich klarer und einfacher verständlich ist.
- Klarheit vor Cleverness. Keine spekulativen Abstraktionen, Framework-Konstrukte,
  unaufgeforderte Konfigurierbarkeit oder Mechanismen für mögliche spätere Anforderungen.
- Den erfolgreichen Hauptablauf mit frühen Prüfungen und Rückgaben linear halten.
- Keine Fehlerfälle behandeln, die laut Vertrag nicht auftreten können. Daten und Fehler an
  echten I/O-, Sicherheits- und Systemgrenzen behandeln und nachgelagert nicht erneut prüfen.
- Eine 200-zeilige Lösung neu schreiben, wenn 50 verständliche Zeilen genügen. Die
  Gesamtkomplexität aus Konzepten, Abstraktionsebenen, Verzweigungen und Lesesprüngen zählt.

### Validierung

- Nur bestehende Vertragsregeln prüfen. Keine Regex, Grenzwerte, Allowlists oder Sonderfälle
  aus vermutetem Future-Proofing ergänzen.
- Kleine zentrale Zuordnungen nicht zusätzlich durch abgeleitete Namensregeln einschränken.
  `releaselinien.json` legt beispielsweise `etaps_linie` ohne weitere Regex fest.
- Jede Formatregel hat einen Eigentümer. Andere Module importieren sie oder leiten ihre
  Prüfung daraus ab, statt sie erneut zu formulieren.

### Helferfunktionen

- Vor dem Anlegen oder Beibehalten einer Helferfunktion produktive Aufrufstellen suchen.
  Testaufrufe zählen nicht als Wiederverwendung der Produktionslogik.
- Eine produktive Aufrufstelle ist ein Warnsignal. Triviale Einmal-Helfer für Bedingungen,
  Zugriffe, Validierungen, Formatierungen, Projektionen oder Weiterleitungen einbetten, wenn
  dadurch Code, Begriffe oder Lesesprünge entfallen.
- Ein Einmal-Helfer darf eine nicht triviale I/O-, Sicherheits- oder fachliche Grenze
  kapseln oder einen langen Ablauf deutlich klären. Er muss eigene Logik enthalten und darf
  Code nicht bloß verschieben. Den Grund an der Funktion kommentieren.
- Ein sprechender Name oder mögliche spätere Wiederverwendung rechtfertigt keine
  Abstraktion. Wenige direkte, narrativ kommentierte Zeilen sind dann vorzuziehen.
- Gesamtunterschied aus Zeilen, Namen, Typen, Verzweigungen und Lesesprüngen vergleichen.
  Bei KISS-Überarbeitungen bestehende Helfer einbeziehen und triviale entfernen.

## Sonstiges

- Der alte Bash-Hook ist schreibgeschütztes Referenzmaterial und darf nie geändert werden.
