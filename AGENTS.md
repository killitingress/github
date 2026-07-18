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

- **jede** Python Funktion muss einen Kommentar bekommen der den Zweck
  beschreibt und ggf. in den Ablauf einordnet
- **jede** Konstante muss einen Kommentar haben der sie beschreibt
- **jeder** Codeblock muss einen kurzen Kommentar haben der ihn beschreibt
- jeder YAML Workflow muss ausreichend viele Kommentare enthalten, die klar
  machen was die einzelnen Dinge tun
