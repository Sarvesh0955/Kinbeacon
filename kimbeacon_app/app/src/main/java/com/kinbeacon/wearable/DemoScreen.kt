package com.kinbeacon.wearable

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat

internal enum class DemoRole(val title: String) {
    GUARDIAN("Guardian"), WEARABLE("Wearable Demo"), RELAY("Attendee Relay")
}

@Composable
internal fun DemoScreen(role: DemoRole, heartbeatStatus: String, back: () -> Unit) {
    val context = LocalContext.current
    val venue = remember { DemoVenue.load(context) }
    val view = LocalView.current
    DisposableEffect(view) {
        val original = view.keepScreenOn
        view.keepScreenOn = true
        onDispose { view.keepScreenOn = original }
    }
    val permissions = remember {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_ADVERTISE, Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION)
        } else listOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
    }
    fun hasPermissions() = permissions.filter { it != Manifest.permission.ACCESS_COARSE_LOCATION }
        .all { ContextCompat.checkSelfPermission(context, it) == PackageManager.PERMISSION_GRANTED }

    var ready by remember { mutableStateOf(hasPermissions()) }
    var radioVersion by remember { mutableIntStateOf(0) }
    var radioError by remember { mutableStateOf<String?>(null) }
    val permissionRequest = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { ready = hasPermissions() }
    LaunchedEffect(Unit) {
        if (!ready) permissionRequest.launch(permissions.toTypedArray())
    }

    val scope = rememberCoroutineScope()
    var radio by remember { mutableStateOf<DemoRadio?>(null) }
    var listener by remember { mutableStateOf<(DemoPacket, String, Int) -> Unit>({ _, _, _ -> }) }
    var heartbeat by remember { mutableStateOf<(Int) -> Unit>({}) }
    DisposableEffect(ready, role, radioVersion) {
        val service = Intent(context, KinBeaconAdvertiserService::class.java)
        if (ready) {
            radio = DemoRadio(context, scope, { radioError = it }) { result ->
                val record = result.scanRecord ?: return@DemoRadio
                if (record.getManufacturerSpecificData(DEMO_HEARTBEAT_COMPANY)
                        ?.contentEquals(demoHeartbeat) == true) heartbeat(result.rssi)
                record.getManufacturerSpecificData(DEMO_CONTROL)?.let { data ->
                    DemoPacket.decode(DEMO_CONTROL, data)?.let {
                        listener(it, result.device.address, result.rssi)
                    }
                }
            }
            if (role == DemoRole.WEARABLE) {
                service.action = KinBeaconAdvertiserService.ACTION_START_DEMO
                runCatching { ContextCompat.startForegroundService(context, service) }
                    .onFailure { radioError = "Could not start wearable heartbeat" }
            }
        }
        onDispose {
            radio?.close()
            radio = null
            if (ready && role == DemoRole.WEARABLE) context.stopService(service)
        }
    }

    Column(
        Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()
            .imePadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        TextButton(onClick = back) { Text("Back to roles") }
        Text(role.title, style = MaterialTheme.typography.headlineMedium)
        if (!ready) {
            Text("Bluetooth and location permissions are needed for nearby demo packets.")
            Button(onClick = { permissionRequest.launch(permissions.toTypedArray()) }) {
                Text("Grant permissions")
            }
        }
        if (role == DemoRole.WEARABLE && ready) Text(heartbeatStatus)
        radioError?.let {
            Text(it, color = MaterialTheme.colorScheme.error)
            TextButton(onClick = { radioError = null; radioVersion++ }) { Text("Restart Bluetooth") }
        }

        when (role) {
            DemoRole.GUARDIAN -> GuardianDemo(venue, radio, { listener = it }, { heartbeat = it })
            DemoRole.WEARABLE, DemoRole.RELAY -> DemoResponder(
                role, venue, radio, { listener = it }
            )
        }
    }
}

@Composable
internal fun DemoToggle(label: String, checked: Boolean, change: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically
    ) {
        Switch(checked = checked, onCheckedChange = change)
        Text(label)
    }
}
