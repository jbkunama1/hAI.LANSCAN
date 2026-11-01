# hAI.LANSCAN

Eigener, schlanker LAN-TCP-Scanner mit Mobile-first-Weboberfläche und dauerhaftem SQLite-Index. MIT-Lizenz. Kein Nmap, kein fremdes Scanner-Frontend.

## Funktionen im ersten Stand
- Einzelhost, Hostname, mehrere Ziele, IPv4-Range und CIDR, maximal 256 Hosts
- Alle TCP-Ports oder eigene Portauswahl, parallele Verbindungsprüfung ohne Ping-Voraussetzung
- HTTP/HTTPS-Abfrage von /: Titel, Status, Server und begrenzter HTML-Body
- SQLite-Inventar, erster/letzter Fund und Scan-Historie
- Mobile Host-Karten, Suche, CSV- und JSON-Ausgabe
- Administrator-Anmeldung, CSRF-Schutz, Session, begrenzte Login-Versuche
- Ocean-, Dark- und Light-Theme
- Admin: Standardziele, Ports, Timeout, Parallelität, HTTP-Abfrage und Theme

Noch nicht enthalten: Scheduler, Passwortwechsel im UI, Tags/Notizen, IPv6, UDP, Banner-/Versionserkennung, Scan-Abbruch und Mehrbenutzerrollen. Dauerbetrieb des Containers ist möglich, Scans werden vorerst manuell ausgelöst.

## Start auf dem vorgesehenen Host 192.168.178.1
Voraussetzung: Dieser Host kann tatsächlich Docker ausführen; die Adresse allein bestätigt das nicht. Keine Installation auf einem Router voraussetzen.

```sh
git clone https://github.com/jbkunama1/hAI.LANSCAN.git
cd hAI.LANSCAN
cp .env.example .env
# .env mit joe bearbeiten: eigenes langes ADMIN_PASSWORD und zufälligen SECRET_KEY setzen
# Beispiel für einen Secret-Key: openssl rand -hex 32
docker compose up -d --build
```

Browser: http://192.168.178.1:8088

```sh
docker compose logs -f
docker compose down
```

SQLite bleibt im benannten Volume erhalten. `docker compose down -v` löscht die Daten! Port 8088 muss frei sein. Für Portainer müssen Dockerfile und Dateien als Build-Kontext verfügbar sein; Compose allein reicht nicht. Alternativ das in CI geprüfte Dockerfile auf dem Host bauen. Dieser erste Workflow veröffentlicht noch kein Registry-Image.

## Sicherheit
Nur eigene/autorisiert verwaltete Netze scannen. Kein Exploit- oder Passwortscan. TCP- und HTTP-Probes erzeugen echte Verbindungen, auch zu empfindlichen IoT-Geräten. HTTP-Abfrage bei Bedarf abschalten. ALLOWED_NETWORKS in .env begrenzt Ziele serverseitig, Standard 192.168.178.0/24. DNS wird vor dem Scan aufgelöst und jede IP geprüft.

Nicht öffentlich exponieren. Für verschlüsselte Anmeldung HTTPS über einen passenden Reverse Proxy verwenden und COOKIE_SECURE=true setzen. Bei direktem HTTP schützt die Anmeldung nicht vor Mitlesen im Netzwerk. Passwort und Secret ausschließlich lokal setzen, niemals committen. Passwortwechsel erfolgt in .env mit Container-Neuerstellung; SECRET_KEY-Wechsel meldet bestehende Sessions ab. Login-Limit gilt global pro Prozess: zehn Versuche in fünf Minuten, auch gültige Versuche zählen. Bei vielen Nutzern ist ein externer Auth-Dienst sinnvoll.

## Was die Ergebnisse bedeuten
Portnamen stammen aus der lokalen Service-Tabelle, keine verifizierte Diensterkennung. Nur erfolgreicher TCP-Verbindungsaufbau wird erfasst. Closed/filtered/offline werden nicht unterschieden. Kurze Timeouts können Hosts/Ports übersehen. Historische Funde bleiben stehen: last_seen ist keine Garantie aktueller Erreichbarkeit. DHCP-Wechsel werden nicht als stabile Geräteidentität verfolgt.

Für jeden offenen Port werden optional HTTP und HTTPS versucht, je maximal 2,5 Sekunden. Nur /, keine Redirects, kein JavaScript, keine Unterseiten. Antwortlimit 64 KiB inklusive Header; UTF-8 mit Ersatzzeichen, keine vollständige Browser-/Kompressions-/Charset-Unterstützung. Selbstsignierte TLS-Zertifikate werden akzeptiert, Identität nicht verifiziert. HTML liegt nur in SQLite und wird nicht im Browser gerendert. Datenbank/Backups können vertrauliche Informationen enthalten.

Ein Scan gleichzeitig; alle TCP-Ports in einem /24 können Stunden dauern. Ein Container-Neustart unterbricht den Scan; vorhandene Funde bleiben erhalten, der Lauf wird als interrupted markiert. Keine Wiederaufnahme. Nur ein Gunicorn-Worker erlaubt, da Scan-Sperre und Status pro Prozess verwaltet werden.

## Daten / API
SQLite: /data/index.sqlite
- services: letzter Fund je IP+Port, HTML, HTTP-Daten, first_seen, last_seen
- scans: Läufe und Fehler
- observations: offene Ports je Lauf, keine vollständigen HTML-Snapshots
- settings: Admin-Einstellungen

GET /api/services, GET /api/status, GET /api/scans und GET /api/export.csv erfordern Anmeldung. POST /api/scan und POST /api/settings benötigen zusätzlich X-CSRF-Token aus der angemeldeten Session. Keine ungeschützte Automatisierungs-API.

## GitHub Pages
Die öffentliche Projektseite liegt unter docs/index.html. Unter Settings → Pages die Quelle 'Deploy from a branch', Branch main und Ordner /docs wählen. Sie ist rein statisch: weder Scanner noch LAN-Daten oder Zugangsdaten werden dort veröffentlicht. Pages ist durch den Commit nicht automatisch aktiviert.

## Build und Tests
GitHub Actions führt Syntaxprüfung, Unit-Tests und Docker-Build durch. Es findet kein Scan des eigenen LANs auf GitHub statt. Der tatsächliche erste Workflow-Status muss nach dem Push kontrolliert werden; diese README behauptet keinen erfolgreichen Build. HTTP-Sonderfälle, Browserdarstellung und echter LAN-Betrieb benötigen einen lokalen Funktionstest.
