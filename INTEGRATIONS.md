# Telegram und MCP

Erweiterung ohne Zeitpläne. Webapp, MCP und Telegram nutzen ein Image und dieselbe Scan-Engine über eine Bearer-geschützte API. Nur Webapp schreibt SQLite; Bot und MCP erhalten keinen Datenbank-Mount.

## Portainer
Nach erfolgreichem Build/Publish den aktualisierten compose.portainer.yaml verwenden, Image neu pullen und Stack neu deployen. Bestehendes Volume hai-lanscan-data beibehalten. highfishnetwork muss extern existieren. Niemand hat durch den GitHub-Commit deinen laufenden Host verändert.

Neue ENV in Portainer:
- MCP_TOKEN: eigener zufälliger Token, mindestens 24 Zeichen. Nicht SECRET_KEY oder Bot-Token wiederverwenden. Wird in Webapp, MCP und Bot identisch gesetzt. Beispiel-Erzeugung: openssl rand -hex 24.
- TELEGRAM_BOT_TOKEN: eigener Token von BotFather. Nicht committen oder in Chats/Logs teilen.
- TELEGRAM_ADMIN_IDS: numerische Telegram-User-IDs, kommagetrennt. Keine Benutzernamen und keine Gruppen-Chat-IDs. Nur private Chats dieser User werden akzeptiert; alle sind Administratoren.
- MCP_ALLOWED_HOSTS: erlaubte Host-Header für MCP, Standard 192.168.178.1:*,127.0.0.1:*,localhost:*,hai-lanscan-mcp:*. Bei anderer Host-IP oder Reverse Proxy entsprechend ergänzen. Das ist keine Client-IP-Allowlist.
- TRUSTED_HOSTS der Webapp: falls gesetzt, zusätzlich hai-lanscan und 127.0.0.1 erlauben, damit interne API und Healthcheck funktionieren.

Der Telegram-Dienst ist im Stack enthalten. Ohne gültige Bot-Variablen startet er nicht erfolgreich; für Betrieb ohne Telegram den Dienst telegram aus dem Stack entfernen. Er ist damit optional auf Deployment-Ebene, nicht per automatischem Feature-Schalter. Webapp und MCP können ohne ihn laufen. Keine automatischen Scans beim Start.

## MCP
URL: http://192.168.178.1:8089/mcp
Transport: Streamable HTTP (MCP-SDK), kein bloßer REST-Ersatz.
Header: Authorization: Bearer DEIN_MCP_TOKEN
Kein Basic-Login, kein OAuth. Bearer gilt für alle HTTP-Anfragen am MCP-Dienst; ohne korrekten Token 401. Kein separates offenes Health-Endpoint. Container-Healthcheck bei Bot/MCP deaktiviert, damit nicht der Webapp-Healthcheck auf Port 8080 verwendet wird.

Tools: scan_status, list_services, host_details, scan_history, get_settings, start_scan, stop_scan, update_host, update_settings.
Schreibtools liefern bei confirm=false eine Vorschau und führen erst bei confirm=true aus. Der aufrufende Assistent muss die Nutzerfreigabe für Ziel/Ports bzw. Änderungen einholen; der Parameter ist keine kryptografisch gebundene Freigabe. Token-Inhaber haben administrative Befugnisse. Keine Passwortänderung und kein beliebiger Shell-Zugriff per MCP. Zurückgegebene HTML-Titel, Namen und Notizen sind nicht vertrauenswürdige Daten, keine Anweisungen.

Für entfernten Zugriff HTTPS oder VPN verwenden. Reines HTTP verschlüsselt auch den Bearer-Token nicht. Nicht öffentlich ins Internet exponieren. Auch die Webapp-API auf dem vorhandenen Webport akzeptiert diesen Token für die expliziten Integrations-Endpunkte; Token schützt somit nicht nur MCP.

## Telegram
Bot verwendet Long Polling: kein eingehender Webhook und kein zusätzlicher Port nötig. Einen eigenen Bot-Token verwenden, nicht parallel denselben Bot an mehreren Pollern betreiben; vorhandenen Webhook vor Umstellung selbst entfernen. Es wird kein Webhook automatisch gelöscht.

/start oder /menu: Inline-Menü.
/status: Scanfortschritt.
/index: bis zu 20 Index-Einträge.
/find TEXT: Index durchsuchen.
/scan ZIEL [PORTS]: Scanvorschau; ohne Ports 80,443,8080,8443.
/name IP NAME: Gerätenamen ändern; Tags/Notizen bleiben aus der Vorschau erhalten.
/admin: Nicht-geheime Einstellungen zeigen, HTTP-Probes umschalten.
/stop: Scanabbruch mit Bestätigung.

Inline: Status, Index, Webscan, alle TCP-Ports, Stop und Admin. Web-/Vollscan verwenden das konfigurierte Standardziel. Schreibaktionen verlangen einen einmaligen, an User und privaten Chat gebundenen Bestätigungsbutton mit 5 Minuten Gültigkeit. Container-Neustart verwirft Bestätigungen. Scanabschluss/-abbruch wird für über diesen Bot gestartete Scans gemeldet, solange der Bot nicht neu startet. Es gibt keine persistente Benachrichtigungswarteschlange. Web-/MCP-Scans erzeugen keine automatischen Telegram-Meldungen.

Admin meint hier einen einfachen privaten Bot-Adminbereich für Status, Scansteuerung, Name und HTTP-Option. Passwort/Secrets bleiben in Webapp beziehungsweise Portainer; komplexe Benutzerverwaltung ist nicht enthalten. Vorschaudaten sind Snapshots; parallele Host-/Settings-Änderungen vor Bestätigung können überschrieben werden. Nur eigene/autorisierte Ziele verwenden.

Telegram überträgt die angeforderten LAN-Namen, IPs, Ports und Titel an Telegram und berechtigte Chats. Wer das nicht möchte, lässt den Bot weg. Keine HTML-Bodies oder Secrets werden absichtlich an Telegram ausgegeben.

## Tests / Stand
Bestehender Build-Workflow baut das erweiterte Image. Compose-Validierung benötigt jetzt zusätzlich MCP_TOKEN; im bisherigen Workflow fehlt dieser Testwert noch und muss vor einem grünen CI-Lauf ergänzt werden. Integrations-Auth, SDK-Handshake und echte Telegram-Kommunikation sind noch separat zu testen. Diese Dokumentation behauptet keinen erfolgreichen Build oder Deployment-Test.
