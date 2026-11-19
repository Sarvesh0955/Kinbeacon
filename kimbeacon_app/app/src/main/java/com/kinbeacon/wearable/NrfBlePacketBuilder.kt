package com.kinbeacon.wearable

object NrfBlePacketBuilder {
    
    const val COMPANY_ID = 0xFFFF

    enum class FramingMode(val displayName: String) {
        COMPACT_KV("Compact KV (19B)"),
        LEGACY_JSON("Legacy JSON Base64 (27B)"),
        EXTENDED_JSON("Extended Full JSON (32B)")
    }

    fun buildPayload(rpiResult: CryptoKeyManager.RpiResult, mode: FramingMode): ByteArray {
        val payloadStr = when (mode) {
            FramingMode.COMPACT_KV -> rpiResult.hexString
            FramingMode.LEGACY_JSON -> "{\"device_id\":\"${rpiResult.base64String}\"}"
            FramingMode.EXTENDED_JSON -> "{\"device_id\":\"${rpiResult.hexString}\"}"
        }
        return payloadStr.toByteArray(Charsets.UTF_8)
    }

    fun computeRawHexPdu(payload: ByteArray): String {
        val length = payload.size + 3 // 1 byte for AD type, 2 bytes for Company ID
        val adType = 0xFF // Manufacturer Specific Data
        
        val pduBytes = ByteArray(length + 1)
        pduBytes[0] = length.toByte()
        pduBytes[1] = adType.toByte()
        // Little Endian for Company ID (0xFFFF is FF FF, so it's the same)
        pduBytes[2] = (COMPANY_ID and 0xFF).toByte()
        pduBytes[3] = ((COMPANY_ID shr 8) and 0xFF).toByte()
        
        System.arraycopy(payload, 0, pduBytes, 4, payload.size)
        
        return pduBytes.joinToString("") { "%02X".format(it) }
    }
}
