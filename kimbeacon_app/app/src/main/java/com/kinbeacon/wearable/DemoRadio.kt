package com.kinbeacon.wearable

import android.annotation.SuppressLint
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanFilter
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

internal fun demoAdvertiseData(company: Int, payload: ByteArray): AdvertiseData =
    AdvertiseData.Builder().addManufacturerData(company, payload).build()

internal fun demoAdvertiseSettings(): AdvertiseSettings = AdvertiseSettings.Builder()
    .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
    .setConnectable(false)
    .build()

@SuppressLint("MissingPermission")
internal class DemoRadio(
    context: Context,
    scope: CoroutineScope,
    private val error: (String) -> Unit,
    private val receive: (ScanResult) -> Unit
) {
    private data class Burst(
        val packet: DemoPacket,
        val duration: Long,
        val onStarted: () -> Unit,
        val valid: () -> Boolean
    )

    private val adapter = context.getSystemService(BluetoothManager::class.java)?.adapter
    private val scanner = runCatching { adapter?.bluetoothLeScanner }.getOrNull()
    private val advertiser = runCatching { adapter?.bluetoothLeAdvertiser }.getOrNull()
    private val outgoing = Channel<Burst>(16)
    private val callback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) = receive(result)
        override fun onScanFailed(errorCode: Int) = error("BLE scan failed ($errorCode)")
    }
    private val job = scope.launch {
        for (burst in outgoing) {
            if (burst.valid()) transmit(burst)
        }
    }

    init {
        val filters = listOf(
            ScanFilter.Builder().setManufacturerData(DEMO_HEARTBEAT_COMPANY, demoHeartbeat).build(),
            ScanFilter.Builder().setManufacturerData(DEMO_CONTROL, byteArrayOf()).build()
        )
        if (scanner == null) {
            error("Turn on Bluetooth to scan")
        } else {
            runCatching {
                scanner.startScan(filters, ScanSettings.Builder()
                    .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build(), callback)
            }.onFailure { error("BLE scan unavailable") }
        }
    }

    fun send(
        packet: DemoPacket,
        duration: Long = 800,
        onStarted: () -> Unit = {},
        valid: () -> Boolean = { true }
    ) {
        if (outgoing.trySend(Burst(packet, duration, onStarted, valid)).isFailure) {
            error("BLE transmit queue full")
        }
    }

    private suspend fun transmit(burst: Burst) {
        val transmitter: BluetoothLeAdvertiser = advertiser ?: run {
            error("BLE advertising unavailable")
            return
        }
        var callback: AdvertiseCallback? = null
        try {
            val status = withTimeoutOrNull(1200) {
                suspendCancellableCoroutine<Int> { continuation ->
                    val listener = object : AdvertiseCallback() {
                        override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
                            if (continuation.isActive) continuation.resume(0)
                        }

                        override fun onStartFailure(errorCode: Int) {
                            if (continuation.isActive) continuation.resume(errorCode)
                        }
                    }
                    callback = listener
                    transmitter.startAdvertising(
                        demoAdvertiseSettings(),
                        demoAdvertiseData(burst.packet.company, burst.packet.encode()),
                        listener
                    )
                }
            }
            if (status == 0) {
                burst.onStarted()
                delay(burst.duration)
            } else error("BLE advertising failed" + (status?.let { " ($it)" } ?: " to start"))
        } catch (_: SecurityException) {
            error("Bluetooth permission required")
        } catch (_: IllegalStateException) {
            error("Turn on Bluetooth to advertise")
        } finally {
            callback?.let { runCatching { transmitter.stopAdvertising(it) } }
        }
    }

    fun close() {
        outgoing.close()
        job.cancel()
        runCatching { scanner?.stopScan(callback) }
    }
}
