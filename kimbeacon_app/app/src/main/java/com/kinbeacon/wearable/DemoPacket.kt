package com.kinbeacon.wearable

import java.nio.ByteBuffer
import kotlin.math.abs
import kotlin.math.roundToInt

internal const val DEMO_CONTROL = 0xFFFE
internal const val DEMO_UPLINK = 0xFFFD
internal const val DEMO_HEARTBEAT_COMPANY = 0xFFFF
internal val demoHeartbeat = "kb-demo-child".encodeToByteArray()

internal data class DemoPoint(val lat: Double, val lon: Double)

internal enum class DemoType(val length: Int) {
    FIND_REQ(5), FIND_TARGET(6), LOCATE_ME(5), NEIGHBOR_LOC(14), LOC_RESULT(14), LOC_UPLINK(13)
}

internal data class DemoPacket(
    val type: DemoType,
    val incidentId: Int,
    val ttl: Int,
    val point: DemoPoint? = null,
    val action: Int = 0,
    val rssi: Int = 0,
    val radius: Int = 10,
    val landmark: Int = 0
) {
    val company: Int get() = if (type == DemoType.LOC_UPLINK) DEMO_UPLINK else DEMO_CONTROL

    fun encode(): ByteArray {
        val bytes = ByteBuffer.allocate(type.length)
        bytes.put(type.ordinal.toByte()).putShort(incidentId.toShort()).put(ttl.toByte())
        if (type != DemoType.LOC_RESULT) bytes.put(1)
        if (point != null) {
            bytes.putInt((point.lat * 1e7).roundToInt()).putInt((point.lon * 1e7).roundToInt())
        }
        when (type) {
            DemoType.FIND_TARGET -> bytes.put(action.toByte())
            DemoType.NEIGHBOR_LOC -> bytes.put(rssi.toByte())
            DemoType.LOC_RESULT -> bytes.put(radius.toByte()).put(landmark.toByte())
            else -> Unit
        }
        return bytes.array()
    }

    companion object {
        fun decode(company: Int, payload: ByteArray): DemoPacket? {
            if (payload.size < 4) return null
            val bytes = ByteBuffer.wrap(payload)
            val type = DemoType.entries.getOrNull(bytes.get().toInt()) ?: return null
            if (payload.size != type.length) return null
            if (company != if (type == DemoType.LOC_UPLINK) DEMO_UPLINK else DEMO_CONTROL) return null
            val id = bytes.short.toInt() and 0xffff
            val ttl = bytes.get().toInt()
            if (ttl !in 1..2 || (type != DemoType.LOC_RESULT && bytes.get().toInt() != 1)) return null

            return when (type) {
                DemoType.FIND_REQ -> DemoPacket(type, id, ttl)
                DemoType.FIND_TARGET -> {
                    val action = bytes.get().toInt()
                    if (action !in 0..1 || (action == 1 && ttl != 1)) return null
                    DemoPacket(type, id, ttl, action = action)
                }
                DemoType.LOCATE_ME -> if (ttl == 1) DemoPacket(type, id, ttl) else null
                DemoType.NEIGHBOR_LOC, DemoType.LOC_RESULT, DemoType.LOC_UPLINK -> {
                    val point = DemoPoint(bytes.int / 1e7, bytes.int / 1e7)
                    if (abs(point.lat) > 90 || abs(point.lon) > 180) return null
                    when (type) {
                        DemoType.LOC_RESULT -> {
                            val radius = bytes.get().toInt()
                            val landmark = bytes.get().toInt()
                            if (radius != 10 || landmark !in 0..1) return null
                            DemoPacket(type, id, ttl, point, radius = radius, landmark = landmark)
                        }
                        DemoType.NEIGHBOR_LOC -> if (ttl == 1) {
                            DemoPacket(type, id, ttl, point, rssi = bytes.get().toInt())
                        } else null
                        else -> if (ttl == 1) DemoPacket(type, id, ttl, point) else null
                    }
                }
            }
        }
    }
}
