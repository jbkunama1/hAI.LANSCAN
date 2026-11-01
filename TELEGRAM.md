# Telegram-Dashboard und Berichte

Neues Bot-Modul: telegram_ui.py. Beide Compose-Dateien verwenden es; integrations.py bleibt für MCP und gemeinsame API-Funktionen bestehen. Nach erfolgreichem Build neues Image pullen und Stack inklusive neuer Command-/Volume-Konfiguration aktualisieren.

## Darstellung
Emoji-Symbole, HTML-Formatierung, grüne Fortschrittssegmente und Inline-Menüs. Keine frei wählbaren Textfarben und keine Bildanhänge: bewusst leichtgewichtig. Eingelesene Namen, Titel und Notizen werden für Telegram-HTML escaped und gekürzt. Übersicht zeigt historische Hosts/Ports/Webdienste, nicht aktuelle Online-Geräte.

/start, /menu, /status: Dashboard. /report: Zusammenfassung auf Abruf. /index und /find TEXT: bis zu zehn Einträge. /scan ZIEL [PORTS], /stop, /admin, /name IP NAME und Inline-Bestätigungen wie bisher. Schreibaktionen bleiben an Admin-ID, privaten Chat und einmalige 5-Minuten-Bestätigung gebunden.

## Startmeldung
Pro Bot-Prozessstart und Admin-ID einmal, sobald Webapp erreichbar und Telegram-Versand möglich sind. Bestätigt Bot-/Backend-Verbindung, nicht die Erreichbarkeit aller LAN-Geräte. Empfänger muss den Bot vorher selbst mit /start angeschrieben haben. Nach Container-Neustart kommt eine neue Startmeldung. Kein separater Auslöser nur beim Webapp-Neustart.

## Tagesbericht
- TELEGRAM_REPORT_TIME: HH:MM, Standard 08:00.
- TELEGRAM_TIMEZONE: IANA-Zeitzone, Standard Europe/Berlin; berücksichtigt Sommer-/Winterzeit.
- Admins aus TELEGRAM_ADMIN_IDS bekommen den Bericht im privaten Chat.
- Bericht liest nur vorhandene Status-/Indexdaten. Er startet keinen Scan. Scan-Zeitpläne bleiben ausgeschlossen.
- Der Bericht wird frühestens zur eingestellten Zeit gesendet; Polling/Netzfehler können ihn verzögern. Bei Start nach dem Termin wird der heutige Bericht nachgeholt. Keine Nachholung vergangener Tage.
- Anzahl Scanstarts der letzten 24 h basiert auf den maximal letzten 100 Scanläufen, nicht einer vollständigen unbegrenzten Historie.
- Erfolgreicher Berichtstag wird pro Empfänger im Volume hai-lanscan-bot-data gespeichert. Neustarts erzeugen normalerweise keinen zweiten Tagesbericht. Genau-einmal-Zustellung ist bei Absturz zwischen Versand und Speicherung nicht garantiert.
- Einmalige Bestätigungen und Abschlussmeldungen für Bot-Scans bleiben prozesslokal; kein persistenter Job-Scheduler.

Neue Portainer-ENV optional setzen: TELEGRAM_REPORT_TIME=08:00, TELEGRAM_TIMEZONE=Europe/Berlin. Bestehende ADMIN_PASSWORD, SECRET_KEY, MCP_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_IDS behalten; keine Secrets veröffentlichen. Beide Volumes behalten. Telegram benötigt kein zusätzliches eingehendes Port-Mapping. Nur einen Poller mit demselben Bot-Token betreiben.

## MCP unverändert
Endpoint: http://192.168.178.1:8089/mcp
Transport: Streamable HTTP.
Header: Authorization: Bearer DEIN_MCP_TOKEN
Tools: scan_status, list_services, host_details, scan_history, get_settings, start_scan, stop_scan, update_host, update_settings. Schreibtools führen erst mit confirm=true aus. Dies ist eine API-Konvention; der Client muss echte Nutzerfreigabe einholen. Token-Inhaber sind Admins. Keine Shell-/Passworttools. Für entfernten Zugriff HTTPS/VPN.

## Abnahme
Keine echte Telegram-Kommunikation oder tägliche Zustellung in der Erstellungsumgebung getestet. Bestehender CI-Workflow prüft telegram_ui.py bislang nicht explizit mit compileall; Docker COPY allein ist kein Funktionstest. Bericht und Formatierung benötigen einen Funktionstest nach Deployment. Ein grüner bisheriger Workflow belegt keinen vollständigen Telegram-/MCP-Test.
