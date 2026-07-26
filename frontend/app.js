// ── 都道府県カラーテーブル（地方ブロック別） ────────────────────────────────
const PREFECTURE_COLORS = {
  北海道: "#1565C0",
  青森県: "#2E7D32", 岩手県: "#388E3C", 宮城県: "#43A047",
  秋田県: "#4CAF50", 山形県: "#66BB6A", 福島県: "#81C784",
  茨城県: "#E65100", 栃木県: "#EF6C00", 群馬県: "#F57C00",
  埼玉県: "#FB8C00", 千葉県: "#FFA726", 東京都: "#D84315",
  神奈川県: "#FF5722",
  新潟県: "#6A1B9A", 富山県: "#7B1FA2", 石川県: "#8E24AA",
  福井県: "#9C27B0", 山梨県: "#AB47BC", 長野県: "#BA68C8",
  岐阜県: "#CE93D8", 静岡県: "#7B1FA2", 愛知県: "#4A148C",
  三重県: "#880E4F", 滋賀県: "#AD1457", 京都府: "#C2185B",
  大阪府: "#E91E63", 兵庫県: "#EC407A", 奈良県: "#F06292",
  和歌山県: "#F48FB1",
  鳥取県: "#00695C", 島根県: "#00796B", 岡山県: "#00897B",
  広島県: "#009688", 山口県: "#26A69A",
  徳島県: "#BF360C", 香川県: "#D84315", 愛媛県: "#E64A19",
  高知県: "#FF5722",
  福岡県: "#37474F", 佐賀県: "#455A64", 長崎県: "#546E7A",
  熊本県: "#607D8B", 大分県: "#78909C", 宮崎県: "#90A4AE",
  鹿児島県: "#B0BEC5",
  沖縄県: "#00838F",
};
const DEFAULT_COLOR = "#757575";

function getPrefectureColor(prefecture) {
  return PREFECTURE_COLORS[prefecture] || DEFAULT_COLOR;
}

// ── 認証 ─────────────────────────────────────────────────────────────────────
let currentUser = null;

async function checkAuth() {
  try {
    const r = await fetch("/api/auth/me");
    if (r.ok) {
      currentUser = await r.json();
      return currentUser;
    }
  } catch (_) {}
  return null;
}

async function logout() {
  await fetch("/api/auth/logout", { method: "POST" });
  location.reload();
}

// Google Sign-In コールバック（GIS ライブラリが呼び出す）
async function handleGoogleSignIn(response) {
  const r = await fetch("/api/auth/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ credential: response.credential }),
  });
  if (r.ok) {
    location.reload();
  } else {
    const err = await r.json().catch(() => ({}));
    alert("ログインに失敗しました: " + (err.error || "不明なエラー"));
  }
}

function renderGoogleSignInButton(containerId) {
  if (window.google && google.accounts) {
    google.accounts.id.renderButton(document.getElementById(containerId), {
      theme: "outline",
      size: "medium",
      locale: "ja",
    });
  }
}

// ── API: ロケーション取得（認証必須） ─────────────────────────────────────────
async function loadLocations() {
  const r = await fetch("/api/locations");
  if (r.status === 401) throw new Error("auth_required");
  if (!r.ok) throw new Error("ロケーション取得に失敗しました");
  return r.json();
}

// ── 都道府県・市区町村でグループ化 ──────────────────────────────────────────
function groupLocations(locations) {
  const grouped = {};
  for (const loc of locations) {
    const pref = loc.prefecture || "不明";
    const city = loc.city || "不明";
    if (!grouped[pref]) grouped[pref] = {};
    if (!grouped[pref][city]) grouped[pref][city] = [];
    grouped[pref][city].push(loc);
  }
  return grouped;
}

// ── CSV エクスポート ─────────────────────────────────────────────────────────
function exportCsv(locations) {
  const header = ["店名", "住所", "都道府県", "市区町村", "緯度", "経度", "Instagram URL"];
  const rows = locations.map((l) => [
    l.shop_name || "",
    l.address || "",
    l.prefecture || "",
    l.city || "",
    l.lat || "",
    l.lng || "",
    l.instagram_url || "",
  ]);
  const csvContent =
    "﻿" +
    [header, ...rows]
      .map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(","))
      .join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `instagram_shops_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ── API ヘルパー ─────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.error || `HTTP ${r.status}`);
  }
  return r.json();
}

// ── ジャンル別ピン設定 ────────────────────────────────────────────────────────
const GENRE_STORAGE_KEY = "igmap_genre_settings";

const DEFAULT_GENRES = [
  { id: "cafe",        name: "カフェ・喫茶",               icon: "☕",  color: "#5D4037", size: 1.0,
    keywords: ["カフェ","喫茶","珈琲","コーヒー","coffee","cafe","純喫茶","紅茶","ティー","tea","カフェバー","カフェレストラン","ベーカリーカフェ","シェアラウンジ","動物カフェ","ブックカフェ","テーマカフェ","古民家カフェ","甘味処"] },
  { id: "hotel",       name: "ホテル・リゾート・温泉宿",   icon: "🏨",  color: "#37474F", size: 1.0,
    keywords: ["ホテル","旅館","リゾート","温泉","グランピング","宿","ラブホ","ペンション","コテージ","貸別荘"] },
  { id: "izakaya",     name: "居酒屋・酒場",               icon: "🍺",  color: "#4E342E", size: 1.0,
    keywords: ["居酒屋","酒場","炉端","クラフトビール","ビアバー","パブ","立ち飲み","ビアホール"] },
  { id: "ramen",       name: "ラーメン・麺類・そば",        icon: "🍜",  color: "#E65100", size: 1.0,
    keywords: ["ラーメン","らーめん","拉麺","麺","うどん","そば","蕎麦","つけ麺","担々麺","ラーメン店","蕎麦屋"] },
  { id: "italian",     name: "イタリアン・フレンチ・洋食",  icon: "🍝",  color: "#2E7D32", size: 1.0,
    keywords: ["イタリアン","イタリア","フレンチ","フランス料理","フランス菓子","ビストロ","洋食","ピザ","ピッツェリア","ダイナー","グリル"] },
  { id: "bakery",      name: "ベーカリー・パン屋",          icon: "🥐",  color: "#FF8F00", size: 1.0,
    keywords: ["ベーカリー","パン","パン屋","ブレッド","bread"] },
  { id: "sweets",      name: "スイーツ・デザート",          icon: "🍰",  color: "#AD1457", size: 1.0,
    keywords: ["スイーツ","ケーキ","パティスリー","デザート","アイス","ジェラート","クレープ","ドーナツ","チョコ","菓子","和菓子","甘味","ショコラ"] },
  { id: "amusement",   name: "テーマパーク・アミューズメント", icon: "🎡", color: "#7B1FA2", size: 1.0,
    keywords: ["テーマパーク","アミューズメント","遊園地","ゲームセンター","アスレチック","レジャー施設","遊び場"] },
  { id: "restaurant",  name: "レストラン・食堂・定食",      icon: "🍽️", color: "#C62828", size: 1.0,
    keywords: ["レストラン","食堂","ダイニング","定食","家庭料理","ビュッフェ","バイキング","食べ放題","ファミレス"] },
  { id: "bar",         name: "バー・ワインバー",            icon: "🍷",  color: "#1A237E", size: 1.0,
    keywords: ["バー","bar","ワインバー","ワイン","カクテル","ナイトプール","ビアバー","バー・レストラン"] },
  { id: "yakiniku",    name: "焼肉・ステーキ・肉料理",      icon: "🥩",  color: "#B71C1C", size: 1.0,
    keywords: ["焼肉","やきにく","ステーキ","BBQ","バーベキュー","ハンバーグ","肉","ビーフ","焼き肉"] },
  { id: "sushi",       name: "寿司・海鮮",                  icon: "🍣",  color: "#0277BD", size: 1.0,
    keywords: ["寿司","すし","鮨","海鮮","刺身","海鮮丼","海鮮レストラン"] },
  { id: "shopping",    name: "ショッピング・雑貨",           icon: "🛍️", color: "#00838F", size: 1.0,
    keywords: ["ショッピング","ショップ","雑貨","買い物","モール","百貨店","マーケット","ショッピングモール"] },
  { id: "museum",      name: "ミュージアム・博物館",         icon: "🏛️", color: "#4527A0", size: 1.0,
    keywords: ["ミュージアム","博物館","美術館","科学館","ギャラリー","展示","展覧","資料館"] },
  { id: "ethnic",      name: "アジア・エスニック料理",       icon: "🌮",  color: "#558B2F", size: 1.0,
    keywords: ["タイ","インド","メキシコ","中東","エスニック","スペイン","アジア料理","ベトナム","韓国以外のアジア"] },
  { id: "tourism",     name: "観光スポット・公園",           icon: "🌸",  color: "#00695C", size: 1.0,
    keywords: ["観光","公園","道の駅","名所","スポット","庭園","広場","観光地","観光スポット"] },
  { id: "chinese",     name: "中華料理",                    icon: "🥟",  color: "#D32F2F", size: 1.0,
    keywords: ["中華","中国料理","餃子","点心","飲茶","中華料理"] },
  { id: "korean",      name: "韓国料理",                    icon: "🫕",  color: "#F57F17", size: 1.0,
    keywords: ["韓国","サムギョプサル","ビビンバ","チゲ","トッポッキ","冷麺","韓国料理"] },
  { id: "washoku",     name: "和食・日本料理",               icon: "🍱",  color: "#0288D1", size: 1.0,
    keywords: ["和食","日本料理","懐石","割烹","天ぷら","うなぎ","鰻","天麩羅","日本食"] },
  { id: "burger",      name: "ハンバーガー",                 icon: "🍔",  color: "#FF6D00", size: 1.0,
    keywords: ["ハンバーガー","burger","バーガー","キッチンカー"] },
  { id: "curry",       name: "カレー",                      icon: "🍛",  color: "#F9A825", size: 1.0,
    keywords: ["カレー","curry","スパイス","カレーライス"] },
  { id: "yakitori",    name: "焼き鳥・串焼き",               icon: "🍢",  color: "#6D4C41", size: 1.0,
    keywords: ["焼き鳥","焼鳥","やきとり","串","串焼き","鳥料理"] },
  { id: "spa",         name: "スパ・サウナ・銭湯",           icon: "🧖",  color: "#006064", size: 1.0,
    keywords: ["サウナ","スパ","銭湯","温浴","サウナ・銭湯","銭湯・サウナ","温泉施設","スパリゾート"] },
  { id: "experience",  name: "体験・アクティビティ",         icon: "🏕️", color: "#1B5E20", size: 1.0,
    keywords: ["体験","アクティビティ","アウトドア","キャンプ","トレッキング","釣り","ものづくり"] },
  { id: "complex",     name: "複合施設・道の駅",             icon: "🏢",  color: "#546E7A", size: 1.0,
    keywords: ["複合施設","道の駅","商業施設","アウトレット","道の駅"] },
  { id: "tonkatsu",    name: "とんかつ・揚げ物",             icon: "🍱",  color: "#BF360C", size: 1.0,
    keywords: ["とんかつ","揚げ物","からあげ","天丼","フライ","カツ"] },
  { id: "entertainment", name: "音楽・カラオケ・エンタメ",  icon: "🎵",  color: "#880E4F", size: 1.0,
    keywords: ["音楽","ライブ","カラオケ","スタジオ","シアター","映画","エンタメ"] },
  { id: "other",       name: "その他",                      icon: "📍",  color: "#757575", size: 1.0,
    keywords: [] },
];

let _genresCache = null;

async function fetchGenres() {
  try {
    const data = await apiFetch("/api/genres");
    _genresCache = data;
    return data;
  } catch (_) {
    return JSON.parse(JSON.stringify(DEFAULT_GENRES));
  }
}

async function saveGenres(genres) {
  _genresCache = genres;
  await apiFetch("/api/genres", { method: "PUT", body: JSON.stringify(genres) });
}

function getGenreSettings() {
  return _genresCache ? _genresCache : JSON.parse(JSON.stringify(DEFAULT_GENRES));
}

function detectGenre(shopName, genres) {
  const name = (shopName || "").toLowerCase();
  for (const g of genres) {
    if (g.id === "other") continue;
    for (const kw of (g.keywords || [])) {
      if (name.includes(kw.toLowerCase())) return g;
    }
  }
  return genres.find(g => g.id === "other") || genres[genres.length - 1];
}

// DBに保存されたジャンル名を優先し、設定から色・アイコン・サイズを解決する。
// 完全一致なければ genre 文字列をキーワード検出にかけ、それでもなければ店名で検出。
function resolveGenre(loc, genres) {
  if (loc.genre) {
    const exact = genres.find(g => g.name === loc.genre);
    if (exact) return exact;
    return detectGenre(loc.genre, genres);
  }
  return detectGenre(loc.shop_name, genres);
}

function createPinElement(genre, opts = {}) {
  const size  = Math.max(0.5, Math.min(2.0, Number(genre.size) || 1.0));
  const cw    = Math.round(34 * size);
  const fs    = Math.round(17 * size);
  const sw    = Math.round(6  * size);
  const sh    = Math.round(9  * size);
  const col   = genre.color || "#757575";

  const wrap = document.createElement("div");
  wrap.style.cssText = "display:inline-flex;flex-direction:column;align-items:center;cursor:pointer;";

  const head = document.createElement("div");
  const shadow = opts.wantAgain
    ? "0 0 0 3px #e91e63, 0 0 0 6px rgba(233,30,99,0.25), 0 2px 8px rgba(0,0,0,0.35)"
    : "0 2px 8px rgba(0,0,0,0.35)";
  head.style.cssText =
    `width:${cw}px;height:${cw}px;` +
    `background:${col};` +
    "border-radius:50%;" +
    "border:2px solid rgba(255,255,255,0.85);" +
    `box-shadow:${shadow};` +
    "display:flex;align-items:center;justify-content:center;" +
    `font-size:${fs}px;line-height:1;user-select:none;`;
  head.textContent = genre.icon || "📍";

  const stem = document.createElement("div");
  stem.style.cssText =
    "width:0;height:0;" +
    `border-left:${sw}px solid transparent;` +
    `border-right:${sw}px solid transparent;` +
    `border-top:${sh}px solid ${col};`;

  wrap.appendChild(head);
  wrap.appendChild(stem);
  return wrap;
}

// ─── 訪問記録モーダル ──────────────────────────────────────────────────────────

let _vmCurrentLocId = null;
let _vmCurrentVisitId = null;
let _vmRating = 0;
let _vmVisited = 0;
let _vmExistingImages = [];
let _vmPendingFiles = [];

function _ensureVisitModal() {
  if (document.getElementById("visit-modal-overlay")) return;

  const style = document.createElement("style");
  style.textContent = `
    .vm-overlay {
      position:fixed;inset:0;background:rgba(0,0,0,.5);
      display:none;align-items:center;justify-content:center;z-index:9999;
    }
    .vm-overlay.active { display:flex; }
    .vm-modal {
      background:#fff;border-radius:16px;width:440px;max-width:95vw;
      max-height:90vh;overflow-y:auto;
      box-shadow:0 8px 40px rgba(0,0,0,.22);
      animation:vmIn .18s ease;
    }
    @keyframes vmIn { from{transform:translateY(16px);opacity:0} to{transform:none;opacity:1} }
    .vm-header {
      display:flex;align-items:center;justify-content:space-between;
      padding:18px 20px 14px;border-bottom:1px solid #f0f0f0;
    }
    .vm-title { font-size:15px;font-weight:700;color:#222;flex:1;margin-right:8px; }
    .vm-close {
      background:none;border:none;font-size:20px;cursor:pointer;
      color:#aaa;padding:2px 6px;border-radius:6px;line-height:1;
    }
    .vm-close:hover { background:#f5f5f5;color:#333; }
    .vm-body { padding:20px; }
    .vm-lbl {
      font-size:11px;font-weight:700;color:#888;
      text-transform:uppercase;letter-spacing:.5px;display:block;margin-bottom:8px;
    }
    .vm-section { margin-bottom:18px; }
    .vm-toggle-row { display:flex;gap:8px; }
    .vm-toggle {
      flex:1;padding:8px 12px;border-radius:8px;border:2px solid #e0e0e0;
      background:#fff;font-size:13px;cursor:pointer;transition:all .15s;
    }
    .vm-toggle.active { border-color:#4caf50;background:#e8f5e9;color:#2e7d32;font-weight:700; }
    .vm-stars { display:flex;gap:6px;margin-bottom:4px; }
    .vm-star {
      font-size:30px;cursor:pointer;color:#ddd;transition:color .1s;
      user-select:none;line-height:1;
    }
    .vm-star.lit { color:#ffc107; }
    .vm-hint { font-size:11px;color:#aaa;margin-bottom:14px; }
    .vm-textarea {
      width:100%;box-sizing:border-box;border:1px solid #e0e0e0;border-radius:8px;
      padding:10px 12px;font-size:14px;font-family:inherit;
      resize:vertical;min-height:72px;
    }
    .vm-textarea:focus { outline:none;border-color:#2196f3; }
    .vm-check-row {
      display:flex;align-items:center;gap:10px;
      padding:10px 14px;border-radius:10px;border:1px solid #e0e0e0;
      cursor:pointer;margin-bottom:14px;
    }
    .vm-check-row:hover { background:#fafafa; }
    .vm-check-row input { width:18px;height:18px;cursor:pointer;accent-color:#e91e63; }
    .vm-check-label { font-size:14px;font-weight:600;color:#333; }
    .vm-divider { margin:0 0 18px;border:none;border-top:1px solid #f0f0f0; }
    .vm-footer {
      display:flex;justify-content:flex-end;gap:10px;
      padding:14px 20px;border-top:1px solid #f0f0f0;
    }
    .vm-btn { padding:8px 22px;border-radius:8px;border:none;font-size:14px;font-weight:700;cursor:pointer;transition:.15s; }
    .vm-btn-cancel { background:#f0f0f0;color:#555; }
    .vm-btn-cancel:hover { background:#e0e0e0; }
    .vm-btn-save { background:#1976d2;color:#fff; }
    .vm-btn-save:hover { background:#1565c0; }
    .vm-btn-delete { background:#fff;color:#d32f2f;border:1px solid #ef9a9a;margin-right:auto; }
    .vm-btn-delete:hover { background:#ffebee; }
    .vm-image-grid { display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px; }
    .vm-img-wrap { position:relative;width:76px;height:76px; }
    .vm-img-wrap img { width:100%;height:100%;object-fit:cover;border-radius:8px;cursor:pointer; }
    .vm-img-del {
      position:absolute;top:-6px;right:-6px;width:20px;height:20px;
      background:#f44336;color:#fff;border:none;border-radius:50%;
      font-size:11px;cursor:pointer;display:flex;align-items:center;justify-content:center;
      padding:0;line-height:1;
    }
    .vm-upload-label { display:inline-block;cursor:pointer; }
    .vm-upload-btn {
      display:inline-block;padding:6px 14px;border-radius:8px;
      border:1px dashed #90caf9;color:#1565c0;background:#e3f2fd;
      font-size:13px;
    }
    .vm-upload-btn:hover { background:#bbdefb; }
  `;
  document.head.appendChild(style);

  const el = document.createElement("div");
  el.id = "visit-modal-overlay";
  el.className = "vm-overlay";
  el.innerHTML = `
    <div class="vm-modal" onclick="event.stopPropagation()">
      <div class="vm-header">
        <div style="flex:1;min-width:0">
          <span class="vm-title" id="vm-shop-name"></span>
          <div id="vm-subtitle" style="font-size:11px;color:#888;margin-top:2px;"></div>
        </div>
        <button class="vm-close" onclick="closeVisitModal()">✕</button>
      </div>
      <div class="vm-body">
        <div class="vm-section">
          <span class="vm-lbl">評価 (0〜5)</span>
          <div class="vm-stars" id="vm-stars">
            <span class="vm-star" data-v="1" onclick="vmSetRating(1)" onmouseover="vmHover(1)" onmouseout="vmHover(0)">★</span>
            <span class="vm-star" data-v="2" onclick="vmSetRating(2)" onmouseover="vmHover(2)" onmouseout="vmHover(0)">★</span>
            <span class="vm-star" data-v="3" onclick="vmSetRating(3)" onmouseover="vmHover(3)" onmouseout="vmHover(0)">★</span>
            <span class="vm-star" data-v="4" onclick="vmSetRating(4)" onmouseover="vmHover(4)" onmouseout="vmHover(0)">★</span>
            <span class="vm-star" data-v="5" onclick="vmSetRating(5)" onmouseover="vmHover(5)" onmouseout="vmHover(0)">★</span>
          </div>
          <div class="vm-hint" id="vm-rating-hint">評価なし</div>
        </div>
        <div class="vm-section">
          <span class="vm-lbl">感想</span>
          <textarea id="vm-impression" class="vm-textarea" placeholder="お店の感想を入力..."></textarea>
        </div>
        <hr class="vm-divider">
        <div class="vm-section">
          <label class="vm-check-row">
            <input type="checkbox" id="vm-want-again" onchange="vmToggleWantAgain()">
            <span class="vm-check-label">また行きたい ❤️</span>
          </label>
          <div id="vm-next-section" style="display:none">
            <span class="vm-lbl">次回のコメント</span>
            <textarea id="vm-next-comment" class="vm-textarea" placeholder="次は何を食べたい？試したいことは？"></textarea>
          </div>
        </div>
        <hr class="vm-divider">
        <div class="vm-section">
          <span class="vm-lbl">写真</span>
          <div id="vm-image-grid" class="vm-image-grid"></div>
          <label class="vm-upload-label">
            <input type="file" id="vm-file-input" accept="image/*" multiple style="display:none" onchange="vmHandleFiles(this)">
            <span class="vm-upload-btn">📷 写真を追加</span>
          </label>
        </div>
      </div>
      <div class="vm-footer">
        <button class="vm-btn vm-btn-delete" id="vm-btn-delete" style="display:none" onclick="deleteVisitModal()">🗑 削除</button>
        <button class="vm-btn vm-btn-cancel" onclick="closeVisitModal()">キャンセル</button>
        <button class="vm-btn vm-btn-save"   onclick="saveVisitModal()">保存</button>
      </div>
    </div>
  `;
  el.addEventListener("click", e => { if (e.target === el) closeVisitModal(); });
  document.body.appendChild(el);
}

function _openVisitModalBase(locId, shopName, subtitle) {
  _ensureVisitModal();
  _vmCurrentLocId = locId;
  _vmRating = 0;
  _vmVisited = 1;
  _vmExistingImages = [];
  _vmPendingFiles = [];
  document.getElementById("vm-shop-name").textContent = shopName || "（店名不明）";
  document.getElementById("vm-subtitle").textContent = subtitle;
  document.getElementById("vm-btn-delete").style.display = "none";
  vmSetRating(0);
  document.getElementById("vm-impression").value = "";
  document.getElementById("vm-want-again").checked = false;
  document.getElementById("vm-next-comment").value = "";
  vmToggleWantAgain();
  vmRenderImages();
}

function openVisitModal(locId, shopName) {
  _vmCurrentVisitId = null;
  _openVisitModalBase(locId, shopName, "📝 新しいレビューを投稿");
  document.getElementById("visit-modal-overlay").classList.add("active");
}

async function openVisitModalForEdit(visitId, locId, shopName) {
  _vmCurrentVisitId = visitId;
  _openVisitModalBase(locId, shopName, "✏️ レビューを編集");

  let visit = { visited: 0, rating: 0, impression: "", want_again: 0, next_comment: "", images: [] };
  try { visit = await apiFetch(`/api/visits/${visitId}`); } catch (_) {}

  _vmVisited = 1;
  vmSetRating(visit.rating || 0);
  document.getElementById("vm-impression").value = visit.impression || "";
  document.getElementById("vm-want-again").checked = !!(visit.want_again);
  document.getElementById("vm-next-comment").value = visit.next_comment || "";
  vmToggleWantAgain();
  _vmExistingImages = (visit.images || []).map(img => ({ ...img, url: `/api/visit-images/${img.filename}` }));
  vmRenderImages();

  document.getElementById("vm-btn-delete").style.display = "inline-block";
  document.getElementById("visit-modal-overlay").classList.add("active");
}

function openVisitModalById(locId) {
  const loc = typeof allLocations !== "undefined" ? allLocations.find(l => l.id === locId) : null;
  openVisitModal(locId, loc ? loc.shop_name : "");
}

function closeVisitModal() {
  const el = document.getElementById("visit-modal-overlay");
  if (el) el.classList.remove("active");
  _vmCurrentLocId = null;
  _vmCurrentVisitId = null;
}

async function deleteVisitModal() {
  if (_vmCurrentVisitId === null) return;
  if (!confirm("このレビューを削除しますか？")) return;
  const locId = _vmCurrentLocId;
  const visitId = _vmCurrentVisitId;
  try {
    await apiFetch(`/api/visits/${visitId}`, { method: "DELETE" });
    closeVisitModal();
    if (typeof refreshOpenThread === "function") {
      refreshOpenThread(locId);
    }
  } catch (e) {
    alert("削除に失敗しました: " + e.message);
  }
}

function vmSetVisited(v) {
  _vmVisited = v;
  document.getElementById("vm-btn-notvisited").classList.toggle("active", v === 0);
  document.getElementById("vm-btn-visited").classList.toggle("active", v === 1);
  document.getElementById("vm-visited-section").style.display = v ? "" : "none";
}

function vmSetRating(v) {
  _vmRating = v;
  vmRenderStars(v);
}

function vmHover(v) {
  vmRenderStars(v || _vmRating);
}

const _RATING_LABELS = ["評価なし", "★ いまいち", "★★ 普通", "★★★ 良い", "★★★★ とても良い", "★★★★★ 最高！"];

function vmRenderStars(highlight) {
  document.querySelectorAll(".vm-star").forEach(s => {
    s.classList.toggle("lit", parseInt(s.dataset.v) <= highlight);
  });
  const hint = document.getElementById("vm-rating-hint");
  if (hint) hint.textContent = _RATING_LABELS[highlight] || "評価なし";
}

function vmToggleWantAgain() {
  const checked = document.getElementById("vm-want-again").checked;
  document.getElementById("vm-next-section").style.display = checked ? "" : "none";
}

async function saveVisitModal() {
  if (_vmCurrentLocId === null) return;
  const data = {
    visited: _vmVisited,
    rating: _vmRating,
    impression: document.getElementById("vm-impression").value.trim(),
    want_again: document.getElementById("vm-want-again").checked ? 1 : 0,
    next_comment: document.getElementById("vm-next-comment").value.trim(),
  };
  try {
    let visitId = _vmCurrentVisitId;
    if (visitId === null) {
      const res = await apiFetch(`/api/locations/${_vmCurrentLocId}/visit`, {
        method: "POST", body: JSON.stringify(data),
      });
      visitId = res.visit_id;
    } else {
      await apiFetch(`/api/visits/${visitId}`, {
        method: "PUT", body: JSON.stringify(data),
      });
    }
    for (const file of _vmPendingFiles) {
      const fd = new FormData();
      fd.append("image", file);
      fd.append("visit_id", visitId);
      await fetch(`/api/locations/${_vmCurrentLocId}/visit/images`, {
        method: "POST", body: fd, credentials: "same-origin",
      });
    }
    const loc = typeof allLocations !== "undefined" ? allLocations.find(l => l.id === _vmCurrentLocId) : null;
    if (loc) Object.assign(loc, data);
    _updateShopItemVisitUI(_vmCurrentLocId, data);
    if (typeof refreshOpenThread === "function") {
      refreshOpenThread(_vmCurrentLocId);
    }
    closeVisitModal();
  } catch (e) {
    alert("保存に失敗しました: " + e.message);
  }
}

function _updateShopItemVisitUI(locId, data) {
  const shopItem = document.querySelector(`.shop-item[data-loc-id="${locId}"]`);
  if (!shopItem) return;

  // ピンク網掛け
  shopItem.dataset.wantAgain = data.want_again ? "1" : "";

  // ハートアイコン（店名前）
  const shopTop = shopItem.querySelector(".shop-top");
  if (shopTop) {
    let heart = shopTop.querySelector(".want-heart");
    if (data.want_again && !heart) {
      heart = document.createElement("span");
      heart.className = "want-heart";
      heart.textContent = "❤️";
      shopTop.insertBefore(heart, shopTop.firstChild);
    } else if (!data.want_again && heart) {
      heart.remove();
    }
  }

  // 訪問済みステータス行
  const shopMain = shopItem.querySelector(".shop-main");
  let statusLine = shopItem.querySelector(".visit-status-line");
  if (data.visited) {
    const stars = "★".repeat(data.rating || 0) + "☆".repeat(5 - (data.rating || 0));
    if (!statusLine) {
      statusLine = document.createElement("div");
      statusLine.className = "visit-status-line";
      const shopTopEl = shopMain && shopMain.querySelector(".shop-top");
      if (shopTopEl && shopTopEl.nextSibling) {
        shopMain.insertBefore(statusLine, shopTopEl.nextSibling);
      } else if (shopMain) {
        shopMain.appendChild(statusLine);
      }
    }
    statusLine.innerHTML = `<span class="visit-status">✓ 訪問済み ${stars}</span>`;
  } else if (statusLine) {
    statusLine.remove();
  }
}

function vmHandleFiles(input) {
  _vmPendingFiles.push(...Array.from(input.files));
  vmRenderImages();
  input.value = "";
}

function vmRenderImages() {
  const grid = document.getElementById("vm-image-grid");
  if (!grid) return;
  const existHtml = _vmExistingImages.map(img => {
    const src = img.url || `/api/visit-images/${img.filename}`;
    return `<div class="vm-img-wrap">
      <img src="${src}" onclick="window.open('${src}','_blank')">
      <button class="vm-img-del" onclick="vmDeleteExistingImage(${img.id})">✕</button>
    </div>`;
  }).join("");
  const pendHtml = _vmPendingFiles.map((f, i) => {
    const url = URL.createObjectURL(f);
    return `<div class="vm-img-wrap">
      <img src="${url}">
      <button class="vm-img-del" onclick="vmRemovePendingImage(${i})">✕</button>
    </div>`;
  }).join("");
  grid.innerHTML = existHtml + pendHtml;
}

async function vmDeleteExistingImage(imageId) {
  await apiFetch(`/api/visit-images/${imageId}`, { method: "DELETE" });
  _vmExistingImages = _vmExistingImages.filter(img => img.id !== imageId);
  vmRenderImages();
}

function vmRemovePendingImage(index) {
  _vmPendingFiles.splice(index, 1);
  vmRenderImages();
}

// ── モバイルナビ ──────────────────────────────────────────────────────────────
function toggleNav() {
  const nav = document.getElementById("header-nav");
  if (nav) nav.classList.toggle("open");
}
document.addEventListener("click", function(e) {
  const nav = document.getElementById("header-nav");
  const btn = document.getElementById("hamburger-btn");
  if (nav && nav.classList.contains("open") &&
      !nav.contains(e.target) && e.target !== btn) {
    nav.classList.remove("open");
  }
});
