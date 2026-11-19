package com.kinbeacon.wearable

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.*

import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {

    private var isBroadcasting by mutableStateOf(false)
    private var telemetryHexId by mutableStateOf("--")
    private var telemetryJson by mutableStateOf("--")
    private var telemetryRawPdu by mutableStateOf("--")
    private var telemetryCounter by mutableStateOf(0L)
    private var telemetryExecTime by mutableStateOf(0L)
    private var telemetryRadioState by mutableStateOf("INACTIVE")

    private val telemetryReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            if (intent.action == KinBeaconAdvertiserService.ACTION_TELEMETRY) {
                telemetryHexId = intent.getStringExtra(KinBeaconAdvertiserService.EXTRA_DEVICE_ID_HEX) ?: "--"
                telemetryJson = intent.getStringExtra(KinBeaconAdvertiserService.EXTRA_DEVICE_ID_JSON) ?: "--"
                telemetryRawPdu = intent.getStringExtra(KinBeaconAdvertiserService.EXTRA_RAW_PDU) ?: "--"
                telemetryCounter = intent.getLongExtra(KinBeaconAdvertiserService.EXTRA_COUNTER, 0L)
                telemetryExecTime = intent.getLongExtra(KinBeaconAdvertiserService.EXTRA_EXECUTION_TIME_US, 0L)
                telemetryRadioState = intent.getStringExtra(KinBeaconAdvertiserService.EXTRA_RADIO_STATE) ?: "UNKNOWN"
            }
        }
    }

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val allGranted = permissions.entries.all { it.value }
        if (!allGranted) {
            Toast.makeText(this, "BLE permissions required", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        
        checkPermissions()
        
        val filter = IntentFilter(KinBeaconAdvertiserService.ACTION_TELEMETRY)
        val receiverFlags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            RECEIVER_NOT_EXPORTED
        } else {
            0
        }
        ContextCompat.registerReceiver(this, telemetryReceiver, filter, receiverFlags)

        CryptoKeyManager.loadSession(this)

        setContent {
            MaterialTheme(
                colorScheme = darkColorScheme(
                    background = Color(0xFF0F172A),
                    surface = Color(0xFF1E293B),
                    primary = Color(0xFF3B82F6),
                    secondary = Color(0xFF10B981),
                    error = Color(0xFFEF4444)
                )
            ) {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    KinBeaconApp()
                }
            }
        }
    }

    private fun checkPermissions() {
        val requiredPermissions = mutableListOf<String>()
        requiredPermissions.add(Manifest.permission.ACCESS_FINE_LOCATION)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            requiredPermissions.add(Manifest.permission.BLUETOOTH_ADVERTISE)
            requiredPermissions.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            requiredPermissions.add(Manifest.permission.POST_NOTIFICATIONS)
        }

        val missingPermissions = requiredPermissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }

        if (missingPermissions.isNotEmpty()) {
            requestPermissionLauncher.launch(missingPermissions.toTypedArray())
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        unregisterReceiver(telemetryReceiver)
    }

    private fun toggleBroadcasting(mode: NrfBlePacketBuilder.FramingMode) {
        if (isBroadcasting) {
            val intent = Intent(this, KinBeaconAdvertiserService::class.java).apply {
                action = KinBeaconAdvertiserService.ACTION_STOP
            }
            startService(intent)
            isBroadcasting = false
            telemetryRadioState = "INACTIVE"
        } else {
            val intent = Intent(this, KinBeaconAdvertiserService::class.java).apply {
                action = KinBeaconAdvertiserService.ACTION_START
                putExtra(KinBeaconAdvertiserService.EXTRA_FRAMING_MODE, mode.name)
            }
            startForegroundService(intent)
            isBroadcasting = true
        }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    fun KinBeaconApp() {
        val coroutineScope = rememberCoroutineScope()
        var serverUrl by remember { mutableStateOf("http://192.168.1.100:8000") }
        var isRegistered by remember { mutableStateOf(CryptoKeyManager.initialDeviceId != null) }
        var rttOffset by remember { mutableStateOf(CryptoKeyManager.clockOffsetMs) }
        var sharedSecretHex by remember { mutableStateOf(CryptoKeyManager.getSharedSecretHex() ?: "--") }
        var showOverridePanel by remember { mutableStateOf(false) }
        
        var selectedMode by remember { mutableStateOf(NrfBlePacketBuilder.FramingMode.COMPACT_KV) }
        var expandedModeMenu by remember { mutableStateOf(false) }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Header (Long press for overrides)
            Text(
                text = "KinBeacon Wearable",
                style = MaterialTheme.typography.headlineMedium,
                color = Color.White,
                modifier = Modifier.pointerInput(Unit) {
                    detectTapGestures(
                        onLongPress = { showOverridePanel = !showOverridePanel }
                    )
                }
            )

            // Server Config Card
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface)
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Server Configuration", style = MaterialTheme.typography.titleMedium, color = Color.White)
                    OutlinedTextField(
                        value = serverUrl,
                        onValueChange = { serverUrl = it },
                        label = { Text("Venue Server URL") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true
                    )
                    if (isRegistered) {
                        Card(
                            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                            modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp)
                        ) {
                            Column(modifier = Modifier.padding(12.dp)) {
                                Text("Registration State: REGISTERED", color = MaterialTheme.colorScheme.secondary, fontWeight = FontWeight.Bold)
                                Spacer(modifier = Modifier.height(4.dp))
                                Text("RTT Offset (Δt): $rttOffset ms", style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
                                Text("AES Key KK (first 16): $sharedSecretHex", style = MaterialTheme.typography.bodySmall, color = Color.LightGray)
                            }
                        }
                    }

                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = {
                                coroutineScope.launch {
                                    CryptoKeyManager.generateKeyPair()
                                    val clientPub = CryptoKeyManager.getPublicKeyBase64()
                                    val result = RegistrationClient.register(serverUrl, clientPub)
                                    when (result) {
                                        is RegistrationResult.Success -> {
                                            CryptoKeyManager.computeSharedSecret(result.serverPubKeyBase64)
                                            CryptoKeyManager.computeClockOffset(result.tSend, result.tRecv, result.serverTimeMs)
                                            CryptoKeyManager.saveSession(this@MainActivity, result.deviceId, result.rotationIntervalSec)
                                            isRegistered = true
                                            rttOffset = CryptoKeyManager.clockOffsetMs
                                            sharedSecretHex = CryptoKeyManager.getSharedSecretHex() ?: "--"
                                            Toast.makeText(this@MainActivity, "Registration Success", Toast.LENGTH_SHORT).show()
                                        }
                                        is RegistrationResult.Error -> {
                                            Toast.makeText(this@MainActivity, "Error: ${result.message}", Toast.LENGTH_LONG).show()
                                        }
                                    }
                                }
                            },
                            modifier = Modifier.weight(1f),
                            enabled = !isBroadcasting
                        ) {
                            Text("1. ECDH Register")
                        }
                        OutlinedButton(
                            onClick = {
                                CryptoKeyManager.setOfflineDemoKey(this@MainActivity)
                                CryptoKeyManager.saveSession(this@MainActivity, CryptoKeyManager.initialDeviceId ?: "KB-OFFLINE-TEST", 3)
                                isRegistered = true
                                rttOffset = CryptoKeyManager.clockOffsetMs
                                sharedSecretHex = CryptoKeyManager.getSharedSecretHex() ?: "--"
                                Toast.makeText(this@MainActivity, "Offline Test Key Set", Toast.LENGTH_SHORT).show()
                            },
                            enabled = !isBroadcasting
                        ) {
                            Text("Offline Test")
                        }
                    }
                }
            }

            // Framing Mode Selector
            ExposedDropdownMenuBox(
                expanded = expandedModeMenu,
                onExpandedChange = { expandedModeMenu = !expandedModeMenu },
                modifier = Modifier.fillMaxWidth()
            ) {
                OutlinedTextField(
                    value = selectedMode.displayName,
                    onValueChange = {},
                    readOnly = true,
                    label = { Text("Framing Mode") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expandedModeMenu) },
                    modifier = Modifier.menuAnchor(ExposedDropdownMenuAnchorType.PrimaryNotEditable, true).fillMaxWidth(),
                    enabled = !isBroadcasting
                )
                ExposedDropdownMenu(
                    expanded = expandedModeMenu,
                    onDismissRequest = { expandedModeMenu = false }
                ) {
                    NrfBlePacketBuilder.FramingMode.entries.forEach { mode ->
                        DropdownMenuItem(
                            text = { Text(mode.displayName) },
                            onClick = {
                                selectedMode = mode
                                expandedModeMenu = false
                            }
                        )
                    }
                }
            }

            // Live Telemetry Dashboard
            Card(
                colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                modifier = Modifier.fillMaxWidth()
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Live Telemetry", style = MaterialTheme.typography.titleMedium, color = Color.White)
                    
                    Text("Active Token (RPIt):", color = Color.LightGray)
                    Text(
                        text = telemetryHexId,
                        style = MaterialTheme.typography.headlineSmall,
                        fontFamily = FontFamily.Monospace,
                        color = MaterialTheme.colorScheme.secondary,
                        modifier = Modifier.background(Color.Black.copy(alpha = 0.3f)).padding(8.dp).fillMaxWidth()
                    )

                    Text("JSON Preview:", color = Color.LightGray)
                    Text(text = telemetryJson, fontFamily = FontFamily.Monospace, color = Color.White)

                    Text("Raw Over-the-Air PDU (Hex):", color = Color.LightGray)
                    val pduByteCount = if (telemetryRawPdu == "--") 0 else telemetryRawPdu.length / 2
                    Text(
                        text = "$telemetryRawPdu ($pduByteCount / 31B)",
                        fontFamily = FontFamily.Monospace,
                        color = if (pduByteCount > 31) MaterialTheme.colorScheme.error else Color.White
                    )

                    HorizontalDivider(color = Color.DarkGray)
                    
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Counter (tt):", color = Color.LightGray)
                        Text(telemetryCounter.toString(), color = Color.White)
                    }
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("AES-128 Execution:", color = Color.LightGray)
                        Text("${telemetryExecTime} μs", color = Color.White)
                    }
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Radio State:", color = Color.LightGray)
                        Text(telemetryRadioState, color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
                    }
                }
            }

            // Master Broadcast Toggle
            Button(
                onClick = { toggleBroadcasting(selectedMode) },
                modifier = Modifier.fillMaxWidth().height(60.dp),
                enabled = isRegistered,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isBroadcasting) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
                ),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text(
                    text = if (isBroadcasting) "STOP BROADCASTING" else "2. START BROADCASTING",
                    fontWeight = FontWeight.Bold
                )
            }

            // Hidden Judge Override Panel
            if (showOverridePanel) {
                Card(
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(8.dp)) {
                        Text("Manual Zone Override", style = MaterialTheme.typography.labelLarge)
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                            listOf("Zone A", "Zone B", "Zone C").forEach { zone ->
                                TextButton(onClick = {
                                    coroutineScope.launch {
                                        val success = RegistrationClient.overrideZone(serverUrl, telemetryHexId, zone)
                                        Toast.makeText(this@MainActivity, "Override $zone: $success", Toast.LENGTH_SHORT).show()
                                    }
                                }) {
                                    Text(zone)
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
