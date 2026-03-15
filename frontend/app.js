"use strict";

// ── Konfiguration ─────────────────────────────────────────
const API = (() => {
    const h = window.location.hostname;
    if (h === "localhost" || h === "127.0.0.1") {
        return "http://localhost:8000/api";
    }
    return `http://${h}:8000/api`;
})();

let jobs        = [];
let aktiverJobId = null;

const ST = {
    "warteschlange":   "⏳ Warteschlange",
    "herunterladen":   "⬇ Download",
    "verarbeitung":    "🔧 Verarbeitung",
    "transkription":   "📝 Transkription",
    "zusammenfassung": "✨ Zusammenfassung",
    "abgeschlossen":   "✅ Fertig",
    "fehler":          "❌ Fehler",
    "abgebrochen":     "🛑 Abgebrochen",
};

const ABBRECHBAR = new Set([
    "warteschlange", "herunterladen",
    "verarbeitung", "transkription", "zusammenfassung"
]);

const LOESCHBAR = new Set([
    "abgeschlossen", "fehler", "abgebrochen"
]);

// ── Tab-Navigation ────────────────────────────────────────
function tab(n) {
    document.getElementById("tab-dashboard").style.display =
        n === "dashboard" ? "" : "none";
    document.getElementById("tab-suche").style.display =
        n === "suche" ? "" : "none";
    document.querySelectorAll(".nav-btn")
        .forEach(b => b.classList.remove("aktiv"));
    const navEl = document.getElementById("nav-" + n);
    if (navEl) navEl.classList.add("aktiv");
}

// ── Job starten ───────────────────────────────────────────
async function starten() {
    const urlEl = document.getElementById("url");
    if (!urlEl) return;
    const u = urlEl.value.trim();
    if (!u) { alert("Bitte YouTube-URL eingeben."); return; }

    const btn = document.getElementById("start-btn");
    if (btn) { btn.textContent = "⏳ Wird gesendet..."; btn.disabled = true; }

    try {
        const r = await fetch(API + "/jobs/", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                url:                       u,
                whisper_modell:            document.getElementById("modell")?.value || "base",
                zusammenfassung_stil:      document.getElementById("stil")?.value   || "stichpunkte",
                kapitel_erkennen:          document.getElementById("kap")?.checked  ?? true,
                zusammenfassung_erstellen: document.getElementById("zf")?.checked   ?? true,
                podcast_erstellen:         document.getElementById("pod")?.checked  ?? false,
            })
        });
        if (!r.ok) throw new Error(await r.text());
        urlEl.value = "";
        await laden();
    } catch(e) {
        alert("Fehler beim Starten: " + e.message);
    } finally {
        if (btn) { btn.textContent = "🚀 Analyse starten"; btn.disabled = false; }
    }
}

// ── Jobs laden ────────────────────────────────────────────
async function laden() {
    try {
        const r = await fetch(API + "/jobs/?limit=50");
        if (!r.ok) throw new Error("HTTP " + r.status);
        jobs = await r.json();
        rendern();
        stats();
    } catch(e) {
        console.error("Laden fehlgeschlagen:", e);
        const c = document.getElementById("jobs");
        if (c) c.innerHTML = `
            <div class="leer" style="color:var(--err)">
                ⚠️ API nicht erreichbar: ${esc(e.message)}<br>
                <small style="opacity:.6">${API}/jobs/</small>
            </div>`;
    }
}

// ── Jobs rendern ──────────────────────────────────────────
function rendern() {
    const c = document.getElementById("jobs");
    if (!c) return;

    if (!jobs.length) {
        c.innerHTML = '<div class="leer">📭 Noch keine Jobs vorhanden.</div>';
        return;
    }

    c.innerHTML = jobs.map(j => {
        const kannAbbrechen = ABBRECHBAR.has(j.status);
        const kannLoeschen  = LOESCHBAR.has(j.status);

        return `
        <div class="job-karte" onclick="detail('${j.id}')">
            <div class="job-kopf">
                <div style="min-width:0;flex:1">
                    <div class="job-titel">${esc(kurz(j.url, 65))}</div>
                    <div class="job-meta">
                        ${zeit(j.erstellt_am)}
                        &nbsp;·&nbsp;
                        ${Math.round(j.fortschritt || 0)}%
                    </div>
                </div>
                <div style="display:flex;align-items:center;gap:.4rem;flex-shrink:0">
                    <span class="badge b-${j.status}">
                        ${ST[j.status] || j.status}
                    </span>
                    ${kannAbbrechen ? `
                    <button class="abbruch-btn"
                        onclick="event.stopPropagation();jobAbbrechen('${j.id}',this)"
                        title="Job abbrechen">🛑
                    </button>` : ""}
                    ${kannLoeschen ? `
                    <button class="abbruch-btn"
                        onclick="event.stopPropagation();jobLoeschen('${j.id}',this)"
                        title="Job löschen">🗑️
                    </button>` : ""}
                </div>
            </div>
            <div class="fortschritt">
                <div class="fortschritt-bar"
                     style="width:${j.fortschritt || 0}%">
                </div>
            </div>
        </div>`;
    }).join("");
}

// ── Statistiken ───────────────────────────────────────────
function stats() {
    let q = 0, w = 0, d = 0, e = 0;
    jobs.forEach(j => {
        if (j.status === "warteschlange")          q++;
        else if (ABBRECHBAR.has(j.status))         w++;
        else if (j.status === "abgeschlossen")     d++;
        else if (LOESCHBAR.has(j.status) &&
                 j.status !== "abgeschlossen")     e++;
    });
    const sq = document.getElementById("s-queue");
    const sw = document.getElementById("s-work");
    const sd = document.getElementById("s-done");
    const se = document.getElementById("s-err");
    if (sq) sq.textContent = "⏳ Warteschlange: "   + q;
    if (sw) sw.textContent = "⚙️ In Bearbeitung: "  + w;
    if (sd) sd.textContent = "✅ Fertig: "           + d;
    if (se) se.textContent = "❌ Fehler/Abbruch: "  + e;
}

// ── Job abbrechen ─────────────────────────────────────────
async function jobAbbrechen(jobId, btn) {
    if (!confirm("Job wirklich abbrechen?")) return;
    btn.disabled = true;
    btn.textContent = "⏳";
    try {
        const r = await fetch(`${API}/jobs/${jobId}/abbrechen`, {
            method: "POST"
        });
        if (!r.ok) {
            const err = await r.json().catch(() => ({}));
            alert("Fehler: " + (err.detail || r.status));
            btn.disabled = false;
            btn.textContent = "🛑";
            return;
        }
        await laden();
    } catch(e) {
        alert("Fehler: " + e.message);
        btn.disabled = false;
        btn.textContent = "🛑";
    }
}

// ── Job löschen ───────────────────────────────────────────
async function jobLoeschen(jobId, btn) {
    btn.disabled = true;
    btn.textContent = "⏳";
    try {
        const r = await fetch(`${API}/jobs/${jobId}`, { method: "DELETE" });
        if (!r.ok) throw new Error(await r.text());
        await laden();
    } catch(e) {
        alert("Fehler beim Löschen: " + e.message);
        btn.disabled = false;
        btn.textContent = "🗑️";
    }
}

// ── Alle abgebrochenen/fehlerhaften Jobs löschen ──────────
async function alleAbgebrochenLoeschen() {
    const anzahl = jobs.filter(j =>
        LOESCHBAR.has(j.status) && j.status !== "abgeschlossen"
    ).length;

    if (anzahl === 0) { alert("Keine Jobs zum Löschen vorhanden."); return; }
    if (!confirm(`${anzahl} Job(s) löschen?`)) return;

    try {
        const r = await fetch(`${API}/jobs/batch/abgebrochen`, {
            method: "DELETE"
        });
        if (!r.ok) throw new Error(await r.text());
        const d = await r.json();
        await laden();
        console.log(`${d.geloescht} Jobs gelöscht`);
    } catch(e) {
        alert("Fehler: " + e.message);
    }
}

// ── Job-Detail Modal ──────────────────────────────────────
async function detail(id) {
    aktiverJobId = id;
    const modal  = document.getElementById("modal");
    const inhalt = document.getElementById("modal-inhalt");
    if (!modal || !inhalt) return;

    modal.style.display = "flex";
    inhalt.innerHTML =
        "<p style='color:var(--ged);padding:2rem;text-align:center'>⏳ Lade...</p>";

    try {
        const [jr, vr] = await Promise.allSettled([
            fetch(`${API}/jobs/${id}`).then(r => r.json()),
            fetch(`${API}/jobs/${id}/video`).then(r => r.ok ? r.json() : null),
        ]);
        const j = jr.status === "fulfilled" ? jr.value : null;
        const v = vr.status === "fulfilled" ? vr.value : null;

        if (!j) throw new Error("Job konnte nicht geladen werden");

        const kapitelHtml = v?.kapitel?.length
            ? `<ul class="kap-liste">${v.kapitel.map(k => `
                <li>
                    <span class="kap-ts">${esc(k.zeitstempel || "")}</span>
                    <span>${esc(k.titel || "")}</span>
                </li>`).join("")}</ul>`
            : `<p style="color:var(--ged);padding:.5rem 0">
                   Keine Kapitel erkannt.
               </p>`;

        inhalt.innerHTML = `
            <h2 style="margin-bottom:.3rem;font-size:1.15rem;padding-right:2rem">
                ${esc(v?.titel || kurz(j.url, 60))}
            </h2>
            <p style="color:var(--ged);font-size:.83rem;margin-bottom:1.5rem">
                ${v ? esc(v.kanal) + " &nbsp;·&nbsp; " + dauer(v.dauer) : ""}
                &nbsp;
                <span class="badge b-${j.status}">
                    ${ST[j.status] || j.status}
                </span>
                ${j.fehlermeldung ? `
                <br><span style="color:var(--err);font-size:.8rem">
                    ${esc(j.fehlermeldung)}
                </span>` : ""}
            </p>

            <div class="mtabs">
                <button class="mtab aktiv"
                    onclick="mtab('zf',this)">📝 Zusammenfassung</button>
                <button class="mtab"
                    onclick="mtab('tr',this)">📄 Transkript</button>
                <button class="mtab"
                    onclick="mtab('ka',this)">📑 Kapitel</button>
                <button class="mtab"
                    onclick="mtab('chat',this)">💬 KI-Chat</button>
            </div>

            <div id="mt-zf">
                <div class="inhalt">${esc(
                    v?.zusammenfassung || "Zusammenfassung noch nicht verfügbar."
                )}</div>
            </div>
            <div id="mt-tr" style="display:none">
                <div class="inhalt">${esc(
                    v?.transkript || "Transkript noch nicht verfügbar."
                )}</div>
            </div>
            <div id="mt-ka" style="display:none">
                ${kapitelHtml}
            </div>
            <div id="mt-chat" style="display:none">
                <div class="chat-box" id="chat-verlauf"></div>
                <div class="chat-eingabe">
                    <input id="chat-frage" type="text"
                           placeholder="Frage zum Video stellen..."
                           onkeydown="if(event.key==='Enter')chatSenden()"/>
                    <button onclick="chatSenden()">➤</button>
                    <button class="exp-btn" onclick="chatLoeschen()"
                            title="Chat leeren">🗑</button>
                </div>
            </div>

            <div class="export-zeile">
                <button class="exp-btn" onclick="exp('${id}','txt')">
                    ⬇ TXT
                </button>
                <button class="exp-btn" onclick="exp('${id}','markdown')">
                    ⬇ Markdown
                </button>
                <button class="exp-btn" onclick="exp('${id}','json')">
                    ⬇ JSON
                </button>
                ${v?.podcast_pfad ? `
                <button class="exp-btn" onclick="exp('${id}','podcast')">
                    🎙 Podcast
                </button>` : ""}
                <button class="exp-btn"
                        style="margin-left:auto;color:var(--err);border-color:var(--err)"
                        onclick="modalZu();jobLoeschen('${id}',this)">
                    🗑️ Löschen
                </button>
            </div>`;

    } catch(e) {
        inhalt.innerHTML =
            `<p style="color:var(--err);padding:1rem">
                ❌ Fehler: ${esc(e.message)}
             </p>`;
    }
}

// ── Modal-Tabs ────────────────────────────────────────────
function mtab(n, btn) {
    ["zf", "tr", "ka", "chat"].forEach(t => {
        const el = document.getElementById("mt-" + t);
        if (el) el.style.display = t === n ? "" : "none";
    });
    document.querySelectorAll(".mtab")
        .forEach(b => b.classList.remove("aktiv"));
    btn.classList.add("aktiv");
    if (n === "chat") {
        setTimeout(() =>
            document.getElementById("chat-frage")?.focus(), 100);
    }
}

function modalZu() {
    const modal = document.getElementById("modal");
    if (modal) modal.style.display = "none";
}

// ── Export ────────────────────────────────────────────────
function exp(id, fmt) {
    window.open(`${API}/export/${id}/${fmt}`, "_blank");
}

// ── KI-Chat ───────────────────────────────────────────────
async function chatSenden() {
    const eingabe = document.getElementById("chat-frage");
    const frage   = eingabe?.value.trim();
    if (!frage || !aktiverJobId) return;
    eingabe.value = "";

    chatMsg("nutzer", frage);
    const ladeId = "laden-" + Date.now();
    chatMsg("assistent", "⏳ Denke nach...", ladeId);

    try {
        const r = await fetch(`${API}/chat/${aktiverJobId}`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ frage })
        });
        document.getElementById(ladeId)?.remove();
        if (!r.ok) throw new Error(await r.text());
        const d = await r.json();
        chatMsg("assistent", d.antwort);
    } catch(e) {
        document.getElementById(ladeId)?.remove();
        chatMsg("fehler", "❌ " + e.message);
    }
}

function chatMsg(rolle, text, id) {
    const box = document.getElementById("chat-verlauf");
    if (!box) return;
    const div = document.createElement("div");
    div.className = `chat-msg chat-${rolle}`;
    if (id) div.id = id;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

async function chatLoeschen() {
    if (!aktiverJobId) return;
    await fetch(`${API}/chat/${aktiverJobId}/verlauf`,
        { method: "DELETE" }).catch(() => {});
    const box = document.getElementById("chat-verlauf");
    if (box) box.innerHTML = "";
}

// ── Suche ─────────────────────────────────────────────────
async function suchen() {
    const qEl = document.getElementById("sq");
    const c   = document.getElementById("such-ergebnisse");
    if (!qEl || !c) return;

    const q = qEl.value.trim();
    if (!q) return;

    c.innerHTML = "<p style='color:var(--ged)'>⏳ Suche läuft...</p>";

    try {
        const r = await fetch(API + "/suche/", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ suchwort: q, limit: 20 })
        });
        if (!r.ok) throw new Error("HTTP " + r.status);
        const res = await r.json();

        if (!res.length) {
            c.innerHTML =
                `<p style="color:var(--ged)">
                     Keine Treffer für „${esc(q)}" gefunden.
                 </p>`;
            return;
        }

        c.innerHTML = res.map(e => `
            <div class="s-result" onclick="detail('${e.job_id}')">
                <h4>${esc(e.titel)}</h4>
                <div class="s-snip">"...${esc(e.ausschnitt)}..."</div>
                <div class="s-meta">
                    Gefunden in: ${esc(e.gefunden_in)}
                    &nbsp;·&nbsp; ${esc(e.kanal)}
                </div>
            </div>`).join("");
    } catch(e) {
        c.innerHTML =
            `<p style="color:var(--err)">❌ Suchfehler: ${esc(e.message)}</p>`;
    }
}

// ── Hilfsfunktionen ───────────────────────────────────────
function kurz(s, n) {
    if (!s) return "";
    return s.length > n ? s.slice(0, n) + "…" : s;
}

function esc(s) {
    if (s === null || s === undefined) return "";
    return String(s)
        .replace(/&/g,  "&amp;")
        .replace(/</g,  "&lt;")
        .replace(/>/g,  "&gt;")
        .replace(/"/g,  "&quot;")
        .replace(/'/g,  "&#39;");
}

function zeit(iso) {
    if (!iso) return "";
    const d = (Date.now() - new Date(iso)) / 1000;
    if (d < 60)    return "gerade eben";
    if (d < 3600)  return Math.floor(d / 60) + " Min";
    if (d < 86400) return Math.floor(d / 3600) + " Std";
    return Math.floor(d / 86400) + " Tagen";
}

function dauer(s) {
    if (!s) return "";
    const h   = Math.floor(s / 3600);
    const m   = Math.floor((s % 3600) / 60);
    const sek = s % 60;
    return h > 0 ? `${h}h ${m}m` : `${m}m ${sek}s`;
}

// ── Event Listener + Initialisierung ─────────────────────
function init() {
    const sq  = document.getElementById("sq");
    const url = document.getElementById("url");
    const mod = document.getElementById("modal");

    if (sq) {
        sq.addEventListener("keydown", e => {
            if (e.key === "Enter") suchen();
        });
    }
    if (url) {
        url.addEventListener("keydown", e => {
            if (e.key === "Enter") starten();
        });
    }
    if (mod) {
        mod.addEventListener("click", function(e) {
            if (e.target === this) modalZu();
        });
    }

    console.log("✅ YouTube AI Suite – API:", API);
    laden();
    setInterval(laden, 5000);
}

// DOM abwarten
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}