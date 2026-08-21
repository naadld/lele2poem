/**
 * Cloudflare Worker: lele2poem
 * Dedicated 100% Serverless Gateway & Telegram Command Center for Poem Automation
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Health Check
    if (url.pathname === "/" || url.pathname === "/health") {
      return new Response(JSON.stringify({
        project: "Lê Lê Học Tiếng Trung - Module Đọc Thơ Cổ Phong",
        worker: "lele2poem",
        status: "Online (100% Serverless)",
        audio_engine: "100% OmniVoice Zero-Shot Cloning",
        reference_voice: "Vegetarian Wolf.wav",
        google_sheet_tab: "poem",
        endpoints: {
          telegramWebhook: "/api/telegram-webhook (POST)",
          setupTelegram: "/api/setup-telegram-webhook (GET)",
          generateVoice: "/api/generate-voice (POST)",
          voiceReady: "/api/voice-ready (POST)",
          renderVideo: "/api/render-video (POST)",
          qcVideo: "/api/qc-video (POST)"
        },
        time: new Date().toISOString()
      }, null, 2), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 2. Setup Telegram Webhook
    if (url.pathname === "/api/setup-telegram-webhook") {
      const token = env.TELEGRAM_BOT_TOKEN;
      if (!token) {
        return new Response(JSON.stringify({ error: "TELEGRAM_BOT_TOKEN missing" }), { status: 500 });
      }
      const webhookUrl = `https://${url.host}/api/telegram-webhook`;
      const tgRes = await fetch(`https://api.telegram.org/bot${token}/setWebhook?url=${encodeURIComponent(webhookUrl)}`);
      const tgData = await tgRes.json();
      return new Response(JSON.stringify({ webhook_url: webhookUrl, result: tgData }), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 3. Telegram Webhook Handler (Commands & Buttons)
    if (url.pathname === "/api/telegram-webhook" && request.method === "POST") {
      try {
        const update = await request.json();
        ctx.waitUntil(handleTelegramUpdate(update, env, url.origin));
        return new Response("OK", { status: 200 });
      } catch (err) {
        console.error("Telegram webhook error:", err);
        return new Response("Error", { status: 500 });
      }
    }

    // 4. API: Dispatch Voice Generation on GitHub Actions
    if (url.pathname === "/api/generate-voice" && request.method === "POST") {
      try {
        const body = await request.json();
        const rowId = body.row_id || "2";
        const poemId = body.poem_id || "01_yong_e";

        await dispatchGitHubWorkflow(env, "VoiceGeneration.yml", {
          row_id: String(rowId),
          poem_id: String(poemId)
        });

        return new Response(JSON.stringify({ success: true, message: `VoiceGeneration dispatched for Row #${rowId}` }), {
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: err.message }), { status: 500 });
      }
    }

    // 5. API: Voice Ready Webhook -> Auto Trigger Render.yml
    if ((url.pathname === "/api/voice-ready" || url.pathname === "/api/render-video") && request.method === "POST") {
      try {
        const body = await request.json();
        const rowId = body.row_id || "2";

        console.log(`[POEM-GATEWAY] Voice is ready for Row #${rowId}. Auto-dispatching Render.yml on GitHub Actions...`);

        await dispatchGitHubWorkflow(env, "Render.yml", {
          row_id: String(rowId)
        });

        return new Response(JSON.stringify({ success: true, message: `Render workflow dispatched for Row #${rowId}` }), {
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: err.message }), { status: 500 });
      }
    }

    // 6. API: Gatekeeper 2 / Product QC Webhook
    if (url.pathname === "/api/qc-video" && request.method === "POST") {
      try {
        const body = await request.json();
        const rowId = body.row_id || "2";
        const qcPassed = body.qc_passed !== false;

        console.log(`[POEM-GATEKEEPER-2] QC Video result for Row #${rowId}: ${qcPassed ? 'PASSED' : 'FAILED'}`);

        return new Response(JSON.stringify({
          success: true,
          row_id: rowId,
          status: qcPassed ? "Ready" : "QC_Rejected"
        }), {
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: err.message }), { status: 500 });
      }
    }

    return new Response("Not Found", { status: 404 });
  }
};

/**
 * Dispatch a workflow on GitHub Actions repository naadld/lele2poem
 */
async function dispatchGitHubWorkflow(env, workflowFile, inputs = {}) {
  const token = env.GITHUB_TOKEN || env.GH_PAT;
  const owner = env.GITHUB_OWNER || "naadld";
  const repo = env.GITHUB_REPO || "lele2poem";

  if (!token) {
    throw new Error("GITHUB_TOKEN missing in Cloudflare environment secrets.");
  }

  const url = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${workflowFile}/dispatches`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/vnd.github+json",
      "User-Agent": "lele2poem-cloudflare-worker",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      ref: "main",
      inputs: inputs
    })
  });

  if (res.status !== 204) {
    const errText = await res.text();
    throw new Error(`GitHub API error (${res.status}): ${errText}`);
  }
  return true;
}

/**
 * Send message to Telegram Chat
 */
async function sendTelegram(botToken, chatId, text, inlineKeyboard = null) {
  if (!botToken || !chatId) return;
  const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
  const payload = {
    chat_id: chatId,
    text: text,
    parse_mode: "HTML",
    disable_web_page_preview: true
  };
  if (inlineKeyboard) {
    payload.reply_markup = { inline_keyboard: inlineKeyboard };
  }
  await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
}

/**
 * Handle incoming Telegram Updates
 */
async function handleTelegramUpdate(update, env, originUrl) {
  const botToken = env.TELEGRAM_BOT_TOKEN;
  if (!botToken) return;

  const msg = update.message || update.edited_message;
  const callback = update.callback_query;

  if (callback) {
    const chatId = callback.message.chat.id;
    const data = callback.data || "";
    
    if (data.startsWith("voice_")) {
      const rowId = data.split("_")[1] || "2";
      try {
        await dispatchGitHubWorkflow(env, "VoiceGeneration.yml", { row_id: rowId, poem_id: `01_yong_e` });
        await sendTelegram(botToken, chatId, `🎙️ <b>Đã kích hoạt sinh giọng ngâm OmniVoice</b> cho Dòng #${rowId}!\n\n• Audio sẽ được sinh trực tiếp và lưu vào Google Drive.\n• Sau khi hoàn thành sẽ tự động chuyển sang Render video.`);
      } catch (e) {
        await sendTelegram(botToken, chatId, `🚨 <b>Lỗi kích hoạt Voice:</b> ${e.message}`);
      }
    } else if (data.startsWith("render_")) {
      const rowId = data.split("_")[1] || "2";
      try {
        await dispatchGitHubWorkflow(env, "Render.yml", { row_id: rowId });
        await sendTelegram(botToken, chatId, `🎬 <b>Đã kích hoạt Render Video 9:16 (60fps)</b> cho Dòng #${rowId}!\n\n• Video sẽ được xuất chuẩn 1080x1920 với Karaoke 3 tầng và upload lên Google Drive.`);
      } catch (e) {
        await sendTelegram(botToken, chatId, `🚨 <b>Lỗi kích hoạt Render:</b> ${e.message}`);
      }
    } else if (data.startsWith("qc_")) {
      const rowId = data.split("_")[1] || "2";
      try {
        await dispatchGitHubWorkflow(env, "ProductQC.yml", { row_id: rowId });
        await sendTelegram(botToken, chatId, `🔍 <b>Đã kích hoạt Gatekeeper 2 Auto-QC</b> cho Dòng #${rowId}!`);
      } catch (e) {
        await sendTelegram(botToken, chatId, `🚨 <b>Lỗi kích hoạt QC:</b> ${e.message}`);
      }
    }
    return;
  }

  if (!msg || !msg.text) return;
  const chatId = msg.chat.id;
  const text = msg.text.trim();

  if (text === "/start" || text === "/help" || text === "/menu") {
    const menuText = (
      `📜 <b>LÊ LÊ HỌC TIẾNG TRUNG - ĐỌC THƠ CỔ PHONG</b>\n\n` +
      `Chào bạn! Đây là hệ thống điều khiển tự động 100% Cloud cho module ngâm thơ.\n\n` +
      `<b>Các lệnh nhanh:</b>\n` +
      `• <code>/voice &lt;dòng&gt;</code> - Sinh giọng ngâm OmniVoice\n` +
      `• <code>/render &lt;dòng&gt;</code> - Render video 9:16 1080x1920 60fps\n` +
      `• <code>/qc &lt;dòng&gt;</code> - Kiểm định chất lượng video (Gatekeeper 2)\n\n` +
      `<b>Chọn thao tác mẫu cho Dòng #2 (《咏鹅》):</b>`
    );

    const keyboard = [
      [
        { text: "🎙️ Sinh Voice OmniVoice (#2)", callback_data: "voice_2" },
        { text: "🎬 Render Video 9:16 (#2)", callback_data: "render_2" }
      ],
      [
        { text: "🔍 Auto-QC Gatekeeper (#2)", callback_data: "qc_2" }
      ]
    ];

    await sendTelegram(botToken, chatId, menuText, keyboard);
    return;
  }

  if (text.startsWith("/voice")) {
    const parts = text.split(" ");
    const rowId = parts[1] || "2";
    try {
      await dispatchGitHubWorkflow(env, "VoiceGeneration.yml", { row_id: rowId, poem_id: `01_yong_e` });
      await sendTelegram(botToken, chatId, `🎙️ <b>Đã kích hoạt OmniVoice Generation</b> cho Dòng #${rowId} trên GitHub Actions!`);
    } catch (e) {
      await sendTelegram(botToken, chatId, `🚨 <b>Lỗi:</b> ${e.message}`);
    }
    return;
  }

  if (text.startsWith("/render")) {
    const parts = text.split(" ");
    const rowId = parts[1] || "2";
    try {
      await dispatchGitHubWorkflow(env, "Render.yml", { row_id: rowId });
      await sendTelegram(botToken, chatId, `🎬 <b>Đã kích hoạt Render Video 9:16 (60fps)</b> cho Dòng #${rowId} trên GitHub Actions!`);
    } catch (e) {
      await sendTelegram(botToken, chatId, `🚨 <b>Lỗi:</b> ${e.message}`);
    }
    return;
  }

  if (text.startsWith("/qc")) {
    const parts = text.split(" ");
    const rowId = parts[1] || "2";
    try {
      await dispatchGitHubWorkflow(env, "ProductQC.yml", { row_id: rowId });
      await sendTelegram(botToken, chatId, `🔍 <b>Đã kích hoạt Auto-QC</b> cho Dòng #${rowId} trên GitHub Actions!`);
    } catch (e) {
      await sendTelegram(botToken, chatId, `🚨 <b>Lỗi:</b> ${e.message}`);
    }
    return;
  }
}
