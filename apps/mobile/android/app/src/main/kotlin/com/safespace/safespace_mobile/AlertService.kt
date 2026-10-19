package com.safespace.safespace_mobile

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.SystemClock
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

/** Keeps the authenticated event feed active after the Flutter activity is closed. */
class AlertService : Service() {
    companion object {
        const val ACTION_START = "safespace.alerts.START"
        const val ACTION_STOP = "safespace.alerts.STOP"
        const val EXTRA_TOKEN = "token"
        const val EXTRA_URLS = "urls"
        private const val MONITOR_CHANNEL = "safespace_monitor"
        private const val ALERT_CHANNEL = "safespace_native_alerts"
        private const val MONITOR_ID = 1
    }

    @Volatile private var running = false
    @Volatile private var token = ""
    @Volatile private var urls = emptyList<String>()
    private var worker: Thread? = null
    private val notifications by lazy { getSystemService(NotificationManager::class.java) }
    private val state by lazy { getSharedPreferences("safespace_alert_state", MODE_PRIVATE) }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        intent?.getStringExtra(EXTRA_TOKEN)?.takeIf { it.isNotBlank() }?.let { token = it }
        intent?.getStringArrayListExtra(EXTRA_URLS)?.let { urls = it.filter { url -> url.startsWith("http://") || url.startsWith("https://") } }
        if (token.isBlank() || urls.isEmpty()) {
            stopSelf()
            return START_NOT_STICKY
        }
        createChannels()
        val notification = Notification.Builder(this, MONITOR_CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle("SafeSpace alerts are on")
            .setContentText("Watching connected cameras for new alerts")
            .setContentIntent(PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(MONITOR_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_REMOTE_MESSAGING)
        } else {
            startForeground(MONITOR_ID, notification)
        }
        if (!running) {
            running = true
            worker = Thread({ pollLoop() }, "SafeSpaceAlerts").also { it.start() }
        }
        return START_REDELIVER_INTENT
    }

    private fun createChannels() {
        notifications.createNotificationChannel(NotificationChannel(MONITOR_CHANNEL, "Alert connection", NotificationManager.IMPORTANCE_LOW))
        notifications.createNotificationChannel(NotificationChannel(ALERT_CHANNEL, "Security alerts", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "New SafeSpace rule and threat alerts"
            enableVibration(true)
        })
    }

    private fun pollLoop() {
        while (running) {
            try {
                val previous = state.getLong("seq", -1L)
                val page = fetchPage(previous.coerceAtLeast(0L))
                if (page != null) {
                    val head = page.optLong("head_seq", 0L)
                    if (previous < 0L || head < previous) {
                        // First pairing and a reset feed establish a baseline without replaying old alerts.
                        state.edit().putLong("seq", head).apply()
                    } else {
                        val items = page.optJSONArray("items")
                        if (items != null) {
                            for (index in 0 until items.length()) {
                                val event = items.optJSONObject(index) ?: continue
                                val seq = event.optLong("change_seq", previous)
                                if (seq <= state.getLong("seq", 0L)) continue
                                if (isAlert(event)) notifyAlert(event)
                                state.edit().putLong("seq", seq).apply()
                            }
                        }
                    }
                }
            } catch (_: Exception) {
                // Keep the service alive; route and connectivity can recover on the next poll.
            }
            SystemClock.sleep(5000)
        }
    }

    private fun fetchPage(after: Long): JSONObject? {
        for (base in urls) {
            var connection: HttpURLConnection? = null
            try {
                connection = URL("${base.trimEnd('/')}/api/v1/changes?after=$after&limit=200").openConnection() as HttpURLConnection
                connection.connectTimeout = 3500
                connection.readTimeout = 3500
                connection.setRequestProperty("Authorization", "Bearer $token")
                connection.setRequestProperty("Accept", "application/json")
                if (connection.responseCode == 200) {
                    return JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
                }
            } catch (_: Exception) {
            } finally {
                connection?.disconnect()
            }
        }
        return null
    }

    private fun isAlert(event: JSONObject): Boolean {
        if (event.optString("created_at") != event.optString("updated_at")) return false
        val category = event.optJSONObject("category")?.optString("key") ?: ""
        val severity = event.optString("severity")
        return category == "RULE_ALERT" || severity == "HIGH" || severity == "CRITICAL"
    }

    private fun notifyAlert(event: JSONObject) {
        val category = event.optJSONObject("category")
        val camera = event.optJSONObject("camera")
        val label = category?.optString("label")?.takeIf { it.isNotBlank() } ?: "Detection"
        val cameraName = camera?.optString("name")?.takeIf { it.isNotBlank() } ?: "camera"
        val isRule = category?.optString("key") == "RULE_ALERT"
        val title = if (isRule) "SafeSpace rule: $label" else "SafeSpace threat: $label"
        // Detector summaries contain confidence percentages. Keep those in History,
        // but make the phone alert a short, readable description.
        val detail = if (isRule) {
            event.optString("summary")
                .replace(Regex("(?i)(?:\\s+at)?\\s+\\d+(?:\\.\\d+)?\\s*(?:%|percent)\\s*confidence"), "")
                .replace(Regex("(?i)confidence\\s*[:=]?\\s*\\d+(?:\\.\\d+)?\\s*(?:%|percent)"), "")
                .replace(Regex("(?i)\\b\\d+(?:\\.\\d+)?\\s*(?:%|percent)(?!\\w)"), "")
                .replace(Regex("\\s{2,}"), " ")
                .trim()
                .ifBlank { "Rule triggered on $cameraName" }
        } else {
            "$label detected on $cameraName"
        }
        val notification = Notification.Builder(this, ALERT_CHANNEL)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(detail)
            .setStyle(Notification.BigTextStyle().bigText(detail))
            .setAutoCancel(true)
            .setContentIntent(PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
            .build()
        notifications.notify(event.optString("id").hashCode(), notification)
    }

    override fun onDestroy() {
        running = false
        worker?.interrupt()
        super.onDestroy()
    }
}
