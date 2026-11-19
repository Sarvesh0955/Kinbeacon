package com.kinbeacon.wearable

import android.os.SystemClock
import android.os.VibrationEffect
import android.os.Vibrator
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.math.roundToInt
import kotlin.random.Random

private data class SearchAttempt(val id: Int, val lan: Boolean, val wifi: Boolean, val retry: Int = 0)
internal data class DemoLocation(val point: DemoPoint, val radius: Int, val landmark: String, val source: String)

@Composable
internal fun GuardianDemo(
    venue: DemoVenue,
    radio: DemoRadio?,
    listen: ((DemoPacket, String, Int) -> Unit) -> Unit,
    hearHeartbeat: ((Int) -> Unit) -> Unit
) {
    val context = LocalContext.current
    var url by rememberSaveable { mutableStateOf("http://192.168.1.100:8000") }
    var lan by rememberSaveable { mutableStateOf(true) }
    var wifi by rememberSaveable { mutableStateOf(false) }
    var interference by rememberSaveable { mutableStateOf(false) }
    var attempt by remember { mutableStateOf<SearchAttempt?>(null) }
    var status by remember { mutableStateOf("idle") }
    var location by remember { mutableStateOf<DemoLocation?>(null) }
    var networkError by remember { mutableStateOf(false) }
    var guiding by remember { mutableStateOf(false) }
    var radar by remember { mutableStateOf(false) }
    var reunionPending by remember { mutableStateOf(false) }
    var reunionError by remember { mutableStateOf<String?>(null) }
    var signal by remember { mutableStateOf<Double?>(null) }
    var lastSignal by remember { mutableLongStateOf(0L) }
    var strongReadings by remember { mutableIntStateOf(0) }
    var lastId by remember { mutableStateOf<Int?>(null) }

    fun start(useLan: Boolean) {
        val id = generateSequence { Random.nextInt(65536) }.first { it != lastId }
        lastId = id
        lan = useLan
        status = "searching"
        networkError = false
        location = null
        guiding = false
        radar = false
        strongReadings = 0
        signal = null
        attempt = SearchAttempt(id, useLan, wifi)
    }

    fun located(result: DemoLocation) {
        if (status != "searching") return
        location = result
        networkError = false
        status = "located"
    }

    DisposableEffect(venue) {
        listen { packet, _, _ ->
            val search = attempt
            if (packet.type == DemoType.LOC_RESULT && search != null && packet.incidentId == search.id && !search.lan) {
                located(DemoLocation(requireNotNull(packet.point), packet.radius,
                    venue.landmarks[packet.landmark].name, "Received over BLE"))
            }
        }
        hearHeartbeat { rssi ->
            if (rssi in -127..20) {
                val now = SystemClock.elapsedRealtime()
                val previous = signal?.takeIf { now - lastSignal < 3000 }
                val smoothed = previous?.let { it * 0.72 + rssi * 0.28 } ?: rssi.toDouble()
                signal = smoothed
                lastSignal = now
                if (status == "located") {
                    strongReadings = if (previous != null && smoothed >= -82) strongReadings + 1 else 0
                    if (strongReadings >= 3) radar = true
                }
            }
        }
        onDispose {
            listen { _, _, _ -> }
            hearHeartbeat {}
        }
    }

    LaunchedEffect(attempt) {
        val search = attempt ?: return@LaunchedEffect
        if (!search.lan) radio?.send(DemoPacket(DemoType.FIND_REQ, search.id, 2), 1000) {
            status == "searching" && attempt == search
        }
        val deadline = SystemClock.elapsedRealtime() + if (search.lan) 6000 else 10_000
        fun accept(incident: JSONObject) {
            if (incident.optInt("incident_id", -1) != search.id || status != "searching") return
            val result = incident.optJSONObject("result")
            if (result != null && (result.optString("source") == "simulated") == search.lan) {
                located(DemoLocation(
                    DemoPoint(result.getDouble("lat"), result.getDouble("lon")),
                    result.getInt("radius_m"), result.getString("landmark"),
                    if (search.lan) "Simulated" else "Received over Wi-Fi"
                ))
            } else if (incident.optString("status") == "timed_out") status = "timed_out"
        }

        if (search.lan || search.wifi) {
            var submitted = false
            while (status == "searching" && SystemClock.elapsedRealtime() < deadline) {
                try {
                    if (!submitted) {
                        accept(demoRequest(url, "/find", JSONObject().put("incident_id", search.id)
                            .put("mode", if (search.lan) "lan" else "ble")))
                        submitted = true
                    } else {
                        demoRequest(url, "/state").optJSONObject("incident")?.let { accept(it) }
                    }
                    networkError = false
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (_: Exception) {
                    if (status == "searching") networkError = true
                }
                if (status == "searching") delay(1000)
            }
        } else {
            while (status == "searching" && SystemClock.elapsedRealtime() < deadline) delay(100)
        }

        if (status == "searching") status = if (search.lan) "retry" else "timed_out"
    }

    LaunchedEffect(reunionPending, url) {
        val search = attempt ?: return@LaunchedEffect
        while (reunionPending) {
            try {
                demoRequest(url, "/reunite", JSONObject().put("incident_id", search.id))
                reunionPending = false
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: DemoHttpError) {
                if (failure.code == 404 || failure.code == 409) {
                    reunionPending = false
                    reunionError = "Venue server no longer has a located incident for this search."
                }
            } catch (_: Exception) {
                // Keep the local confirmation while venue Wi-Fi reconnects.
            }
            if (reunionPending) delay(1000)
        }
    }

    var time by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    LaunchedEffect(radar, status) {
        val vibrator = context.getSystemService(Vibrator::class.java)
        var lastPulse = 0L
        while (radar && status == "located") {
            time = SystemClock.elapsedRealtime()
            val strength = signal
            if (strength != null && time - lastSignal < 3000) {
                val interval = (850 - (strength + 85).coerceIn(0.0, 40.0) * 17).toLong()
                if (time - lastPulse >= interval) {
                    vibrator?.vibrate(VibrationEffect.createOneShot(35, VibrationEffect.DEFAULT_AMPLITUDE))
                    lastPulse = time
                }
            }
            delay(75)
        }
    }

    val active = status == "searching" || status == "located"
    OutlinedTextField(
        value = url, onValueChange = { url = it }, enabled = !active,
        label = { Text("Venue server URL") }, singleLine = true, modifier = Modifier.fillMaxWidth()
    )
    if (!active && !reunionPending && status != "retry") {
        DemoToggle("LAN rehearsal", lan) { lan = it }
        if (!lan) DemoToggle("Use Wi-Fi fallback", wifi) { wifi = it }
        if (status == "timed_out") {
            Text("No BLE result")
            OutlinedButton(onClick = { start(true) }) { Text("Run LAN Rehearsal") }
        }
        Button(onClick = { start(lan) }, enabled = lan || radio != null) { Text("Find Child") }
    }
    DemoToggle("Simulate indoor interference", interference) { interference = it }

    if (status == "searching") {
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(if (attempt?.lan == true) "Finding the rehearsal position…" else "Waiting for a BLE result…")
    }
    if (networkError && status in setOf("searching", "retry", "timed_out")) {
        Text("Venue server unreachable or busy", color = MaterialTheme.colorScheme.error)
        Button(onClick = {
            status = "searching"
            networkError = false
            attempt = attempt?.let { it.copy(retry = it.retry + 1) }
        }) { Text("Retry") }
        if (status == "retry") TextButton(onClick = {
            status = "idle"
            networkError = false
            attempt = null
        }) { Text("Change search mode") }
    }
    location?.let { result ->
        Text(result.landmark, style = MaterialTheme.typography.titleLarge)
        Text("${result.radius} m radius · ${result.source}")
        DemoMap(venue, result)
        if (status == "located") {
            if (guiding) DemoGuidance(venue, result, interference)
            else Button(onClick = { guiding = true }) { Text("Guide Me There") }

            Text("Close-Range Finder", style = MaterialTheme.typography.titleMedium)
            val strength = signal
            if (!radar) {
                Text("Move toward ${result.landmark} to pick up the wearable signal.")
            } else if (strength == null || time - lastSignal >= 3000) {
                Text("Signal lost")
            } else {
                val warmth = ((strength + 95) / 50).toFloat().coerceIn(0f, 1f)
                LinearProgressIndicator(progress = { warmth }, modifier = Modifier.fillMaxWidth())
                Text("${if (warmth >= 0.45) "Warmer" else "Colder"} · ${strength.roundToInt()} dBm")
            }
            OutlinedButton(enabled = radar && radio != null && time - lastSignal < 3000, onClick = {
                val id = attempt?.id ?: return@OutlinedButton
                radio?.send(DemoPacket(DemoType.FIND_TARGET, id, 1, action = 1))
            }) { Text("Beep & Flash") }
            Button(onClick = {
                status = "reunited"
                reunionError = null
                reunionPending = true
            }) { Text("Confirm Reunited") }
        }
    }

    if (status == "reunited") {
        Text("Reunited", style = MaterialTheme.typography.titleLarge)
        if (reunionPending) Text("Waiting for venue Wi-Fi to update the staff dashboard.")
        reunionError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    }
}

private class DemoHttpError(val code: Int) : Exception("Demo server returned $code")

private suspend fun demoRequest(url: String, route: String, body: JSONObject? = null): JSONObject =
    withContext(Dispatchers.IO) {
        val connection = URL(url.trim().trimEnd('/') + "/api/v1/demo" + route)
            .openConnection() as HttpURLConnection
        try {
            connection.useCaches = false
            connection.connectTimeout = 1200
            connection.readTimeout = 1200
            if (body != null) {
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toString().encodeToByteArray()) }
            }
            val code = connection.responseCode
            if (code !in 200..299) throw DemoHttpError(code)
            JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
        } finally {
            connection.disconnect()
        }
    }
