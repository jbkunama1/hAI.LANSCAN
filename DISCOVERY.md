# Host-Discovery

Webansicht /discovery, verlinkt oben auf der Startseite. Vorausgewählt 192.168.178.0-255; vollständige /24-Range wird zu CIDR normalisiert und lässt Netz-/Broadcastadresse aus. 192.168.178.1 bis .254 werden geprüft. ALLOWED_NETWORKS gilt unverändert, maximal 256 Hosts. Kein automatischer Scan beim Öffnen der Seite.

Ohne Root/zusätzliche Capabilities: TCP-Verbindungsprüfung auf 80,443,22,445,8080,3389. Ein offener Port oder ECONNREFUSED gilt als TCP-Antwortbeleg; der erste Beleg beendet die Hostprüfung. Keine ARP-, ICMP-, Hersteller-, Hostnamen- oder MAC-Erkennung. Geräte mit still gefilterten Ports können fehlen; Proxy/Firewall kann selbst Antworten erzeugen. Darum lautet der Status Antwort/keine Antwort und nicht garantiert online/offline. Es werden bei Discovery keine HTTP-Inhalte abgerufen.

Mobile Oberfläche: Raster für den tatsächlichen Zielbereich und dauerhaft gespeicherte Hostkarten mit Suche/Filter, erstem/letztem Fund und TCP-Beleg. Ein Klick im Raster filtert die Liste. Historische Hosts werden bei ausbleibender Antwort nicht gelöscht. Liste auch als angemeldetes JSON unter /api/discovery/hosts. Ein Link pro Host übernimmt dessen IP in die Portscan-Ansicht; startet den Portscan nicht automatisch.

SQLite-Zusatztabellen discovery_runs, discovery_hosts, discovery_checks liegen im bestehenden DB-Volume und werden automatisch angelegt. Discovery ist getrennt vom offenen-Port-Inventar: ein nur per Ablehnung erkannter Host erscheint hier auch ohne offenen Port. Vorhandene Namen aus hosts werden gelesen. Für neue reine Discovery-Hosts gibt es noch keinen eigenen Namenseditor. Keine zusätzliche Datenbank/Container/Volumes.

Discovery und Portscan teilen dieselbe Prozesssperre und können nicht parallel starten. Discovery hat eigenen Fortschritt und Stop-Endpunkt; der bestehende Portscan-Status und Telegram/MCP zeigen Discovery nicht als eigenen Job. Abbruch erhält abgeschlossene Hostprüfungen. Datenbankeinträge für unterbrochene Läufe werden beim Start markiert. Scan-Historienbereinigung und Pagination fehlen noch.

Direkte Theme-Auswahl Hell/Dunkel/Ocean auf Login, Index und Discovery. Browserpräferenz wird in localStorage gespeichert und hat beim Seitenladen Vorrang vor dem Admin-Standard. Admin-Theme ändert weiter den DB-Standard; die direkte Auswahl ist pro Browser. Keine Änderung von Zugangsdaten oder Scan-Einstellungen durch Theme-Wahl. CSS und Theme-JS enthalten keine LAN-Daten und sind vor Login freigegeben, damit das Login gestaltet bleibt. Daten-APIs und Discovery-JS bleiben geschützt.

Keine neuen ENV/Netzwerkrechte; highfishnetwork bleibt bestehen. Neues Image nach erfolgreichem Build pullen und Stack aktualisieren. Keine Scan-Zeitpläne enthalten. MCP/Telegram-Discovery-Tools sind in diesem Commit nicht ergänzt. Der bestehende CI-Workflow testet Discovery noch nicht separat; Mock-, Browser- und LAN-Funktionstests stehen dafür noch aus. Keine Behauptung einer vollständig erfolgten Testabnahme.
