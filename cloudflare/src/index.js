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
          generateVoice: "/api/generate-voice (POST: Dispatches VoiceGeneration.yml)",
          voiceReady: "/api/voice-ready (POST: Auto-dispatches Render.yml)",
          renderVideo: "/api/render-video (POST: Dispatches Render.yml)",
          qcVideo: "/api/qc-video (POST: Dispatches ProductQC.yml or updates QC)"
        },
        time: new Date().toISOString()
      }, null, 2), {
        headers: { "Content-Type": "application/json" }
      });
    }

    // 2. Dispatch Voice Generation on GitHub Actions
    if (url.pathname === "/api/generate-voice" && request.method === "POST") {
      try {
        const body = await request.json();
        const rowId = body.row_id || "2";
        const poemId = body.poem_id || "01_yong_e";

        console.log(`[POEM-GATEWAY] Dispatching VoiceGeneration.yml for Row #${rowId} (${poemId})...`);

        if (env.GH_PAT) {
          const ghUrl = `https://api.github.com/repos/naadld/lele2poem/actions/workflows/VoiceGeneration.yml/dispatches`;
          const ghRes = await fetch(ghUrl, {
            method: "POST",
            headers: {
              "Authorization": `Bearer ${env.GH_PAT}`,
              "Accept": "application/vnd.github+json",
              "User-Agent": "lele2poem-worker"
            },
            body: JSON.stringify({
              ref: "main",
              inputs: { row_id: String(rowId), poem_id: String(poemId) }
            })
          });

          if (!ghRes.ok) {
            const errText = await ghRes.text();
            throw new Error(`GitHub API Error: ${ghRes.status} - ${errText}`);
          }
        }

        return new Response(JSON.stringify({ success: true, message: `VoiceGeneration workflow dispatched for Row #${rowId}` }), {
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: err.message }), { status: 500 });
      }
    }

    // 3. Voice Ready Webhook -> Trigger Render.yml on GitHub Actions
    if ((url.pathname === "/api/voice-ready" || url.pathname === "/api/render-video") && request.method === "POST") {
      try {
        const body = await request.json();
        const rowId = body.row_id || "2";

        console.log(`[POEM-GATEWAY] Dispatching Render.yml for Row #${rowId}...`);

        if (env.GH_PAT) {
          const ghUrl = `https://api.github.com/repos/naadld/lele2poem/actions/workflows/Render.yml/dispatches`;
          const ghRes = await fetch(ghUrl, {
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

          if (!ghRes.ok) {
            const errText = await ghRes.text();
            throw new Error(`GitHub API Error: ${ghRes.status} - ${errText}`);
          }
        }

        return new Response(JSON.stringify({ success: true, message: `Render workflow dispatched for Row #${rowId}` }), {
          headers: { "Content-Type": "application/json" }
        });
      } catch (err) {
        return new Response(JSON.stringify({ success: false, error: err.message }), { status: 500 });
      }
    }

    // 4. Gatekeeper 2 / Product QC Webhook
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
