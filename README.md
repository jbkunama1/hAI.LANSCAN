# hAI.LANSCAN · v1.0

Eigener LAN-TCP-Scanner, Mobile-first-Oberfläche und persistenter SQLite-Index. MIT-Lizenz, keine Nmap-Abhängigkeit. Aktiver Server: `core.py` (die älteren Dateien `app.py` und Templates bleiben nur als Legacy-Stand im Repository).

## Enthalten
- IPv4-Host, Hostname, Range und CIDR; maximal 256 Hosts, alle TCP-Ports oder eigene Auswahl
- Sofortiges Speichern offener Ports vor optionaler HTTP-/HTTPS-Abfrage
- Scan-Abbruch mit Erhalt bereits gespeicherter Funde; Fehler und Neustarts getrennt markiert
- Explizit geschlossene SQLite-Verbindungen, serialisierte Schreibzugriffe, garantierte Freigabe der Scan-Sperre
- Namen, Tags, Notizen und mobile Hostdetails; numerisch sortierte IPs
- Scope-bewusster Vergleich vollständiger Scans, neue/zurückgekehrte/fehlende Ports
- Filter für Webdienste, Änderungen und seit mindestens sieben Tagen nicht gesehene Funde
- Passwort-Anmeldung, Passwortwechsel im Adminbereich mit Session-Invalidierung, CSRF und CSP
- Light, Dark, Ocean; Standardziele, Ports, Timeout, Parallelität und HTTP-Probes konfigurierbar
- CSV/JSON-Export; Healthcheck; CI mit Backend-Tests, JavaScript-Prüfung und Browser-Smoke-Tests
- GHCR-Publishing nach bestandenen Tests, amd64 und arm64

Keine Zeitpläne in v1.0. Scheduler frühestens in v1.1. Kein UDP/IPv6, kein Exploit-/Passwortscan, keine echte Banner-/Versionserkennung.

## Lokal bauen
```sh
git clone https://github.com/jbkunama1/hAI.LANSCAN.git
cd hAI.LANSCAN
cp .env.example .env
joe .env
# Eigenes ADMIN_PASSWORD (mind. 12 Zeichen), zufälligen SECRET_KEY (mind. 32 Zeichen) setzen.
# Secret erzeugen: openssl rand -hex 32
docker compose up -d --build
```
Vorgesehener Host: 192.168.178.1, Oberfläche http://192.168.178.1:8088. Voraussetzung: Dort läuft Docker und Port 8088 ist frei. Das Repository installiert nichts automatisch auf diesem Host.

## Portainer / Registry
`compose.portainer.yaml` als Stack einfügen und Variablen in Portainer setzen. Es benötigt keinen lokalen Build-Kontext.
- ADMIN_PASSWORD: eigenes langes Initialpasswort
- SECRET_KEY: zufälliger Session-Schlüssel
- ALLOWED_NETWORKS: 192.168.178.0/24 oder explizit freigegebene Netze, kommagetrennt
- LANSCAN_PORT: 8088
- LANSCAN_VERSION: latest oder ein veröffentlichter sha-Tag für reproduzierbare Updates
- COOKIE_SECURE: true nur bei HTTPS-Betrieb
- TRUSTED_HOSTS: optional erlaubte Hostnamen/IPs ohne Ports, kommagetrennt

Image: `ghcr.io/jbkunama1/hai.lanscan:latest`. Erst verwendbar, sobald der Publish-Job erfolgreich war. Ein öffentliches Repository garantiert nicht automatisch die öffentliche Sichtbarkeit des GHCR-Pakets: falls anonymes Pull fehlschlägt, Package Settings prüfen oder Portainer-Registry authentifizieren. Verfügbarkeit und CI-Erfolg werden nicht durch diese README behauptet.

## Persistenz / Upgrade
Volume heißt nun explizit `hai-lanscan-data`, DB liegt unter /data/index.sqlite. Vor einem Upgrade vom ersten Stand prüfen: dessen Compose-Volume kann `<projekt>_lanscan-data` heißen. Um vorhandene Daten zu behalten, den neuen Volume-Namen in BEIDEN Compose-Dateien auf den bisherigen tatsächlichen Namen ändern oder Daten bei gestopptem Container vollständig übertragen. Nicht versehentlich mit einem neuen leeren Volume starten. Zusatz-Tabellen werden automatisch angelegt; alte Scanläufe ohne gespeicherten Scope können nicht rückwirkend zuverlässig verglichen werden.

ADMIN_PASSWORD initialisiert nur beim ersten Start den in SQLite gespeicherten Passwort-Hash. Nach einem Passwortwechsel im UI gilt das DB-Passwort, nicht ein später geänderter Environment-Wert. SECRET_KEY-Wechsel meldet Sessions ab. Beispielwerte werden beim Start abgelehnt.

## Scan- und Index-Semantik
- Offene TCP-Verbindung wird sofort gespeichert. HTTP-Metadaten folgen nachgelagert innerhalb derselben Worker; keine zweite Scan-Queue.
- Abbruch beendet laufende Netzwerkaufgaben, kein Fortsetzen nach Neustart. Bereits gespeicherte Funde bleiben.
- Vergleich nur zwischen vollständig erfolgreich beendeten Scans, die dieselbe IP und denselben Port abdeckten. Abgebrochene oder fehlerhafte Scans erzeugen keine negativen Aussagen.
- `not_found` bedeutet keine erfolgreiche Verbindung, NICHT nachweislich geschlossen; Filter/Timeout/offline können die Ursache sein.
- `not_checked`: letzter Lauf enthielt die IP oder den Port nicht. `observed_partial`: positiver Fund eines noch laufenden/abgebrochenen/fehlerhaften Laufs. Weitere Vergleichsfelder beziehen sich weiterhin auf abgeschlossene passende Läufe.
- Filter 'Neu' bedeutet bisher in genau einem Scan gefunden; kein zeitlich begrenztes Ereignis. DHCP-Wechsel werden nicht als stabile Geräteidentität erkannt.
- HTTP-Daten sind der letzte erfolgreiche Webabruf, nicht zwingend aus dem letzten Scan. HTML und Metadaten bleiben bei fehlgeschlagener erneuter HTTP-Abfrage erhalten; last_seen bezieht sich auf TCP.
- Portname ist eine lokale Zuordnung, keine verifizierte Diensterkennung.
- Ganznetz-Vollscans können Stunden dauern. Die Oberfläche lädt den gesamten Index; Pagination und Historiensäuberung sind noch nicht enthalten.

## Sicherheit und Grenzen
Nur eigene/autorisiert verwaltete Systeme. Aktive TCP-/HTTP-Probes können empfindliche Geräte stören. HTTP-Abfrage abschaltbar. Ziel-IP-Prüfung gegen ALLOWED_NETWORKS nach DNS-Auflösung. Nur TCP/IPv4. Ein Gunicorn-Worker (vier HTTP-Threads), ein Scan gleichzeitig. Status und Sperre sind pro Prozess.

HTTP-Abfrage: GET /, maximal 64 KiB gesamte Antwort, je Versuch 2,5 s, kein JavaScript, keine Redirects/Unterseiten, vereinfachte UTF-8-Auswertung. Selbstsignierte Zertifikate akzeptiert, keine Zertifikatsidentitätsprüfung. HTML wird nur gespeichert und nicht im Browser ausgeführt. DB und Backups können vertrauliche Informationen enthalten.

Nur vertrauenswürdiges LAN; für verschlüsselte Anmeldung HTTPS-Reverse-Proxy verwenden und COOKIE_SECURE=true setzen. Ohne HTTPS kann Netzwerkverkehr mitgelesen werden. Login-Limit global: zehn Versuche je fünf Minuten; gültige Versuche zählen ebenfalls. /healthz öffentlich, Inventar/API und statische App-Dateien erfordern Anmeldung. Kein ungeschützter Automatisierungs-Endpunkt.

## Backup / Restore
Für eine einfache konsistente Kopie Container stoppen und den kompletten Volume-Inhalt inklusive eventueller WAL-/SHM-Dateien sichern. Beispiel (lokaler Build-Stack):
```sh
docker compose stop lanscan
mkdir -p backups
# Helper-Image vorab laden, falls nötig. Backup-Verzeichnis ist der aktuelle Projektordner/backups.
docker run --rm -v hai-lanscan-data:/data:ro -v "$PWD/backups:/backup" alpine:3.21 tar czf /backup/lanscan-data.tgz -C /data .
docker compose start lanscan
```
Backups außerhalb des Hosts geschützt aufbewahren. Wiederherstellung: Container stoppen, Sicherung in das richtige, leere Volume entpacken, Eigentümer UID/GID 10001:10001 prüfen, Container starten. Nicht über eine laufende Datenbank kopieren. `docker compose down -v` löscht das Volume!

## Build und Tests
Actions: Backend-Tests, Python/JS-Syntax, Compose-Prüfung, Docker-Build, Login/Navigation/Theme in Chromium bei Handy-/Desktop-Auflösung. Danach Multiarch-Build und GHCR-Push. ARM64 wird gebaut, aber nicht mit Browser-Smoke-Test auf ARM-Hardware ausgeführt. CI scannt kein privates LAN; Netzverhalten wird mit Mocks getestet. Echte LAN-/TLS-/Fehlerfälle benötigen zusätzlich lokalen Test. Tests lokal:
```sh
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_core.py' -v
node --check static/v1.js
```
Legacy-Test `tests/test_app.py` gehört nicht zur aktiven v1-Suite.

## Pages
`docs/index.html` ist die statische öffentliche Projektseite. Settings → Pages → Deploy from a branch → main → /docs. Pages wird nicht automatisch aktiviert. Dort liegen keine LAN-Daten oder Login-Secrets. Die Projektseite kann noch den allgemeinen ersten Funktionsumfang beschreiben; maßgeblich für v1 ist diese README.
