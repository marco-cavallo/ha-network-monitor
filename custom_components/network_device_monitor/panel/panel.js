/*
 * Network monitor - sidebar panel
 * By Marco Cavallo
 *
 * Vanilla custom element: no external dependencies, no build step.
 * Talks to the integration through its own WebSocket commands.
 */

const DOMAIN = "network_device_monitor";

const STYLES = `
:host {
  --nm-radius: 16px;
  --nm-gap: 16px;
  --nm-accent: #03a9f4;
  --nm-amber: #ffc008;
  --nm-green: #4caf50;
  --nm-red: #f44336;
  --nm-bg: var(--primary-background-color, #f5f6f8);
  --nm-card: var(--card-background-color, #fff);
  --nm-text: var(--primary-text-color, #212121);
  --nm-dim: var(--secondary-text-color, #6b7280);
  --nm-line: var(--divider-color, rgba(128,128,128,.22));
  display: block;
  background: var(--nm-bg);
  min-height: 100vh;
  color: var(--nm-text);
  font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif);
}
* { box-sizing: border-box; }

/* ---------- header ---------- */
.top {
  position: sticky; top: 0; z-index: 10;
  background: linear-gradient(135deg, #0277bd 0%, #03a9f4 60%, #4fc3f7 100%);
  color: #fff;
  padding: 18px var(--nm-gap) 20px;
  box-shadow: 0 2px 14px rgba(0,0,0,.18);
}
.top-row { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.menu-btn {
  flex: none; width: 42px; height: 42px; border-radius: 12px; cursor: pointer;
  display: grid; place-items: center; color: #fff;
  background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.26);
  transition: background .15s, transform .1s;
}
.menu-btn:hover { background: rgba(255,255,255,.28); }
.menu-btn:active { transform: scale(.94); }
.brand { display: flex; align-items: baseline; gap: 10px; flex: 1; min-width: 220px; }
.brand h1 { margin: 0; font-size: 26px; font-weight: 600; letter-spacing: .2px; }
.badge {
  font-size: 12px; font-weight: 600; padding: 3px 9px; border-radius: 999px;
  background: rgba(255,255,255,.22); border: 1px solid rgba(255,255,255,.32);
}
.by { font-size: 13px; opacity: .9; }

/* ---------- stat tiles ---------- */
.stats { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 16px; }
.stats[hidden] { display: none; }
.top.collapsed { padding-bottom: 14px; }
.compact {
  display: flex; gap: 14px; margin-top: 10px; font-size: 13px;
  opacity: .95; flex-wrap: wrap;
}
.compact b { font-size: 15px; }
.mini.watch { border-color: #7e57c2; color: #7e57c2; }
.mini.unwatch { border-color: var(--nm-dim); color: var(--nm-dim); }
.tag.watch { background: rgba(126,87,194,.18); color: #5e35b1; }
.tag.down { background: rgba(244,67,54,.18); color: #c62828; }
.card.down { border-left: 5px solid var(--nm-red); }
@media (max-width: 700px) {
  .brand h1 { font-size: 21px; }
  .grid { grid-template-columns: 1fr; }
  .stat { min-width: 92px; padding: 8px 11px; }
}
.stat {
  background: rgba(255,255,255,.16); border: 1px solid rgba(255,255,255,.24);
  border-radius: 12px; padding: 10px 14px; min-width: 104px;
}
.stat .v { font-size: 24px; font-weight: 700; line-height: 1.1; }
.stat .l { font-size: 11px; text-transform: uppercase; letter-spacing: .6px; opacity: .88; }
.stat.warn .v { color: #fff3c4; }

/* ---------- toolbar ---------- */
.bar {
  display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  padding: var(--nm-gap); position: sticky; top: 0; z-index: 5;
}
.search {
  flex: 1; min-width: 200px; position: relative;
}
.search input {
  width: 100%; padding: 12px 14px 12px 40px; font-size: 15px;
  border-radius: 999px; border: 1px solid var(--nm-line);
  background: var(--nm-card); color: var(--nm-text);
  outline: none; transition: border-color .15s, box-shadow .15s;
}
.search input:focus { border-color: var(--nm-accent); box-shadow: 0 0 0 3px rgba(3,169,244,.16); }
.search svg { position: absolute; left: 13px; top: 50%; transform: translateY(-50%); opacity: .5; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip {
  padding: 8px 14px; border-radius: 999px; cursor: pointer; font-size: 13px;
  font-weight: 500; border: 1px solid var(--nm-line); background: var(--nm-card);
  color: var(--nm-text); transition: all .15s;
}
.chip:hover { border-color: var(--nm-accent); }
.chip[aria-pressed="true"] { background: var(--nm-accent); color: #fff; border-color: var(--nm-accent); }
.btn {
  padding: 10px 16px; border-radius: 10px; border: none; cursor: pointer;
  font-size: 14px; font-weight: 600; background: var(--nm-accent); color: #fff;
  transition: filter .15s;
}
.btn:hover { filter: brightness(1.08); }
.btn.ghost { background: var(--nm-card); color: var(--nm-text); border: 1px solid var(--nm-line); }

/* ---------- device grid ---------- */
.grid {
  display: grid; gap: 12px; padding: 0 var(--nm-gap) 40px;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
}
.card {
  background: var(--nm-card); border-radius: var(--nm-radius);
  border: 1px solid var(--nm-line); overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  transition: transform .12s, box-shadow .12s;
}
.card:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(0,0,0,.11); }
.card.anom { border-left: 5px solid var(--nm-amber); }
.card.off { opacity: .62; }

.head { display: flex; gap: 12px; align-items: flex-start; padding: 14px 16px 10px; }
.emoji {
  font-size: 26px; line-height: 1; width: 44px; height: 44px; flex: none;
  display: grid; place-items: center; border-radius: 12px;
  background: color-mix(in srgb, var(--nm-accent) 12%, transparent);
}
.title { flex: 1; min-width: 0; }
.title .n {
  font-size: 17px; font-weight: 600; margin: 0 0 3px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.title .s { font-size: 12.5px; color: var(--nm-dim); }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; margin-right: 5px; }
.dot.on { background: var(--nm-green); box-shadow: 0 0 0 3px rgba(76,175,80,.18); }
.dot.off { background: var(--nm-dim); }

.sep { height: 1px; background: var(--nm-line); margin: 0 16px; }

.rows { padding: 10px 16px 12px; display: grid; gap: 7px; }
.row { display: flex; gap: 10px; font-size: 13.5px; align-items: center; }
.row .k { color: var(--nm-dim); width: 84px; flex: none; font-size: 12px;
          text-transform: uppercase; letter-spacing: .4px; }
.row .v { font-family: ui-monospace, "SF Mono", Menlo, monospace; word-break: break-all; }

.note {
  margin: 0 16px 12px; padding: 9px 12px; border-radius: 10px; font-size: 13px;
  background: color-mix(in srgb, var(--nm-amber) 14%, transparent);
  border-left: 3px solid var(--nm-amber);
}
.acts { display: flex; gap: 8px; padding: 0 16px 14px; flex-wrap: wrap; }
.mini {
  padding: 7px 12px; font-size: 12.5px; font-weight: 600; border-radius: 8px;
  border: 1px solid var(--nm-line); background: transparent; color: var(--nm-text);
  cursor: pointer; transition: all .15s;
}
.mini:hover { border-color: var(--nm-accent); color: var(--nm-accent); }
.mini.trust { border-color: var(--nm-green); color: var(--nm-green); }
.mini.untrust { border-color: var(--nm-amber); color: #b8860b; }
.tag {
  font-size: 10.5px; font-weight: 700; padding: 3px 8px; border-radius: 6px;
  text-transform: uppercase; letter-spacing: .5px;
}
.tag.ok { background: rgba(76,175,80,.16); color: #2e7d32; }
.tag.no { background: rgba(255,192,8,.2); color: #9a6b00; }

/* ---------- dialog ---------- */
dialog {
  border: none; border-radius: var(--nm-radius); padding: 0; max-width: 460px; width: 92vw;
  background: var(--nm-card); color: var(--nm-text);
  box-shadow: 0 24px 60px rgba(0,0,0,.3);
}
dialog::backdrop { background: rgba(0,0,0,.45); backdrop-filter: blur(2px); }
.dlg-h { padding: 18px 20px 6px; font-size: 19px; font-weight: 600; }
.dlg-b { padding: 8px 20px 4px; display: grid; gap: 14px; }
.dlg-b label { font-size: 12px; text-transform: uppercase; letter-spacing: .5px;
               color: var(--nm-dim); display: block; margin-bottom: 5px; }
.dlg-b input, .dlg-b textarea {
  width: 100%; padding: 11px 13px; font-size: 15px; border-radius: 10px;
  border: 1px solid var(--nm-line); background: var(--nm-bg); color: var(--nm-text);
  outline: none; font-family: inherit;
}
.dlg-b input:focus, .dlg-b textarea:focus { border-color: var(--nm-accent); }
.dlg-b textarea { min-height: 84px; resize: vertical; }
.dlg-f { display: flex; justify-content: flex-end; gap: 10px; padding: 16px 20px 20px; }

.ports { display: flex; gap: 6px; flex-wrap: wrap; padding: 0 16px 12px; }
.port {
  font-size: 11.5px; font-weight: 600; padding: 4px 9px; border-radius: 7px;
  background: color-mix(in srgb, var(--nm-accent) 13%, transparent);
  color: var(--nm-accent); border: 1px solid color-mix(in srgb, var(--nm-accent) 32%, transparent);
  font-family: ui-monospace, Menlo, monospace;
}
.port.web { background: rgba(76,175,80,.15); color: #2e7d32; border-color: rgba(76,175,80,.4); }
.port.risk { background: rgba(244,67,54,.13); color: #c62828; border-color: rgba(244,67,54,.38); }
.mini.open { border-color: var(--nm-green); color: var(--nm-green); font-weight: 700; }
.ports-none { padding: 0 16px 12px; font-size: 12px; color: var(--nm-dim); font-style: italic; }

.empty { padding: 60px 20px; text-align: center; color: var(--nm-dim); }
.foot { padding: 0 var(--nm-gap) 30px; text-align: center; color: var(--nm-dim); font-size: 12.5px; }
`;

const ICON_SEARCH =
  '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
  'stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/>' +
  '<path d="M20 20l-3.5-3.5"/></svg>';

const esc = (v) =>
  String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const when = (iso) => {
  if (!iso) return "mai";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  return d.toLocaleString(undefined, {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
};

const ago = (iso) => {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${Math.round(s)} s fa`;
  if (s < 3600) return `${Math.round(s / 60)} min fa`;
  if (s < 86400) return `${Math.round(s / 3600)} h fa`;
  return `${Math.round(s / 86400)} g fa`;
};

class NetworkMonitorPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._filter = "all";
    this._query = "";
    this._editing = null;
    // Collapsed by default on narrow screens: the stat tiles eat the fold.
    let saved = null;
    try { saved = localStorage.getItem("nm_stats_open"); } catch (e) { /* private mode */ }
    this._statsOpen = saved === null ? window.innerWidth > 700 : saved === "1";
    this._timer = null;
    this._rendered = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._load();
  }

  connectedCallback() {
    this._timer = setInterval(() => this._load(), 15000);
  }

  disconnectedCallback() {
    if (this._timer) clearInterval(this._timer);
  }

  async _call(type, extra = {}) {
    return this._hass.callWS({ type, ...extra });
  }

  async _load() {
    if (!this._hass) return;
    try {
      this._data = await this._call(`${DOMAIN}/devices`);
      this._render();
    } catch (err) {
      this._error = err?.message || String(err);
      this._render();
    }
  }

  _visible() {
    if (!this._data) return [];
    const q = this._query.trim().toLowerCase();
    return this._data.devices
      .filter((d) => {
        if (this._filter === "online" && !d.online) return false;
        if (this._filter === "offline" && d.online) return false;
        if (this._filter === "anomalous" && (d.whitelisted || !d.online)) return false;
        if (this._filter === "trusted" && !d.whitelisted) return false;
        if (this._filter === "web" && !d.url) return false;
        if (this._filter === "watched" && !d.watched) return false;
        if (!q) return true;
        const portText = (d.ports || [])
          .map((p) => `${p.port} ${p.name}`).join(" ");
        return [d.name, d.ip, d.mac, d.vendor, d.hostname, d.note, d.ha_device,
                d.web_name, d.web_model, d.web_server, portText]
          .some((f) => String(f ?? "").toLowerCase().includes(q));
      })
      .sort((a, b) => {
        // A watched device that is down is the most urgent thing here.
        const da = a.watched && !a.online, db = b.watched && !b.online;
        if (da !== db) return da ? -1 : 1;
        if (a.online !== b.online) return a.online ? -1 : 1;
        if (a.whitelisted !== b.whitelisted) return a.whitelisted ? 1 : -1;
        const na = a.ip.split(".").map(Number);
        const nb = b.ip.split(".").map(Number);
        for (let i = 0; i < 4; i++) if (na[i] !== nb[i]) return na[i] - nb[i];
        return 0;
      });
  }

  _render() {
    if (!this._rendered) {
      this.shadowRoot.innerHTML = `<style>${STYLES}</style><div id="app"></div>`;
      this._rendered = true;
    }
    const app = this.shadowRoot.getElementById("app");

    if (this._error) {
      app.innerHTML = `<div class="empty"><h2>Errore</h2><p>${esc(this._error)}</p></div>`;
      return;
    }
    if (!this._data) {
      app.innerHTML = `<div class="empty">Caricamento…</div>`;
      return;
    }

    const d = this._data;
    const info = d.integration || {};
    const list = this._visible();

    app.innerHTML = `
      <div class="top${this._statsOpen ? "" : " collapsed"}">
        <div class="top-row">
          <button class="menu-btn" id="menu" title="Apri il menu laterale"
                  aria-label="Apri il menu laterale">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z"/>
            </svg>
          </button>
          <div class="brand">
            <h1>${esc(info.name || "Network monitor")}</h1>
            <span class="badge">v${esc(info.version || "?")}</span>
            <span class="by">By ${esc(info.author || "Marco Cavallo")}</span>
          </div>
          <button class="btn ghost" id="stats-toggle"
                  title="${this._statsOpen ? "Nascondi le informazioni" : "Mostra le informazioni"}">
            ${this._statsOpen ? "▲ Info" : "▼ Info"}</button>
          <button class="btn ghost" id="scan">Scansiona adesso</button>
        </div>
        ${this._statsOpen ? "" : `<div class="compact">
          <span><b>${d.total}</b> dispositivi</span>
          <span><b>${d.online}</b> online</span>
          <span><b>${d.anomalous}</b> anomali</span>
          ${d.watched ? `<span><b>${d.watched_offline}</b>/${d.watched} sorvegliati giù</span>` : ""}
          <span>${esc(ago(d.last_scan))}</span>
        </div>`}
        <div class="stats"${this._statsOpen ? "" : " hidden"}>
          <div class="stat"><div class="v">${d.total}</div><div class="l">Dispositivi</div></div>
          <div class="stat"><div class="v">${d.online}</div><div class="l">Online</div></div>
          <div class="stat ${d.anomalous ? "warn" : ""}"><div class="v">${d.anomalous}</div><div class="l">Anomali</div></div>
          <div class="stat"><div class="v" style="font-size:15px;padding-top:5px">${esc(d.subnet)}</div><div class="l">Rete</div></div>
          <div class="stat"><div class="v" style="font-size:15px;padding-top:5px">${esc(when(d.last_scan))}</div>
               <div class="l">Ultima scansione · ${esc(ago(d.last_scan))}</div></div>
          <div class="stat"><div class="v" style="font-size:15px;padding-top:5px">${esc(d.scan_method || "-")} / ${d.scan_interval}s</div>
               <div class="l">Metodo · intervallo</div></div>
          <div class="stat ${d.watched_offline ? "warn" : ""}"><div class="v">${d.watched_offline}/${d.watched}</div>
               <div class="l">Sorvegliati giù</div></div>
          <div class="stat"><div class="v" style="font-size:15px;padding-top:5px">${d.port_scan ? "attivo" : "disattivo"}</div>
               <div class="l">Scansione porte${d.default_open_port ? " · apri :" + d.default_open_port : ""}</div></div>
        </div>
      </div>

      <div class="bar">
        <div class="search">
          ${ICON_SEARCH}
          <input id="q" type="search" placeholder="Cerca per nome, IP, MAC, produttore, nota…"
                 value="${esc(this._query)}" />
        </div>
        <div class="chips">
          ${[["all", "Tutti"], ["online", "Online"], ["offline", "Offline"],
             ["anomalous", "Anomali"], ["trusted", "Attendibili"], ["watched", "Sorvegliati"], ["web", "Con interfaccia web"]]
            .map(([k, l]) =>
              `<button class="chip" data-f="${k}" aria-pressed="${this._filter === k}">${l}</button>`)
            .join("")}
        </div>
      </div>

      <div class="grid">${list.map((x) => this._card(x)).join("")}</div>
      ${list.length ? "" : `<div class="empty">Nessun dispositivo corrisponde alla ricerca.</div>`}
      <div class="foot">${esc(info.name)} v${esc(info.version)} — By ${esc(info.author)} ·
        ${list.length} di ${d.total} dispositivi mostrati</div>

      <dialog id="dlg">
        <div class="dlg-h">Modifica dispositivo</div>
        <div class="dlg-b">
          <div><label>Nome personalizzato</label>
            <input id="f-name" placeholder="Lascia vuoto per usare il nome rilevato" /></div>
          <div><label>Nota</label>
            <textarea id="f-note" placeholder="Es. telecamera del garage, di proprietà del vicino…"></textarea></div>
        </div>
        <div class="dlg-f">
          <button class="btn ghost" id="dlg-cancel">Annulla</button>
          <button class="btn" id="dlg-save">Salva</button>
        </div>
      </dialog>`;

    this._wire();
  }

  _card(x) {
    const cls = ["card"];
    if (!x.whitelisted && x.online) cls.push("anom");
    if (!x.online) cls.push("off");
    if (x.watched && !x.online) cls.push("down");
    const sub = [x.vendor, x.hostname].filter(Boolean).join(" · ");

    return `
      <div class="${cls.join(" ")}">
        <div class="head">
          <div class="emoji">${esc(x.emoji || "🔷")}</div>
          <div class="title">
            <p class="n">${esc(x.name)}</p>
            <div class="s">
              <span class="dot ${x.online ? "on" : "off"}"></span>${x.online ? "online" : "offline"}
              ${sub ? " · " + esc(sub) : ""}
            </div>
          </div>
          <span class="tag ${x.whitelisted ? "ok" : "no"}">${x.whitelisted ? "attendibile" : "non autorizzato"}</span>
          ${x.watched ? `<span class="tag ${x.online ? "watch" : "down"}">${x.online ? "sorvegliato" : "GIÙ"}</span>` : ""}
        </div>
        <div class="sep"></div>
        <div class="rows">
          <div class="row"><span class="k">IP</span><span class="v">${esc(x.ip)}</span></div>
          <div class="row"><span class="k">MAC</span><span class="v">${esc(x.mac || "sconosciuto")}</span></div>
          ${x.ha_device ? `<div class="row"><span class="k">Device HA</span><span class="v">${esc(x.ha_device)}</span></div>` : ""}
          ${x.web_name ? `<div class="row"><span class="k">Nome web</span><span class="v">${esc(x.web_name)}</span></div>` : ""}
          ${x.web_model ? `<div class="row"><span class="k">Modello</span><span class="v">${esc(x.web_model)}</span></div>` : ""}
          ${x.web_server ? `<div class="row"><span class="k">Server</span><span class="v">${esc(x.web_server)}</span></div>` : ""}
          <div class="row"><span class="k">Prima volta</span><span class="v">${esc(when(x.first_seen))}</span></div>
          <div class="row"><span class="k">Ultima volta</span><span class="v">${esc(when(x.last_seen))} (${esc(ago(x.last_seen))})</span></div>
        </div>
        ${this._ports(x)}
        ${x.note ? `<div class="note">${esc(x.note)}</div>` : ""}
        <div class="acts">
          <button class="mini" data-edit="${esc(x.key)}">Modifica</button>
          <button class="mini ${x.whitelisted ? "untrust" : "trust"}"
                  data-trust="${esc(x.key)}" data-val="${x.whitelisted ? "0" : "1"}">
            ${x.whitelisted ? "Rimuovi da attendibili" : "Segna attendibile"}</button>
          ${x.url
            ? `<button class="mini open" data-open="${esc(x.url)}">Apri ${esc(x.url)}</button>`
            : ""}
          <button class="mini ${x.watched ? "unwatch" : "watch"}"
                  data-watch="${esc(x.key)}" data-wval="${x.watched ? "0" : "1"}">
            ${x.watched ? "Non monitorare" : "Monitora"}</button>
          ${this._data.port_scan
            ? `<button class="mini" data-ports="${esc(x.key)}">Rileva porte</button>`
            : ""}
        </div>
      </div>`;
  }

  _ports(x) {
    if (!this._data.port_scan) return "";
    if (!x.ports || !x.ports.length) {
      return x.ports_scanned_at
        ? `<div class="ports-none">Nessuna porta aperta fra quelle controllate</div>`
        : `<div class="ports-none">Porte non ancora controllate</div>`;
    }
    const WEB = [80, 443, 8080, 8123, 8443, 8083, 9000];
    const RISK = [21, 23, 3389, 5900, 445, 139];
    return `<div class="ports">${x.ports
      .map((p) => {
        const cls = WEB.includes(p.port) ? "web" : RISK.includes(p.port) ? "risk" : "";
        const lbl = p.name ? `${p.port} ${p.name}` : String(p.port);
        return `<span class="port ${cls}" title="Porta ${p.port}">${esc(lbl)}</span>`;
      })
      .join("")}</div>`;
  }

  _wire() {
    const $ = (s) => this.shadowRoot.querySelector(s);
    const all = (s) => this.shadowRoot.querySelectorAll(s);

    const q = $("#q");
    q.addEventListener("input", (e) => {
      this._query = e.target.value;
      const pos = e.target.selectionStart;
      this._render();
      const nq = this.shadowRoot.querySelector("#q");
      nq.focus();
      nq.setSelectionRange(pos, pos);
    });

    all(".chip").forEach((c) =>
      c.addEventListener("click", () => { this._filter = c.dataset.f; this._render(); }));

    $("#menu").addEventListener("click", () => {
      // Standard Home Assistant event: the app shell toggles the sidebar.
      this.dispatchEvent(
        new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true })
      );
    });

    $("#stats-toggle").addEventListener("click", () => {
      this._statsOpen = !this._statsOpen;
      try { localStorage.setItem("nm_stats_open", this._statsOpen ? "1" : "0"); }
      catch (e) { /* storage unavailable, keep it in memory only */ }
      this._render();
    });

    all("[data-watch]").forEach((b) =>
      b.addEventListener("click", async () => {
        await this._call(`${DOMAIN}/set_watch`,
          { key: b.dataset.watch, watched: b.dataset.wval === "1" });
        this._load();
      }));

    $("#scan").addEventListener("click", async () => {
      await this._call(`${DOMAIN}/scan`);
      setTimeout(() => this._load(), 1500);
    });

    all("[data-open]").forEach((b) =>
      b.addEventListener("click", () =>
        window.open(b.dataset.open, "_blank", "noopener")));

    all("[data-ports]").forEach((b) =>
      b.addEventListener("click", async () => {
        const label = b.textContent;
        b.textContent = "Controllo…";
        b.disabled = true;
        try {
          await this._call(`${DOMAIN}/scan_ports`, { key: b.dataset.ports });
          this._load();
        } catch (err) {
          b.textContent = err?.code === "busy" ? "Scansione in corso…" : "Errore";
          setTimeout(() => { b.textContent = label; b.disabled = false; }, 2500);
        }
      }));

    all("[data-trust]").forEach((b) =>
      b.addEventListener("click", async () => {
        await this._call(`${DOMAIN}/set_whitelist`,
          { key: b.dataset.trust, trusted: b.dataset.val === "1" });
        this._load();
      }));

    const dlg = $("#dlg");
    all("[data-edit]").forEach((b) =>
      b.addEventListener("click", () => {
        const dev = this._data.devices.find((x) => x.key === b.dataset.edit);
        if (!dev) return;
        this._editing = dev.key;
        $("#f-name").value = dev.custom_name || "";
        $("#f-note").value = dev.note || "";
        dlg.showModal();
      }));

    $("#dlg-cancel").addEventListener("click", () => dlg.close());
    $("#dlg-save").addEventListener("click", async () => {
      await this._call(`${DOMAIN}/update_device`, {
        key: this._editing,
        name: $("#f-name").value,
        note: $("#f-note").value,
      });
      dlg.close();
      this._load();
    });
  }
}

customElements.define("network-monitor-panel", NetworkMonitorPanel);
