# hAI.LANSCAN · v1.0

Dein LAN. Dein Index. Eigener TCP-Scanner mit mobiler Weboberfläche, SQLite-Inventar, Passwortschutz und Administration. MIT-Lizenz, ohne Nmap-Abhängigkeit.

[Projektseite](https://jbkunama1.github.io/hAI.LANSCAN/) · [Build-Verlauf](https://github.com/jbkunama1/hAI.LANSCAN/actions) · [Portainer-Compose](compose.portainer.yaml) · [ENV-Vorlage](.env.example)

Die Projektseiten-Adresse funktioniert erst nach Aktivierung von GitHub Pages. Ein vorhandener Workflow bedeutet noch keinen erfolgreichen Build oder verfügbares Image.

## Funktionen
- Einzelhost, Hostname, mehrere IPs, IPv4-Range oder CIDR; maximal 256 Hosts.
- Alle TCP-Ports oder eigene Portauswahl, ohne Ping-Voraussetzung.
- Offene Ports sofort speichern; optional GET / per HTTP/HTTPS mit Seitentitel, Status, Server-Header und begrenztem HTML.
- Scan stoppen; bereits gespeicherte Funde bleiben erhalten.
- Namen, Tags, Notizen und Hostdetails, numerische IP-Sortierung.
- Änderungen zwischen vollständig abgeschlossenen passenden Scans; Filter für Webdienste, neue Funde und ältere Einträge.
- CSV/JSON, Scanverlauf, Admin-Einstellungen und Ocean-/Dark-/Light-Theme.
- Passwortwechsel im Adminbereich, Session-Invalidierung, CSRF, CSP und Healthcheck.
- Build-/Test-Workflow und anschließende Veröffentlichung für linux/amd64 und linux/arm64.

Keine Zeitpläne in v1.0; automatische Indexierung ist für frühestens v1.1 vorgesehen. Kein UDP/IPv6, keine Exploits und keine verifizierte Banner-/Versionserkennung.

## Portainer: Installation Schritt für Schritt

Diese Anleitung ist für Docker Standalone. Auf dem vorgesehenen Host 192.168.178.1 müssen Docker und ein erreichbares Portainer-Environment vorhanden sein. Es wird nichts automatisch auf diesem Host installiert.

### 1. Build und Image prüfen

Im [Actions-Verlauf](https://github.com/jbkunama1/hAI.LANSCAN/actions) muss der gewünschte Commit erfolgreich getestet und der Job `publish` abgeschlossen sein. Erwartetes Image:

```text
ghcr.io/jbkunama1/hai.lanscan:latest
```

Das GHCR-Paket hat eigene Sichtbarkeitseinstellungen. Für anonymes Pull muss es öffentlich sein; andernfalls eine authentifizierte GHCR-Registry in Portainer verwenden. Keine Tokens in öffentliche YAML-Dateien schreiben.

### 2. Stack anlegen

1. In Portainer das richtige Docker-Environment wählen.
2. Stacks → Add stack öffnen.
3. Stackname `hai-lanscan` vergeben.
4. Web editor wählen und den folgenden Stack einfügen. Er entspricht `compose.portainer.yaml` und benötigt keinen lokalen Build-Kontext.

```yaml
services:
  lanscan:
    image: ghcr.io/jbkunama1/hai.lanscan:${LANSCAN_VERSION:-latest}
    container_name: hai-lanscan
    restart: unless-stopped
    ports:
      - "${LANSCAN_PORT:-8088}:8080"
    environment:
      ADMIN_PASSWORD: ${ADMIN_PASSWORD:?Set a unique ADMIN_PASSWORD}
      SECRET_KEY: ${SECRET_KEY:?Set a random SECRET_KEY}
      ALLOWED_NETWORKS: ${ALLOWED_NETWORKS:-192.168.178.0/24}
      COOKIE_SECURE: ${COOKIE_SECURE:-false}
      TRUSTED_HOSTS: ${TRUSTED_HOSTS:-}
    volumes:
      - lanscan-data:/data
    cap_drop: [ALL]
    security_opt: ["no-new-privileges:true"]
    stop_grace_period: 15s
volumes:
  lanscan-data:
    name: hai-lanscan-data
```

### 3. Environment variables setzen

Unterhalb des Editors die Variablen einzeln hinzufügen oder eine eigene lokale ENV-Datei über Load variables from .env file importieren. In Portainers einzelnen Eingabefeldern Werte ohne umschließende Anführungszeichen eintragen.

| Variable | Pflicht / Standard | Erklärung |
| --- | --- | --- |
| `ADMIN_PASSWORD` | Pflicht, mindestens 12 Zeichen | Eigenes Initialpasswort für den ersten Start. Unveränderte `replace-with...`-Beispiele werden abgelehnt. |
| `SECRET_KEY` | Pflicht, mindestens 32 Zeichen | Zufälliger geheimer Schlüssel zur Signierung von Sessions. Nicht das Login-Passwort. Konstant halten; Wechsel meldet bestehende Sessions ab. |
| `ALLOWED_NETWORKS` | Standard `192.168.178.0/24` | Erlaubte IPv4-Zielnetze für Scans, kommagetrennt. KEINE Zugriffsbeschränkung für Browser-Clients. |
| `LANSCAN_PORT` | Standard `8088` | Freier Port auf dem Docker-Host. Container-intern bleibt es 8080. |
| `LANSCAN_VERSION` | Standard `latest` | Image-Tag. Für reproduzierbare Updates einen tatsächlich veröffentlichten `sha-...`-Tag aus dem Paket verwenden. Eine Versionsnummer im UI erzeugt noch keinen Registry-Tag. |
| `COOKIE_SECURE` | Standard `false` | `false` beim direkten HTTP-Zugriff. `true` bei Browser-Zugriff über HTTPS. Aktiviert kein HTTPS, sondern beschränkt Session-Cookies auf HTTPS. |
| `TRUSTED_HOSTS` | Optional, leer | Erlaubte HTTP-Hostnamen/IPs ohne Protokoll oder Port, kommagetrennt. Leer = keine zusätzliche Host-Header-Allowlist. Begrenzt weder Scan-Ziele noch Client-IP-Adressen. |

`LANSCAN_PORT` und `LANSCAN_VERSION` werden von Compose ausgewertet. Die anderen Werte werden ausdrücklich an den Container übergeben. Eine Portainer-Variable wird nicht allein durch das Anlegen automatisch zur Container-Variable.

Session-Schlüssel zum Beispiel auf deinem Rechner erzeugen:

```sh
openssl rand -hex 32
```

Das ergibt 64 Hex-Zeichen. Den erzeugten Wert lokal in `SECRET_KEY` eintragen, nicht ins Repository oder in öffentliche Logs.

Für die erste Installation im LAN:
- `ADMIN_PASSWORD`: selbst vergeben.
- `SECRET_KEY`: zufällig erzeugen.
- `ALLOWED_NETWORKS`: `192.168.178.0/24`.
- `LANSCAN_PORT`: `8088`.
- `LANSCAN_VERSION`: `latest`, sofern erfolgreich veröffentlicht.
- `COOKIE_SECURE`: `false` für direkten HTTP-Zugriff.
- `TRUSTED_HOSTS`: zunächst leer lassen; später beispielsweise `192.168.178.1,localhost,127.0.0.1` setzen. Bei einer Allowlist muss `127.0.0.1` für den internen Healthcheck enthalten sein; einen Reverse-Proxy-Hostnamen zusätzlich aufnehmen.

### 4. Deploy und erster Scan

Deploy the stack auswählen, danach Containerstatus, Healthcheck und Logs prüfen. Browser:

```text
http://192.168.178.1:8088
```

Mit dem Initialpasswort anmelden. Zum ersten Test unter Scan einen bekannten Host mit `22,80,443,8080,8443` prüfen. Danach bei Bedarf `1-65535`. Die HTTP-Abfrage lässt sich im Adminbereich deaktivieren. Namen, Tags und Notizen findest du im Index unter Details & Notizen.

Alternativ zu Web editor kann Portainer aus diesem öffentlichen Git-Repository deployen: Repository `https://github.com/jbkunama1/hAI.LANSCAN`, Branch main (bei Bedarf als `refs/heads/main`), Compose path `compose.portainer.yaml`. ENV-Werte weiterhin in Portainer setzen. Änderungen an der Git-Compose-Datei erfolgen im Repository.

## Was wird wo konfiguriert?

| Ort | Einstellungen |
| --- | --- |
| Portainer / Container-ENV | Erlaubte Netze, Session-Schlüssel, Cookie-/Host-Einstellungen; beim ersten Start das Initialpasswort |
| Compose / Portainer-Variablen | Host-Port und gewünschtes Image-Tag |
| Admin-Weboberfläche / SQLite | Standardziele, Ports, Timeout, Parallelität, HTTP-Abfrage, Theme und Passwortwechsel |
| Hostdetails / SQLite | Name, Tags und Notizen |

`ADMIN_PASSWORD` initialisiert den in SQLite gespeicherten Hash nur beim ersten Start. Danach gilt das DB-Passwort, auch wenn ENV später geändert wird. Passwort im Adminbereich ändern; dabei werden bestehende Sessions ungültig. Aktuell gibt es keinen dokumentierten Passwort-Reset per ENV. Nicht das Volume löschen, um das Passwort zu ändern: Das würde auch deinen Index entfernen.

## Updates und vorhandene Daten

1. Backup erstellen und tatsächlichen Volume-Namen prüfen.
2. Gewünschten erfolgreichen Image-Tag auswählen oder `latest` erneut pullen.
3. Stack in Portainer aktualisieren und erneutes Image-Pullen aktivieren, sofern angeboten. Nur ein Container-Neustart lädt kein neues Image.
4. Logs, Healthcheck, Anmeldung und Inventar kontrollieren.

Der neue feste Volume-Name ist `hai-lanscan-data`. Beim allerersten Projektstand konnte das Volume `<projekt>_lanscan-data` heißen. Vor einem Upgrade den Volume-Namen im Stack auf den tatsächlichen bisherigen Namen setzen oder bei gestopptem Container migrieren. Sonst erscheint ein leerer Index, obwohl die alten Daten noch in einem anderen Volume liegen. Zusatz-Tabellen werden automatisch angelegt; alte Scans ohne gespeicherten Zielumfang sind nicht rückwirkend vollständig vergleichbar. Ein Rollback des Images macht DB-Änderungen nicht rückgängig; Sicherung behalten.

## Lokal bauen, ohne Registry

```sh
git clone https://github.com/jbkunama1/hAI.LANSCAN.git
cd hAI.LANSCAN
cp .env.example .env
joe .env
# Passwort und Secret durch eigene Werte ersetzen.
docker compose up -d --build
```

Aktiver Server ist `core.py`. `app.py`, ältere Templates und `tests/test_app.py` sind Legacy-Dateien und werden nicht für den v1-Container verwendet.

## Index richtig lesen

- `open`: beim letzten vollständig abgeschlossenen passenden Scan offen.
- `not_found`: bei passender Prüfung nicht erneut gefunden; kann auch durch Timeout, Filter oder ausgeschalteten Host entstehen, bedeutet NICHT sicher geschlossen.
- `not_checked`: letzter Lauf enthielt die IP oder diesen Port nicht.
- `observed_partial`: positiver Fund im jüngsten noch laufenden, abgebrochenen oder fehlerhaften Lauf.
- `historical`: kein vollständiger passender Vergleich verfügbar.

Änderungen werden zwischen erfolgreich abgeschlossenen Scans verglichen, die dieselbe IP und denselben Port enthalten. Ein Webport-Scan darf SSH nicht als verschwunden markieren. Filter Neu bedeutet bisher in genau einem Scan gefunden, nicht zwingend heute entdeckt. Namen beziehen sich auf IPs; DHCP-Wechsel werden nicht als stabile Geräteidentität erkannt. HTTP-Daten stammen vom letzten erfolgreichen Webabruf; `last_seen` bezieht sich auf TCP, nicht auf die Aktualität des HTML.

## Backup

Container stoppen und das komplette Volume konsistent sichern, gegebenenfalls einschließlich WAL/SHM. Beispiel auf dem Docker-Host, tatsächlichen Volume-Namen prüfen:

```sh
docker stop hai-lanscan
mkdir -p backups
docker run --rm -v hai-lanscan-data:/data:ro -v "$PWD/backups:/backup" alpine:3.21 tar czf /backup/lanscan-data.tgz -C /data .
docker start hai-lanscan
```

Helper-Image gegebenenfalls vorab laden. Ein vorhandenes gleichnamiges Archiv wird überschrieben; Sicherungen versioniert und geschützt außerhalb des Hosts aufbewahren. Restore nur bei gestopptem Container in das richtige leere Volume; Eigentümer UID/GID 10001:10001 prüfen. Nicht über eine laufende Datenbank kopieren. `docker compose down -v` löscht das Volume!

## Troubleshooting

| Problem | Prüfen |
| --- | --- |
| `manifest unknown` / Image fehlt | `publish` erfolgreich? Tag wirklich vorhanden? |
| `unauthorized` / `denied` beim Pull | GHCR-Paket öffentlich oder passende Portainer-Registry-Anmeldung? |
| Container beendet sich beim Start | Eigenes Passwort >=12 Zeichen und Secret >=32 Zeichen; Logs lesen; Volume-Berechtigungen prüfen. |
| Anmeldung springt zurück | `COOKIE_SECURE=true` bei HTTP? Passwort im DB-Stand statt ENV? Cookies/Session und erlaubte Hosts prüfen. |
| Healthcheck schlägt nach Host-Allowlist fehl | `127.0.0.1` in `TRUSTED_HOSTS` aufnehmen. |
| Ziel wird abgelehnt | IP nach DNS-Auflösung innerhalb von `ALLOWED_NETWORKS`? |
| Keine Funde | Routen/Firewall vom Docker-Host zum Zielnetz, Portauswahl und Timeout prüfen. |
| Index nach Update leer | Wurde versehentlich ein anderes Volume eingebunden? |
| Port bereits belegt | `LANSCAN_PORT` ändern und Stack neu deployen. |

## Sicherheit und Grenzen

Nur eigene oder autorisiert verwaltete Netze prüfen. Aktive Probes können empfindliche IoT-Geräte stören. App nicht öffentlich exponieren. Für verschlüsselte Anmeldung einen HTTPS-Reverse-Proxy verwenden und `COOKIE_SECURE=true` setzen; HTTP schützt nicht vor Mitlesen im Netzwerk.

Nur TCP/IPv4, ein Scan gleichzeitig, ein Gunicorn-Worker. Vollscans ganzer Netze können Stunden dauern. Kein automatisches Fortsetzen nach Neustart; bereits gespeicherte Funde bleiben. Oberfläche lädt den gesamten Index; keine Pagination oder automatische Historienbereinigung.

HTTP: GET /, höchstens 64 KiB gesamte Antwort, je Versuch 2,5 Sekunden, keine Redirects, Unterseiten oder JavaScript-Ausführung; vereinfachte UTF-8-Auswertung. Selbstsignierte TLS-Zertifikate werden akzeptiert, Identität nicht geprüft. HTML wird gespeichert, aber nicht als HTML gerendert. Portnamen sind lokale Zuordnungen, keine verifizierte Diensterkennung. DB und Backups können vertrauliche Daten enthalten.

Login-Limit global pro Prozess: zehn Versuche pro fünf Minuten, auch gültige Versuche zählen. `/healthz` ist öffentlich; Inventar, API und statische App-Dateien erfordern Anmeldung. Login-CSS kann dadurch vor der Anmeldung nicht geladen werden; das Login bleibt funktional, ist im aktuellen Stand aber möglicherweise ungestylt. Keine ungeschützte API für Automatisierung.

## CI, Tests und Veröffentlichung

Push auf main → Backend-Tests, Python-/JS-Syntax, Compose-Prüfung, Docker-Build und Chromium-Smoke-Tests bei Handy-/Desktop-Auflösung → bei Erfolg Multiarch-Build und GHCR-Push. ARM64 wird gebaut, nicht auf ARM-Hardware per Browser getestet. CI scannt kein privates LAN; Scanabläufe werden mit Mocks geprüft. Echte LAN-/TLS-Tests bleiben erforderlich. Den tatsächlichen Laufstatus unter Actions prüfen, nicht aus dieser README ableiten.

```sh
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_core.py' -v
node --check static/v1.js
```

## GitHub Pages

Settings → Pages → Deploy from a branch → main → /docs → Save. `docs/index.html` ist nur die öffentliche Projekt- und Installationsseite. Scanner, Anmeldung und SQLite laufen ausschließlich im eigenen Container. Pages wird durch einen Commit nicht automatisch aktiviert.

## Offizielle Referenzen

- [Portainer: Stack anlegen](https://docs.portainer.io/user/docker/stacks/add)
- [Portainer: Stack ändern](https://docs.portainer.io/user/docker/stacks/edit)
- [GitHub: Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

## Lizenz

[MIT](LICENSE) · Copyright 2026 Daniel Lienhard.
