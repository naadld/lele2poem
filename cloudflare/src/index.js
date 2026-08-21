/**
 * Cloudflare Worker: lele2poem
 * Dedicated 100% Serverless Gateway for Poem Video Automation & Gatekeepers
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // 1. Health Check
    if (url.pathname === "/" || url.pathname === "/health") {
      return new Response(JSON.stringify({
        project: "LeLe Hoc Tieng Trung - Poem Engine",
        worker: "lele2poem",
        status: "Online (100% Serverless)",
        audio_engine: "100% OmniVoice (Zero-Shot Voice Cloning)",
        reference_voice: "Vegetarian Wolf.wav",
        google_sheet_tab: "poem",
        endpoints: {
          receivePoem: "/api/receive-poem (POST: Gatekeeper 1)",
          voiceReady: "/api/voice-ready (POST: Auto-trigger Render)",
          qcVideo: "/api/qc-video (POST: Gatekeeper 2 Product QC)"
        },
        time: new Date().toISOString()
      }, null, 2), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 2. Voice Ready Webhook -> Trigger Render.yml on GitHub Actions
    if (url.pathname === "/api/voice-ready" && request.method === "POST") {
      try {
        const body = await request.json();
        const rowId = body.row_id || "2";

        console.log(`[POEM-GATEWAY] Voice is ready for Row #${rowId}. Dispatching Render.yml on GitHub Actions...`);

        if (env.GH_PAT) {
          const ghUrl = `https://api.github.com/repos/naadld/lele2poem/actions/workflows/Render.yml/dispatches`;
          await fetch(ghUrl, {
            method: "POST",
            headers: {
              "Authorization": `Bearer ${env.GH_PAT}`,
              "Accept": "application/vnd.github+json",
              "User-Agent": "lele2poem-worker"
            },
            body: JSON.stringify({
              ref: "main",
              inputs: { row_id: String(rowId) }
            })
          });
        }

        return new Response(JSON.stringify({ success: true, message: `Render workflow dispatched for Row #${rowId}` }), {
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: err.message }), { status: 500 });
      }
    }

    // 3. Gatekeeper 2 / Product QC Webhook -> Updates Status to Ready
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
  },

  async scheduled(event, env, ctx) {
    console.log(`[POEM-CRON] Triggered cron at ${event.cron}...`);
  }
};
