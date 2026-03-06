package helium314.keyboard.latin

import android.os.Handler
import android.os.Looper
import java.net.HttpURLConnection
import java.net.URL
import org.json.JSONArray
import org.json.JSONObject

object ClaudisAI {

    private val API_KEY = System.getenv("ANTHROPIC_API_KEY") ?: ""
    private val handler = Handler(Looper.getMainLooper())
    private var lastText = ""

    fun getSuggestions(text: String, callback: (List<String>) -> Unit) {
        if (text == lastText || text.length < 3) return
        lastText = text

        Thread {
            try {
                val url = URL("https://api.anthropic.com/v1/messages")
                val conn = url.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.setRequestProperty("x-api-key", API_KEY)
                conn.setRequestProperty("anthropic-version", "2023-06-01")
                conn.doOutput = true
                conn.connectTimeout = 3000
                conn.readTimeout = 3000

                val body = JSONObject()
                body.put("model", "claude-haiku-4-5-20251001")
                body.put("max_tokens", 30)
                val msgs = JSONArray()
                val msg = JSONObject()
                msg.put("role", "user")
                msg.put("content", "CLAUDIS-IA: sugira 3 palavras em portugues para: " + text + ". Responda APENAS as 3 palavras separadas por virgula, sem explicacao.")
                msgs.put(msg)
                body.put("messages", msgs)

                conn.outputStream.write(body.toString().toByteArray())

                val response = conn.inputStream.bufferedReader().readText()
                val json = JSONObject(response)
                val result = json.getJSONArray("content").getJSONObject(0).getString("text")
                val words = result.split(",").map { it.trim() }.filter { it.isNotEmpty() }.take(3)

                handler.post { callback(words) }
            } catch (e: Exception) {
                // silencioso
            }
        }.start()
    }
}
