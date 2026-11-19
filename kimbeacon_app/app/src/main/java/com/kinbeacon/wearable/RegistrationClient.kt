package com.kinbeacon.wearable

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL

object RegistrationClient {
    private const val TAG = "RegistrationClient"
    private const val TIMEOUT_MS = 5000

    suspend fun register(serverUrl: String, clientPubKeyBase64: String): RegistrationResult = withContext(Dispatchers.IO) {
        val tSend = System.currentTimeMillis()
        var connection: HttpURLConnection? = null
        
        try {
            val url = URL("$serverUrl/api/register")
            connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.connectTimeout = TIMEOUT_MS
            connection.readTimeout = TIMEOUT_MS
            connection.doOutput = true
            connection.doInput = true

            val requestJson = JSONObject().apply {
                put("client_pub_key", clientPubKeyBase64)
                put("cipher_suite", "AES-128-ECB-TRUNC64")
            }

            OutputStreamWriter(connection.outputStream).use { writer ->
                writer.write(requestJson.toString())
                writer.flush()
            }

            val responseCode = connection.responseCode
            val tRecv = System.currentTimeMillis()
            
            if (responseCode == HttpURLConnection.HTTP_OK) {
                val responseString = connection.inputStream.bufferedReader().use { it.readText() }
                val responseJson = JSONObject(responseString)
                
                val deviceId = responseJson.optString("device_id").takeIf { it.isNotEmpty() }
                    ?: responseJson.getString("permanent_id")
                val serverPubKey = responseJson.getString("server_pub_key")
                val serverTimeMs = responseJson.getLong("server_time_ms")
                val rotationInterval = responseJson.optInt("rotation_interval_sec", 3)

                RegistrationResult.Success(deviceId, serverPubKey, serverTimeMs, rotationInterval, tSend, tRecv)
            } else {
                RegistrationResult.Error("HTTP Error: $responseCode")
            }

        } catch (e: Exception) {
            Log.e(TAG, "Registration failed", e)
            RegistrationResult.Error(e.message ?: "Unknown network error")
        } finally {
            connection?.disconnect()
        }
    }

    suspend fun overrideZone(serverUrl: String, currentDeviceIdHex: String, targetZone: String): Boolean = withContext(Dispatchers.IO) {
        var connection: HttpURLConnection? = null
        try {
            val url = URL("$serverUrl/api/override_zone")
            connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.setRequestProperty("Content-Type", "application/json")
            connection.connectTimeout = TIMEOUT_MS
            connection.readTimeout = TIMEOUT_MS
            connection.doOutput = true

            val requestJson = JSONObject().apply {
                put("device_id", currentDeviceIdHex)
                put("override_zone", targetZone)
            }

            OutputStreamWriter(connection.outputStream).use { writer ->
                writer.write(requestJson.toString())
                writer.flush()
            }

            connection.responseCode == HttpURLConnection.HTTP_OK
        } catch (e: Exception) {
            Log.e(TAG, "Zone override failed", e)
            false
        } finally {
            connection?.disconnect()
        }
    }
}

sealed class RegistrationResult {
    data class Success(
        val deviceId: String,
        val serverPubKeyBase64: String,
        val serverTimeMs: Long,
        val rotationIntervalSec: Int,
        val tSend: Long,
        val tRecv: Long
    ) : RegistrationResult()
    
    data class Error(val message: String) : RegistrationResult()
}
