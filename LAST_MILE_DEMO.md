# Last-Mile Find demo

Use one laptop and two Android phones on a private venue network. The tablet is optional. The venue and wearable coordinates are fictional, and the demo endpoints and packets are open. Keep the Android role screens open during the run.

## Start the laptop

1. In `Kinbeacon_central_server`, install `requirements.txt` and run `uvicorn app.main:app --host 0.0.0.0 --port 8000` with one worker. A restart clears demo incidents. The server and APK both read the same checked-in venue JSON. If you run the server from a separate checkout, set `KINBEACON_DEMO_VENUE` to the path of a copy of that file.
2. In `Kinbeacon_dashboard`, run `npm ci` then `npm run dev`. Open the Search page on the laptop and watch **Last-Mile Demo**.
3. For live BLE, install the anchor's `requirements.txt` and run `python main.py --demo-server http://127.0.0.1:8000 --demo-adapter hci0` from `Kinbeacon_anchor` on Linux. Use the local BlueZ adapter name for TX. The existing Bleak scanner receives requests, uplinks, and the wearable heartbeat. Use `--demo-mock-tx` to log transmissions while keeping the real scanner, or add `--mock` to run without BLE hardware.

## Run LAN rehearsal

1. Build and install the same debug APK on both phones. Turn on Bluetooth and grant the requested permissions. On phone 1, choose **Start Wearable Demo** and wait for **Wearable heartbeat active**.
2. On phone 2, choose **Guardian** and enter the laptop's LAN URL, such as `http://192.168.1.100:8000`. Leave **LAN rehearsal** on. Tap **Find Child** and look for **Simulated**, a 10 m circle, and **Blue Pavilion**.
3. Tap **Guide Me There**. Turn the phone while facing different directions. Toggle **Simulate indoor interference** to show map and landmark guidance.
4. Move the phones together to reveal the strength meter. Walk apart to see the reading cool and stop the wearable heartbeat to check **Signal lost**. With the devices close again, tap **Beep & Flash** and check the wearable's tone, torch, and screen.
5. Tap **Confirm Reunited**. To rehearse offline confirmation, disconnect the Guardian from the LAN before confirming and reconnect while staying on the Guardian screen. Check that the dashboard shows **Reunited**.

## Run live BLE

1. Start the Linux anchor and check for `kb-demo-child` in its log and a recent anchor sighting on the dashboard.
2. Open **Attendee Relay** on the tablet. For a two-phone run, select **Wearable-only demo** on the wearable to let it send its bundled point.
3. On the Guardian, turn off **LAN rehearsal**, **Use Wi-Fi fallback**, and mobile data. Keep the laptop connected to FastAPI. Tap **Find Child** and check for **Received over BLE**. Time from the tap to the result card. Confirm reunion and repeat with a fresh incident.
4. Close the relay and turn off **Wearable-only demo** before another search. After **No BLE result**, tap **Run LAN Rehearsal** and check for **Simulated**. Wi-Fi must be connected for the rehearsal and dashboard reunion to sync.

The server expires searches without a BLE uplink after 10 seconds and retains incident IDs for 10 minutes for retries. The Android app uses one scanner and one burst queue per role. The wearable phone needs to support advertising the heartbeat and a search burst concurrently.

## Verification

Run `python -m pytest -q` from both Python projects, `bash gradlew testDebugUnitTest assembleDebug` from `kimbeacon_app`, and `npm run build` from the dashboard. The Python anchor suite and Android packet tests use the same six hex fixtures.

Real-device tap-to-result timing is pending a Linux anchor and Android test devices.
