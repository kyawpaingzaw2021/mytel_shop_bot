const tg = window.Telegram.WebApp; tg.expand();
window.onerror = function(msg, url, line) {
    if (typeof tg !== 'undefined' && tg.showAlert) tg.showAlert("⚠️ Error: " + msg + " (Line: " + line + ")");
    return true;
};

let selectedItemId = null, currentFilters = { orders: 'pending', topups: 'pending' };
let isMaintenance = "off", currentBalance = 0, currentUserRole = "user", allItems = [], categoryImages = {}, currentUserId = null;
let currentView = 'main', currentCat = null, currentSub = null, userDefaultPhone = '', isSubmittingOrder = false;
let waitTimeText = '၅ မိနစ်';
window.allAdminItems = [];

function openModal(id) { document.getElementById(id).classList.add('show'); }
function closeModal(id) { document.getElementById(id).classList.remove('show'); }
function getCategories(s) { if (!s) return ["Other"]; return s.split(',').map(c => c.trim()).filter(c => c); }

async function updateBalance() {
    try {
        const res = await fetch('/api/user/balance', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
        if (!res.ok) return;
        const data = await res.json();
        if (currentBalance !== data.balance) {
            const diff = data.balance - currentBalance; currentBalance = data.balance;
            const wEl = document.getElementById('wallet-display');
            if (wEl) wEl.innerText = `💰 Balance: ${data.balance.toLocaleString()} Ks`;
            if (diff > 0) { tg.showAlert(`💰 ပိုက်ဆံ ${diff.toLocaleString()} Ks ဝင်လာပါပြီ`); loadUserHistory(); }
        }
    } catch (e) {}
}

async function autoRefresh() {
    if (currentUserRole === 'user') { await updateBalance(); } 
    else { await loadAdminDash(); }
}

function buildUserNav() {
    document.getElementById('nav-container').innerHTML = `
        <div id="user-nav" class="bottom-nav" style="display:flex; justify-content:space-around;">
            <div class="nav-item active" onclick="switchTab('u', 'shop', this)"><span>🛍️</span>ဆိုင်</div>
            <div class="nav-item" onclick="switchTab('u', 'topup', this)"><span>💳</span>ငွေဖြည့်</div>
            <div class="nav-item" onclick="switchTab('u', 'history', this)"><span>📋</span>မှတ်တမ်း</div>
            <div class="nav-item" onclick="switchTab('u', 'support', this)"><span>📞</span>အကူအညီ</div>
        </div>`;
}

function buildAdminNav() {
    document.getElementById('nav-container').innerHTML = `
        <div id="admin-nav" class="bottom-nav" style="display:grid; grid-template-columns: repeat(4, 1fr); gap: 10px 5px; padding: 10px 10px 20px 10px;">
            <div class="nav-item active" onclick="switchTab('a', 'dash', this)"><span>📊</span>Dash</div>
            <div class="nav-item" onclick="switchTab('a', 'orders', this)"><span>🧾</span>Orders</div>
            <div class="nav-item" onclick="switchTab('a', 'topups', this)"><span>💸</span>Topups</div>
            <div class="nav-item" onclick="switchTab('a', 'items', this)"><span>📦</span>Items</div>
            <div class="nav-item" onclick="switchTab('a', 'users', this)"><span>👥</span>Users</div>
            <div class="nav-item" onclick="switchTab('a', 'reports', this)"><span>📈</span>Report</div>
            <div class="nav-item" onclick="switchTab('a', 'admins', this)"><span>🛡️</span>Admins</div>
            <div class="nav-item" onclick="switchTab('a', 'settings', this)"><span>⚙️</span>Set</div>
        </div>`;
}

async function initApp() {
    try {
        const imgRes = await fetch('/api/category_images'); categoryImages = await imgRes.json();
        const res = await fetch('/api/init', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
        if (!res.ok) throw new Error("Init API Error");
        const data = await res.json();
        
        document.getElementById('user-name').innerText = data.name || "User";
        isMaintenance = data.maintenance; currentUserRole = data.role;
        waitTimeText = data.wait_time || '၅ မိနစ်';
        if (data.support) document.getElementById('user-support-contact').innerText = data.support;
        if (data.kpay || data.wave) {
            document.getElementById('u-pay-info').innerHTML = `
                <span onclick="tg.setClipboard('${data.kpay}'); tg.showAlert('ကူးယူပြီး')" style="cursor:pointer; display:block; margin-bottom:5px;">📋 KPay: ${data.kpay || '-'}</span>
                <span onclick="tg.setClipboard('${data.wave}'); tg.showAlert('ကူးယူပြီး')" style="cursor:pointer; display:block;">📋 Wave: ${data.wave || '-'}</span>`;
        }

        if (data.role === 'admin' || data.role === 'super_admin') {
            document.getElementById('admin-app').style.display = 'block';
            buildAdminNav();
            loadAdminDash(); loadAdminOrders(); loadAdminTopups(); loadAdminItems(); loadAdminUsers(); loadAdminSettings(); loadAdmins();
        } else {
            if (isMaintenance === 'on') document.getElementById('maintenance-overlay').style.display = 'flex';
            document.getElementById('user-app').style.display = 'block';
            buildUserNav();
            document.getElementById('wallet-display').style.display = 'inline-block'; currentBalance = data.balance || 0;
            document.getElementById('wallet-display').innerText = `💰 Balance: ${currentBalance.toLocaleString()} Ks`;
            await loadUserItems(); loadUserHistory();
            setInterval(autoRefresh, 10000);
        }
    } catch (e) { tg.showAlert("Init Error: " + e.message); }
}

function switchTab(role, tab, el) {
    document.querySelectorAll(`#${role === 'u' ? 'user-app' : 'admin-app'} .tab-content`).forEach(c => c.classList.remove('active'));
    document.getElementById(`${role}-tab-${tab}`).classList.add('active');
    const navId = role === 'u' ? 'user-nav' : 'admin-nav';
    document.querySelectorAll(`#${navId} .nav-item`).forEach(n => n.classList.remove('active'));
    el.classList.add('active');
    if(tab === 'history') loadUserHistory();
    if(tab === 'shop') showMainCategories();
    if(tab === 'orders') loadAdminOrders();
    if(tab === 'topups') { loadAdminTopups(); loadAdminCashouts(); }
    if(tab === 'users') loadAdminUsers();
    if(tab === 'items') loadAdminItems();
    if(tab === 'dash') loadAdminDash();
    if(tab === 'settings') loadAdminSettings();
    if(tab === 'reports') { loadDailyReport(); loadMonthlyReport(); }
    if(tab === 'admins') loadAdmins();
}

function setFilter(type, status, el) {
    currentFilters[type] = status; document.querySelectorAll(`#a-tab-${type} .filter-btn`).forEach(b => b.classList.remove('active')); el.classList.add('active');
    if(type === 'orders') loadAdminOrders(); else loadAdminTopups();
}

async function loadUserItems() { const res = await fetch('/api/items'); allItems = await res.json(); showMainCategories(); }

function showMainCategories() {
    currentView = 'main'; currentCat = null; currentSub = null;
    const container = document.getElementById('u-tab-shop'); let allCats = [];
    allItems.forEach(i => { allCats = allCats.concat(getCategories(i.category)); });
    const categories = [...new Set(allCats)];
    if(categories.length === 0) { container.innerHTML = '<p style="text-align:center; color:var(--hint);">Item မရှိပါ</p>'; return; }
    let html = `<div class="category-title">📂 အမျိုးအစား ရွေးချယ်ပါ</div>
                <div style="background:rgba(59,130,246,0.1); padding:10px 15px; border-radius:12px; margin-bottom:15px; display:flex; align-items:center; gap:10px; border:1px solid rgba(59,130,246,0.2);">
                    <span style="font-size:20px;">⏳</span>
                    <span style="font-size:13px; color:var(--primary); font-weight:bold;">Data ဖြည့်ရန် စောင့်ဆိုင်းချိန် - ${waitTimeText}</span>
                </div>
                <div class="category-grid">`;
    categories.forEach(cat => {
        let imgKey = Object.keys(categoryImages).find(k => k.toLowerCase() === cat.toLowerCase());
        let img = imgKey ? `<img src="${categoryImages[imgKey]}">` : `<span class="folder-icon">📁</span>`;
        html += `<div class="category-card" onclick="showSubCategories('${cat}')">${img}<b>${cat}</b></div>`;
    });
    container.innerHTML = html + `</div>`;
}

function showSubCategories(mainCat) {
    currentView = 'sub'; currentCat = mainCat; currentSub = null;
    const container = document.getElementById('u-tab-shop'); const catItems = allItems.filter(i => getCategories(i.category).includes(mainCat));
    const subCats = [...new Set(catItems.map(i => i.subcategory).filter(s => s))];
    let html = `<button class="btn btn-sm btn-outline" style="margin-bottom:15px;" onclick="showMainCategories()">⬅️ နောက်သို့</button><div class="category-title">📂 ${mainCat}</div>`;
    if (subCats.length === 0) { html += renderItems(catItems); } else {
        html += `<div class="category-grid">`;
        subCats.forEach(sub => { html += `<div class="category-card" onclick="showItemsList('${mainCat}', '${sub}')"><span style="font-size:20px;">📄</span><b>${sub}</b></div>`; });
        if (catItems.some(i => !i.subcategory)) { html += `<div class="category-card" onclick="showItemsList('${mainCat}', 'none')"><span style="font-size:20px;">📄</span><b>အခြား</b></div>`; }
        html += `</div>`;
    }
    container.innerHTML = html;
}

function showItemsList(mainCat, subCat) {
    currentView = 'items'; currentCat = mainCat; currentSub = subCat;
    const container = document.getElementById('u-tab-shop'); let catItems = allItems.filter(i => getCategories(i.category).includes(mainCat));
    if (subCat === 'none') catItems = catItems.filter(i => !i.subcategory); else catItems = catItems.filter(i => i.subcategory === subCat);
    let html = `<button class="btn btn-sm btn-outline" style="margin-bottom:15px;" onclick="showSubCategories('${mainCat}')">⬅️ နောက်သို့</button><div class="category-title">📂 ${mainCat} / ${subCat === 'none' ? 'အခြား' : subCat}</div>${renderItems(catItems)}`;
    container.innerHTML = html;
}

function renderItems(items) {
    let html = '';
    items.forEach(i => {
        let displayPrice = i.price; if (currentUserRole === 'reseller' && i.reseller_price) displayPrice = i.reseller_price;
        html += `<div class="card item-card"><div class="item-info"><span class="item-name">${i.name}</span><span class="item-price">${displayPrice.toLocaleString()} Ks</span></div><button class="btn btn-sm" onclick='openOrder(${JSON.stringify(i)})'>ဝယ်မယ်</button></div>`;
    });
    return html || '<p style="text-align:center; color:var(--hint);">ပစ္စည်း မရှိပါ</p>';
}

function openOrder(item) {
    if(isMaintenance === 'on') return tg.showAlert("ဆိုင်ပိတ်ထားပါသည်");
    selectedItemId = item.id; document.getElementById('m-item-name').innerText = item.name;
    document.getElementById('m-item-price').innerText = (currentUserRole === 'reseller' && item.reseller_price ? item.reseller_price : item.price).toLocaleString() + ' Ks';
    document.getElementById('m-phone').value = userDefaultPhone;
    const formType = item.form_type || 'phone';
    const isGame = formType === 'MLBB' || formType === 'PUBG';
    const isSim = formType === 'sim' || (item.category && item.category.toLowerCase().includes('sim'));
    const gameFields = document.getElementById('m-game-fields');
    const simFields = document.getElementById('m-sim-fields');
    const dataFields = document.getElementById('m-data-fields');
    if (gameFields) gameFields.style.display = isGame ? 'block' : 'none';
    if (simFields) simFields.style.display = isSim ? 'block' : 'none';
    if (dataFields) dataFields.style.display = (isSim || isGame) ? 'none' : 'block';
    if (isGame) {
        const zoneBox = document.getElementById('m-zone-box');
        if (zoneBox) zoneBox.style.display = (formType === 'MLBB') ? 'block' : 'none';
    }
    const noteEl = document.getElementById('m-item-note');
    if (noteEl) {
        if (item.note && item.note.trim() !== '') { noteEl.innerText = "⚠️ " + item.note; noteEl.style.display = 'block'; }
        else { noteEl.style.display = 'none'; }
    }
    openModal('order-modal');
}

async function submitOrder() {
    if (isSubmittingOrder) return;
    const isGame = document.getElementById('m-game-fields')?.style.display === 'block';
    const isSim = document.getElementById('m-sim-fields')?.style.display === 'block';
    const phone = document.getElementById('m-phone')?.value.trim() || '';
    const address = document.getElementById('m-address')?.value.trim() || '';
    const contactPhone = document.getElementById('m-contact-phone')?.value.trim() || '';
    const gameId = document.getElementById('m-game-id')?.value.trim() || '';
    const gameZone = document.getElementById('m-game-zone')?.value.trim() || '';
    const gameName = document.getElementById('m-game-name')?.value.trim() || '';

    if (isGame) { if (!gameId) return tg.showAlert("Game ID ဖြည့်ပါ"); }
    else if (isSim) { if (!address || !contactPhone) return tg.showAlert("လိပ်စာနဲ့ ဖုန်းနံပါတ် ဖြည့်ပါ"); }
    else { if (!/^09\d{7,9}$/.test(phone)) return tg.showAlert("Phone မှန်ကန်အောင် ရိုက်ပါ"); }

    isSubmittingOrder = true; tg.MainButton.showProgress();
    try {
        const res = await fetch('/api/order', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, item_id: selectedItemId, phone: phone || 'N/A', address, contact_phone: contactPhone, game_id: gameId, game_zone: gameZone, game_name: gameName }) });
        const data = await res.json();
        if (res.ok) { tg.showAlert("✅ အောင်မြင်ပါသည်"); closeModal('order-modal'); loadUserHistory(); }
        else {
            if (data.detail && data.detail.includes("Balance မလုံလောက်ပါ")) {
                try {
                    tg.showPopup({ title: 'Balance မလုံလောက်ပါ', message: 'ငွေဖြည့်ရန် သွားမလား?', buttons: [{id: 'topup', type: 'default', text: '💰 ငွေဖြည့်မယ်'}, {id: 'cancel', type: 'cancel'}] },
                    function (buttonId) { if (buttonId === 'topup') { closeModal('order-modal'); const t = document.querySelector('#user-nav .nav-item:nth-child(2)'); if (t) switchTab('u', 'topup', t); } });
                } catch (e) {
                    closeModal('order-modal');
                    if (confirm("Balance မလုံလောက်ပါ။ ငွေဖြည့်ရန် သွားမလား?")) { const t = document.querySelector('#user-nav .nav-item:nth-child(2)'); if (t) switchTab('u', 'topup', t); }
                }
            } else { tg.showAlert("❌ " + (data.detail || "မအောင်မြင်ပါ")); }
        }
    } catch (e) { tg.showAlert("❌ အင်တာနက် Error"); } finally { isSubmittingOrder = false; tg.MainButton.hideProgress(); }
}

async function loadUserHistory() {
    const res = await fetch('/api/user/history', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
    const data = await res.json(); let oHtml = '', tHtml = '';
    (data.orders || []).forEach(o => { let bc = o.status === 'completed' ? 'bg-success' : 'bg-pending'; oHtml += `<div class="card" style="padding:12px;"><div style="display:flex; justify-content:space-between;"><b style="font-size:14px;">${o.item}</b><span class="badge ${bc}">${o.status}</span></div><div style="display:flex; justify-content:space-between; margin-top:8px;"><small style="color:var(--hint);">${o.date}</small><span style="color:var(--danger); font-weight:bold;">${o.price.toLocaleString()} Ks</span></div></div>`; });
    (data.transactions || []).forEach(t => { let c = t.amount > 0 ? 'var(--success)' : 'var(--danger)'; let s = t.amount > 0 ? '+' : ''; tHtml += `<div class="card" style="padding:12px;"><div style="display:flex; justify-content:space-between;"><b style="font-size:14px;">${t.type.toUpperCase()}</b><span style="color:${c}; font-weight:bold;">${s}${t.amount.toLocaleString()} Ks</span></div><div style="margin-top:5px;"><small style="color:var(--hint);">${t.date} | ${t.note || ''}</small></div></div>`; });
    document.getElementById('u-history-list').innerHTML = oHtml || '<p style="text-align:center; color:var(--hint);">မရှိပါ</p>';
    document.getElementById('u-wallet-list').innerHTML = tHtml || '<p style="text-align:center; color:var(--hint);">မရှိပါ</p>';
}

async function submitTopup() {
    const amount = document.getElementById('topup-amount').value; const senderPhone = document.getElementById('topup-sender-phone').value.trim(); const file = document.getElementById('topup-file').files[0];
    if(!amount || !file || !senderPhone) return tg.showAlert("အချက်အလက် ပြည့်စုံအောင် ဖြည့်ပါ");
    tg.MainButton.showProgress();
    const fd = new FormData(); fd.append('initData', tg.initData); fd.append('amount', amount); fd.append('sender_phone', senderPhone); fd.append('file', file);
    const res = await fetch('/api/user/topup', { method: 'POST', body: fd }); tg.MainButton.hideProgress();
    if(res.ok) { tg.showAlert("Topup တင်ပြီးပါပြီ"); document.getElementById('topup-amount').value=''; document.getElementById('file-name').innerText=''; } else { tg.showAlert("မအောင်မြင်ပါ"); }
}

async function submitCashout() {
    const amount = document.getElementById('cashout-amount').value;
    const accName = document.getElementById('cashout-acc-name').value.trim();
    const phone = document.getElementById('cashout-phone').value.trim();
    if (!amount || !accName || !phone) return tg.showAlert("အကွက်အားလုံး ဖြည့်ပါ");
    tg.MainButton.showProgress();
    const res = await fetch('/api/user/cashout', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, amount, account_name: accName, phone }) });
    const d = await res.json();
    tg.MainButton.hideProgress();
    if (res.ok) { tg.showAlert("✅ Cash Out တောင်းဆိုပြီးပါပြီ"); document.getElementById('cashout-amount').value=''; document.getElementById('cashout-acc-name').value=''; document.getElementById('cashout-phone').value=''; }
    else { tg.showAlert("❌ " + (d.detail || "မအောင်မြင်ပါ")); }
}

async function loadAdminDash() {
    const res = await fetch('/api/admin/dashboard', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
    const d = await res.json();
    document.getElementById('st-orders').innerText = d.pending_orders; document.getElementById('st-topups').innerText = d.pending_topups; document.getElementById('st-users').innerText = d.total_users;
    document.getElementById('st-cash-in').innerText = d.cash_in.toLocaleString() + ' Ks'; document.getElementById('st-cash-out').innerText = d.cash_out.toLocaleString() + ' Ks';
    document.getElementById('st-today-sales').innerText = d.today_sales.toLocaleString() + ' Ks'; document.getElementById('st-today-orders').innerText = d.today_orders;
    const btn = document.getElementById('maint-btn'); if(d.maintenance === 'on') { btn.innerText = "ပြန်ဖွင့်မယ်"; btn.className = "btn btn-sm btn-success"; } else { btn.innerText = "ပိတ်မယ်"; btn.className = "btn btn-sm btn-outline"; }
    try {
        const cRes = await fetch('/api/admin/chart_data', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
        if (cRes.ok) {
            const cData = await cRes.json(); const ctx = document.getElementById('salesChart');
            if (ctx && window.Chart) { new Chart(ctx, { type: 'bar', data: { labels: cData.labels, datasets: [{ label: 'ဝင်ငွေ', data: cData.data, backgroundColor: 'rgba(59,130,246,0.6)' }] }, options: { responsive: true, maintainAspectRatio: false } }); }
        }
    } catch (e) {}
}

async function toggleMaintenance() {
    const btn = document.getElementById('maint-btn'); const ns = btn.innerText === "ပိတ်မယ်" ? "on" : "off";
    await fetch('/api/admin/maintenance', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, status: ns }) }); loadAdminDash(); tg.showAlert("ပြောင်းလဲပြီးပါပြီ");
}

async function loadAdminOrders() {
    const res = await fetch('/api/admin/orders', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, status: currentFilters.orders }) });
    const orders = await res.json(); let html = '';
    orders.forEach(o => { let p = o.phones.join(', '); let bc = o.status === 'completed' ? 'bg-success' : 'bg-pending'; html += `<div class="card"><div style="display:flex; justify-content:space-between;"><b style="font-size:14px;">${o.code} - ${o.item}</b><span class="badge ${bc}">${o.status}</span></div><p style="font-size:13px; color:var(--hint); margin:8px 0;">📱 ${p}</p>${o.status === 'pending' ? `<div style="display:flex; gap:10px;"><button class="btn btn-sm btn-success" style="flex:1;" onclick="orderAction(${o.id}, 'done')">✅ Done</button><button class="btn btn-sm btn-danger" style="flex:1;" onclick="orderAction(${o.id}, 'fail')">❌ Fail</button></div>` : ''}</div>`; });
    document.getElementById('a-order-list').innerHTML = html || '<p style="text-align:center; color:var(--hint);">Order မရှိပါ</p>';
}

async function orderAction(id, action) {
    let reason = "";
    if (action === 'fail') { reason = prompt("Fail ဖြစ်ရတဲ့ အကြောင်းပြချက်:"); if (reason === null) return; }
    await fetch('/api/admin/order_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id, action, reason }) });
    loadAdminOrders(); loadAdminDash(); tg.showAlert("အောင်မြင်ပါသည်");
}

async function loadAdminTopups() {
    const res = await fetch('/api/admin/topups', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, status: currentFilters.topups }) });
    const list = await res.json(); let html = '';
    list.forEach(t => { html += `<div class="card"><div style="display:flex; justify-content:space-between;"><div><b style="font-size:14px;">${t.user}</b><br><span class="item-price">${t.amount.toLocaleString()} Ks</span></div><img src="${t.ss_url}" style="width:60px; height:60px; object-fit:cover; border-radius:8px;" onclick="window.open('${t.ss_url}', '_blank')"></div>${t.status === 'pending' ? `<div style="display:flex; gap:10px; margin-top:10px;"><button class="btn btn-sm btn-success" style="flex:1;" onclick="topupAction(${t.id}, 'approve')">Approve</button><button class="btn btn-sm btn-danger" style="flex:1;" onclick="topupAction(${t.id}, 'reject')">Reject</button></div>` : ''}</div>`; });
    document.getElementById('a-topup-list').innerHTML = html || '<p style="text-align:center; color:var(--hint);">Topup မရှိပါ</p>';
}

async function topupAction(id, action) { await fetch('/api/admin/topup_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id, action }) }); loadAdminTopups(); loadAdminDash(); tg.showAlert("အောင်မြင်ပါသည်"); }

async function loadAdminCashouts() {
    const el = document.getElementById('a-cashout-list'); if (!el) return;
    const res = await fetch('/api/admin/cashouts', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
    if (!res.ok) return;
    const list = await res.json(); let html = '';
    list.forEach(c => { html += `<div class="card"><div style="display:flex; justify-content:space-between;"><div><b style="font-size:14px;">${c.user}</b><br><span class="item-price">${c.amount.toLocaleString()} Ks</span></div></div><p style="font-size:12px; color:var(--hint); margin:5px 0;">🏦 ${c.account_name}<br>📱 ${c.phone}</p><div style="display:flex; gap:10px; margin-top:10px;"><button class="btn btn-sm btn-success" style="flex:1;" onclick="cashoutAction(${c.id}, 'approve')">Approve</button><button class="btn btn-sm btn-danger" style="flex:1;" onclick="cashoutAction(${c.id}, 'reject')">Reject</button></div></div>`; });
    el.innerHTML = html || '<p style="text-align:center; color:var(--hint);">မရှိပါ</p>';
}

async function cashoutAction(id, action) {
    if (!confirm(action === 'approve' ? "Approve လုပ်မှာ သေချာလား?" : "Reject လုပ်မှာ သေချာလား?")) return;
    await fetch('/api/admin/cashout_action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id, action }) });
    loadAdminCashouts(); tg.showAlert("အောင်မြင်ပါသည်");
}

async function loadAdminItems() {
    const res = await fetch('/api/admin/items/all', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
    window.allAdminItems = await res.json(); let html = '';
    window.allAdminItems.forEach(i => { let sc = i.status === 'active' ? 'bg-success' : 'bg-danger'; let rp = i.reseller_price ? `<br><small style="color:var(--hint);">Reseller: ${i.reseller_price.toLocaleString()} Ks</small>` : ''; let st = i.subcategory ? ` / ${i.subcategory}` : ''; let ct = i.category || 'Other';
        html += `<div class="card"><div style="display:flex; justify-content:space-between;"><div><b style="font-size:14px;">${i.name}</b><span class="badge ${sc}" style="margin-left:8px; font-size:9px;">${i.status}</span><br><span class="item-price">${i.price.toLocaleString()} Ks</span>${rp}</div><small style="color:var(--hint); font-weight:bold; text-align:right;">${ct}${st}</small></div><div style="display:flex; gap:8px; margin-top:10px;"><button class="btn btn-sm btn-outline" style="flex:1;" onclick="openEditItem(${i.id})">ဈေးပြင်</button><button class="btn btn-sm btn-warning" style="flex:1;" onclick="itemAction(${i.id}, 'toggle')">${i.status === 'active' ? 'ပိတ်မယ်' : 'ဖွင့်မယ်'}</button><button class="btn btn-sm btn-danger" style="flex:1;" onclick="itemAction(${i.id}, 'delete')">ဖျက်မယ်</button></div></div>`;
    });
    document.getElementById('a-item-list').innerHTML = html || '<p style="text-align:center; color:var(--hint);">Item မရှိပါ</p>';
}

function openEditItem(id) {
    const item = window.allAdminItems.find(x => x.id === id); if(!item) return;
    document.getElementById('edit-i-id').value = item.id; document.getElementById('edit-i-name').value = item.name; document.getElementById('edit-i-price').value = item.price; document.getElementById('edit-i-reseller-price').value = item.reseller_price || ''; document.getElementById('edit-i-cost-price').value = item.cost_price || ''; document.getElementById('edit-i-cat').value = item.category || ''; document.getElementById('edit-i-subcat').value = item.subcategory || ''; document.getElementById('edit-i-note').value = item.note || ''; openModal('edit-item-modal');
}

async function saveEditItem() {
    const id = document.getElementById('edit-i-id').value, name = document.getElementById('edit-i-name').value, price = document.getElementById('edit-i-price').value, subcat = document.getElementById('edit-i-subcat').value, rPrice = document.getElementById('edit-i-reseller-price').value, costPrice = document.getElementById('edit-i-cost-price').value, cat = document.getElementById('edit-i-cat').value, note = document.getElementById('edit-i-note').value;
    await fetch('/api/admin/item/action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id, action: 'edit', name, price, category: cat, subcategory: subcat, reseller_price: rPrice, cost_price: costPrice, note }) });
    closeModal('edit-item-modal'); loadAdminItems(); tg.showAlert("ပြင်ပြီးပါပြီ");
}

async function itemAction(id, action) { await fetch('/api/admin/item/action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id, action }) }); loadAdminItems(); }

async function addItem() {
    const name = document.getElementById('i-name').value, price = document.getElementById('i-price').value, cat = document.getElementById('i-cat').value, subcat = document.getElementById('i-subcat').value, rPrice = document.getElementById('i-reseller-price').value, costPrice = document.getElementById('i-cost-price').value, note = document.getElementById('i-note').value;
    const formType = document.getElementById('i-form-type') ? document.getElementById('i-form-type').value : 'phone';
    if(!name || !price || !cat) return tg.showAlert("အကုန်ဖြည့်ပါ");
    await fetch('/api/admin/item/add', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, name, price, category: cat, subcategory: subcat, reseller_price: rPrice, cost_price: costPrice, note, form_type: formType }) });
    document.getElementById('i-name').value=''; document.getElementById('i-price').value=''; document.getElementById('i-cat').value=''; document.getElementById('i-subcat').value=''; document.getElementById('i-reseller-price').value=''; document.getElementById('i-cost-price').value=''; document.getElementById('i-note').value='';
    loadAdminItems(); tg.showAlert("Item ထည့်ပြီးပါပြီ");
}

async function loadAdminUsers() {
    const res = await fetch('/api/admin/users', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
    const users = await res.json(); let html = '';
    users.forEach(u => {
        let bc = u.role === 'reseller' ? 'bg-success' : 'bg-pending'; let en = encodeURIComponent(u.name || "Unknown");
        let roleBtn = u.role === 'reseller' ? `<button class="btn btn-sm btn-danger" style="margin-top:10px; width:100%;" onclick="event.stopPropagation(); userAction(${u.id}, 'remove_reseller')">Reseller ဖြုတ်မယ်</button>` : `<button class="btn btn-sm btn-success" style="margin-top:10px; width:100%;" onclick="event.stopPropagation(); userAction(${u.id}, 'make_reseller')">Reseller ပေးမယ်</button>`;
        let banBtn = u.is_banned ? `<button class="btn btn-sm btn-success" style="margin-top:5px; width:100%;" onclick="event.stopPropagation(); userAction(${u.id}, 'unban')">Ban ဖြုတ်မယ်</button>` : `<button class="btn btn-sm btn-warning" style="margin-top:5px; width:100%;" onclick="event.stopPropagation(); userAction(${u.id}, 'ban')">Ban လုပ်မယ်</button>`;
        html += `<div class="card" style="cursor:pointer;" onclick="openUserDetail(${u.id}, decodeURIComponent('${en}'), '${u.role}')"><div style="display:flex; justify-content:space-between;"><b style="font-size:14px;">${u.name || 'Unknown'}</b><span class="badge ${bc}">${u.role}</span></div><small style="display:block; margin-top:5px; font-weight:bold; color:var(--primary);">💰 ${u.balance.toLocaleString()} Ks</small>${roleBtn}${banBtn}</div>`;
    });
    document.getElementById('a-user-list').innerHTML = html || '<p style="text-align:center; color:var(--hint);">User မရှိပါ</p>';
}

async function openUserDetail(id, name, role) {
    currentUserId = id; document.getElementById('ud-name').innerText = name; document.getElementById('ud-balance').innerText = "Loading..."; document.getElementById('ud-transactions').innerHTML = '<p style="text-align:center; color:var(--hint);">ရှာဖွေနေသည်...</p>';
    let bc = role === 'reseller' ? 'bg-success' : 'bg-pending'; document.getElementById('ud-role').className = `badge ${bc}`; document.getElementById('ud-role').innerText = role.toUpperCase(); document.getElementById('ud-amount').value = '';
    openModal('user-detail-modal'); await refreshUserDetail();
}

async function refreshUserDetail() {
    if (!currentUserId) return;
    const resUser = await fetch('/api/admin/users', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) });
    const users = await resUser.json(); const user = users.find(u => u.id === currentUserId); if (user) document.getElementById('ud-balance').innerText = `${user.balance.toLocaleString()} Ks`;
    const resHist = await fetch('/api/admin/user/history', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, user_id: currentUserId }) });
    const txs = await resHist.json(); let html = '';
    if (txs.length === 0) { html = '<p style="text-align:center; color:var(--hint); font-size:12px;">မှတ်တမ်း မရှိပါ</p>'; }
    else { txs.forEach(t => { let c = t.amount > 0 ? 'var(--success)' : 'var(--danger)'; let s = t.amount > 0 ? '+' : ''; html += `<div style="border-bottom:1px solid rgba(0,0,0,0.05); padding: 8px 0;"><div style="display:flex; justify-content:space-between;"><b style="font-size:12px;">${t.type.toUpperCase()}</b><span style="color:${c}; font-weight:bold; font-size:13px;">${s}${t.amount.toLocaleString()} Ks</span></div><small style="color:var(--hint); font-size:10px;">${t.date} | ${t.note || ''}</small></div>`; }); }
    document.getElementById('ud-transactions').innerHTML = html;
}

async function adjustUserBalance(action) {
    const amt = document.getElementById('ud-amount').value; if (!amt || amt <= 0) return tg.showAlert("ပမာဏ မှန်ကန်အောင် ရိုက်ပါ");
    const fa = action === 'add' ? amt : -amt;
    await fetch('/api/admin/user/action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id: currentUserId, action: 'adjust_balance', amount: fa }) });
    tg.showAlert("အောင်မြင်ပါသည်"); document.getElementById('ud-amount').value = ''; await refreshUserDetail(); loadAdminUsers();
}

async function userAction(id, action) {
    if (action === 'ban' || action === 'zero_balance') { if (!confirm("သေချာလား?")) return; }
    await fetch('/api/admin/user/action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id, action }) });
    loadAdminUsers(); tg.showAlert("အောင်မြင်ပါသည်");
    if (currentUserId) await refreshUserDetail();
}

async function removeUserBalance() {
    const amt = document.getElementById('ud-remove-amount')?.value; if (!amt || amt <= 0) return tg.showAlert("ပမာဏ မှန်ကန်အောင် ရိုက်ပါ");
    if (!confirm(`Balance ${parseInt(amt).toLocaleString()} Ks ကို ပြန်နုတ်မှာ သေချာလား?`)) return;
    await fetch('/api/admin/user/action', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, id: currentUserId, action: 'remove_balance', amount: amt }) });
    tg.showAlert("✅ ပြန်နုတ်ပြီးပါပြီ"); document.getElementById('ud-remove-amount').value = ''; await refreshUserDetail(); loadAdminUsers();
}

async function loadAdminSettings() {
    const res = await fetch('/api/admin/settings/all', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData }) }); const d = await res.json();
    document.getElementById('s-shop-name').value = d.shop_name || ''; document.getElementById('s-support').value = d.support_contact || ''; document.getElementById('s-pay-name').value = d.payment_name || ''; document.getElementById('s-kpay').value = d.payment_kpay || ''; document.getElementById('s-wave').value = d.payment_wave || ''; document.getElementById('s-wait-time').value = d.wait_time || '၅ မိနစ်';
    const mcInput = document.getElementById('s-min-cashout'); if (mcInput) mcInput.value = d.min_cashout || '1000';
}

async function uploadCatImage() {
    const name = document.getElementById('cat-img-name').value; const file = document.getElementById('cat-img-file').files[0]; if(!name || !file) return tg.showAlert("Category နာမည်နဲ့ ပုံရွေးပါ");
    tg.MainButton.showProgress(); const fd = new FormData(); fd.append('initData', tg.initData); fd.append('name', name); fd.append('file', file);
    const res = await fetch('/api/admin/category_image', { method: 'POST', body: fd }); tg.MainButton.hideProgress();
    if(res.ok) { tg.showAlert("ပုံတင်ပြီးပါပြီ"); document.getElementById('cat-img-name').value = ''; document.getElementById('cat-img-file').value = ''; const ir = await fetch('/api/category_images'); categoryImages = await ir.json(); } else { tg.showAlert("မအောင်မြင်ပါ"); }
}

async function saveSettings() {
    const s = { shop_name: document.getElementById('s-shop-name').value, support_contact: document.getElementById('s-support').value, payment_name: document.getElementById('s-pay-name').value, payment_kpay: document.getElementById('s-kpay').value, payment_wave: document.getElementById('s-wave').value, wait_time: document.getElementById('s-wait-time').value || '၅ မိနစ်', min_cashout: document.getElementById('s-min-cashout')?.value || '1000' };
    tg.MainButton.showProgress(); await fetch('/api/admin/settings/update', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, settings: s }) }); tg.MainButton.hideProgress(); tg.showAlert("သတ်မှတ်ချက်များ သိမ်းဆည်းပြီးပါပြီ");
}

async function sendBroadcast() {
    const msg = document.getElementById('bc-msg').value; if(!msg) return tg.showAlert("စာသား ရိုက်ပါ");
    tg.MainButton.showProgress();
    const res = await fetch('/api/admin/broadcast', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, message: msg }) });
    const d = await res.json(); tg.MainButton.hideProgress(); document.getElementById('bc-msg').value=''; tg.showAlert(`User ${d.count} ယောက်ဆီ ပို့ပြီးပါပြီ`);
}

async function loadAdmins() {
    const listEl = document.getElementById('a-admin-list'); if (!listEl) return;
    const res = await fetch('/api/admin/admins/all', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ initData: tg.initData }) });
    if (!res.ok) { listEl.innerHTML = '<p style="text-align:center; color:var(--danger);">Super Admin မဟုတ်ပါ</p>'; return; }
    const admins = await res.json(); let html = '';
    admins.forEach(a => { let roleText = a.role === 'super_admin' ? '👑 Super Admin' : '🛡️ Admin'; html += `<div class="card"><div style="display:flex; justify-content:space-between;"><div><b>ID: ${a.telegram_id}</b><br><small style="color:var(--primary); font-weight:bold;">${roleText}</small></div><button class="btn btn-sm btn-danger" onclick="deleteAdmin(${a.id})">ဖျက်မယ်</button></div></div>`; });
    listEl.innerHTML = html || '<p style="text-align:center; color:var(--hint);">Admin မရှိပါ</p>';
}

async function addAdmin() {
    const tid = document.getElementById('new-admin-id').value; const role = document.getElementById('new-admin-role').value;
    if (!tid) return tg.showAlert("Telegram ID ရိုက်ပါ"); tg.MainButton.showProgress();
    const res = await fetch('/api/admin/admins/add', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ initData: tg.initData, telegram_id: tid, role: role }) });
    tg.MainButton.hideProgress();
    if (res.ok) { tg.showAlert("✅ Admin ခန့်ပြီးပါပြီ"); document.getElementById('new-admin-id').value = ''; loadAdmins(); }
    else { const d = await res.json(); tg.showAlert("❌ " + (d.detail || "မအောင်မြင်ပါ")); }
}

async function deleteAdmin(id) {
    if (!confirm("သေချာလား?")) return;
    await fetch('/api/admin/admins/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ initData: tg.initData, id }) });
    loadAdmins();
}

async function loadDailyReport() {
    const dateInput = document.getElementById('report-date'); const dateStr = dateInput ? dateInput.value : '';
    const res = await fetch('/api/reports/daily', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, date: dateStr }) });
    const container = document.getElementById('daily-report-content');
    if (!res.ok) { container.innerHTML = '<p style="color:red; text-align:center;">Super Admin မဟုတ်ပါ</p>'; return; }
    const d = await res.json();
    let html = `<div class="stats-grid"><div class="stat-card"><h4>စုစုပေါင်း ရောင်းရငွေ</h4><div class="value" style="color:var(--success);">${d.total_income.toLocaleString()} Ks</div></div><div class="stat-card"><h4>အရင်းဈေး</h4><div class="value" style="color:var(--danger);">${d.total_cost.toLocaleString()} Ks</div></div><div class="stat-card" style="grid-column: span 2; background:rgba(59,130,246,0.1);"><h4>အမြတ်</h4><div class="value" style="color:var(--primary);">${d.total_profit.toLocaleString()} Ks</div></div></div><div class="category-title">📋 အသေးစိတ်</div>`;
    if (Object.keys(d.breakdown).length === 0) { html += '<p style="text-align:center; color:var(--hint);">ဒီနေ့ အရောင်း မရှိပါ</p>'; }
    else { html += '<div class="card" style="padding:0; overflow-x:auto;"><table style="width:100%; border-collapse:collapse; font-size:12px;"><thead><tr style="background:var(--bg);"><th style="padding:8px;">Item</th><th style="padding:8px;">အရေအတွက်</th><th style="padding:8px;">ဝင်ငွေ</th><th style="padding:8px;">အမြတ်</th></tr></thead><tbody>';
        for (const [name, data] of Object.entries(d.breakdown)) { html += `<tr style="border-bottom:1px solid rgba(0,0,0,0.05);"><td style="padding:8px;">${name}</td><td style="padding:8px; text-align:center;">${data.count}</td><td style="padding:8px; text-align:right; color:var(--success);">${data.income.toLocaleString()}</td><td style="padding:8px; text-align:right; color:var(--primary);">${data.profit.toLocaleString()}</td></tr>`; }
        html += '</tbody></table></div>'; }
    container.innerHTML = html;
}

async function loadMonthlyReport() {
    const monthInput = document.getElementById('report-month'); const monthStr = monthInput ? monthInput.value : '';
    const res = await fetch('/api/reports/monthly', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ initData: tg.initData, month: monthStr }) });
    const container = document.getElementById('monthly-report-content');
    if (!res.ok) { container.innerHTML = '<p style="color:red; text-align:center;">Super Admin မဟုတ်ပါ</p>'; return; }
    const d = await res.json();
    let html = `<div class="stats-grid"><div class="stat-card"><h4>စုစုပေါင်း ရောင်းရငွေ</h4><div class="value" style="color:var(--success);">${d.total_income.toLocaleString()} Ks</div></div><div class="stat-card"><h4>အရင်းဈေး</h4><div class="value" style="color:var(--danger);">${d.total_cost.toLocaleString()} Ks</div></div><div class="stat-card" style="grid-column: span 2; background:rgba(59,130,246,0.1);"><h4>အမြတ်</h4><div class="value" style="color:var(--primary);">${d.total_profit.toLocaleString()} Ks</div></div></div><div class="category-title">📋 အသေးစိတ်</div>`;
    if (Object.keys(d.breakdown).length === 0) { html += '<p style="text-align:center; color:var(--hint);">ဒီလ အရောင်း မရှိပါ</p>'; }
    else { html += '<div class="card" style="padding:0; overflow-x:auto;"><table style="width:100%; border-collapse:collapse; font-size:12px;"><thead><tr style="background:var(--bg);"><th style="padding:8px;">Item</th><th style="padding:8px;">အရေအတွက်</th><th style="padding:8px;">ဝင်ငွေ</th><th style="padding:8px;">အမြတ်</th></tr></thead><tbody>';
        for (const [name, data] of Object.entries(d.breakdown)) { html += `<tr style="border-bottom:1px solid rgba(0,0,0,0.05);"><td style="padding:8px;">${name}</td><td style="padding:8px; text-align:center;">${data.count}</td><td style="padding:8px; text-align:right; color:var(--success);">${data.income.toLocaleString()}</td><td style="padding:8px; text-align:right; color:var(--primary);">${data.profit.toLocaleString()}</td></tr>`; }
        html += '</tbody></table></div>'; }
    container.innerHTML = html;
}

initApp();
