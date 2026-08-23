# Skizze für parallele Releaselinien und Teillieferungen

## Drei dauerhafte Entwicklungsstände

```text
release/260      vorherige Releaselinie
main             aktuell produktive Releaselinie 261
release/270      kommende Releaselinie
```

Jede Linie hat eigene Feature-Branches und eine eigene M/Text-Umgebung.
Änderungen gelangen über Pull Requests in diese geschützten Branches. `main`
ist nicht der Sammelplatz für kommende Entwicklungen.

| Name | Rolle |
|---|---|
| `main` | Produktive Releaselinie und Abnahmestand in M/Text-Funktionstest |
| `release/nnn` | Parallel gepflegte Releaselinie und Abnahmestand in M/Text-Funktionstest |
| `feature/nnn/<Bezeichnung>` | Einzelne Änderung, Synchronisation nach M/Text-Entwicklung |
| `bereitstellung/nnn.nnn` | Kurzlebiger Arbeitsbranch für eine Teillieferung |
| `rnnn.nnn` | Liefer-Tag auf dem bestätigten Git-Stand |

Die Releaselinie heißt in der zentralen Zuordnung zum Beispiel `260`. Derselbe
Wert steht in Branchname, Feature-Branch und Mandantenkonfiguration.

## Die `.100`-Lieferung ist der Ausgangspunkt

`r260.100` ist ein FULL. Der Tag bezeichnet den vollständigen Stand
von `main` oder `release/260` und wird direkt auf diesem Branchstand erstellt.
Er ist die Basis aller weiteren Lieferungen dieser Releaselinie.

Eine Teillieferung mit der Version `.100` ist nicht vorgesehen.

## Spätere Teillieferungen

Mehrere Features liegen auf dem Abnahmebranch und in M/Text-Funktionstest.
Zur nächsten Lieferung sind nicht alle davon bereit. Der Abnahmebranch bleibt
der Abnahmestand. Die Lieferung ist eine ausgewählte Teilmenge.

```text
r260.154
    │ Arbeitsbranch anlegen
    ▼
bereitstellung/260.155
    │ vorgesehene Squash-Commits mit EGit cherry-picken
    ▼
festgehaltene SHA, Vorprüfung des Lieferumfangs
    │ Bestätigung
    ▼
r260.155
    │
    ▼
CodePipeline
```

1. `bereitstellung/260.155` entsteht aus dem vorherigen Liefer-Tag.
2. Die zusätzlich gewünschten Squash-Commits werden mit EGit cherry-gepickt.
3. Der Workflow hält die SHA fest und zeigt den Lieferumfang.
4. Nach der Bestätigung erzeugt er `r260.155` auf dieser SHA.
5. Er startet die Mainframe-Übertragung.

Der Arbeitsbranch kann danach gelöscht werden. Der Liefer-Tag bleibt. Spätere
Pakete sind kumulative DELTAs gegen `.100`.

Stimmt der gewünschte Lieferstand mit `main` oder `release/nnn` überein,
entfallen Arbeitsbranch und Cherry-Picks. Der Workflow taggt diesen
Branchstand.

Ein Cherry-Pick nach Konfliktlösung kann vom abgenommenen Squash-Commit
abweichen. Die Vorprüfung gilt für den zusammengestellten Commit.

Der Arbeitsbranch wird nicht nach M/Text-Funktionstest synchronisiert.

## Bestätigung

Das Vier-Augenprinzip ist der empfohlene Weg. Jede Lieferung wird in zwei
manuellen Workflow-Schritten ausgeführt:

1. Eine Person startet **Lieferung vorbereiten**.
2. Der Workflow hält SHA und Lieferumfang fest und zeigt die
   Vorbereitung unter dem geplanten Liefer-Tag an.
3. Nach der Prüfung startet eine Person **Lieferung ausführen** mit diesem
   Liefer-Tag.
4. Tag und Übertragung entstehen.

Startet dieselbe Person beide Workflows, ist es eine Direktlieferung. Startet
eine andere Person den zweiten Workflow, ist es eine Vier-Augen-Freigabe. Eine
Direktlieferung muss beim manuellen Start bewusst als Abweichung vom
empfohlenen Vier-Augenprinzip bestätigt werden.

Vorprüfung, Bestätigung und Liefer-Tag beziehen sich auf die zu Beginn
festgehaltene SHA. Die Branchspitze wird danach nicht erneut aufgelöst.

Die Mandantenkonfiguration enthält keine Vorgabe für die Bestätigungsart.

Die Mainframe-Lieferungen sind keine Releases im Sinne des FI-Leitfadens. Ein
Liefer-Tag ohne `v`-Präfix darf gelöscht werden. Ein Tag-Push allein startet
keine Übertragung.

## Wiederholung einer Lieferung

Der Tag bezeichnet den Git-Stand, nicht den einzelnen CodePipeline-Lauf.
Derselbe Stand darf über **Lieferung ausführen** mehrfach übertragen werden.
Eine erneute Bestätigung ist dafür nicht erforderlich.

## Wechsel auf die kommende Releaselinie

Korrekturen auf `main`, die auch für 270 gelten, werden während der
Parallelphase nach `release/270` übernommen.

Beim Wechsel:

1. Der bisherige Stand von `main` wird als `release/261` erhalten.
2. `release/270` enthält den vollständigen neuen Stand.
3. `feature/270/releaselinienwechsel` entsteht aus dem aktuellen `main`.
4. `release/270` wird in diesen Branch gemergt.
5. Konflikte und weitere Unterschiede werden so aufgelöst, dass der fachliche
   Inhalt dem Stand von `release/270` entspricht.
6. Die Mandantenkonfiguration wird auf Releaselinie `270` geändert.
7. Der Branch wird über einen Pull Request mit Squash Merge nach `main`
   übernommen.
8. `main` synchronisiert einen FULL nach `en02` und `fu02`.
9. Danach beginnt die Vorbereitung von `release/271`.

Nach dem Wechsel entspricht `main` dem vorbereiteten Stand von 270. Die
einzelnen 270-Commits bleiben auffindbar.

## Folgen für Zielbild und Automation

- Dauerhafte Branches sind `main` und `release/nnn`.
- Eine Teillieferung nutzt den temporären Branch `bereitstellung/nnn.nnn`.
- Liefer-Tags heißen `rnnn.nnn`.
- `.100` ist der vollständige Branchstand und die Basis späterer Lieferungen.
- Die Mandantenkonfiguration enthält keinen technischen Lieferstatus.
- Die Branchmuster und die Mandantenkonfiguration verwenden `nnn` statt `Rnnn`.
