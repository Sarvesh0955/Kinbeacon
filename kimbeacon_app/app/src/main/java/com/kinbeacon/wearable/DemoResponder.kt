package com.kinbeacon.wearable

import android.content.Context
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.SystemClock
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.random.Random

private data class PendingRelay(val sender: String, val ttl: Int, val expiry: Long, var pending: Boolean)

@Composable
internal fun DemoResponder(
    role: DemoRole,
    venue: DemoVenue,
    radio: DemoRadio?,
    listen: ((DemoPacket, String, Int) -> Unit) -> Unit
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var wearableOnly by rememberSaveable { mutableStateOf(false) }
    var status by remember { mutableStateOf("Ready for a search") }
    var alerting by remember { mutableStateOf(false) }
    var heard by remember { mutableIntStateOf(0) }
    var forwarded by remember { mutableIntStateOf(0) }
    var suppressed by remember { mutableIntStateOf(0) }
    var collecting by remember { mutableStateOf<Int?>(null) }
    var strongest by remember { mutableStateOf<DemoPacket?>(null) }
    val responded = remember { mutableMapOf<Pair<Int, Int>, Long>() }
    val relays = remember { mutableMapOf<Pair<Int, DemoType>, PendingRelay>() }

    DisposableEffect(radio, role, wearableOnly) {
        listen { packet, sender, rssi ->
            val activeRadio = radio ?: return@listen
            val now = SystemClock.elapsedRealtime()
            responded.entries.removeAll { it.value <= now }
            val key = packet.incidentId to packet.action
            if (role == DemoRole.WEARABLE) {
                when (packet.type) {
                    DemoType.FIND_TARGET -> {
                        if (key in responded || (packet.action == 0 && collecting != null)) return@listen
                        responded[key] = now + if (packet.action == 1) 1800 else 30_000
                        if (packet.action == 1) {
                            if (!alerting) scope.launch {
                                alerting = true
                                try {
                                    pulseWearable(context)
                                } finally {
                                    alerting = false
                                }
                            }
                        } else {
                            collecting = packet.incidentId
                            strongest = null
                            status = "Listening for a nearby relay"
                            scope.launch {
                                try {
                                    activeRadio.send(DemoPacket(DemoType.LOCATE_ME, packet.incidentId, 1), 700)
                                    delay(2000)
                                    val point = strongest?.point ?: venue.wearable.takeIf { wearableOnly }
                                    if (point != null) {
                                        activeRadio.send(DemoPacket(DemoType.LOC_UPLINK, packet.incidentId, 1, point))
                                        status = if (strongest != null) "Relay position sent" else "Wearable-only point sent"
                                    } else status = "No relay response"
                                } finally {
                                    collecting = null
                                }
                            }
                        }
                    }
                    DemoType.NEIGHBOR_LOC -> if (packet.incidentId == collecting &&
                        packet.rssi > (strongest?.rssi ?: Int.MIN_VALUE)) strongest = packet
                    else -> Unit
                }
            } else if (packet.type == DemoType.LOCATE_ME) {
                if (key !in responded) {
                    responded[key] = now + 30_000
                    activeRadio.send(DemoPacket(DemoType.NEIGHBOR_LOC, packet.incidentId, 1,
                        venue.relay, rssi = rssi.coerceIn(-128, 127)), 700)
                }
            } else if (packet.type == DemoType.FIND_REQ || packet.type == DemoType.LOC_RESULT ||
                (packet.type == DemoType.FIND_TARGET && packet.action == 0)) {
                relays.entries.removeAll { it.value.expiry <= now }
                val relayKey = packet.incidentId to packet.type
                val previous = relays[relayKey]
                if (previous == null) {
                    heard++
                    if (relays.size >= 128) relays.remove(relays.keys.first())
                    val entry = PendingRelay(sender, packet.ttl, now + 30_000, packet.ttl > 1)
                    relays[relayKey] = entry
                    if (entry.pending) scope.launch {
                        delay(Random.nextLong(50, 151))
                        if (entry.pending) activeRadio.send(
                            packet.copy(ttl = packet.ttl - 1), 600, onStarted = { forwarded++ }
                        ) {
                            val pending = entry.pending
                            entry.pending = false
                            pending && relays[relayKey] === entry
                        }
                    }
                } else if (previous.pending && previous.sender != sender && packet.ttl < previous.ttl) {
                    previous.pending = false
                    suppressed++
                }
            }
        }
        onDispose { listen { _, _, _ -> } }
    }

    if (role == DemoRole.WEARABLE) {
        DemoToggle("Wearable-only demo", wearableOnly) { wearableOnly = it }
        if (alerting) Text(
            "Beep & Flash active",
            color = MaterialTheme.colorScheme.secondary,
            style = MaterialTheme.typography.headlineMedium
        )
        Text(status)
    } else {
        Text("Venue · ${venue.name}")
        Text("Heard $heard   Forwarded $forwarded   Suppressed $suppressed")
    }
}

private suspend fun pulseWearable(context: Context) {
    val manager = context.getSystemService(CameraManager::class.java)
    val camera = manager?.let {
        runCatching {
            it.cameraIdList.firstOrNull { id ->
                it.getCameraCharacteristics(id).get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
            }
        }.getOrNull()
    }
    val tone = runCatching { ToneGenerator(AudioManager.STREAM_MUSIC, 85) }.getOrNull()
    try {
        repeat(3) {
            tone?.startTone(ToneGenerator.TONE_PROP_BEEP, 160)
            if (camera != null) runCatching { manager?.setTorchMode(camera, true) }
            delay(180)
            if (camera != null) runCatching { manager?.setTorchMode(camera, false) }
            delay(170)
        }
    } finally {
        if (camera != null) runCatching { manager?.setTorchMode(camera, false) }
        tone?.release()
    }
}
