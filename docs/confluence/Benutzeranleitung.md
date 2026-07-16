# Benutzeranleitung für die M/Text-Lieferung mit GitHub Actions

**Stand:** 15. Juli 2026

**Zielgruppe:** Ressourcenautoren, Release-Verantwortliche, Freigebende und
Betrieb

**Bezug:** [Zielbild](./Zielbild_GitHub_Actions_Git.md),
[Soll-Grafik](../../Architektur_Soll_GitHub_Actions_Git.drawio) und
[offene Aktivierungsschritte](./Naechste_Schritte.md)

## 1. Zweck und aktueller Betriebsstatus

Die Lösung führt M/Text-Ressourcen eines Mandanten über die drei Stufen
`Entwicklung`, `Abnahme` und `Bereitstellung`. Pushes nach Entwicklung und
Abnahme lösen die jeweilige M/Text-Synchronisation aus. Nur der Pull Request
nach Bereitstellung prüft den Auswahlbranch vor dem Merge. Ein Merge nach
Bereitstellung liefert noch nichts aus; erst ein Release-Tag startet FULL oder
DELTA und die nachgelagerte Mainframe-Übergabe.

Der Stand im gemeinsamen Workspace ist noch **nicht aktiviert**:

- die drei Mandantenworkflows referenzieren absichtlich einen nicht
  auflösbaren Null-SHA der zentralen Automatisierung;
- `serverSync`, Adapter und Mainframe sind zusätzlich durch drei auf `false`
  stehende Vertragsschalter gesperrt;
- Runner, Environments, Secrets, Branchrulesets und externe Verträge müssen
  vor der Nutzung gemäß „Nächste Schritte“ eingerichtet und abgenommen werden.

Solange diese Sperren bestehen, darf diese Anleitung nur für Vorbereitung,
Schulung und lokale nebenwirkungsfreie Tests verwendet werden. Ein roter Lauf
wegen Null-SHA oder deaktiviertem Vertrag ist in diesem Zustand erwartetes
Schutzverhalten.

## 2. Rollen und Berechtigungen

| Rolle | Typische Aufgabe | Erforderlicher Zugriff |
|---|---|---|
| Ressourcenautor | Änderung direkt nach Entwicklung pushen und nach erfolgreicher Prüfung nach Abnahme promoten | Schreiben auf Entwicklungs- und Abnahmebranches |
| Release-Verantwortlicher | Nach Abnahme Auswahlbranch erstellen, Bereitstellung mergen und Tag setzen | Branch erstellen, Pull Request mergen, Tag pushen |
| Environment-Freigebender | Mainframe-Übergabe nach erfolgreichem Paketbau genehmigen | Reviewer für das Environment `Bereitstellung` |
| Betrieb/Plattform | Runner, Secrets, Environments, Rulesets und Vertragsschalter verwalten | Repository-/Organisationsadministration |

Ein verpflichtendes fremdes Pull-Request-Review ist im Zielbild nicht
vorgesehen. Direkte Pushes sind für Entwicklung und Abnahme erlaubt. Nur die
Bereitstellung verlangt einen Pull Request; der Ersteller darf ihn nach
erfolgreichen Pflichtchecks selbst mergen.

## 3. Begriffe und Namensregeln

| Element | Verbindliches Format | Beispiel |
|---|---|---|
| Stufenbranch | `Rnnn/Entwicklung`, `Rnnn/Abnahme`, `Rnnn/Bereitstellung` | `R261/Entwicklung` |
| Optionaler Feature-Branch | `feature/Rnnn/<Issue>-<kurzname>` | `feature/R261/12345-neuer-baustein` |
| Auswahlbranch | `release/Rnnn-YYYYMMDDTHHMMSSZ` in UTC | `release/R261-20260715T143000Z` |
| Release-Tag | `Rnnn.nnn` | `R261.100`, `R261.108` |

Feature-Branches sind eine optionale lokale Arbeits- und Namenskonvention. Sie
sind kein Pull-Request-Gate und lösen keine Verteilung aus. Maßgeblich für die
Automatisierung sind nur Pushes auf die Stufenbranches. Groß-/Kleinschreibung
der Stufen ist verbindlich. Aktive Linien sind derzeit `R260`, `R261` und
`R270`.

## 4. Änderung nach Entwicklung bringen

1. Das richtige Mandanten-Repository und die betroffene Releaselinie wählen.
2. Den aktuellen `<Releaselinie>/Entwicklung` auschecken; optional dafür einen
   lokalen Feature-Branch erstellen.
3. Nur die fachlich vorgesehenen Ressourcen ändern. Die Mandantenkonfiguration
   nur gemeinsam mit der fachlichen Zuordnung ändern; keine Secrets ablegen.
4. Änderungen committen und den gewünschten Commit direkt nach
   `<Releaselinie>/Entwicklung` pushen.
5. Unter **Actions → Sync M/Text resources** den durch den Push ausgelösten
   Lauf kontrollieren.

Der Push startet die Synchronisation des exakten Commits. Ein erfolgreicher
Lauf endet mit `ADAPTER_ACCEPTED`; dies bestätigt die synchrone 2xx-Annahme des
Adapters, nicht einen späteren fachlichen M/Text-Jobstatus.

## 5. Nach Abnahme promoten

1. Den in Entwicklung erfolgreich geprüften Commit ermitteln.
2. Genau diesen Commit direkt nach `<Releaselinie>/Abnahme` pushen.
3. Unter **Actions → Sync M/Text resources** den Abnahmelauf kontrollieren.
4. Die fachliche Abnahme außerhalb des Workflows nach dem vereinbarten
   Verfahren dokumentieren.

Der Push nach Abnahme verteilt den vollständigen konfigurierten Projektstand
des vom Anwender fachlich freigegebenen Commits. Er baut noch kein
Mainframe-Paket. Die Auswahl dieses Commits ist eine fachliche
Verantwortlichkeit; der Workflow erzwingt keine Gleichheit mit einem früheren
Entwicklungspush.

## 6. Ausgewählte Änderungen bereitstellen

1. Einen UTC-Zeitstempel bestimmen und den Auswahlbranch
   `release/<Releaselinie>-<YYYYMMDDTHHMMSSZ>` vom aktuellen
   `<Releaselinie>/Bereitstellung` erstellen.
2. Ausschließlich die fachlich freigegebenen Commits aus Abnahme per
   `git cherry-pick` in diesen Branch übernehmen. Konflikte fachlich prüfen;
   keine ungeprüften Konfliktauflösungen übernehmen.
3. Einen Pull Request vom Auswahlbranch nach
   `<Releaselinie>/Bereitstellung` öffnen.
4. Inhalt, Zielbranch und den Check `Validate change / Validate release promotion`
   prüfen und den Pull Request mergen.
5. Den erzeugten Merge-Commit notieren. Der Merge allein startet weder
   Paketbau noch Mainframe-Übergabe.

Der Auswahlbranch muss exakt dem Namensformat entsprechen. Ein direkter Pull
Request von Abnahme nach Bereitstellung wird von der Promotionsvalidierung
abgelehnt.

## 7. FULL oder DELTA auslösen

Vor dem Taggen müssen Releaselinie, Mandant, gewünschter Lieferungstyp und der
exakte Commit auf `<Releaselinie>/Bereitstellung` fachlich bestätigt sein.

- `Rnnn.100` erzeugt ein FULL mit dem vollständigen Stand jedes Projekts der
  Delivery-Allowlist.
- Jede andere gültige dreistellige Endung, zum Beispiel `R261.108`, erzeugt
  ein kumulatives DELTA von `R261.100` bis zum Zieltag.
- Ein DELTA setzt voraus, dass der `.100`-Tag derselben Linie vorhanden und
  erreichbar ist.

Zum Auslösen einen einfachen Git-Tag auf dem bestätigten Bereitstellungscommit
setzen und pushen, zum Beispiel:

```bash
git fetch origin R261/Bereitstellung --tags
git tag R261.108 <vollständiger-commit-sha>
git push origin refs/tags/R261.108
```

Danach unter **Actions → Build and publish release** prüfen:

1. `Build FULL or DELTA artifact` validiert Tag und Branchzuordnung, baut die
   Pakete und erzeugt `manifest.json` mit SHA-256-Prüfsummen.
2. Das Artefakt heißt `<Repository>-<Release-Tag>` und wird standardmäßig
   30 Tage aufbewahrt.
3. `Verify and hand over artifact to Mainframe` wartet im Environment
   `Bereitstellung` auf die eingerichtete manuelle Freigabe.
4. Nach der Freigabe werden Manifest und Prüfsummen erneut geprüft, JCL wird
   aus dem versionierten Template gerendert und Paket plus JCL werden per
   FTP/JES übergeben.

`MAINFRAME_SUBMITTED` bedeutet ausschließlich, dass die unmittelbare
FTP-/JES-Übergabe akzeptiert wurde. Der fachliche Abschluss des Mainframe-Jobs
wird in Ausbaustufe 1 nicht abgefragt.

## 8. Einen Lauf kontrolliert wiederholen

### M/Text-Synchronisation wiederholen

Unter **Actions → Sync M/Text resources → Run workflow** angeben:

- `commit_sha`: vollständiger 40-stelliger SHA des bereits geprüften Commits;
- `source_branch`: der passende Branch `Rxxx/Entwicklung` oder
  `Rxxx/Abnahme`.

Die Automation weist den Lauf zurück, wenn der Commit nicht aus dem gewählten
Branch erreichbar ist. Das Zielsystem kann nicht frei eingegeben werden; es
wird aus Branch und zentraler Konfiguration abgeleitet.

### Release-Lauf wiederholen

Unter **Actions → Build and publish release → Run workflow** den bereits
existierenden `release_tag` angeben. Keinen neuen Tag nur für einen technischen
Wiederanlauf erzeugen. Die Automation löst den Tag erneut auf und prüft seine
Erreichbarkeit aus `<Releaselinie>/Bereitstellung`.

Vor jedem Wiederanlauf klären, ob das Zielsystem die vorherige Übergabe bereits
angenommen hat. GitHub Actions kennt ohne Status-Polling keinen nachgelagerten
fachlichen Endstatus.

## 9. Status und Fehlerbilder verstehen

| Status oder sichtbares Symptom | Bedeutung | Nächste Prüfung |
|---|---|---|
| Workflow kann zentrale Datei am Null-SHA nicht laden | Aktivierungssperre des Entwurfs | Freigegebenen zentralen Commit erst nach den dokumentierten Abnahmen pinnen |
| `VALIDATION_FAILED` | Input, Konfiguration, Schema, Branchrichtung, Vertrag oder JCL ungültig | Erste Fehlermeldung lesen; Branch-/Tagformat und Freigabeschalter prüfen |
| `SOURCE_FAILED` | Commit oder Tag/Basisreferenz nicht auflösbar | SHA, Tag, `.100`-Basis und Branch-Erreichbarkeit prüfen |
| `PACKAGE_FAILED` | Paket, Informationsdatei oder Manifest konnte nicht sicher gebaut werden | Fehlende Projektpfade, Symlinks, leeres/benutztes Ausgabeverzeichnis prüfen |
| `RESOURCE_TRANSFER_FAILED` | Veröffentlichung nach serverSync/NFS fehlgeschlagen | Mount, Rechte, Zielpfad und Runnerzugriff prüfen; Adapter wurde nicht aufgerufen |
| `ADAPTER_FAILED` | Transportfehler oder Nicht-2xx vom Adapter | HTTP-Status und bereinigten Response-Body im Log prüfen |
| `ADAPTER_ACCEPTED` | Unmittelbare Adapterannahme erfolgreich | Kein Beleg für einen nachgelagerten M/Text-Endstatus |
| `ARTIFACT_READY` | Releaseartefakt lokal gebaut und geprüft | Publish-Freigabe beziehungsweise nächsten Job prüfen |
| `MAINFRAME_TRANSFER_FAILED` | FTP-Upload oder JES-Submit unmittelbar fehlgeschlagen | Credentials, Dataset, JES-Ziel, Netzwerk und FTP-Antwort prüfen |
| `MAINFRAME_SUBMITTED` | Unmittelbare FTP-/JES-Übergabe akzeptiert | Mainframe-Endstatus separat nach bestehendem Betriebsverfahren prüfen |

Logs dürfen keine Credentials enthalten. Zugangsdaten niemals in Pull
Requests, Konfigurationsdateien, Workflow-Inputs oder Support-Tickets kopieren.

## 10. Was Benutzer nicht tun dürfen

- keine direkten Pushes auf Stufenbranches erzwingen oder Schutzregeln
  umgehen;
- keinen Tag auf einen Commit außerhalb des zugehörigen
  `Rnnn/Bereitstellung`-Branches setzen;
- bestehende Release-Tags nicht verschieben oder ohne abgestimmtes
  Korrekturverfahren löschen und neu anlegen;
- keine URLs, Mandanten oder Zielsysteme als freie Workflowwerte einschleusen;
- Null-SHA oder Vertragsschalter nicht zur Fehlerbehebung eigenmächtig
  aktivieren;
- einen grünen Adapter- oder Mainframe-Übergabestatus nicht als fachlichen
  Endstatus ausgeben;
- keine Änderungen mehr im alten Jenkins-/SVN-Prozess vornehmen, sobald der
  produktive harte Cut erfolgt ist.

## 11. Kurze Checkliste vor einem Release

- richtiger Mandant und richtige Releaselinie;
- gewünschte Commits fachlich in Abnahme bestätigt;
- Auswahlbranch vom aktuellen Bereitstellungsstand erstellt;
- Pull Request nach Bereitstellung erfolgreich validiert und gemergt;
- Ziel-Commit notiert und Tag noch nicht vorhanden;
- `.100` vorhanden, wenn ein DELTA erzeugt werden soll;
- Build-Artefakt und Manifest erfolgreich;
- manuelle Mainframe-Freigabe durch berechtigte Person;
- unmittelbare Übergabe und nachgelagerter fachlicher Status getrennt
  dokumentiert.

Technische Einrichtung, Aktivierung und Cutover sind keine Benutzeraktionen.
Sie folgen der Seite [Nächste Schritte](./Naechste_Schritte.md).
