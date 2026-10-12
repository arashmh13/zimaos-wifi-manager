/* ZimaOS Wi-Fi Manager — frontend (vanilla JS, no build step) */
"use strict";

/* ============================== i18n ============================== */
const I18N = {
  en: {
    app_title: "Wi-Fi Manager", pill_client: "Client", pill_hotspot: "Hotspot",
    pill_upstream: "Upstream", h_connection: "Current connection",
    k_ip: "IP address", k_iface: "Interface", k_gw: "Gateway", k_rate: "Link rate",
    b_disconnect: "Disconnect", b_reconnect: "Reconnect",
    c_notconn: "Not connected to Wi-Fi",
    c_notconn_d: "Scan for networks below and pick one to join. Saved networks reconnect automatically.",
    b_reconnect_auto: "Reconnect to saved network",
    h_scan: "Available networks", b_scan: "Scan", h_hidden: "Hidden network…",
    p_ssid: "SSID", b_join: "Join", h_saved: "Saved networks",
    h_hotspot: "Wi-Fi hotspot", t_broadcasting: "Broadcasting",
    k_apip: "Hotspot IP", k_apiface: "AP interface", k_clients: "Clients", k_upshare: "Sharing via",
    b_stop_hotspot: "Stop hotspot",
    hs_mode_hint: "This adapter supports simultaneous client + access-point operation on one shared 2.4 GHz channel — your existing Wi-Fi connection stays online while the hotspot runs.",
    f_hssid: "Hotspot name (SSID)", f_hspass: "Password",
    f_hspass_h: "WPA2-AES secured. Never broadcast an open hotspot by default.",
    f_band: "Frequency band", f_band_h: "AR9227 adapter is 2.4 GHz-only — 5 GHz unavailable.",
    f_chan: "Channel", f_chan_h: "Pinned to the client channel while connected.",
    f_sec: "Security", f_subnet: "Client subnet / DHCP",
    f_autostart: "Start hotspot automatically when this app starts",
    b_start_hotspot: "Start hotspot",
    h_clients: "Connected clients", cl_empty: "No clients connected to the hotspot yet.",
    th_dev: "Device", th_ip: "IP", th_sig: "Signal", th_time: "Connected",
    h_diag: "Diagnostics", d_caps: "Hardware capabilities", d_links: "Interfaces & links",
    k_mgmt: "Management IP (eth0)", k_default: "Default route", k_internet: "Internet", k_dns: "DNS",
    d_live: "Live event log (secrets never logged)", b_full_diag: "Run full diagnostics",
    b_rollback: "Copy rollback instructions",
    f_password: "Password", f_password_h: "Stored securely by NetworkManager — never shown in logs.",
    m_open_warn: "This network is open (no password). Traffic is not encrypted.",
    b_cancel: "Cancel", b_connect: "Connect",
    /* dynamic */
    st_connected: "Connected", st_disconnected: "Not connected", st_hotspot: "Hotspot only",
    st_both: "Client + Hotspot", st_off: "Off", st_on: "On", st_unknown: "…",
    up_ok: "OK", up_none: "No uplink", hs_dual: "Dual STA+AP", hs_excl: "Exclusive (client off)",
    sec_open: "Open", on: "ON", off: "OFF",
    saved_connect: "Connect", saved_forget: "Forget", confirm_forget: "Forget",
    confirm_disconnect_q: "Disconnect from this network? Autoconnect stays off until you reconnect.",
    confirm_forget_q: "Forget this saved network? The password will be deleted.",
    confirm_stop_q: "Stop the hotspot? Connected clients will be disconnected.",
    j_connecting: "Connecting…", j_scanning: "Scanning…", j_disconnecting: "Disconnecting…",
    j_forgetting: "Forgetting…", j_starting: "Starting hotspot…", j_stopping: "Stopping hotspot…",
    j_reconnecting: "Reconnecting…",
    toast_connected: "Connected", toast_disconnected: "Disconnected", toast_forgotten: "Network forgotten",
    toast_hotspot_on: "Hotspot started", toast_hotspot_off: "Hotspot stopped",
    toast_scan: "Scan complete", toast_error: "Error", toast_copied: "Copied to clipboard",
    toast_saved: "Saved", toast_password: "Password updated",
    err_generic: "Operation failed", err_network: "Network error — is the app reachable?",
    chan_auto: "Auto", chan_pinned: "pinned to ch {n}",
    scan_empty: "No networks found — try scanning again.",
    ssid_hidden: "(hidden)",
    saved_empty: "No saved Wi-Fi profiles yet.",
    no_clients_yet: "Waiting for clients…", cap_yes: "supported", cap_no: "not supported",
    lang_btn: "فارسی",
    diag_running: "Collecting…", uptime: "Up", last_scan: "last scan",
    h_security: "Security", sec_sub: "HTTP Basic auth",
    sec_hint: "Change the dashboard password. It protects every API endpoint — pick something strong; it is stored only as a salted SHA-256 hash.",
    f_curpass: "Current password", f_newpass: "New password", f_repPass: "Repeat new password",
    b_changepass: "Update password", pw_updated: "Password updated",
    pw_mismatch: "The new passwords do not match.",
    pw_short: "New password must be at least 6 characters.",
    pw_badcur: "Current password is incorrect.",
    vis_hidden: "visible", ch: "ch", ghz: "GHz", secured: "Secured", open_net: "Open",
    explicit_channel: "channel",
  },
  fa: {
    app_title: "مدیریت وای‌فای", pill_client: "کلاینت", pill_hotspot: "هات‌اسپات",
    pill_upstream: "مسیر اصلی", h_connection: "اتصال فعلی",
    k_ip: "آدرس IP", k_iface: "رابط شبکه", k_gw: "درگاه پیش‌فرض", k_rate: "سرعت پیوند",
    b_disconnect: "قطع اتصال", b_reconnect: "اتصال مجدد",
    c_notconn: "به وای‌فای متصل نیستید",
    c_notconn_d: "در پایین شبکه‌ها را جست‌وجو کنید و یکی را انتخاب کنید. شبکه‌های ذخیره‌شده خودکار وصل می‌شوند.",
    b_reconnect_auto: "اتصال به شبکه ذخیره‌شده",
    h_scan: "شبکه‌های موجود", b_scan: "جست‌وجو", h_hidden: "شبکه پنهان…",
    p_ssid: "نام شبکه", b_join: "ورود", h_saved: "شبکه‌های ذخیره‌شده",
    h_hotspot: "هات‌اسپات وای‌فای", t_broadcasting: "در حال پخش",
    k_apip: "آدرس هات‌اسپات", k_apiface: "رابط AP", k_clients: "کلاینت‌ها", k_upshare: "اشتراک از",
    b_stop_hotspot: "توقف هات‌اسپات",
    hs_mode_hint: "این آداپتر هم‌زمان کلاینت + نقطه‌دسترسی روی یک کانال مشترک ۲.۴ گیگاهرتز را پشتیبانی می‌کند — اتصال وای‌فای فعلی شما هنگام فعال بودن هات‌اسپات قطع نمی‌شود.",
    f_hssid: "نام هات‌اسپات (SSID)", f_hspass: "رمز عبور",
    f_hspass_h: "با WPA2-AES ایمن می‌شود. هات‌اسپات باز هرگز به‌صورت پیش‌فرض ساخته نمی‌شود.",
    f_band: "باند فرکانسی", f_band_h: "آداپتر AR9227 فقط ۲.۴ گیگاهرتز دارد — ۵ گیگاهرتز موجود نیست.",
    f_chan: "کانال", f_chan_h: "هنگام اتصال کلاینت، روی کانال آن ثابت می‌شود.",
    f_sec: "امنیت", f_subnet: "زیرشبکه کلاینت / DHCP",
    f_autostart: "شروع خودکار هات‌اسپات هنگام اجرای این برنامه",
    b_start_hotspot: "شروع هات‌اسپات",
    h_clients: "کلاینت‌های متصل", cl_empty: "هنوز کلاینتی به هات‌اسپات وصل نشده است.",
    th_dev: "دستگاه", th_ip: "آدرس IP", th_sig: "سیگنال", th_time: "مدت اتصال",
    h_diag: "عیب‌یابی", d_caps: "قابلیت‌های سخت‌افزار", d_links: "رابط‌ها و مسیرها",
    k_mgmt: "آدرس مدیریتی (eth0)", k_default: "مسیر پیش‌فرض", k_internet: "اینترنت", k_dns: "DNS",
    d_live: "گزارش زنده (رمزها هرگز ثبت نمی‌شوند)", b_full_diag: "اجرای عیب‌یابی کامل",
    b_rollback: "کپی دستورات بازگردانی",
    f_password: "رمز عبور", f_password_h: "به‌صورت امن در NetworkManager ذخیره می‌شود — هرگز در لاگ‌ها نمایش داده نمی‌شود.",
    m_open_warn: "این شبکه باز است (بدون رمز). ترافیک رمزنگاری نمی‌شود.",
    b_cancel: "انصراف", b_connect: "اتصال",
    st_connected: "متصل", st_disconnected: "قطع", st_hotspot: "فقط هات‌اسپات",
    st_both: "کلاینت + هات‌اسپات", st_off: "خاموش", st_on: "روشن", st_unknown: "…",
    up_ok: "سالم", up_none: "بدون مسیر", hs_dual: "هم‌زمان STA+AP", hs_excl: "انحصاری (کلاینت خاموش)",
    sec_open: "باز", on: "فعال", off: "غیرفعال",
    saved_connect: "اتصال", saved_forget: "حذف", confirm_forget: "حذف",
    confirm_disconnect_q: "اتصال قطع شود؟ تا زمان اتصال مجدد، اتصال خودکار خاموش می‌ماند.",
    confirm_forget_q: "این شبکه ذخیره‌شده حذف شود؟ رمز آن پاک می‌شود.",
    confirm_stop_q: "هات‌اسپات متوقف شود؟ کلاینت‌های متصل قطع می‌شوند.",
    j_connecting: "در حال اتصال…", j_scanning: "در حال جست‌وجو…", j_disconnecting: "در حال قطع…",
    j_forgetting: "در حال حذف…", j_starting: "در حال راه‌اندازی هات‌اسپات…", j_stopping: "در حال توقف…",
    j_reconnecting: "در حال اتصال مجدد…",
    toast_connected: "متصل شد", toast_disconnected: "قطع شد", toast_forgotten: "شبکه حذف شد",
    toast_hotspot_on: "هات‌اسپات روشن شد", toast_hotspot_off: "هات‌اسپات خاموش شد",
    toast_scan: "جست‌وجو کامل شد", toast_error: "خطا", toast_copied: "کپی شد",
    toast_saved: "ذخیره شد", toast_password: "رمز عبور به‌روزرسانی شد",
    err_generic: "عملیات ناموفق بود", err_network: "خطای شبکه — برنامه در دسترس است؟",
    chan_auto: "خودکار", chan_pinned: "ثابت روی کانال {n}",
    scan_empty: "شبکه‌ای یافت نشد — دوباره جست‌وجو کنید.",
    ssid_hidden: "(پنهان)",
    saved_empty: "هنوز پروفایل وای‌فای ذخیره نشده است.",
    no_clients_yet: "در انتظار کلاینت…", cap_yes: "پشتیبانی", cap_no: "غیرفعال",
    lang_btn: "English",
    diag_running: "در حال جمع‌آوری…", uptime: "روشن از", last_scan: "آخرین جست‌وجو",
    h_security: "امنیت", sec_sub: "احراز هویت HTTP Basic",
    sec_hint: "رمز داشبورد را تغییر دهید. این رمز همه نقاط دسترسی را محافظت می‌کند — رمز قوی انتخاب کنید؛ فقط به‌صورت هش SHA-256 با نمک ذخیره می‌شود.",
    f_curpass: "رمز فعلی", f_newpass: "رمز جدید", f_repPass: "تکرار رمز جدید",
    b_changepass: "به‌روزرسانی رمز", pw_updated: "رمز به‌روزرسانی شد",
    pw_mismatch: "رمزهای جدید یکسان نیستند.",
    pw_short: "رمز جدید باید حداقل ۶ کاراکتر باشد.",
    pw_badcur: "رمز فعلی نادرست است.",
    vis_hidden: "قابل‌مشاهده", ch: "کانال", ghz: "گیگاهرتز", secured: "امن", open_net: "باز",
    explicit_channel: "کانال",
  },
};
let LANG = localStorage.getItem("wm-lang") || "en";
const t = (k, vars) => {
  let s = (I18N[LANG] && I18N[LANG][k]) || I18N.en[k] || k;
  if (vars) for (const [a, b] of Object.entries(vars)) s = s.replace("{" + a + "}", b);
  return s;
};
function applyLang() {
  const html = document.documentElement;
  html.lang = LANG; html.dir = LANG === "fa" ? "rtl" : "ltr";
  document.querySelectorAll("[data-i18n]").forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-ph]").forEach(el => { el.placeholder = t(el.dataset.i18nPh); });
  document.getElementById("btnLang").textContent = t("lang_btn");
  document.title = t("app_title") + " — ZimaOS";
}

/* ============================== state ============================== */
let statusData = null;
let scanRows = null;
let scanBusy = false;
let scanSilent = false; // suppress toast for the auto-scan on page load
const jobs = new Map();
const handledJobs = new Set(); // dedupe terminal job events (SSE + poll may both deliver)
let evtSource = null;

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ============================== toasts ============================== */
function toast(kind, title, msg, ms = 4200) {
  const wrap = document.createElement("div");
  wrap.className = "toast " + kind;
  const icon = kind === "ok" ? "#i-check" : kind === "err" ? "#i-alert" : "#i-info";
  wrap.innerHTML = `<svg class="ti"><use href="${icon}"/></svg>
    <div class="tx"><b></b>${msg ? "<span></span>" : ""}</div><button class="tc">✕</button>`;
  wrap.querySelector("b").textContent = title;
  if (msg) wrap.querySelector("span").textContent = msg;
  wrap.querySelector(".tc").onclick = () => wrap.remove();
  $("toasts").appendChild(wrap);
  setTimeout(() => { wrap.style.opacity = "0"; wrap.style.transition = ".4s"; setTimeout(() => wrap.remove(), 400); }, ms);
}

function showJob(text, isErr) {
  const bar = $("jobBar");
  if (!text) { bar.classList.remove("show", "err"); return; }
  bar.classList.add("show");
  bar.classList.toggle("err", !!isErr);
  $("jobText").textContent = text;
}

/* ============================== api ============================== */
async function api(path, method = "GET", body) {
  try {
    const r = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = null;
    try { data = await r.json(); } catch (e) { /* empty */ }
    if (!r.ok) {
      const err = (data && data.error) || {};
      const e = new Error(err.message || t("err_generic"));
      e.code = err.code || String(r.status);
      throw e;
    }
    return data;
  } catch (e) {
    if (e instanceof TypeError) { const n = new Error(t("err_network")); n.code = "net"; throw n; }
    throw e;
  }
}

/* ============================== jobs ============================== */
const JOB_LABEL = {
  scan: "j_scanning", connect: "j_connecting", disconnect: "j_disconnecting",
  forget: "j_forgetting", hotspot_start: "j_starting", hotspot_stop: "j_stopping",
  reconnect: "j_reconnecting",
};
function trackJob(job) {
  jobs.set(job.id, job);
  showJob(t(JOB_LABEL[job.kind] || "j_connecting"));
}
function handleJobEvent(job) {
  jobs.set(job.id, job);
  const running = [...jobs.values()].filter(j => j.state === "running");
  if (job.state === "running") { showJob(t(JOB_LABEL[job.kind] || "j_connecting")); return; }
  if (handledJobs.has(job.id)) return;   // already finalized by the other delivery path
  handledJobs.add(job.id);
  if (handledJobs.size > 200) handledJobs.clear();
  if (running.length === 0) showJob(null);
  const titleMap = {
    connect: "toast_connected", disconnect: "toast_disconnected", forget: "toast_forgotten",
    hotspot_start: "toast_hotspot_on", hotspot_stop: "toast_hotspot_off",
    scan: "toast_scan", reconnect: "toast_connected",
  };
  const k = titleMap[job.kind] || "toast_error";
  const silentScan = job.kind === "scan" && scanSilent;
  if (silentScan) scanSilent = false;
  if (job.state === "ok") {
    let msg = job.message || (job.result && job.result.message) || "";
    if (job.kind === "hotspot_start" && job.result && job.result.notes && job.result.notes.length)
      msg += " — " + job.result.notes.join(" ");
    if (!silentScan) toast("ok", t(k), msg);
    if (job.kind === "scan" && job.result && job.result.rows) renderScan(job.result.rows);
    if (job.kind === "connect" || job.kind === "reconnect") closeModal();
    if (job.kind === "forget") refresh();
  } else {
    toast("err", t("toast_error"), job.message || t("err_generic"), 7000);
    if (job.kind === "connect") { $("mErr").classList.add("show"); $("mErrTxt").textContent = job.message || ""; $("mSubmit").disabled = false; }
  }
}

/* ============================== rendering ============================== */
function bars(q) {
  const n = q >= 75 ? 4 : q >= 50 ? 3 : q >= 25 ? 2 : q > 0 ? 1 : 0;
  return n;
}
function renderPills(s) {
  const w = s.wifi, h = s.hotspot;
  // client
  const pd = $("pdClient"), pv = $("pvClient");
  if (w.connected) { pd.className = "dot ok"; pv.textContent = w.ssid || "✓"; }
  else if (h && h.active) { pd.className = "dot hot"; pv.textContent = t("st_off"); }
  else { pd.className = "dot err"; pv.textContent = t("st_disconnected"); }
  // hotspot
  const hd = $("pdHotspot"), hv = $("pvHotspot"), hp = $("pillHotspot");
  if (h && h.active) { hd.className = "dot hot"; hv.textContent = h.ssid || t("st_on"); hp.classList.add("hot-on"); }
  else { hd.className = "dot"; hv.textContent = t("st_off"); hp.classList.remove("hot-on"); }
  // upstream
  const nd = $("pdNet"), nv = $("pvNet");
  if (s.upstream && s.upstream.mgmt_ip) { nd.className = s.internet ? "dot ok" : "dot warn"; nv.textContent = s.upstream.mgmt_ip; }
  else { nd.className = "dot err"; nv.textContent = t("up_none"); }
}
function renderConnection(s) {
  const w = s.wifi;
  const full = $("connFull"), empty = $("connEmpty");
  if (w.connected) {
    full.style.display = ""; empty.style.display = "none";
    $("cSsid").textContent = w.ssid || "—";
    $("cSignalTxt").textContent = `${w.signal ?? "—"} dBm · ${w.quality ?? 0}%`;
    $("cSec").textContent = "WPA2/3"; // security comes from saved profile; scan row has exact
    $("cChan").textContent = `${t("ch")} ${w.channel ?? "—"} · ${w.freq ? (w.freq / 1000).toFixed(3) + " GHz" : ""}`;
    $("cBand").textContent = (w.band || "2.4GHz").replace("GHz", " GHz");
    $("cIp").textContent = (w.ip ? w.ip + "/" + w.prefix : "—");
    $("cIface").textContent = `${w.iface} · ${w.driver || ""}`;
    $("cGw").textContent = (s.upstream && s.upstream.default_gw) || "—";
    $("cRate").textContent = [w.rx_rate, w.tx_rate].filter(Boolean).join(" ↓ ↑ ") || "—";
    $("cSub").textContent = w.autoconnect ? "autoconnect ✓" : "autoconnect off";
    const n = bars(w.quality || 0);
    [...$("cBars").children].forEach((el, i) => el.classList.toggle("on", i < n));
    $("btnDisconnect").style.display = "";
  } else {
    full.style.display = "none"; empty.style.display = "";
    $("cSub").textContent = "";
  }
}
function netRowHTML(r) {
  const n = bars(r.quality);
  const barsHTML = `<span class="bars" style="height:16px">${[1, 2, 3, 4].map(i =>
    `<i class="${i <= n ? "on" : ""}" style="height:${4 + i * 3}px;width:4px"></i>`).join("")}</span>`;
  const lock = r.open
    ? `<svg class="lock open"><use href="#i-unlock"/></svg>`
    : `<svg class="lock"><use href="#i-lock"/></svg>`;
  const secTag = r.open ? t("open_net") : (r.wpa3 && !r.wpa2 ? "WPA3" : "WPA2");
  return `<div class="net ${r.in_use ? "active" : ""}" data-ssid="${esc(r.ssid)}" data-open="${r.open ? 1 : 0}" data-sec="${esc(r.security)}">
    ${lock}
    <div class="nmain">
      <div class="nssid">${esc(r.ssid || t("ssid_hidden"))}${r.in_use ? ' <span class="tag">' + t("st_connected") + "</span>" : ""}</div>
      <div class="nmeta"><span>${t("ch")} ${r.channel ?? "?"}</span><span>${(r.freq / 1000).toFixed(1)} GHz</span><span>${esc(secTag)}</span></div>
    </div>
    <div class="sig">${barsHTML}<span>${r.signal}%</span></div>
    <button class="btn sm primary gobtn">${r.in_use ? t("st_connected") : t("b_connect")}</button>
  </div>`;
}
function renderScan(rows) {
  scanRows = rows;
  scanBusy = false;
  $("btnScan").disabled = false;
  const list = $("scanList");
  if (!rows || rows.length === 0) {
    list.innerHTML = `<div class="empty"><div class="d">${t("scan_empty")}</div></div>`;
  } else {
    list.innerHTML = rows.map(netRowHTML).join("");
    list.querySelectorAll(".net").forEach(el => {
      el.onclick = () => openConnect(el.dataset.ssid, el.dataset.open === "1", el.dataset.sec);
    });
  }
  $("scanTime").textContent = t("last_scan") + " " + new Date().toLocaleTimeString();
}
function renderSaved(s) {
  const list = $("savedList");
  const saved = s.saved || [];
  $("savedCount").textContent = saved.length ? saved.length + (saved.length > 1 ? " profiles" : " profile") : "";
  if (!saved.length) { list.innerHTML = `<div class="empty"><div class="d">${t("saved_empty")}</div></div>`; return; }
  const activeName = s.wifi.active_con;
  list.innerHTML = saved.map(c => `
    <div class="net ${c.name === activeName ? "active" : ""}" data-name="${esc(c.name)}">
      <svg class="lock"><use href="#i-lock"/></svg>
      <div class="nmain">
        <div class="nssid">${esc(c.name)}${c.name === activeName ? ' <span class="tag">' + t("st_connected") + "</span>" : ""}</div>
        <div class="nmeta"><span>${c.autoconnect ? t("on") : t("off")}</span><span class="mono">${esc(c.device || "—")}</span></div>
      </div>
      <div style="display:flex;gap:6px">
        ${c.name !== activeName ? `<button class="btn sm act-connect">${t("saved_connect")}</button>` : `<button class="btn sm danger act-disconnect">${t("b_disconnect")}</button>`}
        <button class="btn sm danger act-forget" title="${t("saved_forget")}"><svg><use href="#i-trash"/></svg></button>
      </div>
    </div>`).join("");
  list.querySelectorAll(".net").forEach(el => {
    const name = el.dataset.name;
    el.querySelector(".act-connect") && (el.querySelector(".act-connect").onclick = async ev => {
      ev.stopPropagation(); startJob("/api/reconnect", { name });
    });
    el.querySelector(".act-disconnect") && (el.querySelector(".act-disconnect").onclick = ev => {
      ev.stopPropagation(); doDisconnect();
    });
    el.querySelector(".act-forget") && (el.querySelector(".act-forget").onclick = ev => {
      ev.stopPropagation();
      if (confirm(t("confirm_forget_q") + "\n" + name)) startJob("/api/forget", { name });
    });
  });
}
function renderHotspot(s) {
  const h = s.hotspot || { active: false };
  const active = h.active;
  $("hsActive").style.display = active ? "" : "none";
  $("hsForm").style.display = active ? "none" : "";
  $("hsSub").textContent = active ? t("st_on") : t("st_off");
  if (active) {
    $("hsSsidView").textContent = h.ssid || "—";
    $("hsModeTag").textContent = h.mode === "exclusive" ? t("hs_excl") : t("hs_dual");
    $("hsChanTag").textContent = `${t("ch")} ${h.channel ?? "?"} · ${(h.freq / 1000 || 2.442).toFixed(3)} GHz`;
    $("hsIp").textContent = h.addr || "—";
    $("hsIface").textContent = h.iface || "—";
    $("hsClients").textContent = String((h.clients || []).length);
    $("hsUp").textContent = (s.upstream && s.upstream.default_iface) || "—";
    $("hsBanner").innerHTML = h.mode === "exclusive"
      ? `<div class="banner warn"><svg><use href="#i-alert"/></svg><span>${LANG === "fa" ? "حالت انحصاری: رابط وای‌فای به‌عنوان AP استفاده می‌شود و اتصال کلاینت وای‌فای قطع است. مسیر مدیریتی eth0 دست‌نخورده باقی می‌ماند." : "Exclusive mode: the Wi-Fi interface is the AP, so the Wi-Fi client link is down. The eth0 management path is untouched."}</span></div>`
      : "";
    renderClients(h);
  } else {
    $("hsBanner").innerHTML = "";
    renderClients({ clients: [] });
    // prefill form from saved config (first time only keeps user edits)
    const cfg = s.hotspot_cfg || {};
    if (!$("hsForm").dataset.touched) {
      $("hsSsid").value = cfg.ssid || "ZimaOS Hotspot";
      $("hsPass").value = cfg.password || "";
      $("hsSubnet").value = cfg.subnet || "10.42.0.1/24";
      $("hsSecurity").value = cfg.security || "wpa2";
      $("hsAutostart").checked = !!cfg.autostart;
      if (cfg.channel) $("hsChannel").value = String(cfg.channel);
    }
  }
}
function renderClients(h) {
  const clients = (h && h.clients) || [];
  $("clientsCount").textContent = String(clients.length);
  if (!clients.length) {
    $("clientsEmpty").style.display = "";
    $("clientsWrap").style.display = "none";
    return;
  }
  $("clientsEmpty").style.display = "none";
  $("clientsWrap").style.display = "";
  $("clientsBody").innerHTML = clients.map(c => {
    const q = c.quality ?? (c.signal ? Math.max(0, Math.min(100, (c.signal + 100) * 2)) : 0);
    const dur = c.connected_time != null ? fmtDur(c.connected_time) : "—";
    return `<tr>
      <td class="mono">${esc(c.mac)}${c.hostname ? "<br><b>" + esc(c.hostname) + "</b>" : ""}</td>
      <td class="mono">${esc(c.ip || "—")}</td>
      <td>${c.signal != null ? c.signal + " dBm" : "—"} <span class="muted">(${q}%)</span></td>
      <td>${dur}</td></tr>`;
  }).join("");
}
function fmtDur(sec) {
  if (sec < 60) return sec + "s";
  if (sec < 3600) return Math.floor(sec / 60) + "m";
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60);
  return h + "h " + m + "m";
}
function renderCaps(s) {
  const c = s.caps || {};
  const chip = (label, ok) => `<span class="cap ${ok ? "y" : "n"}">${label} <b>${ok ? "✓ " + t("cap_yes") : "✕ " + t("cap_no")}</b></span>`;
  $("capsChips").innerHTML = [
    chip("AP mode", c.ap_mode),
    chip("STA+AP simultaneous", c.simultaneous),
    chip("WPA3 (SAE)", c.wpa3_client),
    chip("5 GHz band", c.five_ghz),
    `<span class="cap"><b>${esc((c.band || []).join(" + "))}</b></span>`,
    `<span class="cap">${esc(c.driver || "")} · ${esc(c.phy || "")}</span>`,
  ].join("");
  $("dMgmt").textContent = s.upstream && s.upstream.mgmt_ip || "—";
  $("dDefault").textContent = s.upstream && s.upstream.default_iface ? `${s.upstream.default_iface} → ${s.upstream.default_gw}` : "—";
  $("dInternet").textContent = s.internet ? "✓ " + t("up_ok") : "✗";
  $("dInternet").style.color = s.internet ? "var(--ok)" : "var(--warn)";
  $("dDns").textContent = (s.dns || []).slice(0, 3).join(", ") || "—";
}
function renderEvents(s) {
  const list = $("logList");
  const evts = s.events || [];
  list.innerHTML = evts.map(e =>
    `<div class="logline ${e.level === "error" ? "err" : ""}"><span class="ts">${new Date(e.t * 1000).toLocaleTimeString()}</span> ${esc(e.evt)} ${esc(compact(e))}</div>`
  ).join("") || '<div class="muted">—</div>';
}
function compact(e) {
  const skip = new Set(["t", "evt", "level", "trace"]);
  return Object.entries(e).filter(([k]) => !skip.has(k))
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : v}`).join(" ").slice(0, 180);
}
function render(s) {
  statusData = s;
  renderPills(s); renderConnection(s); renderHotspot(s); renderSaved(s); renderCaps(s); renderEvents(s);
}

/* ============================== interactions ============================== */
async function refresh() {
  try { render(await api("/api/status")); }
  catch (e) { $("pdClient").className = "dot err"; $("pvClient").textContent = t("err_network"); }
}
function startJob(path, body) {
  return api(path, "POST", body || {}).then(r => {
    if (r && r.job) { trackJob(r.job); pollJob(r.job.id); } // poll in case SSE is blocked
    return r;
  }).catch(e => toast("err", t("toast_error"), e.message, 6500));
}
// Fallback delivery for job results: SSE is the fast path, this guarantees completion.
async function pollJob(id) {
  for (let i = 0; i < 150; i++) {
    await new Promise(res => setTimeout(res, 1200));
    let j = null;
    try { j = await api("/api/jobs/" + id); } catch (e) { continue; }
    if (j && j.state && j.state !== "running") { handleJobEvent(j); return; }
  }
}
function doScan(silent) {
  if (scanBusy) return;
  scanBusy = true;
  scanSilent = !!silent;
  $("btnScan").disabled = true;
  $("scanList").innerHTML = '<div class="skel"></div><div class="skel"></div><div class="skel"></div>';
  api("/api/scan", "POST", { rescan: true })
    .then(r => { if (r && r.job) { trackJob(r.job); pollJob(r.job.id); } })
    .catch(e => {                       // POST failed → never leave skeletons behind
      scanBusy = false; scanSilent = false;
      $("btnScan").disabled = false;
      toast("err", t("toast_error"), e.message, 6500);
      if (scanRows) renderScan(scanRows);
      else $("scanList").innerHTML = `<div class="empty"><div class="d">${esc(e.message)}</div></div>`;
    });
}
function doDisconnect() {
  if (!confirm(t("confirm_disconnect_q"))) return;
  startJob("/api/disconnect", {});
}

/* ---- modal ---- */
let modalCtx = null;
function openConnect(ssid, isOpen, security) {
  modalCtx = { ssid, open: isOpen, security };
  $("mTitle").textContent = ssid;
  $("mErr").classList.remove("show");
  $("mPass").value = "";
  $("mSubmit").disabled = false;
  $("mPassWrap").style.display = isOpen ? "none" : "";
  $("mOpenNote").style.display = isOpen ? "" : "none";
  $("mLock").querySelector("use").setAttribute("href", isOpen ? "#i-unlock" : "#i-lock");
  $("mLock").style.stroke = isOpen ? "var(--warn)" : "var(--fg3)";
  $("modal").classList.add("show");
  setTimeout(() => { if (!isOpen) $("mPass").focus(); }, 60);
}
function closeModal() { $("modal").classList.remove("show"); modalCtx = null; }
async function submitConnect() {
  if (!modalCtx) return;
  const body = { ssid: modalCtx.ssid, open: modalCtx.open, security: modalCtx.security };
  if (!modalCtx.open) {
    const pw = $("mPass").value;
    if (pw.length < 8) {
      $("mErr").classList.add("show");
      $("mErrTxt").textContent = LANG === "fa" ? "رمز عبور باید حداقل ۸ کاراکتر باشد." : "Password must be at least 8 characters.";
      return;
    }
    body.password = pw;
  }
  $("mErr").classList.remove("show");
  $("mSubmit").disabled = true;
  try {
    const r = await api("/api/connect", "POST", body);
    if (r.job) trackJob(r.job);
    showJob(t("j_connecting"));
  } catch (e) {
    $("mErr").classList.add("show");
    $("mErrTxt").textContent = e.message;
    $("mSubmit").disabled = false;
  }
}
async function doStartHotspot() {
  const ssid = $("hsSsid").value.trim();
  const pass = $("hsPass").value;
  if (!ssid) { toast("err", t("toast_error"), t("f_hssid") + " ?"); return; }
  if (pass.length < 8) { toast("err", t("toast_error"), LANG === "fa" ? "رمز عبور باید ۸ تا ۶۳ کاراکتر باشد." : "Password must be 8–63 characters."); return; }
  const body = {
    ssid, password: pass,
    channel: $("hsChannel").value === "auto" ? null : Number($("hsChannel").value),
    subnet: $("hsSubnet").value.trim() || null,
    security: $("hsSecurity").value,
    autostart: $("hsAutostart").checked,
  };
  startJob("/api/hotspot/start", body);
}
function doStopHotspot() {
  if (!confirm(t("confirm_stop_q"))) return;
  startJob("/api/hotspot/stop", {});
}
async function runDiag() {
  $("btnDiag").disabled = true;
  $("diagOut").innerHTML = `<div class="muted">${t("diag_running")} <span class="spin-sm"></span></div>`;
  try {
    const d = await api("/api/diag");
    $("diagOut").innerHTML = `
      <div class="logline">NetworkManager: ${esc(d.networkmanager)} · wifi-manager: ${esc(d.self)} · internet: ${d.internet ? "✓" : "✗"} · hotspot: ${d.hotspot_active ? "✓" : "✗"}</div>
      <div class="logline">${(d.addresses || []).map(esc).join("<br>")}</div>
      <div class="logline">${(d.routes || []).filter(r => r.startsWith("default") || r.startsWith("10.")).map(esc).join("<br>")}</div>
      <div class="logline">${esc(d.rollback || "")}</div>
      <div class="muted">backups: ${esc((d.backups || []).join(", ") || "—")}</div>`;
  } catch (e) { $("diagOut").innerHTML = `<div class="errline show">${esc(e.message)}</div>`; }
  $("btnDiag").disabled = false;
}
const ROLLBACK_TXT =
  "ZimaOS Wi-Fi Manager rollback:\n" +
  "1) systemctl stop wifi-manager && systemctl disable wifi-manager\n" +
  "2) rm /etc/systemd/system/wifi-manager.service && systemctl daemon-reload\n" +
  "3) Restore NetworkManager keyfiles: cp -a /DATA/wifi-manager/backup/nm-connections-<ts>/ /etc/NetworkManager/system-connections/\n" +
  "4) Restore firewall: iptables-restore < /DATA/wifi-manager/backup/iptables-<ts>.rules\n" +
  "5) systemctl restart NetworkManager\n" +
  "6) Remove tile: cd /var/lib/casaos/apps/wifi-manager && AppID=wifi-manager docker compose down && rm -rf /var/lib/casaos/apps/wifi-manager && systemctl restart zimaos-app-management";

/* ============================== SSE ============================== */
function connectSSE() {
  if (evtSource) { try { evtSource.close(); } catch (e) {} }
  evtSource = new EventSource("/api/events");
  evtSource.onmessage = ev => {
    let m; try { m = JSON.parse(ev.data); } catch (e) { return; }
    if (m.kind === "status" && m.data && !m.data.error) render(m.data);
    else if (m.kind === "job" && m.data) handleJobEvent(m.data);
    else if (m.kind === "scan" && m.data && m.data.rows) renderScan(m.data.rows);
    else if (m.kind === "log" && statusData) {
      statusData.events = statusData.events || [];
      statusData.events.unshift(m.data);
      statusData.events = statusData.events.slice(0, 14);
      renderEvents(statusData);
    }
  };
  evtSource.onerror = () => { /* EventSource auto-reconnects */ };
}

/* ============================== init ============================== */
function initChannelSelect() {
  const sel = $("hsChannel");
  let html = `<option value="auto">${t("chan_auto")}</option>`;
  for (let i = 1; i <= 13; i++) html += `<option value="${i}">${i}</option>`;
  sel.innerHTML = html;
}
function boot() {
  applyLang();
  initChannelSelect();
  refresh();
  connectSSE();
  setInterval(refresh, 10000); // fallback poll
  setTimeout(() => doScan(true), 350); // populate "Available networks" on load

  $("btnLang").onclick = () => {
    LANG = LANG === "en" ? "fa" : "en";
    localStorage.setItem("wm-lang", LANG);
    applyLang();
    if (statusData) render(statusData); else refresh();
    if (scanRows) renderScan(scanRows);
  };
  $("btnRefresh").onclick = () => { $("btnRefresh").classList.add("spinning"); refresh().finally?.(() => {}); setTimeout(() => $("btnRefresh").classList.remove("spinning"), 700); };
  $("btnScan").onclick = () => doScan(false);
  $("btnDisconnect").onclick = doDisconnect;
  $("btnReconnect").onclick = () => startJob("/api/reconnect", {});
  $("btnReconnect2").onclick = () => startJob("/api/reconnect", {});
  $("btnHsStart").onclick = doStartHotspot;
  $("btnHsStop").onclick = doStopHotspot;
  $("btnDiag").onclick = runDiag;
  $("btnCopyRollback").onclick = async () => {
    try { await navigator.clipboard.writeText(ROLLBACK_TXT); toast("ok", t("toast_copied")); }
    catch (e) { toast("info", "rollback", ROLLBACK_TXT, 12000); }
  };
  $("btnHidden").onclick = () => {
    const ssid = $("hiddenSsid").value.trim();
    if (!ssid) return;
    openConnect(ssid, false, "WPA2");
    $("mHint").textContent = LANG === "fa" ? "شبکه پنهان — اگر رمز ندارد، گزینه شبکه باز را ببینید." : "Hidden network — leave password empty if it is open (use open networks from scan instead).";
  };
  $("mSubmit").onclick = submitConnect;
  $("mCancel").onclick = closeModal;
  $("mClose").onclick = closeModal;
  $("modal").onclick = e => { if (e.target === $("modal")) closeModal(); };
  $("mPass").onkeydown = e => { if (e.key === "Enter") submitConnect(); };
  const eyeHandler = (btn, inp) => {
    btn.onclick = () => {
      const show = inp.type === "password";
      inp.type = show ? "text" : "password";
      btn.querySelector("use").setAttribute("href", show ? "#i-eyeoff" : "#i-eye");
    };
  };
  eyeHandler($("mEye"), $("mPass"));
  eyeHandler($("newPassEye"), $("newPass"));
  $("btnChangePass").onclick = async () => {
    const cur = $("curPass").value, nw = $("newPass").value, rep = $("repPass").value;
    const errBox = $("pwErr"), errTxt = $("pwErrTxt");
    const fail = m => { errBox.classList.add("show"); errTxt.textContent = m; };
    errBox.classList.remove("show");
    if (nw.length < 6) return fail(t("pw_short"));
    if (nw !== rep) return fail(t("pw_mismatch"));
    $("btnChangePass").disabled = true;
    try {
      await api("/api/settings/password", "POST", { current: cur, new: nw });
      toast("ok", t("pw_updated"));
      $("curPass").value = ""; $("newPass").value = ""; $("repPass").value = "";
    } catch (e) {
      fail(e.code === 401 || /current/i.test(e.message || "") ? t("pw_badcur") : e.message);
    }
    $("btnChangePass").disabled = false;
  };
  eyeHandler($("hsPassEye"), $("hsPass"));
  ["hsSsid", "hsPass", "hsSubnet", "hsSecurity", "hsChannel", "hsAutostart"].forEach(id => {
    const el = $(id);
    el.addEventListener("input", () => { $("hsForm").dataset.touched = "1"; });
    el.addEventListener("change", () => { $("hsForm").dataset.touched = "1"; });
  });
}
document.addEventListener("DOMContentLoaded", boot);
