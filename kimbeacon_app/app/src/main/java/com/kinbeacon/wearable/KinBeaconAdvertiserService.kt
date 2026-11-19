package com.kinbeacon.wearable

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.AdvertisingSet
import android.bluetooth.le.AdvertisingSetCallback
import android.bluetooth.le.AdvertisingSetParameters
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

class KinBeaconAdvertiserService : Service() {

    private val TAG = "KinBeaconAdvService"
    private val CHANNEL_ID = "KinBeaconAdvChannel"
    private val NOTIFICATION_ID = 1001
    
    companion object {
        const val ACTION_START = "ACTION_START"
        const val ACTION_STOP = "ACTION_STOP"
        const val EXTRA_FRAMING_MODE = "EXTRA_FRAMING_MODE"
        
        const val ACTION_TELEMETRY = "com.kinbeacon.wearable.TELEMETRY"
        const val EXTRA_DEVICE_ID_HEX = "DEVICE_ID_HEX"
        const val EXTRA_DEVICE_ID_JSON = "DEVICE_ID_JSON"
        const val EXTRA_RAW_PDU = "RAW_PDU"
        const val EXTRA_COUNTER = "COUNTER"
        const val EXTRA_EXECUTION_TIME_US = "EXECUTION_TIME_US"
        const val EXTRA_RADIO_STATE = "RADIO_STATE"
    }

    private var wakeLock: PowerManager.WakeLock? = null
    private var serviceScope = CoroutineScope(Dispatchers.Default + Job())
    private var tickJob: Job? = null
    
    private var bluetoothAdapter: BluetoothAdapter? = null
    private var activeAdvertisingSet: AdvertisingSet? = null
    private var legacyUsingFallback = false
    private var currentMode = NrfBlePacketBuilder.FramingMode.COMPACT_KV

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "KinBeacon::BroadcastWakeLock")
        
        val bluetoothManager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        bluetoothAdapter = bluetoothManager.adapter
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_START) {
            val modeName = intent.getStringExtra(EXTRA_FRAMING_MODE) ?: NrfBlePacketBuilder.FramingMode.COMPACT_KV.name
            currentMode = NrfBlePacketBuilder.FramingMode.valueOf(modeName)
            
            startForegroundServiceWithNotification()
            wakeLock?.acquire(10 * 60 * 1000L /*10 minutes max just in case*/)
            
            startBroadcastingLoop()
        } else if (intent?.action == ACTION_STOP) {
            stopBroadcastingLoop()
            stopSelf()
        }
        
        return START_STICKY
    }

    private fun startForegroundServiceWithNotification() {
        val notification = createNotification("Initializing BLE...")
        
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }
    
    private fun createNotification(content: String): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("KinBeacon Broadcasting")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.ic_secure) // Replace with your icon
            .setOngoing(true)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "BLE Advertising",
                NotificationManager.IMPORTANCE_LOW
            )
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    private fun startBroadcastingLoop() {
        tickJob?.cancel()
        
        if (bluetoothAdapter?.isEnabled == false) {
            Log.e(TAG, "Bluetooth is disabled")
            broadcastTelemetry(radioState = "ERROR_BT_DISABLED")
            return
        }

        val advertiser = try {
            bluetoothAdapter?.bluetoothLeAdvertiser
        } catch (_: SecurityException) {
            null
        }
        if (advertiser == null) {
            Log.e(TAG, "BLE Advertiser not supported")
            broadcastTelemetry(radioState = "ERROR_NO_ADVERTISER")
            return
        }

        tickJob = serviceScope.launch {
            var lastCounter = -1L
            
            while (isActive) {
                try {
                    val rpiResult = CryptoKeyManager.computeCurrentRpiToken()
                    
                    if (rpiResult.counter != lastCounter) {
                        lastCounter = rpiResult.counter
                        
                        val payload = NrfBlePacketBuilder.buildPayload(rpiResult, currentMode)
                        val adData = AdvertiseData.Builder()
                            .setIncludeDeviceName(false)
                            .setIncludeTxPowerLevel(false)
                            .addManufacturerData(NrfBlePacketBuilder.COMPANY_ID, payload)
                            .build()
                            
                        val rawPdu = NrfBlePacketBuilder.computeRawHexPdu(payload)
                        
                        // Update BLE Radio
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !legacyUsingFallback) {
                            if (activeAdvertisingSet == null) {
                                val isExtended = currentMode == NrfBlePacketBuilder.FramingMode.EXTENDED_JSON
                                val supportExtended = bluetoothAdapter?.isLeExtendedAdvertisingSupported == true
                                val useLegacyMode = !(isExtended && supportExtended)
                                
                                val parameters = AdvertisingSetParameters.Builder()
                                    .setLegacyMode(useLegacyMode)
                                    .setConnectable(false)
                                    .setScannable(false)
                                    .setInterval(AdvertisingSetParameters.INTERVAL_LOW) // 100ms
                                    .setTxPowerLevel(AdvertisingSetParameters.TX_POWER_HIGH)
                                    .build()
                                    
                                try {
                                    advertiser.startAdvertisingSet(parameters, adData, null, null, null, advertisingSetCallback)
                                } catch (e: SecurityException) {
                                    Log.e(TAG, "SecurityException: Missing BLE permissions", e)
                                    broadcastTelemetry(radioState = "ERROR_NO_PERMISSION")
                                } catch (e: IllegalArgumentException) {
                                    Log.e(TAG, "IllegalArgumentException starting advertising set", e)
                                    broadcastTelemetry(radioState = "ERROR_ILLEGAL_ARG")
                                }
                            } else {
                                try {
                                    activeAdvertisingSet?.setAdvertisingData(adData)
                                } catch (e: SecurityException) {
                                    Log.e(TAG, "SecurityException updating advertiser data", e)
                                }
                            }
                        } else {
                            legacyUsingFallback = true
                            try {
                                advertiser.stopAdvertising(legacyAdvertiseCallback)
                            } catch (e: SecurityException) {
                                Log.e(TAG, "SecurityException stopping legacy advertiser", e)
                            }
                            
                            val settings = AdvertiseSettings.Builder()
                                .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
                                .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
                                .setConnectable(false)
                                .build()
                            
                            try {
                                advertiser.startAdvertising(settings, adData, legacyAdvertiseCallback)
                            } catch (e: SecurityException) {
                                Log.e(TAG, "SecurityException: Missing BLE permissions", e)
                                broadcastTelemetry(radioState = "ERROR_NO_PERMISSION")
                            } catch (e: IllegalArgumentException) {
                                Log.e(TAG, "IllegalArgumentException starting legacy advertiser", e)
                                broadcastTelemetry(radioState = "ERROR_ILLEGAL_ARG")
                            }
                        }
                        
                        // Update Notification
                        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
                        manager.notify(NOTIFICATION_ID, createNotification("ID: ${rpiResult.hexString}"))
                        
                        // Broadcast Telemetry
                        broadcastTelemetry(
                            rpiResult.hexString,
                            rpiResult.base64String,
                            rawPdu,
                            rpiResult.counter,
                            rpiResult.executionTimeUs,
                            if (legacyUsingFallback) "ACTIVE (LEGACY)" else "ACTIVE (SET)"
                        )
                    }
                    
                    val remainingMs = CryptoKeyManager.getNextBoundaryMs() - System.currentTimeMillis()
                    val delayMs = maxOf(0L, minOf(remainingMs, 100L))
                    delay(delayMs)
                    
                } catch (e: kotlinx.coroutines.CancellationException) {
                    throw e
                } catch (e: Exception) {
                    Log.e(TAG, "Error in broadcast loop", e)
                    delay(1000) // Backoff on error
                }
            }
        }
    }

    private fun stopBroadcastingLoop() {
        tickJob?.cancel()
        
        try {
            val advertiser = try {
                 bluetoothAdapter?.bluetoothLeAdvertiser
            } catch (_: SecurityException) {
                null
            }
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && activeAdvertisingSet != null) {
                    advertiser?.stopAdvertisingSet(advertisingSetCallback)
                    activeAdvertisingSet = null
                } else if (legacyUsingFallback) {
                    advertiser?.stopAdvertising(legacyAdvertiseCallback)
                }
            } catch (e: SecurityException) {
                 Log.e(TAG, "SecurityException stopping advertiser", e)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error stopping advertiser", e)
        }
        
        broadcastTelemetry(radioState = "STOPPED")
    }

    private val advertisingSetCallback = object : AdvertisingSetCallback() {
        override fun onAdvertisingSetStarted(advertisingSet: AdvertisingSet?, txPower: Int, status: Int) {
            if (status == ADVERTISE_SUCCESS) {
                activeAdvertisingSet = advertisingSet
                Log.d(TAG, "Advertising set started")
            } else {
                Log.e(TAG, "Advertising set start failed: $status. Falling back to legacy.")
                legacyUsingFallback = true
                activeAdvertisingSet = null
                // Loop will pick up legacy mode on next tick
            }
        }
    }
    
    private val legacyAdvertiseCallback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
            Log.d(TAG, "Legacy advertising started")
        }
        override fun onStartFailure(errorCode: Int) {
            Log.e(TAG, "Legacy advertising failed: $errorCode")
        }
    }
    
    private fun broadcastTelemetry(
        hexId: String = "",
        base64Id: String = "",
        rawPdu: String = "",
        counter: Long = 0L,
        execTimeUs: Long = 0L,
        radioState: String
    ) {
        val intent = Intent(ACTION_TELEMETRY).apply {
            setPackage(packageName)
            putExtra(EXTRA_DEVICE_ID_HEX, hexId)
            putExtra(EXTRA_DEVICE_ID_JSON, "{\"device_id\":\"$base64Id\"}")
            putExtra(EXTRA_RAW_PDU, rawPdu)
            putExtra(EXTRA_COUNTER, counter)
            putExtra(EXTRA_EXECUTION_TIME_US, execTimeUs)
            putExtra(EXTRA_RADIO_STATE, radioState)
        }
        sendBroadcast(intent)
    }

    override fun onDestroy() {
        super.onDestroy()
        stopBroadcastingLoop()
        if (wakeLock?.isHeld == true) {
            wakeLock?.release()
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
