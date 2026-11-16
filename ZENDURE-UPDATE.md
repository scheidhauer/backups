# Zendure-Script nach Adapterupdate

Das Script verwendet `control.setDeviceAutomationInOutLimit` mit negativem Wert zum Laden und positivem Wert zum Einspeisen. Für die Hyper-HEMS-Ansteuerung ist Adapter 5.2.1 oder neuer vorgesehen; in neueren Versionen sind weitere Hyper-Korrekturen enthalten.

## Umstellung

1. Laufendes PV-Script in ioBroker stoppen und den bisherigen Stand sichern. Das Stoppen des Scripts hebt einen bereits gesetzten Leistungsauftrag nicht automatisch auf.
2. Adapter aktualisieren. Die eingebaute Adapterautomatik für die vom Script gesteuerten Hyper ausgeschaltet lassen.
3. Bei beiden Geräten `control.inverseMaxPower` passend zur erlaubten maximalen Ausgangsleistung prüfen. Das Script fordert maximal 1200 W je Hyper an. `minSoc` und `socSet` nach Aktivierung der HEMS-Steuerung ebenfalls kontrollieren. `acMode`, `autoModel` und `hemsState` verwaltet der Adapter.
4. Die vollständige Datei `PV-Werte-berechnen.ts` in das bestehende ioBroker-Script übernehmen und starten. Erste Lade-/Entladevorgänge und das Log beobachten.

## Verhalten

- Neuberechnung bei Zähleränderungen sowie alle zehn Sekunden; normale Leistungsänderungen mindestens 30 W, grundsätzlich mindestens 30 Sekunden Abstand. Änderungen ab 500 W dürfen diesen Abstand umgehen.
- Nullbefehle umgehen die Drosselung. Die dreiminütige Richtungssperre gilt zentral auch für manuelle Vorgaben und Mindest-SOC-Nachladung. Beim Start wird eine gemessene laufende Richtung zunächst drei Minuten geschützt.
- Fehlen gültige Hyper-Messwerte oder ist `lastUpdate` älter als zehn Minuten, pausiert die Regelung beider Geräte. Dasselbe gilt bei einem mehr als zwei Minuten alten Zählerwert (`ts`, letzter Schreibzeitpunkt). Einmalig wird ein Stopp versucht; dessen Ausführung ist damit nicht bestätigt.
- Bei gemeldetem `socStatus = 1` pausiert die Regelung beider Geräte. Der kalibrierende Hyper erhält keinen Steuerbefehl, der andere einmalig 0 W. Nach Ende der Kalibrierung wird neu gerechnet.
- Nicht jede Hyper-Firmware stellt `socStatus` bereit. Ohne diesen Wert kann das Script eine Kalibrierung nicht zuverlässig erkennen. Lade- und Nullbefehle werden wegen bloßer Soll-/Ist-Abweichung deshalb nicht wiederholt. Einspeiseaufträge werden nur bei bekanntem Normalstatus, frischen Daten und ohne erkennbare Sperre höchstens zweimal je unverändertem Auftrag wiederholt. Eine anhaltende Abweichung wird protokolliert.
- Keine automatischen Adapter- oder Geräteneustarts. Der bestehende Kommunikationsalarm meldet nach zehn Minuten ohne Daten; Prüfung jede Minute.

## Prüfung ohne Geräte

Ab Node.js 22.13: `node tests/zendure-control.test.cjs`

Die Tests simulieren ioBroker-Daten, Zeit und Schreibzugriffe. Sie prüfen unter anderem Stoppen, Drosselung, Richtungssperre, begrenzte Wiederholungen, Kalibrierung, veraltete Daten und die Verteilung auf zwei Hyper. Ein Test an realer Hardware steht aus.
