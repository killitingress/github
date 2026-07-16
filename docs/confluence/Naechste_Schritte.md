# Nächste Schritte

**Zweck:** Operative Restarbeiten bis zum Test-Parallelbetrieb

**Bezug:** [Zielbild](./Zielbild_GitHub_Actions_Git.md)

**Bedienung nach Aktivierung:** [Benutzeranleitung](./Benutzeranleitung.md)

**Migration und Produktivsetzung:**
[Migrations- und Cutover-Runbook](./Migration_und_Cutover_Runbook.md)

**Ablauf:** [Soll-Architektur Ablaufdiagramm](../../Architektur_Soll_GitHub_Actions_Git.drawio)

Diese Seite ist die Arbeitsliste für die erstmalige Einrichtung und die
nichtproduktive Abnahme. Bestätigte Punkte bleiben zur Orientierung sichtbar;
Architekturbegründungen, Bedienabläufe und das spätere Cutover stehen in den
verlinkten Dokumenten.

## 1. GitHub-Grundaufbau herstellen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Zentrales Repository `j520730/mtext-actions` und privates FI-Repository `j517120/mtext-fi` auf GitHub Enterprise anlegen beziehungsweise die lokalen Stände übernehmen | Das zentrale Repository ist nur für das Automatisierungsteam direkt zugänglich; das FI-Repository enthält Ressourcen, Mandantenkonfiguration und dünne Workflows |
| offen | Aktive Stufenbranches und Default Branch einrichten | Für `R260`, `R261` und `R270` bestehen jeweils `Entwicklung`, `Abnahme` und `Bereitstellung`; zunächst ist `R261/Entwicklung` der Default Branch |
| offen | Zentrale Workflowversion pinnen und repositoryübergreifenden Actions-Zugriff freigeben | Alle aufrufenden Workflows verwenden denselben freigegebenen Commit-SHA; nur vorgesehene Mandanten-Repositories dürfen `mtext-actions` aufrufen |
| offen | Zentralen Checkout und mandantensichtbare Logs praktisch prüfen | Ein nichtproduktiver Lauf funktioniert über beide Namespaces und zeigt weder Secrets noch unnötige interne Details; ein gegebenenfalls erforderlicher Installation-Token wird vor Aktivierung sicher in den Workflowvertrag aufgenommen |
| offen | Git-Clients für Ressourcenarbeit und Stufenweitergabe abnehmen | M/Text Workbench unterstützt Authentifizierung, Branchwechsel, Commit und Push; ein zusätzlicher Git-Client unterstützt den dokumentierten Cherry-Pick-Ablauf |
| bestätigt | GitHub-Plattform festhalten | GitHub Enterprise Server 3.20.4 |

## 2. Schutz- und Freigaberegeln konfigurieren

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Mandantenspezifische Verantwortliche benennen | Team für Ressourcenarbeit, technischer Konfigurationskreis und kleines Release-Team sind festgelegt |
| offen | Branchschutz für die drei Stufen einrichten | Berechtigte Text-Entwickler dürfen nach Entwicklung und Abnahme pushen; Bereitstellung ist auf das Release-Team begrenzt; Löschen und Force-Pushes sind gesperrt |
| offen | Zentrale Aufrufdateien und `config/mandant.json` schützen | Normale Ressourcen-Pushes können weder `.github/workflows/**/*` noch die Mandantenkonfiguration verändern; notwendige Bypässe sind eng begrenzt |
| offen | GitHub Environments konfigurieren | `Entwicklung`, `Abnahme` und `Bereitstellung` sind angelegt; nur die Mainframe-Übergabe in `Bereitstellung` erfordert eine manuelle Freigabe; zulässige Branchmuster sind eingetragen |
| offen | Release-Tags schützen | Nur das Release-Team darf Tags nach dem Muster `R[0-9][0-9][0-9].[0-9][0-9][0-9]` erstellen; Ändern und Löschen sind gesperrt |
| offen | Cherry-Pick und Release-Tag praktisch abnehmen | Auswahl nach SHA, Konfliktbehandlung und Push in die Zielstufe sind dokumentiert; ein nichtproduktiver Tag startet genau einen Release-Workflow |

## 3. Runner und technische Abhängigkeiten bereitstellen

Ein GitHub-Actions-Artefakt ist ein von einem Workflow erzeugtes und in GitHub
befristet gespeichertes Dateipaket. In diesem Prozess übergibt der Build-Job
damit Releasepakete, Informationsdateien und Manifest an den Publish-Job; es
ist weder ein Git-Commit noch eine dauerhafte Ablage.

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | Self-hosted Runner und Laufzeit bereitstellen | Labels `self-hosted`, `linux`, `mtext-delivery`, Python 3.14, Git und die Ausführung von Node-20-Actions sind bestätigt; `scripts/runner-preflight.sh` ist erfolgreich |
| offen | GHES-Artefakt-Actions prüfen | Die in den Workflows gepinnten Node-20-Varianten von `upload-artifact` v3.2.2 und `download-artifact` v3.1.0 sind auf GHES 3.20.4 verfügbar; v4 wird nicht verwendet |
| offen | Internes Wheelhouse bereitstellen | `LBS_WHEELHOUSE` verweist als Repository- oder Organisationsvariable auf einen freigegebenen lokalen Pfad; die Installation bleibt `--no-index` |
| offen | Zertifikate und Netzwerkpfade prüfen | Die interne CA ist im Truststore; der Runner erreicht die gewählten M/Text-Ziele sowie Mainframe-FTP und JES, ohne die TLS-Prüfung zu deaktivieren |

## 4. M/Text-Transport entscheiden und abnehmen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| bestätigt | Linien- und URL-Mapping | `R260→en03`, `R261→en01`, `R270→en02`; Hosts jeweils `enXXe` und `enXXa` |
| bestätigt | Heutigen Adaptervertrag als Ausgangslage festhalten | Der bestehende Ablauf schreibt zuerst nach `serverSync` und sendet danach einen POST mit `MAN` und `INR`; dies legt den künftigen Transport noch nicht fest |
| offen | Transportweg nach `serverSync` entscheiden und Zielvertrag festschreiben | Genau eine der im [Zielbild](./Zielbild_GitHub_Actions_Git.md#4-zielarchitektur-und-verantwortlichkeiten) beschriebenen Varianten wird ausgewählt: PUT an den Adapter, Sharezugriff des Runners oder Download eines Actions-Artefakts durch Adapter beziehungsweise M/Text; Verantwortlichkeiten, Authentifizierung, Prüfung und Wiederanlauf sind geklärt |
| offen | Kompatibilität des gewählten Transports nachweisen | Auf `serverSync` entsteht derselbe Verzeichnisbaum wie im bisherigen Verfahren; Transportdateien und technische Metadaten verbleiben nicht im ausgewerteten Bestand |
| offen | Config-Check und Synchronisation nichtproduktiv prüfen | `CONFIG_VALIDATED` bleibt nebenwirkungsfrei; ein vollständiger Projektstand wird erfolgreich über den gewählten Transport bereitgestellt und der Wiederanlauf ist geprüft |

## 5. Mainframe-Übergabe einrichten und abnehmen

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| offen | FTP-Secrets im GitHub Environment `Bereitstellung` hinterlegen | `MAINFRAME_FTP_HOST`, `MAINFRAME_FTP_USER` und `MAINFRAME_FTP_PASSWORD` sind verfügbar |
| bestätigt | Historischen JCL-Eingabevertrag fachlich bestätigen | Der mandantenspezifische Zielcode wird wie bisher über genau einen vorhandenen JCL-Platzhalter eingesetzt; der zentrale Test-/Produktionswert ist auf `T` und `P` begrenzt |
| offen | JCL und unmittelbare Übergabe nichtproduktiv prüfen | FTP-Antworten, `SITE FILETYPE=JES`, Submit, gerendertes JCL und Wiederholung mit demselben geprüften Artefakt sind abgenommen |

Die Mainframe-Übergabe wartet auf eine manuelle Freigabe. Das Releaseartefakt
bleibt 30 Tage erhalten; vor der Übergabe werden Manifest und Prüfsummen erneut
geprüft. Mit der bestätigten Übergabe an IZE9 endet der in GitHub Actions
abgebildete Lieferprozess.

## 6. Test-Parallelbetrieb vorbereiten

| Status | Tätigkeit | Ergebnis |
|---|---|---|
| geplant November/Dezember 2026 | Ersten SVN-Abzug nach dem [Migrations- und Cutover-Runbook](./Migration_und_Cutover_Runbook.md) erstellen | Alle Mandanten-Repositories stehen mit dokumentiertem SVN-Ausgangsstand für Tests bereit; Jenkins und SVN bleiben produktiv |
| offen | Importumfang und Release-Basen je Mandant freigeben | Aktive Linien, Projekte, Dateinamen und Ausschlüsse sind inventarisiert; je aktiver Linie werden mindestens der `.100`-Stand und alle späteren Tags übernommen |
| offen | Nichtproduktiven End-to-End-Pilot abnehmen | Git-Clients, Schutzregeln, M/Text-Synchronisation sowie FULL- und DELTA-Release einschließlich Mainframe-Übergabe sind auf dem vorgesehenen Betriebsweg geprüft |

Der finale SVN-Abzug und der harte Cutover sind ab Januar 2027 vorgesehen. Die
verbindliche Reihenfolge und die Abnahmekriterien stehen ausschließlich im
[Migrations- und Cutover-Runbook](./Migration_und_Cutover_Runbook.md). Der
wiederkehrende Linienwechsel steht in der
[Benutzeranleitung](./Benutzeranleitung.md#3-neue-releaselinie-initial-in-mtext-bereitstellen).
