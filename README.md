# EMS Core – Home Assistant Integration

Custom Component für Home Assistant, die sich mit einer [EMS-Core](https://github.com/JanFirlus/ems-stack)-Instanz
verbindet und deren Werte als native HA-Entities bereitstellt: Gerätestatus,
Energiefluss (PV/Netz/Haus/Akku) und §14a-Lastmanagement-Status.

**Umfang v0.1: reines Monitoring.** Es wird nichts von HA aus am EMS gesteuert
(kein Setzen von Wallbox-Strom, Akku-Notladung, Wärmepumpen-Kontakten o.ä.) –
das ist bewusst nicht Teil dieser Version.

## Installation

### Über HACS (custom repository)

1. HACS → Integrationen → ⋮ → Benutzerdefinierte Repositories.
2. Dieses Repo als "Integration" hinzufügen.
3. "EMS Core" installieren, Home Assistant neu starten.

### Manuell

`custom_components/ems_core/` in das `config/custom_components/`-Verzeichnis
deiner Home-Assistant-Instanz kopieren, danach Home Assistant neu starten.

## Einrichtung

Einstellungen → Geräte & Dienste → Integration hinzufügen → "EMS Core" suchen.

Benötigt:
- **EMS-Core-URL**, z.B. `http://192.168.10.7:8090` (ohne `/docs`, nur die Basis-URL)
- **E-Mail** + **Passwort** eines EMS-Users (Admin-Rechte sind nicht nötig, ein
  normaler `role: user`-Account reicht für alle Lesezugriffe)

## Entities

- Pro EMS-Gerät ein eigenes HA-Gerät mit:
  - Hauptwert-Sensor (Leistung/SOC/Text, je nachdem was der Adapter liefert;
    alle übrigen Rohwerte als Attribute)
  - Online/Offline (`binary_sensor`)
  - bei Akkus zusätzlich eine Voll/Leer-Schätzung
- Unter einem "EMS Core"-Sammel-Gerät: PV-Erzeugung, Netzbezug, Netzeinspeisung,
  Hausverbrauch, Verbraucher, Akku-Leistung, Akku-SOC, §14a-Limit/Verfügbar/
  Grundlast-Reserve, §14a aktiv (`binary_sensor`)

Poll-Intervall: 30s (fest, nicht konfigurierbar in v0.1).

## Bekannte Einschränkungen

- Neue Geräte, die im EMS **nach** dem Einrichten dieser Integration angelegt
  werden, tauchen erst nach einem Neuladen der Integration
  (Einstellungen → Geräte & Dienste → EMS Core → Neu laden) auf – kein
  automatisches Nachziehen neuer Entities zur Laufzeit.
- Das EMS-Login-Token läuft nach 30 Minuten ab (Server-Default); die
  Integration loggt sich bei Bedarf automatisch neu ein, das ist normal und
  braucht kein manuelles Eingreifen.
