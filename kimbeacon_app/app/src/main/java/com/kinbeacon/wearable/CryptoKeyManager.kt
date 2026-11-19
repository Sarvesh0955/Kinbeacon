package com.kinbeacon.wearable

import android.content.Context
import android.content.SharedPreferences
import android.util.Base64
import java.nio.ByteBuffer
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.X509EncodedKeySpec
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.spec.SecretKeySpec

object CryptoKeyManager {
    private const val PREFS_NAME = "KinBeaconPrefs"
    private const val KEY_SHARED_SECRET = "shared_secret"
    private const val KEY_CLOCK_OFFSET = "clock_offset"
    private const val KEY_INITIAL_DEVICE_ID = "initial_device_id"
    private const val KEY_ROTATION_INTERVAL = "rotation_interval"

    private var sharedSecret: ByteArray? = null
    
    fun getSharedSecretHex(): String? {
        return sharedSecret?.joinToString("") { "%02x".format(it) }?.take(16)
    }

    var clockOffsetMs: Long = 0
        private set
    var rotationIntervalSec: Int = 3
        private set
    var initialDeviceId: String? = null
        private set

    lateinit var keyPair: KeyPair

    fun generateKeyPair() {
        val kpg = KeyPairGenerator.getInstance("EC")
        kpg.initialize(ECGenParameterSpec("secp256r1"))
        keyPair = kpg.generateKeyPair()
    }

    fun getPublicKeyBase64(): String {
        return Base64.encodeToString(keyPair.public.encoded, Base64.NO_WRAP)
    }

    fun computeSharedSecret(serverPubKeyBase64: String): ByteArray {
        val serverPubKeyBytes = Base64.decode(serverPubKeyBase64, Base64.DEFAULT)
        val kf = KeyFactory.getInstance("EC")
        val serverPubKey: PublicKey = kf.generatePublic(X509EncodedKeySpec(serverPubKeyBytes))

        val ka = KeyAgreement.getInstance("ECDH")
        ka.init(keyPair.private)
        ka.doPhase(serverPubKey, true)
        val rawSecret = ka.generateSecret()

        val md = MessageDigest.getInstance("SHA-256")
        val hash = md.digest(rawSecret)
        
        sharedSecret = hash.copyOfRange(0, 16)
        return sharedSecret!!
    }

    fun computeClockOffset(tSend: Long, tRecv: Long, tServer: Long) {
        val rtt = tRecv - tSend
        clockOffsetMs = (tServer + rtt / 2) - tRecv
    }
    
    fun setOfflineDemoKey(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val existingSecret = prefs.getString("offline_demo_secret", null)
        val existingDeviceId = prefs.getString("offline_demo_device_id", null)
        
        val secretBytes = if (existingSecret != null) {
            Base64.decode(existingSecret, Base64.NO_WRAP)
        } else {
            val newSecret = ByteArray(16)
            java.security.SecureRandom().nextBytes(newSecret)
            prefs.edit().putString("offline_demo_secret", Base64.encodeToString(newSecret, Base64.NO_WRAP)).apply()
            newSecret
        }
        
        val deviceId = if (existingDeviceId != null) {
            existingDeviceId
        } else {
            val randomId = "KB-OFFLINE-" + secretBytes.take(2).joinToString("") { "%02x".format(it).uppercase() }
            prefs.edit().putString("offline_demo_device_id", randomId).apply()
            randomId
        }
        
        sharedSecret = secretBytes
        rotationIntervalSec = 3
        clockOffsetMs = 0
        initialDeviceId = deviceId
    }

    fun saveSession(context: Context, deviceId: String, interval: Int) {
        this.initialDeviceId = deviceId
        this.rotationIntervalSec = interval
        
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().apply {
            putString(KEY_SHARED_SECRET, sharedSecret?.let { Base64.encodeToString(it, Base64.NO_WRAP) })
            putLong(KEY_CLOCK_OFFSET, clockOffsetMs)
            putString(KEY_INITIAL_DEVICE_ID, initialDeviceId)
            putInt(KEY_ROTATION_INTERVAL, rotationIntervalSec)
        }.apply()
    }

    fun loadSession(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val secretStr = prefs.getString(KEY_SHARED_SECRET, null) ?: return false
        
        sharedSecret = Base64.decode(secretStr, Base64.NO_WRAP)
        clockOffsetMs = prefs.getLong(KEY_CLOCK_OFFSET, 0)
        initialDeviceId = prefs.getString(KEY_INITIAL_DEVICE_ID, null)
        rotationIntervalSec = prefs.getInt(KEY_ROTATION_INTERVAL, 3)
        return true
    }

    fun clearSession(context: Context) {
        sharedSecret = null
        clockOffsetMs = 0
        initialDeviceId = null
        rotationIntervalSec = 3
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE).edit().clear().apply()
    }

    fun getCurrentCounter(): Long {
        // Keep the token constant for now by freezing the counter
        return 0L
        // val syncTime = System.currentTimeMillis() + clockOffsetMs
        // return syncTime / (rotationIntervalSec * 1000L)
    }
    
    fun getNextBoundaryMs(): Long {
        val syncTime = System.currentTimeMillis() + clockOffsetMs
        val periodMs = rotationIntervalSec * 1000L
        val currentT = syncTime / periodMs
        val nextBoundarySyncTime = (currentT + 1) * periodMs
        val nextBoundaryLocalTime = nextBoundarySyncTime - clockOffsetMs
        return nextBoundaryLocalTime
    }

    fun computeCurrentRpiToken(counter: Long = getCurrentCounter()): RpiResult {
        val secret = sharedSecret ?: throw IllegalStateException("Shared secret not established")
        val startTime = System.nanoTime()

        val plaintext = ByteBuffer.allocate(16)
        plaintext.putLong(0L)
        plaintext.putLong(counter)

        val cipher = Cipher.getInstance("AES/ECB/NoPadding")
        val secretKeySpec = SecretKeySpec(secret, "AES")
        cipher.init(Cipher.ENCRYPT_MODE, secretKeySpec)
        
        val ciphertext = cipher.doFinal(plaintext.array())
        
        // 64-bit truncation
        val rpi = ciphertext.copyOfRange(0, 8)
        
        val executionTimeUs = (System.nanoTime() - startTime) / 1000
        
        val hexString = "kb-" + rpi.joinToString("") { "%02x".format(it) }
        val base64String = "kb-" + Base64.encodeToString(rpi, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)

        return RpiResult(rpi, hexString, base64String, executionTimeUs, counter)
    }
    
    data class RpiResult(
        val rpiBytes: ByteArray,
        val hexString: String,
        val base64String: String,
        val executionTimeUs: Long,
        val counter: Long
    ) {
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (javaClass != other?.javaClass) return false

            other as RpiResult

            if (!rpiBytes.contentEquals(other.rpiBytes)) return false
            if (hexString != other.hexString) return false
            if (base64String != other.base64String) return false
            if (executionTimeUs != other.executionTimeUs) return false
            if (counter != other.counter) return false

            return true
        }

        override fun hashCode(): Int {
            var result = rpiBytes.contentHashCode()
            result = 31 * result + hexString.hashCode()
            result = 31 * result + base64String.hashCode()
            result = 31 * result + executionTimeUs.hashCode()
            result = 31 * result + counter.hashCode()
            return result
        }
    }
}
