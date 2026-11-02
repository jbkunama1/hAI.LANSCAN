# Darstellung und Hostliste

Rechts oben auf Login-, Index- und Discovery-Seite: kompakte Farbwahl und kleiner Hell-/Dunkel-Schalter. Ocean, Forest, Sunset und Violet sind jeweils hell/dunkel verfügbar (acht Kombinationen). Auswahl in localStorage unter lanscan-appearance pro Browser gespeichert. Alte lanscan-theme-Werte werden als Ocean mit passender Helligkeit übernommen. Keine Secrets oder Datenbankänderung durch Theme-Wahl.

Die Admin-API behält ihre bisherigen Werte ocean/dark/light. Sie legt die Standard-Helligkeit ohne Browserpräferenz fest. Palette bleibt persönliche Browserauswahl. Der Admin-Theme-Wechsel synchronisiert das Schalter-Symbol; eine vorhandene gespeicherte Browserpräferenz hat nach Neuladen weiter Vorrang. Kein geräteübergreifendes Theme-Profil.

Hostliste: Startseite mit hervorgehobenem Einstieg Deine Netzwerk-Hosts. Discovery zeigt direkt gespeicherte Hosts, Anzahl, Suche und Filter. Scanoptionen sind platzsparend einklappbar, Netzwerkbereich weiterhin 192.168.178.0-255. Raster ist separat unterhalb der Liste einklappbar. Port-Index und Discovery-Daten bleiben getrennt, keine automatische Scan-Ausführung.

Bestehende öffentliche CSS-/Theme-JS-Freigabe bleibt ausreichend. CSP bleibt unverändert; keine Inline-Skripte/Styles hinzugefügt. Templates und statische Dateien sind im Dockerfile bereits abgedeckt; neues Image bauen/pullen und Container aktualisieren. Keine neuen ENV-Werte, Ports oder Volumes. Smartphone-/Desktop-Browserprüfung der acht Varianten ist noch nicht erfolgt; bisheriger CI-Smoke-Test deckt nur die bestehende Admin-Helligkeitsumschaltung ab.
