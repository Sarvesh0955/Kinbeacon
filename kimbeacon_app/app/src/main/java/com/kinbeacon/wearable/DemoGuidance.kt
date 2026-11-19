package com.kinbeacon.wearable

import android.content.Context
import android.graphics.Paint
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import android.view.Surface
import android.view.WindowManager
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlin.math.abs
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.roundToInt

@Composable
internal fun DemoMap(venue: DemoVenue, result: DemoLocation) {
    val background = MaterialTheme.colorScheme.surfaceVariant
    val line = MaterialTheme.colorScheme.outline
    val text = MaterialTheme.colorScheme.onSurfaceVariant
    val primary = MaterialTheme.colorScheme.primary
    val secondary = MaterialTheme.colorScheme.secondary
    Text(venue.name, style = MaterialTheme.typography.titleMedium)
    Text("Venue map · north is up")
    Canvas(Modifier.fillMaxWidth().height(240.dp)) {
        val inset = 20.dp.toPx()
        val widthMeters = (venue.northEast.lon - venue.southWest.lon) * 111_195 *
            cos(Math.toRadians(venue.southWest.lat))
        val heightMeters = (venue.northEast.lat - venue.southWest.lat) * 111_195
        val scale = min((size.width - inset * 2) / widthMeters, (size.height - inset * 2) / heightMeters)
        val width = (widthMeters * scale).toFloat()
        val height = (heightMeters * scale).toFloat()
        val origin = Offset((size.width - width) / 2, (size.height - height) / 2)
        fun map(point: DemoPoint): Offset {
            val dx = (point.lon - venue.southWest.lon) / (venue.northEast.lon - venue.southWest.lon)
            val dy = (venue.northEast.lat - point.lat) / (venue.northEast.lat - venue.southWest.lat)
            return origin + Offset((dx * width).toFloat(), (dy * height).toFloat())
        }
        val bounds = Size(width, height)
        drawRect(background, origin, bounds)
        drawRect(line, origin, bounds, style = Stroke(1.dp.toPx()))
        val target = map(result.point)
        if (target.x in origin.x..origin.x + width && target.y in origin.y..origin.y + height) {
            val radius = (result.radius * scale).toFloat()
            drawCircle(primary.copy(alpha = 0.24f), radius, target)
            drawCircle(primary, radius, target, style = Stroke(1.5.dp.toPx()))
            drawCircle(primary, 5.dp.toPx(), target)
        }
        val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = text.toArgb()
            textSize = 11.dp.toPx()
        }
        (venue.landmarks + DemoLandmark("Start", venue.guardian)).forEach { marker ->
            val position = map(marker.point)
            drawCircle(secondary, 3.dp.toPx(), position)
            drawIntoCanvas {
                it.nativeCanvas.drawText(marker.name, (position.x + 5.dp.toPx())
                    .coerceAtMost(size.width - paint.measureText(marker.name)), position.y - 6.dp.toPx(), paint)
            }
        }
    }
}

@Composable
internal fun DemoGuidance(venue: DemoVenue, result: DemoLocation, interference: Boolean) {
    val heading = rememberDemoHeading(!interference)
    val (distance, bearing) = distanceAndBearing(venue.guardian, result.point)
    Text("About ${distance.roundToInt()} m from the venue start")
    if (heading == null) {
        Text("Heading unavailable · use the map and walk toward ${result.landmark}.")
    } else {
        val turn = shortestTurn(bearing - heading)
        Text(when {
            abs(turn) < 22.5 -> "Walk straight"
            abs(turn) >= 135 -> "Turn around"
            turn < 0 -> "Turn left"
            else -> "Turn right"
        }, style = MaterialTheme.typography.titleLarge)
        val color = MaterialTheme.colorScheme.primary
        Canvas(Modifier.size(104.dp)) {
            rotate(turn.toFloat()) {
                val path = Path().apply {
                    moveTo(center.x, size.height * 0.12f)
                    lineTo(size.width * 0.83f, size.height * 0.56f)
                    lineTo(size.width * 0.60f, size.height * 0.50f)
                    lineTo(size.width * 0.60f, size.height * 0.86f)
                    lineTo(size.width * 0.40f, size.height * 0.86f)
                    lineTo(size.width * 0.40f, size.height * 0.50f)
                    lineTo(size.width * 0.17f, size.height * 0.56f)
                    close()
                }
                drawPath(path, color)
            }
        }
    }
}

@Composable
private fun rememberDemoHeading(enabled: Boolean): Double? {
    val context = LocalContext.current
    var heading by remember { mutableStateOf<Double?>(null) }
    DisposableEffect(enabled, context) {
        val manager = context.getSystemService(SensorManager::class.java)
        val sensor = manager?.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR)
        val matrix = FloatArray(9)
        val displayMatrix = FloatArray(9)
        val angles = FloatArray(3)
        val listener = object : SensorEventListener {
            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {
                if (accuracy < SensorManager.SENSOR_STATUS_ACCURACY_MEDIUM) heading = null
            }

            @Suppress("DEPRECATION")
            override fun onSensorChanged(event: SensorEvent) {
                if (event.accuracy < SensorManager.SENSOR_STATUS_ACCURACY_MEDIUM ||
                    (event.values.size > 4 && event.values[4] > 0.8f)) {
                    heading = null
                    return
                }
                SensorManager.getRotationMatrixFromVector(matrix, event.values)
                val rotation = (context.getSystemService(Context.WINDOW_SERVICE) as WindowManager)
                    .defaultDisplay.rotation
                val (x, y) = when (rotation) {
                    Surface.ROTATION_90 -> SensorManager.AXIS_Y to SensorManager.AXIS_MINUS_X
                    Surface.ROTATION_180 -> SensorManager.AXIS_MINUS_X to SensorManager.AXIS_MINUS_Y
                    Surface.ROTATION_270 -> SensorManager.AXIS_MINUS_Y to SensorManager.AXIS_X
                    else -> SensorManager.AXIS_X to SensorManager.AXIS_Y
                }
                SensorManager.remapCoordinateSystem(matrix, x, y, displayMatrix)
                SensorManager.getOrientation(displayMatrix, angles)
                val sample = Math.toDegrees(angles[0].toDouble())
                heading = heading?.let { shortestTurn(it + shortestTurn(sample - it) * 0.22) } ?: sample
            }
        }
        if (enabled && sensor != null) manager?.registerListener(listener, sensor, SensorManager.SENSOR_DELAY_UI)
        onDispose {
            manager?.unregisterListener(listener)
            heading = null
        }
    }
    return if (enabled) heading else null
}
