# Zielbild für die Ablösung von Jenkins und SVN

**Stand:** 15. Juli 2026
**Dokumenttyp:** Confluence-Extrakt aus dem technischen Handoff
**Geltungsbereich:** M/Text-Ressourcenverteilung und Mainframe-Bereitstellung

Dieses Dokument beschreibt das fachliche und organisatorische Zielbild. Es ist
bewusst weniger implementierungsnah als das technische Handoff. Einzelheiten
zur Migration stehen auf der Seite
[Migration und harter Cut](./Migration_und_harter_Cut.md), der aktuelle
Arbeitsvorrat auf der Seite [Nächste Schritte](./Naechste_Schritte.md). Die
tägliche Bedienung beschreibt die
[Benutzeranleitung](./Benutzeranleitung.md).

## Leseführung und Soll-Grafik

Die editierbare
[Soll-Grafik GitHub Actions/Git](../../Architektur_Soll_GitHub_Actions_Git.drawio)
zeigt den vollständigen fachlichen Ablauf von der lokalen Änderung über
Entwicklung, Abnahme und Bereitstellung bis zu FULL/DELTA und der unmittelbaren
FTP-/JES-Übergabe. Sie zeigt außerdem die zentralen Querschnittskomponenten:
Mandanten-Repositories, das zentrale Automatisierungs-Repository, self-hosted
Runner, GitHub Environments, Null-SHA, Vertragsschalter und Concurrency.

Die Grafik verwendet die verbindlichen Branchschreibweisen und grenzt den
Status `MAINFRAME_SUBMITTED` ausdrücklich vom fachlichen Mainframe-Jobende ab.
Die [Ist-Grafik Jenkins/SVN](../../Architektur_Ist_Jenkins_SVN.drawio) bleibt
als historische Referenz erhalten.

## 1. Executive Summary

Jenkins und SVN werden gemeinsam durch GitHub Actions und Git abgelöst. Die
Umstellung ist als harter Schnitt vorgesehen: Nach dem Cut ist Git die einzige
führende Quelle für Ressourcen und Konfiguration, GitHub Actions der einzige
Orchestrator dieses Prozesses. Ein paralleler produktiver Betrieb oder eine
laufende Synchronisation zwischen SVN und Git ist nicht vorgesehen.

Das bestehende Jenkins-/SVN-Skript bleibt ausschließlich historische Referenz.
Aus ihm werden fachlich relevante Mappings, Paketregeln, Übergabeverfahren und
JCL-Inhalte übernommen. Die monolithische technische Struktur und die
historische Fehlerbehandlung werden nicht fortgeführt.

Der fachliche Promotionsweg bleibt erhalten. Änderungen gelangen zunächst in
die Entwicklungsstufe und werden von dort zum M/Text-Entwicklungssystem
verteilt. Nach erfolgreichen Prüfungen und Merge werden sie in die
Abnahmestufe übernommen und zum M/Text-Abnahmesystem verteilt. Ausgewählte Änderungen
gelangen anschließend in die Bereitstellung. Erst ein manuell gesetzter Release-Tag
auf diesem Stand erzeugt eine FULL- oder DELTA-Lieferung für den bestehenden
Mainframe-Prozess.

Pull Requests bilden die kontrollierte Hülle für Prüfung und Nachvollziehbarkeit.
Sie führen selbst keine Verteilung aus. Erst der Merge erzeugt das Ereignis,
das den jeweiligen Prozess startet. Ein verpflichtendes fremdes Review wird
nicht eingeführt; der Ersteller darf nach erfolgreichen Statuschecks selbst
mergen. Direkte Änderungen an den geschützten Stufenbranches werden verhindert.

Die vorhandenen Integrationsverfahren bleiben in der ersten Ausbaustufe
bewusst bestehen. M/Text wird synchron über den vorhandenen Adapter
angesprochen; die Mainframe-Übergabe erfolgt weiterhin über FTP und
JCL-Submit. Die Lösung bewertet zunächst nur den unmittelbar verfügbaren
Übergabe- beziehungsweise HTTP-Status. Ein nachgelagertes Job-Polling ist nicht
Bestandteil der ersten Ausbaustufe.

## 2. Verbindliche Rahmenbedingungen

Die Umstellung folgt einem klar abgegrenzten Zielvertrag:

- Jenkins und SVN werden für diesen Prozess gemeinsam abgelöst.
- Es gibt weder parallelen Produktivbetrieb noch eine Synchronisation zwischen
  dem alten und dem neuen System.
- Das historische Skript wird nicht verändert und nicht technisch portiert.
- Jeder Mandant erhält ein eigenes GitHub-Quellrepository entsprechend der
  bisherigen fachlichen Trennung.
- Gemeinsame Automatisierung wird zentral versioniert und von den
  Mandanten-Repositories in einer festgelegten Version verwendet.
- Ressourcen und mandantenspezifische Konfiguration stammen nach dem Cut
  ausschließlich aus Git.
- Jeder Lauf arbeitet auf einem eindeutig bestimmten Commit-SHA.
- Der Mandant ergibt sich aus Repository und versionierter Konfiguration und
  ist kein frei eingebbarer Deploymentparameter.
- Pull Requests prüfen Änderungen; externe Verteilungen starten
  erst durch den Merge oder durch einen gültigen Release-Tag.
- Ein Merge nach `Rxxx/Entwicklung` verteilt zum Entwicklungssystem, ein Merge
  nach `Rxxx/Abnahme` zum Abnahmesystem. Ein Merge nach
  `Rxxx/Bereitstellung` erzeugt allein noch keine Lieferung.
- Die bestehenden Adapter- und Mainframe-Verfahren werden in der ersten
  Ausbaustufe nicht um fachliches Status-Polling erweitert.

Die gleichzeitig aktiven Releaselinien besitzen getrennte physische
Git-Branches nach dem Muster `<Releaselinie>/<Stufe>`. Aktuell sind dies
`R260`, `R261` und `R270` mit den Stufen `Entwicklung`, `Abnahme` und
`Bereitstellung`.

## 3. Historische Ist-Architektur als Referenz

Das bisherige Jenkins-Skript bündelt viele fachlich unterschiedliche Aufgaben
in einem Ablauf. Es verwaltet langlebige SVN-Arbeitskopien auf NFS, löst
Release-, Stufen-, Mandanten- und Projektzuordnungen auf, verteilt Ressourcen
an M/Text, erzeugt FULL- und DELTA-Pakete, erstellt Inhalts- und Löschlisten,
überträgt Dateien zum Mainframe, erzeugt JCL und versendet Informationen.

Die historische Struktur ist für die Vollständigkeitsprüfung wertvoll, aber
kein Vorbild für die neue Lösung. Insbesondere werden keine SVN-Arbeitskopien,
Reparaturkommandos oder dynamisch erzeugten credentialhaltigen Skripte
übernommen. Historische Probleme wie blockierte Arbeitsverzeichnisse,
unübersichtliche Abbruchlogik oder eine Vermischung von Benachrichtigung und
fachlichem Status werden im Zielbild durch klare Verantwortlichkeiten und
Tests adressiert.

Die Quellen belegen eine Trennung nach Mandanten sowie die fachlichen Stufen
Entwicklung, Abnahme und Bereitstellung. Sie belegen außerdem, dass DELTA-
Lieferungen kumulativ gegen den `.100`-Stand einer Releaselinie gebildet
werden. Der Vergleich mit dem direkten Vorrelease dient nur der Information
und bestimmt nicht den Paketinhalt. Historische Sonder- und
Sicherungsverzeichnisse dürfen nicht automatisch migriert werden; hierfür ist
eine explizite Allowlist erforderlich. Die ursprünglichen Lieferdateien dienten
nur der Entwicklung dieses Zielbilds. Sie werden nicht als Test-Fixtures oder
dauerhafter Repositorybestand übernommen.

## 4. Zielarchitektur und Verantwortlichkeiten

Die Zielarchitektur trennt fachliche Quellen, gemeinsame Automatisierung und
technische Integrationen deutlich voneinander.

In den Mandanten-Repositories liegen die migrierten M/Text-Ressourcen und die
jeweilige Mandantenkonfiguration. Branches, Tags und Commit-SHAs gelten immer
innerhalb genau eines Mandanten-Repositories. Secrets oder generierte Dateien
mit Zugangsdaten gehören nicht in diese Repositories.

Ein zentrales Automatisierungs-Repository enthält gemeinsame Regeln,
Validierung, Paketlogik, das JCL-Template und die zugehörigen Tests. Dadurch
verwenden alle Mandanten dieselbe freigegebene Automatisierung, ohne dass die
mandantenspezifischen Ressourcen oder Mappings zentralisiert werden müssen.

GitHub Actions reagiert auf Pull Requests, Merges, Release-Tags und
kontrollierte manuelle Wiederholungen. Es validiert Eingaben vor externen
Seiteneffekten, stellt Parallelität kontrolliert ein und dokumentiert den
Status, den die jeweilige Schnittstelle tatsächlich liefert.

Für interne NFS-, Adapter- und Mainframe-Zugriffe wird voraussichtlich ein
gehärteter self-hosted Runner benötigt. Dessen Betrieb, Patchstand,
Netzwerkzugriffe und Werkzeuge liegen in der Verantwortung des Plattformteams.

Der M/Text-Adapter und der Mainframe-Prozess bleiben zunächst unverändert. Ein
erfolgreicher synchroner Adapteraufruf wird als Annahme durch den bestehenden
Vertrag bewertet. Bei der Mainframe-Strecke wird eine bestätigte technische
Übergabe gemeldet, nicht ein fachlicher Endstatus des nachgelagerten Jobs.

## 5. Aktuelle Repository-Struktur

Der erste lokale Implementierungsstand bildet bereits die Trennung zwischen
repräsentativem Mandanten-Repository und zentraler Automatisierung ab. Im
gemeinsamen Arbeitsbereich ist folgende Struktur entstanden:

```text
github/
  docs/
    confluence/
      Zielbild_GitHub_Actions_Git.md
      Migration_und_harter_Cut.md
      Naechste_Schritte.md

  mtext-fi/
    .github/
      workflows/
        validate.yml
        sync-resources.yml
        release.yml
        README.md
    config/
      mandant.json
    tests/
      test_workflow_contract.py
    README.md

  mtext-actions/
    .github/
      workflows/
        ci.yml
        reusable-validate-pr.yml
        reusable-sync-resources.yml
        reusable-release.yml
    config/
      mandant.schema.json
      deployments.schema.json
      deployments.json
    scripts/
      runner-preflight.sh
    src/
      lbs_delivery/
        cli.py
        config.py
        errors.py
        git_refs.py
        jcl.py
        mainframe.py
        manifest.py
        mtext_adapter.py
        release.py
        resources.py
    templates/
      mainframe-upload.jcl
    tests/
      integration/
      unit/
    pyproject.toml
    requirements.lock
    README.md
```

`mtext-fi` ist der repräsentative Mandantenentwurf. Seine Delivery-Allowlist
enthält die fünf bisher verarbeiteten FI-Projekte und deren Paketzuordnungen.
`LOMS_Testdaten` gehört zum späteren Repositoryinhalt, bleibt aber wie bisher
außerhalb von Synchronisation und Paketbau; der redundante alte Sonderpfad
`LOMS_Basis[FI]` entfällt. Drei dünne Workflows bilden Validierung, M/Text-Synchronisation
und Releaseauslösung vollständig auf Mandantenseite ab. Sie enthalten keine
Fachlogik und sind im Entwurf durch eine absichtlich nicht auflösbare zentrale
Referenz gegen Ausführung gesperrt. Ein lokaler Vertragstest prüft Trigger,
Berechtigungen und unveränderliche Workflow-Pins.

`mtext-actions` enthält die gemeinsamen Konfigurationsregeln, die belegten
Releaselinien und Adapterziele, drei wiederverwendbare Workflows, einen eigenen
zentralen CI-Workflow, die vollständige Python-CLI für Validierung,
Synchronisation, Paketbau und Mainframe-Übergabe sowie das aus der
historischen Referenz extrahierte JCL-Template. Lokale Tests decken die
Fachlogik ohne externe Zielaufrufe ab.
Konfiguration und Releasemanifest besitzen verbindliche Schemata. Nach der
Validierung bleiben sie bewusst einfache JSON-Dokumente. Kleine
Hilfsfunktionen bilden nur fachliche Querverweise ab, die sich nicht direkt im
Schema ausdrücken lassen; eine zusätzliche Dataclass- und Immutability-Schicht
ist für den Umfang der ersten Ausbaustufe nicht vorgesehen.
Die drei externen Verträge für serverSync, Adapter und Mainframe sind im
Entwurf getrennt gesperrt und werden erst nach fachlicher Abnahme aktiviert.

Diese Verzeichnisstruktur ist ein Arbeitsentwurf im gemeinsamen Workspace. Im
Zielbetrieb werden `j517120/mtext-fi` und `j520730/mtext-actions` eigenständige
GitHub-Repositories. Weitere Ziel-Repositories sind `mtext-autonom`,
`mtext-by`, `mtext-lh`, `mtext-nw`, `mtext-os` und `mtext-sa`. Sie folgen demselben Muster,
nachdem ihre Bestandsdaten fachlich inventarisiert und freigegeben wurden. Vor
einer Aktivierung wird der Null-SHA gemeinsam in allen aufrufenden Workflows
durch den freigegebenen zentralen Commit-SHA ersetzt. Der
repositoryübergreifende Actions-Zugriff wird in GitHub Enterprise ausdrücklich
freigeschaltet und praktisch geprüft.

## 6. Git-, Promotion- und Workflowmodell

In SVN lagen unter einem Stufenbranch wie `Entwicklung` mehrere
Releaseverzeichnisse nebeneinander. In Git werden Releaselinie und Stufe in den
Branchnamen aufgenommen, beispielsweise `R260/Entwicklung`,
`R260/Abnahme` und `R260/Bereitstellung`. Diese Abweichung ist bewusst: Jede
aktive Linie erhält eine eigene Historie, einen eindeutigen Pull-Request-Pfad,
eigene Schutzregeln und einen unmissverständlichen Deploymentauslöser. Ein
gemeinsamer Stufenbranch mit Releaseordnern würde dagegen Änderungen mehrerer
Linien in einem Pull Request und zusätzliche fehleranfällige Pfadfilter
ermöglichen.

Eine Änderung beginnt in einem Branch wie
`feature/R260/12345-kurzbeschreibung`. Ein Pull Request nach
`R260/Entwicklung` validiert Inhalt, Konfiguration und Promotionsrichtung,
besitzt aber keine externen Seiteneffekte. Nach dem Merge wird der exakte
Merge-Commit automatisch zum M/Text-Entwicklungssystem der Linie verteilt.
Eine zusätzliche manuelle Environment-Freigabe oder ein fremdes Review ist
nicht erforderlich.

Die Promotion zur Abnahme erfolgt durch einen Pull Request von
`R260/Entwicklung` nach `R260/Abnahme`. Dessen Merge verteilt automatisch zum
zugehörigen Abnahmesystem. Für die Bereitstellung werden ausgewählte Commits in
einem UTC-datierten Branch wie `release/R260-20260715T143000Z` gesammelt und
per Pull Request nach `R260/Bereitstellung` übernommen.

Der Pull Request nach Bereitstellung validiert den integrierten Stand vor dem
Merge. Der Merge selbst erzeugt noch keine Lieferung. Ein Benutzer setzt
anschließend einen Tag wie `R260.101`; der Tag-Push startet den Releasebau.
`.100` erzeugt FULL, jede andere gültige dreistellige Endung ein kumulatives
DELTA gegen `.100`. Eine besondere GitHub-Tagschutzregel ist in der ersten
Ausbaustufe nicht vorgesehen.

Die Mandanten-Repositories erhalten keinen zusätzlichen `main`-Branch. Der
Default Branch zeigt auf den Entwicklungsbranch der aktuell führenden Linie,
zunächst `R261/Entwicklung`, und wird beim Linienwechsel manuell umgestellt.
Workflow- und Konfigurationsänderungen werden je aktiver Linie nach
`Rxxx/Entwicklung` eingebracht und normal weiterpromotet. Das vermeidet eine
Automation mit Schreibrechten auf mehrere geschützte Branches.

Die wiederverwendbaren Workflows sind nach Verantwortung getrennt. Der
Release-Workflow hält Paketbau und Mainframe-Übergabe als zwei Jobs in
derselben Datei; nur der Übergabejob bindet das Environment `Bereitstellung`.
Die Promotionsvalidierung läuft ausschließlich als Pull-Request-Gate. Sync und
Releasebau validieren die Konfiguration bei der tatsächlichen Verwendung
erneut. Kontrollierte manuelle Wiederholungen müssen denselben Commit
verwenden; vor einer erneuten M/Text-Verteilung wird geprüft, dass der Commit
im ausgewählten Stufenbranch enthalten ist.

Die Zielplattform ist GitHub Enterprise Server 3.20.4. Für den Transport
zwischen Build- und Übergabejob werden die von GitHub für GHES vorgesehenen
Node-20-v3-Artefakt-Actions verwendet. Ihre fest gepinnten Commit-SHAs und die
Runner-Kompatibilität werden vor Aktivierung auf der konkreten Instanz geprüft.

## 7. Konfigurationsmodell

Fachliche Mappings werden aus dem historischen Skript in versionierte und
validierbare Konfiguration überführt. Mandantenspezifische Angaben wie
Repository-Identität, Projekte, Paketcodes, Subsystem, Assignments und Level
liegen im jeweiligen Mandanten-Repository. Gemeinsame Angaben wie
Releaselinien, Stufenzuordnung, Adapterziele und Dateinamensregeln liegen in der
zentralen Automatisierung.

Aktiv sind `R261 -> en01`, `R270 -> en02` und `R260 -> en03`. Der Adapter wird
je technischer Linie getrennt für Entwicklung und Abnahme adressiert, etwa
über `en01e.ltoma.intern` und `en01a.ltoma.intern`. Der vollständige Endpunkt
endet auf `/vMtextAdapter/sync`; der Payload bleibt `MAN`/`INR`, benötigt
zunächst keine Authentifizierung und akzeptiert jeden 2xx-Status als
unmittelbaren Erfolg. Der serverSync-Sharepfad ist noch auf dem Zielrunner zu
bestätigen.

Die Konfiguration wird vor jeder externen Aktion geprüft. Unbekannte Schlüssel,
Mandanten, Releaselinien oder Zielumgebungen werden nicht durch unsichere
Defaults ersetzt, sondern abgelehnt. Insbesondere wurde der historische
Fallback auf FI-Werte bewusst nicht in den Entwurf übernommen.

Repository und Mandant müssen zueinander passen. Projekt- und Paketcodes sowie
Branch- und Umgebungszuordnungen müssen eindeutig sein. Geheimnisse,
Passwörter und geheime URLs bleiben außerhalb der versionierten Dateien und
werden ausschließlich über geschützte GitHub Environments bereitgestellt.

FI ist der Master für die unfragmentierten Basisprojekte. `mtext-autonom` ist
der Master für `LOMS_Autonom`. Die übrigen Mandanten enthalten Fragmentprojekte
mit Mandantenkürzel in eckigen Klammern. Repositoryinhalte und
Delivery-Allowlist sind dabei verschieden: Testdatenprojekte werden migriert,
aber wie bisher nicht synchronisiert oder paketiert. Noch nicht vollständig
inventarisierte Mandanten werden nicht durch abgeleitete Beispielwerte als
produktiv freigegeben.

## 8. Git- und Release-Modell

Der Commit-SHA ist die technische Identität jedes Laufs. Branches und Tags sind
Auslöser und fachliche Namen, werden aber vor einer Verarbeitung immer auf
einen unveränderlichen Commit aufgelöst. Dadurch bleibt nachvollziehbar,
welcher Quellstand verteilt oder paketiert wurde.

Ein Tag wie `R261.100` erzeugt eine vollständige Lieferung des getaggten
Stands. Ein späterer Tag derselben Linie, etwa `R261.108`, erzeugt ein
kumulatives Delta zwischen `R261.100` und `R261.108`. Es enthält alle seit dem
Vollrelease neu angelegten oder geänderten Dateien sowie die vollständige
Löschliste. Ein ausgelassenes früheres Delta unterbricht damit nicht die
Lieferkette.

Der direkte Vergleich zum vorherigen Release kann weiterhin als Information
ausgegeben werden, beeinflusst den Paketinhalt aber nicht. Diese Trennung wurde
während der Bestandsanalyse belegt und wird mit synthetisch erzeugten
Testständen abgesichert. Historische Lieferdateien werden nicht in der
Testsuite mitgeführt.

Paket, Manifest, Basis- und Ziel-SHA sowie Prüfsumme bilden zusammen das
eindeutige Releaseartefakt. Ein fehlgeschlagener Übergabelauf kann dieses
unveränderte Artefakt erneut verwenden, ohne es neu zu bauen.
Das Manifest wird an beiden Seiten der Build-/Publish-Grenze vollständig gegen
dasselbe versionierte Schema geprüft.

Für jede aktive Linie werden mindestens der `.100`-Tag und alle späteren Tags
übernommen. Der SVN-Name `R260.101_MText` wird bewusst zum Git-Tag
`R260.101` vereinfacht; `_MText` war ausschließlich Teil der SVN-Pfadkonvention.
Ältere Tags und möglichst umfassende Elementhistorie sind Nice-to-have.
Properties, Externals, Autorenidentitäten und große Dateien werden im
Migrationsprotokoll gesondert behandelt.

## 9. JCL als versioniertes Template

Die JCL ist nicht länger in Shell- oder Python-Code eingebettet, sondern liegt
als eigenständige, lesbare und reviewbare Template-Datei vor. Veränderung an
der Mainframe-Ansteuerung wird damit als normale versionierte Änderung sichtbar
und kann unabhängig von der Übertragungslogik geprüft werden.

Das Template verwendet fünf klar benannte Werte: ISPW-Instanz, Level,
Subsystem, Member und Assignment. Diese Werte stammen ausschließlich aus
validierter Konfiguration und dem geprüften Releasekontext. Ein strikter
Renderer lehnt fehlende, unbekannte oder syntaktisch unzulässige Werte ab und
stellt sicher, dass keine Platzhalter in der fertigen JCL verbleiben.

Die gerenderte JCL existiert nur für die Dauer eines Laufs und enthält keine
Credentials. Das FTP-/JES-Verfahren erhält eine fertige JCL-Datei und ist nicht
für deren Erzeugung verantwortlich. Die bestehenden Mainframe-Werte und das
JCL-Verfahren bleiben unverändert. Die technische Übergabe wartet im GitHub
Environment `Bereitstellung` auf eine manuelle Freigabe und verwendet das zuvor
erstellte unveränderte Artefakt.

## 10. Status- und Fehlermodell der ersten Ausbaustufe

Das Statusmodell benennt nur Ergebnisse, die der jeweilige Prozess tatsächlich
belegen kann. Eine fehlgeschlagene Konfiguration oder Quellauflösung endet vor
externen Seiteneffekten als `VALIDATION_FAILED` beziehungsweise
`SOURCE_FAILED`. Fehler bei Paket und Manifest werden als `PACKAGE_FAILED`
gemeldet. Ein vollständig erstelltes und geprüftes Artefakt erreicht
`ARTIFACT_READY`.

Bei der M/Text-Verteilung wird zwischen fehlgeschlagener Ressourcenübergabe
(`RESOURCE_TRANSFER_FAILED`), vom synchronen Adaptervertrag akzeptierter
Anfrage (`ADAPTER_ACCEPTED`) und Transport- oder HTTP-Fehler
(`ADAPTER_FAILED`) unterschieden. Ein HTTP-Fehler, insbesondere der historisch
bekannte Status 400, darf nicht als erfolgreicher Lauf enden.

Auf der Mainframe-Strecke bedeutet `MAINFRAME_SUBMITTED`, dass Paket und JCL
gemäß dem vorhandenen unmittelbaren FTP-/JES-Vertrag technisch übergeben
wurden. Der Status behauptet ausdrücklich keinen fachlich erfolgreichen
Abschluss des Mainframe-Jobs. Unmittelbare Übergabefehler werden als
`MAINFRAME_TRANSFER_FAILED` gemeldet.

Optionale Benachrichtigungen bleiben vom fachlichen Ergebnis getrennt. Ein
`NOTIFICATION_FAILED` erzeugt eine Warnung, verändert aber nicht rückwirkend
den bereits feststehenden Lieferstatus. Status-Polling für M/Text oder
Mainframe bleibt außerhalb dieser ersten Ausbaustufe.
Zunächst genügen die GitHub-Benachrichtigungen; E-Mail-Benachrichtigungen sind
eine spätere Erweiterung. Mainframe-Übergaben werden je Mandant serialisiert,
dürfen aber für verschiedene Mandanten parallel laufen.
