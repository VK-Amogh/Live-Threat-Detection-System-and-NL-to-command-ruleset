package com.safespace.safespace_mobile

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.ImageFormat
import android.graphics.Rect
import android.graphics.YuvImage
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Build
import androidx.core.content.ContextCompat
import android.view.WindowManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.ByteArrayOutputStream
import java.net.Inet4Address
import java.net.NetworkInterface

class MainActivity : FlutterActivity() {
    private val jpegChannel = "safespace/jpeg"
    private val networkChannel = "safespace/network"
    private val linksChannel = "safespace/links"
    private val screenChannel = "safespace/screen"
    private val alertsChannel = "safespace/alerts"

    private var links: MethodChannel? = null
    private var launchLink: String? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        val messenger = flutterEngine.dartExecutor.binaryMessenger

        // NV21 camera frame -> upright JPEG, on this side because Dart is too slow to do it per frame.
        MethodChannel(messenger, jpegChannel).setMethodCallHandler { call, result ->
            if (call.method != "nv21ToJpeg") {
                result.notImplemented()
                return@setMethodCallHandler
            }
            try {
                val nv21 = call.argument<ByteArray>("nv21")
                val width = call.argument<Int>("width") ?: 640
                val height = call.argument<Int>("height") ?: 480
                val quality = call.argument<Int>("quality") ?: 72
                val rotation = call.argument<Int>("rotation") ?: 0
                if (nv21 == null || nv21.size < width * height * 3 / 2) {
                    result.error("INVALID_ARGS", "NV21 frame is missing or too small", null)
                    return@setMethodCallHandler
                }
                val upright = rotateNv21(nv21, width, height, rotation)
                val w = if (rotation == 90 || rotation == 270) height else width
                val h = if (rotation == 90 || rotation == 270) width else height
                val cropW: Int
                val cropH: Int
                if (w * 9 > h * 16) {
                    cropW = ((h * 16) / 9) and -2
                    cropH = h and -2
                } else {
                    cropW = w and -2
                    cropH = ((w * 9) / 16) and -2
                }
                val left = ((w - cropW) / 2) and -2
                val top = ((h - cropH) / 2) and -2
                val out = ByteArrayOutputStream((cropW * cropH / 4).coerceAtLeast(1024))
                YuvImage(upright, ImageFormat.NV21, w, h, null).compressToJpeg(
                    Rect(left, top, left + cropW, top + cropH),
                    quality,
                    out,
                )
                result.success(out.toByteArray())
            } catch (e: Exception) {
                result.error("ENCODE_ERROR", e.message, null)
            }
        }

        // What the phone knows about itself. Reported to the laptop as telemetry; never used to allow or deny access.
        MethodChannel(messenger, networkChannel).setMethodCallHandler { call, result ->
            if (call.method != "getDeviceInfo") {
                result.notImplemented()
                return@setMethodCallHandler
            }
            try {
                result.success(deviceInfo())
            } catch (e: Exception) {
                result.error("INFO_ERROR", e.message, null)
            }
        }

        // safespace://pair?... links (the dashboard's QR code, scanned with the camera app).
        links = MethodChannel(messenger, linksChannel).also { channel ->
            channel.setMethodCallHandler { call, result ->
                if (call.method == "getInitialLink") {
                    result.success(launchLink)
                    launchLink = null
                } else {
                    result.notImplemented()
                }
            }
        }
        launchLink = linkFrom(intent)

        MethodChannel(messenger, alertsChannel).setMethodCallHandler { call, result ->
            when (call.method) {
                "start" -> {
                    val token = call.argument<String>("token") ?: ""
                    val urls = call.argument<ArrayList<String>>("urls") ?: arrayListOf()
                    if (token.isBlank() || urls.isEmpty()) {
                        result.error("INVALID_ARGS", "An admin pairing and a server address are required", null)
                    } else {
                        val service = Intent(this, AlertService::class.java).apply {
                            action = AlertService.ACTION_START
                            putExtra(AlertService.EXTRA_TOKEN, token)
                            putStringArrayListExtra(AlertService.EXTRA_URLS, urls)
                        }
                        ContextCompat.startForegroundService(this, service)
                        result.success(null)
                    }
                }
                "stop" -> {
                    stopService(Intent(this, AlertService::class.java))
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }

        // A camera that is streaming must keep the screen on; Stealth mode dims it instead of turning it off.
        MethodChannel(messenger, screenChannel).setMethodCallHandler { call, result ->
            when (call.method) {
                "keepAwake" -> {
                    val on = call.argument<Boolean>("on") ?: false
                    runOnUiThread {
                        if (on) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                        else window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
                    }
                    result.success(null)
                }
                "setBrightness" -> {
                    val level = call.argument<Double>("level")
                    runOnUiThread {
                        val attrs = window.attributes
                        attrs.screenBrightness = level?.toFloat() ?: WindowManager.LayoutParams.BRIGHTNESS_OVERRIDE_NONE
                        window.attributes = attrs
                    }
                    result.success(null)
                }
                else -> result.notImplemented()
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        linkFrom(intent)?.let { links?.invokeMethod("onLink", it) }
    }

    private fun linkFrom(intent: Intent?): String? {
        val data = intent?.data ?: return null
        return if (data.scheme == "safespace") data.toString() else null
    }

    private fun deviceInfo(): Map<String, Any?> {
        var ip = ""
        var iface = ""
        val interfaces = NetworkInterface.getNetworkInterfaces()
        while (interfaces != null && interfaces.hasMoreElements()) {
            val nif = interfaces.nextElement()
            if (!nif.isUp || nif.isLoopback) continue
            val addrs = nif.inetAddresses
            while (addrs.hasMoreElements()) {
                val addr = addrs.nextElement()
                if (addr is Inet4Address && !addr.isLoopbackAddress) {
                    // Prefer the Wi-Fi interface; otherwise take whatever has an address.
                    if (ip.isEmpty() || nif.name.startsWith("wlan")) {
                        ip = addr.hostAddress ?: ""
                        iface = nif.name
                    }
                }
            }
        }
        val cm = getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        val caps = cm?.getNetworkCapabilities(cm.activeNetwork)
        val onWifi = caps?.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) == true

        val bm = getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
        val batteryPct = bm?.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: 100
        val battery = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val status = battery?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val charging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        val tempC = (battery?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 340) ?: 340) / 10.0

        @Suppress("DEPRECATION")
        val rssi = (applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager)?.connectionInfo?.rssi

        return mapOf(
            "device_model" to "${Build.MANUFACTURER} ${Build.MODEL}",
            "os_version" to "Android ${Build.VERSION.RELEASE}",
            "local_ip" to ip,
            "interface_name" to iface,
            "on_wifi" to onWifi,
            "battery_pct" to batteryPct,
            "is_charging" to charging,
            "temp_c" to tempC,
            "wifi_rssi" to rssi,
        )
    }

    /** Rotate an NV21 frame clockwise by 0/90/180/270 degrees (luma plane, then the interleaved VU plane). */
    private fun rotateNv21(src: ByteArray, w: Int, h: Int, rotation: Int): ByteArray {
        if (rotation == 0) return src
        val ySize = w * h
        val out = ByteArray(ySize + ySize / 2)
        var i = 0
        when (rotation) {
            90 -> {
                for (x in 0 until w) for (y in h - 1 downTo 0) out[i++] = src[y * w + x]
                i = ySize
                var x = 0
                while (x < w) {
                    for (y in h / 2 - 1 downTo 0) {
                        out[i++] = src[ySize + y * w + x]
                        out[i++] = src[ySize + y * w + x + 1]
                    }
                    x += 2
                }
            }
            180 -> {
                for (k in 0 until ySize) out[k] = src[ySize - 1 - k]
                val chroma = ySize / 2
                var k = 0
                while (k < chroma) {
                    out[ySize + k] = src[ySize + chroma - 2 - k]
                    out[ySize + k + 1] = src[ySize + chroma - 1 - k]
                    k += 2
                }
            }
            270 -> {
                for (x in w - 1 downTo 0) for (y in 0 until h) out[i++] = src[y * w + x]
                i = ySize
                var x = w - 2
                while (x >= 0) {
                    for (y in 0 until h / 2) {
                        out[i++] = src[ySize + y * w + x]
                        out[i++] = src[ySize + y * w + x + 1]
                    }
                    x -= 2
                }
            }
            else -> return src
        }
        return out
    }
}
