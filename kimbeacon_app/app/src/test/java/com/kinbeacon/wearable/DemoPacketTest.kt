package com.kinbeacon.wearable

import org.junit.Assert.*
import org.junit.Test

class DemoPacketTest {
    @Test
    fun sharedPacketsRoundTripAndRejectMalformedFrames() {
        val fixtures = requireNotNull(javaClass.getResourceAsStream("/demo_packets.txt"))
            .bufferedReader().use { it.readLines() }
        assertEquals(DemoType.entries.size, fixtures.size)
        fixtures.forEachIndexed { index, line ->
            val (company, hex) = line.split(" ")
            val id = company.toInt(16)
            val payload = hex.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
            val packet = requireNotNull(DemoPacket.decode(id, payload))
            assertEquals(DemoType.entries[index], packet.type)
            assertEquals(0xbeef, packet.incidentId)
            assertArrayEquals(payload, packet.encode())
            assertNull(DemoPacket.decode(id, payload.copyOf(payload.size - 1)))
            assertNull(DemoPacket.decode(DEMO_HEARTBEAT_COMPANY, payload))
            if (packet.type in setOf(DemoType.NEIGHBOR_LOC, DemoType.LOC_RESULT, DemoType.LOC_UPLINK)) {
                assertEquals(DemoPoint(12.00024, -77.00018), packet.point)
                val invalid = payload.clone()
                invalid[if (packet.type == DemoType.LOC_RESULT) 4 else 5] = 0x7f
                assertNull(DemoPacket.decode(id, invalid))
            }
        }
    }

    @Test
    fun headingUsesShortestArcAcrossNorth() {
        assertEquals(2.0, shortestTurn(1.0 - 359.0), 1e-9)
        assertEquals(-2.0, shortestTurn(359.0 - 1.0), 1e-9)
    }
}
