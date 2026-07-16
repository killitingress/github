# Dokumentationsübersicht

**Stand:** 15. Juli 2026

Diese Seite ist der Einstieg in die Dokumentation für die Ablösung von
Jenkins/SVN durch GitHub Actions/Git. Der lokale Stand ist ein gegen externe
Ausführung gesperrter Implementierungsentwurf; offene Aktivierungs- und
Cutover-Arbeiten sind ausdrücklich als solche dokumentiert.

## Für Fachanwender und Release-Verantwortliche

- [Benutzeranleitung](./confluence/Benutzeranleitung.md): Änderungen über
  Entwicklung und Abnahme bis zur Bereitstellung führen, Release-Tags setzen,
  Läufe wiederholen und Status auswerten.
- [Soll-Grafik GitHub Actions/Git](../Architektur_Soll_GitHub_Actions_Git.drawio):
  editierbarer End-to-End-Ablauf für Entwicklung, Abnahme, Bereitstellung,
  FULL/DELTA und Mainframe-Übergabe.

## Für Architektur, Betrieb und Migration

- [Zielbild GitHub Actions/Git](./confluence/Zielbild_GitHub_Actions_Git.md):
  fachliches und technisches Zielbild in Confluence-geeigneter Form.
- [Nächste Schritte](./confluence/Naechste_Schritte.md): verbindliche offene,
  gesperrte und bereits entschiedene Tätigkeiten.
- [Technisches Handoff](../Handoff_Jenkins_SVN_zu_GitHub_Actions.md):
  ausführliche Herleitung aus dem Altsystem, Entscheidungen,
  Akzeptanzkriterien und Implementierungsstand.
- [Ist-Grafik Jenkins/SVN](../Architektur_Ist_Jenkins_SVN.drawio): editierbare
  Referenz des abzulösenden Ablaufs.

## Repository-spezifische Dokumentation

- [Zentrale Automatisierung](../mtext-actions/README.md): Workflows, CLI,
  Konfiguration, Runner, Sicherheitsriegel und Tests.
- [Repräsentatives Mandanten-Repository](../mtext-fi/README.md):
  Ressourcenstruktur und fachlicher Branch-/Releasefluss für FI.
- [Mandanten-Workflowvertrag](../mtext-fi/.github/workflows/README.md): Trigger,
  Inputs, GitHub-Einstellungen und Aktivierung der dünnen Workflows.

## Verbindlichkeit und Pflege

Bei Widersprüchen gilt die ausführbare Konfiguration im aktuellen Stand als
technischer Ist-Vertrag. Fachliche Zielentscheidungen und noch nicht
ausführbare Betriebsannahmen werden im Zielbild beziehungsweise unter
„Nächste Schritte“ geführt. Änderungen an Branches, Releaselinien, Workflow-
Inputs oder externen Verträgen müssen zusammen mit der Benutzeranleitung und
der Soll-Grafik aktualisiert werden.
