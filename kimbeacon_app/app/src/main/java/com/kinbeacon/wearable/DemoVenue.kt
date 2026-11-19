package com.kinbeacon.wearable

import android.content.Context
import org.json.JSONObject
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.hypot

internal data class DemoLandmark(val name: String, val point: DemoPoint)
internal data class DemoVenue(
    val name: String,
    val guardian: DemoPoint,
    val wearable: DemoPoint,
    val relay: DemoPoint,
    val southWest: DemoPoint,
    val northEast: DemoPoint,
    val landmarks: List<DemoLandmark>
) {
    companion object {
        fun load(context: Context): DemoVenue {
            val json = JSONObject(context.assets.open("demo_venue.json").bufferedReader().use { it.readText() })
            fun point(data: JSONObject, key: String): DemoPoint {
                val values = data.getJSONArray(key)
                return DemoPoint(values.getDouble(0), values.getDouble(1))
            }
            val bounds = json.getJSONArray("bounds")
            val landmarks = json.getJSONArray("landmarks")
            return DemoVenue(
                json.getString("name"), point(json, "guardian"), point(json, "wearable"), point(json, "relay"),
                DemoPoint(bounds.getDouble(0), bounds.getDouble(1)),
                DemoPoint(bounds.getDouble(2), bounds.getDouble(3)),
                List(landmarks.length()) {
                    val item = landmarks.getJSONObject(it)
                    DemoLandmark(item.getString("name"), point(item, "point"))
                }
            )
        }
    }
}

internal fun shortestTurn(degrees: Double): Double = ((degrees % 360 + 540) % 360) - 180

internal fun distanceAndBearing(from: DemoPoint, to: DemoPoint): Pair<Double, Double> {
    val north = (to.lat - from.lat) * 111_195
    val east = (to.lon - from.lon) * 111_195 * cos(Math.toRadians(from.lat))
    return hypot(north, east) to Math.toDegrees(atan2(east, north))
}
