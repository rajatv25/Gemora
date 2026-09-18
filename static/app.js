const tokenKey = 'member_portal_token';
const authScreen = document.querySelector('#auth-screen');
const trackerScreen = document.querySelector('#tracker-screen');
const message = document.querySelector('#message');
const trackerMessage = document.querySelector('#tracker-message');
const loginForm = document.querySelector('#login-form');
const registerForm = document.querySelector('#register-form');
const rateForm = document.querySelector('#rate-form');
const billForm = document.querySelector('#bill-form');
const saleForm = document.querySelector('#sale-form');
const inventoryForm = document.querySelector('#inventory-form');
const inventoryFormWrap = document.querySelector('#inventory-form-wrap');
const inventoryList = document.querySelector('#inventory-list');
const inventoryDetail = document.querySelector('#inventory-detail');
const inventoryMessage = document.querySelector('#inventory-message');
const customerForm = document.querySelector('#customer-form');
const customerFormWrap = document.querySelector('#customer-form-wrap');
const customerList = document.querySelector('#customer-list');
const customerDetail = document.querySelector('#customer-detail');
const customerMessage = document.querySelector('#customer-message');
const exchangeForm = document.querySelector('#exchange-form');
const purchaseForm = document.querySelector('#purchase-form');
const exchangeMessage = document.querySelector('#exchange-message');
const purchaseMessage = document.querySelector('#purchase-message');
const reportsMessage = document.querySelector('#reports-message');
const paymentsMessage = document.querySelector('#payments-message');
let currentCalculation = null;
let inventoryItems = [];
let customers = [];
let exchangeInventoryItems = [];

function showMessage(element, text, success = false) {
  element.textContent = text;
  element.className = success ? 'message success' : 'message';
}

async function request(path, options = {}) {
  const token = localStorage.getItem(tokenKey);
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.detail || 'Something went wrong.');
    error.status = response.status;
    throw error;
  }
  return data;
}

function switchAuthView(view) {
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.view === view));
  loginForm.classList.toggle('hidden', view !== 'login');
  registerForm.classList.toggle('hidden', view !== 'register');
  showMessage(message, '');
}

function showCategory(category) {
  document.querySelectorAll('.category-panel').forEach((panel) => {
    panel.classList.toggle('active-panel', panel.dataset.panel === category);
  });
  document.querySelectorAll('[data-category]').forEach((button) => {
    button.classList.toggle('active', button.dataset.category === category);
  });
}

function animateNumber(element, target, formatter = (value) => Math.round(value).toLocaleString()) {
  const end = Number(target) || 0;
  const start = Number(element.dataset.value || 0);
  const duration = 520;
  const startedAt = performance.now();
  const tick = (now) => {
    const progress = Math.min((now - startedAt) / duration, 1);
    const eased = 1 - ((1 - progress) ** 3);
    element.textContent = formatter(start + ((end - start) * eased));
    if (progress < 1) requestAnimationFrame(tick);
    else element.dataset.value = String(end);
  };
  requestAnimationFrame(tick);
}

function addRipple(event) {
  const button = event.target.closest('button');
  if (!button || button.disabled) return;
  const ripple = document.createElement('span');
  ripple.className = 'click-ripple';
  const bounds = button.getBoundingClientRect();
  ripple.style.left = `${event.clientX - bounds.left}px`;
  ripple.style.top = `${event.clientY - bounds.top}px`;
  button.appendChild(ripple);
  window.setTimeout(() => ripple.remove(), 520);
}

document.addEventListener('click', addRipple);

document.querySelectorAll('[data-category]').forEach((button) => {
  button.addEventListener('click', () => showCategory(button.dataset.category));
});

function applyTheme(theme) {
  document.body.classList.toggle('dark-mode', theme === 'dark');
  const themeToggle = document.querySelector('#theme-toggle');
  themeToggle.textContent = theme === 'dark' ? '☀' : '◐';
  themeToggle.setAttribute('aria-pressed', String(theme === 'dark'));
  themeToggle.setAttribute('title', theme === 'dark' ? 'Switch to light mode' : 'Switch to extreme dark mode');
  localStorage.setItem('gemora_theme', theme);
}

document.querySelector('#theme-toggle').addEventListener('click', () => {
  applyTheme(document.body.classList.contains('dark-mode') ? 'light' : 'dark');
});
applyTheme(localStorage.getItem('gemora_theme') || 'light');

document.querySelectorAll('.tab').forEach((tab) => tab.addEventListener('click', () => switchAuthView(tab.dataset.view)));

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(loginForm);
  try {
    const data = await request('/login', { method: 'POST', body: JSON.stringify(Object.fromEntries(form)) });
    localStorage.setItem(tokenKey, data.acces_token);
    await loadDashboard();
  } catch (error) {
    showMessage(message, error.message);
  }
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(registerForm);
  try {
    await request('/register', { method: 'POST', body: JSON.stringify(Object.fromEntries(form)) });
    registerForm.reset();
    switchAuthView('login');
    showMessage(message, 'Account created. Sign in now.', true);
  } catch (error) {
    showMessage(message, error.message);
  }
});

async function loadDashboard() {
  try {
    const data = await request('/jewellery/dashboard');
    authScreen.classList.add('hidden');
    trackerScreen.classList.remove('hidden');
    renderDashboard(data);
    await loadReports();
    await loadPayments();
    await loadInventory();
    await loadCustomers();
    await loadTradeModules(data);
  } catch (error) {
    if (error.status === 401) {
      localStorage.removeItem(tokenKey);
      trackerScreen.classList.add('hidden');
      authScreen.classList.remove('hidden');
      showMessage(message, 'Your session has expired. Please sign in again.');
    } else showMessage(trackerMessage, error.message);
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;',
  }[character]));
}

function inventoryQuery() {
  const params = new URLSearchParams();
  const fields = {
    search: '#inventory-search',
    category: '#inventory-category',
    metal_type: '#inventory-metal',
    purity: '#inventory-purity',
    status: '#inventory-status',
    sort_by: '#inventory-sort',
  };
  Object.entries(fields).forEach(([name, selector]) => {
    const value = document.querySelector(selector).value;
    if (value) params.set(name, value);
  });
  return params;
}

async function loadInventory() {
  try {
    inventoryList.innerHTML = '<p class="loading-state">Loading inventory...</p>';
    const data = await request(`/inventory?${inventoryQuery().toString()}`);
    inventoryItems = data.items;
    renderInventory(data.items);
  } catch (error) {
    showMessage(inventoryMessage, error.message);
  }
}

function renderInventory(items) {
  document.querySelector('#inventory-count').textContent = `${items.length} ITEMS`;
  const categorySelect = document.querySelector('#inventory-category');
  const categories = [...new Set(inventoryItems.map((item) => item.category))].sort();
  const selectedCategory = categorySelect.value;
  categorySelect.innerHTML = '<option value="">All categories</option>' + categories.map((category) => `<option>${escapeHtml(category)}</option>`).join('');
  categorySelect.value = selectedCategory;
  inventoryList.innerHTML = items.length ? items.map((item) => `
    <article class="inventory-row">
      <div class="inventory-image">${item.product_image ? `<img src="${escapeHtml(item.product_image)}" alt="">` : '<span>GJ</span>'}</div>
      <div class="inventory-main"><strong>${escapeHtml(item.product_name)}</strong><small>${escapeHtml(item.sku)} · ${escapeHtml(item.category)} / ${escapeHtml(item.subcategory || 'General')}</small><small>${escapeHtml(item.metal_type)} ${escapeHtml(item.purity)} · ${Number(item.net_metal_weight).toFixed(3)}g net</small></div>
      <span class="status-badge status-${item.status.toLowerCase().replaceAll(' ', '-')}">${escapeHtml(item.status)}</span>
      <strong class="inventory-price">₹${Number(item.selling_price).toFixed(2)}</strong>
      <div class="inventory-actions"><button class="text-button" data-inventory-action="details" data-inventory-id="${item.id}" type="button">Details</button><button class="text-button" data-inventory-action="edit" data-inventory-id="${item.id}" type="button">Edit</button><button class="archive-button" data-inventory-action="archive" data-inventory-id="${item.id}" type="button">Archive</button></div>
    </article>`).join('') : '<p class="empty-state">No inventory items match these filters.</p>';

  inventoryList.querySelectorAll('[data-inventory-action]').forEach((button) => {
    button.addEventListener('click', () => handleInventoryAction(button.dataset.inventoryAction, Number(button.dataset.inventoryId)));
  });
}

function openInventoryForm(item = null) {
  inventoryForm.reset();
  inventoryForm.querySelector('[name="id"]').value = item?.id || '';
  document.querySelector('#inventory-form-title').textContent = item ? 'Edit jewellery item' : 'Add jewellery item';
  inventoryFormWrap.classList.remove('hidden');
  if (item) {
    Object.keys(item).forEach((key) => {
      const field = inventoryForm.querySelector(`[name="${key}"]`);
      if (field && item[key] !== null && item[key] !== undefined) field.value = item[key];
    });
  }
  inventoryFormWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function handleInventoryAction(action, itemId) {
  const item = inventoryItems.find((candidate) => candidate.id === itemId);
  if (action === 'edit' && item) openInventoryForm(item);
  if (action === 'details') await showInventoryDetails(itemId);
  if (action === 'archive' && window.confirm('Archive this jewellery item?')) {
    try {
      await request(`/inventory/${itemId}`, { method: 'DELETE' });
      showMessage(inventoryMessage, 'Inventory item archived.', true);
      await loadInventory();
    } catch (error) { showMessage(inventoryMessage, error.message); }
  }
}

async function showInventoryDetails(itemId) {
  try {
    const data = await request(`/inventory/${itemId}/history`);
    const item = data.item;
    inventoryDetail.classList.remove('hidden');
    inventoryDetail.innerHTML = `
      <div class="surface-heading"><div><p class="eyebrow">ITEM DETAILS</p><h3>${escapeHtml(item.product_name)}</h3><small>${escapeHtml(item.sku)}</small></div><button class="text-button" id="close-inventory-detail" type="button">Close</button></div>
      <div class="detail-grid"><span>Category<strong>${escapeHtml(item.category)} / ${escapeHtml(item.subcategory || 'General')}</strong></span><span>Metal / purity<strong>${escapeHtml(item.metal_type)} / ${escapeHtml(item.purity)}</strong></span><span>Weights<strong>${Number(item.gross_weight).toFixed(3)}g gross · ${Number(item.net_metal_weight).toFixed(3)}g net</strong></span><span>Supplier / karigar<strong>${escapeHtml(item.supplier || 'Not assigned')} / ${escapeHtml(item.karigar || 'Not assigned')}</strong></span><span>Hallmark / HUID<strong>${escapeHtml(item.hallmark_huid || 'Not recorded')}</strong></span><span>Barcode / QR<strong>${escapeHtml(item.barcode || item.qr_code || 'Not recorded')}</strong></span></div>
      <div class="movement-controls"><select id="movement-type"><option value="purchase">Purchase received</option><option value="return">Customer return</option><option value="exchange">Exchange out</option><option value="adjustment">Stock adjustment</option></select><input id="movement-reference" placeholder="Reference / invoice"><button id="record-movement" class="primary-button compact-button" type="button">Record movement</button></div>
      <h4>Stock history</h4><div class="history-list">${data.history.map((entry) => `<div class="history-row"><strong>${escapeHtml(entry.movement_type)}</strong><span>${escapeHtml(entry.status_before)} → ${escapeHtml(entry.status_after)}</span><small>${escapeHtml(entry.created_at)} · ${escapeHtml(entry.reference || 'No reference')}</small></div>`).join('')}</div>`;
    document.querySelector('#close-inventory-detail').addEventListener('click', () => inventoryDetail.classList.add('hidden'));
    document.querySelector('#record-movement').addEventListener('click', async () => {
      try {
        await request(`/inventory/${itemId}/movement`, { method: 'POST', body: JSON.stringify({ movement_type: document.querySelector('#movement-type').value, reference: document.querySelector('#movement-reference').value }) });
        showMessage(inventoryMessage, 'Stock movement recorded.', true);
        await loadInventory();
        await showInventoryDetails(itemId);
      } catch (error) { showMessage(inventoryMessage, error.message); }
    });
    inventoryDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) { showMessage(inventoryMessage, error.message); }
}

function renderDashboard(data) {
  const firstName = data.user.full_name.split(' ')[0];
  document.querySelector('#welcome-heading').textContent = `Good morning, ${firstName}`;
  document.querySelector('#user-email').textContent = data.user.email;
  document.querySelector('#avatar').textContent = data.user.full_name.charAt(0).toUpperCase();
  const kpis = data.kpis || {};
  animateNumber(document.querySelector('#today-sales'), kpis.today_sales, (value) => `₹${value.toFixed(2)}`);
  animateNumber(document.querySelector('#total-customers'), kpis.total_customers);
  animateNumber(document.querySelector('#inventory-items'), kpis.inventory_items);
  animateNumber(document.querySelector('#outstanding-amount'), kpis.outstanding_amount, (value) => `₹${value.toFixed(2)}`);
  animateNumber(document.querySelector('#gold-stock'), kpis.gold_stock, (value) => `${value.toFixed(3)}g`);
  renderDashboardCharts(data.charts || {});

  const ratesList = document.querySelector('#rates-list');
  ratesList.innerHTML = data.rates.length
    ? data.rates.map((rate) => `
      <div class="rate-row">
        <div>
          <strong>${rate.metal_name}</strong>
          <small>Purity ${rate.purity_percentage}%</small>
        </div>
        <span class="rate-value">₹${Number(rate.rate_per_gram).toFixed(2)}/g</span>
      </div>`).join('')
    : '<p class="empty-state">No live metal rates added yet.</p>';

  const billList = document.querySelector('#bill-list');
  billList.innerHTML = data.bills.length
    ? data.bills.map((bill) => `
      <div class="bill-row">
        <div>
          <strong>${bill.bill_number}</strong>
          <small>${bill.customer_name}</small>
        </div>
        <div class="bill-meta">
          <span class="bill-total">₹${Number(bill.total_amount).toFixed(2)}</span>
          <button class="download-link" data-bill-id="${bill.id}" type="button">Download invoice</button>
        </div>
      </div>`).join('')
    : '<p class="empty-state">No bills created yet.</p>';

  document.querySelectorAll('[data-bill-id]').forEach((button) => {
    button.addEventListener('click', () => downloadBill(button.dataset.billId));
  });
}

function renderDashboardCharts(charts) {
  const sales = charts.sales || [];
  const maxSales = Math.max(...sales.map((entry) => Number(entry.amount)), 1);
  document.querySelector('#sales-chart').innerHTML = sales.length ? sales.map((entry) => `<div class="sales-bar-wrap"><div class="sales-bar" style="height:${Math.max((Number(entry.amount) / maxSales) * 100, entry.amount ? 8 : 2)}%" title="₹${Number(entry.amount).toFixed(2)}"><span>₹${Number(entry.amount).toFixed(0)}</span></div><small>${escapeHtml(entry.label)}</small></div>`).join('') : '<p class="empty-state">No sales recorded yet.</p>';
  const metals = charts.inventory_by_metal || [];
  const maxWeight = Math.max(...metals.map((entry) => Number(entry.weight)), 1);
  document.querySelector('#metal-chart').innerHTML = metals.length ? metals.map((entry) => `<div class="metal-chart-row"><div class="metal-label"><strong>${escapeHtml(entry.metal)}</strong><small>${Number(entry.items)} items · ${Number(entry.weight).toFixed(3)}g</small></div><div class="metal-track"><span style="width:${Math.max((Number(entry.weight) / maxWeight) * 100, 4)}%"></span></div></div>`).join('') : '<p class="empty-state">No available inventory yet.</p>';
  const transactions = charts.recent_transactions || [];
  document.querySelector('#recent-transactions-list').innerHTML = transactions.length ? transactions.map((entry) => `<div class="history-row"><strong>${escapeHtml(entry.type)}</strong><span>${escapeHtml(entry.label)} · ${escapeHtml(entry.detail || '')}</span><strong>₹${Number(entry.amount || 0).toFixed(2)}</strong><small>${escapeHtml(entry.date)}</small></div>`).join('') : '<p class="empty-state">No transactions recorded yet.</p>';
}

async function loadReports() {
  try {
    const data = await request('/jewellery/reports');
    renderReports(data);
  } catch (error) { showMessage(reportsMessage, error.message); }
}

function renderReports(data) {
  const sales = data.sales_report || [];
  document.querySelector('#sales-report-count').textContent = `${sales.length} RECORDS`;
  document.querySelector('#sales-report').innerHTML = sales.length ? sales.map((item) => `<div class="report-row"><span><strong>${escapeHtml(item.bill_number)}</strong><small>${escapeHtml(item.date)} · ${escapeHtml(item.customer)}</small></span><strong>₹${Number(item.amount).toFixed(2)}</strong></div>`).join('') : '<p class="empty-state">No sales records.</p>';
  const inventory = data.inventory_report || [];
  document.querySelector('#inventory-report-count').textContent = `${inventory.length} ITEMS`;
  document.querySelector('#inventory-report').innerHTML = inventory.length ? inventory.map((item) => `<div class="report-row"><span><strong>${escapeHtml(item.product)}</strong><small>${escapeHtml(item.sku)} · ${escapeHtml(item.metal)} ${escapeHtml(item.purity)} · ${Number(item.weight).toFixed(3)}g</small></span><span class="status-badge status-${item.status.toLowerCase().replaceAll(' ', '-')}">${escapeHtml(item.status)}</span></div>`).join('') : '<p class="empty-state">No inventory records.</p>';
  const outstanding = data.customer_outstanding_report || [];
  document.querySelector('#outstanding-report-count').textContent = `${outstanding.length} CUSTOMERS`;
  document.querySelector('#outstanding-report').innerHTML = outstanding.length ? outstanding.map((item) => `<div class="report-row"><span><strong>${escapeHtml(item.customer)}</strong><small>${escapeHtml(item.customer_id)} · ${escapeHtml(item.mobile)}</small></span><strong class="report-outstanding">₹${Number(item.outstanding).toFixed(2)}</strong></div>`).join('') : '<p class="empty-state">No customer records.</p>';
}

async function loadCustomers() {
  try {
    customerList.innerHTML = '<p class="loading-state">Loading customers...</p>';
    const params = new URLSearchParams();
    const search = document.querySelector('#customer-search').value.trim();
    if (search) params.set('search', search);
    const data = await request(`/customers?${params.toString()}`);
    customers = data.customers;
    renderCustomers(customers);
    const saleCustomer = document.querySelector('#sale-customer');
    const selected = saleCustomer.value;
    saleCustomer.innerHTML = '<option value="">Walk-in customer</option>' + customers.map((customer) => `<option value="${customer.id}">${escapeHtml(customer.name)} · ${escapeHtml(customer.mobile_number)}</option>`).join('');
    saleCustomer.value = selected;
  } catch (error) { showMessage(customerMessage, error.message); }
}

async function loadTradeModules(dashboardData = null) {
  try {
    if (!dashboardData) dashboardData = await request('/jewellery/dashboard');
    const inventoryData = await request('/inventory?status=In%20Stock&sort_by=product_name&sort_order=asc');
    exchangeInventoryItems = inventoryData.items;
    const customerOptions = '<option value="">Select customer</option>' + customers.map((customer) => `<option value="${customer.id}">${escapeHtml(customer.name)} · ${escapeHtml(customer.mobile_number)}</option>`).join('');
    document.querySelector('#exchange-customer').innerHTML = customerOptions;
    document.querySelector('#exchange-new-item').innerHTML = '<option value="">Enter new jewellery amount</option>' + exchangeInventoryItems.map((item) => { const amount = Number(item.selling_price) > 0 ? item.selling_price : item.purchase_price; return `<option value="${item.id}" data-amount="${amount}">${escapeHtml(item.product_name)} · ₹${Number(amount).toFixed(2)}</option>`; }).join('');
    const goldRate = dashboardData?.rates?.find((rate) => rate.metal_name.toLowerCase() === 'gold');
    if (goldRate) document.querySelector('#exchange-form [name="current_metal_rate"]').value = Number(goldRate.rate_per_gram).toFixed(2);
    await Promise.all([loadPurchases(), loadExchanges()]);
    if (!document.querySelector('#purchase-form [name="purchase_date"]').value) document.querySelector('#purchase-form [name="purchase_date"]').value = new Date().toISOString().slice(0, 10);
    if (!document.querySelector('#exchange-form [name="exchange_date"]').value) document.querySelector('#exchange-form [name="exchange_date"]').value = new Date().toISOString().slice(0, 10);
  } catch (error) { showMessage(exchangeMessage, error.message); }
}

async function loadPurchases() {
  document.querySelector('#purchase-list').innerHTML = '<p class="loading-state">Loading purchases...</p>';
  const data = await request('/trade/purchases');
  const list = document.querySelector('#purchase-list');
  list.innerHTML = data.purchases.length ? data.purchases.map((purchase) => `<div class="history-row"><strong>${escapeHtml(purchase.product)}</strong><span>${escapeHtml(purchase.supplier)} · ${escapeHtml(purchase.metal)} ${escapeHtml(purchase.purity)}</span><span>${Number(purchase.weight).toFixed(3)}g · ₹${Number(purchase.total_amount).toFixed(2)}</span><small>${escapeHtml(purchase.purchase_date)} · Stock item #${purchase.inventory_item_id}</small></div>`).join('') : '<p class="empty-state">No purchases recorded yet.</p>';
}

async function loadExchanges() {
  document.querySelector('#exchange-list').innerHTML = '<p class="loading-state">Loading exchanges...</p>';
  const data = await request('/trade/exchanges');
  const list = document.querySelector('#exchange-list');
  list.innerHTML = data.exchanges.length ? data.exchanges.map((exchange) => `<div class="history-row"><strong>${escapeHtml(exchange.new_jewellery)}</strong><span>Customer #${exchange.customer_id} · ${Number(exchange.old_jewellery_weight).toFixed(3)}g ${escapeHtml(exchange.old_purity)}</span><span>Exchange ₹${Number(exchange.exchange_value).toFixed(2)} · Difference ₹${Number(exchange.difference_amount).toFixed(2)}</span><small>${escapeHtml(exchange.exchange_date)}</small></div>`).join('') : '<p class="empty-state">No gold exchanges recorded yet.</p>';
}

async function loadPayments() {
  try {
    document.querySelector('#payment-list').innerHTML = '<p class="loading-state">Loading payments...</p>';
    const data = await request('/customers/payments/all');
    const payments = data.payments || [];
    document.querySelector('#payment-count').textContent = `${payments.length} RECORDS`;
    document.querySelector('#payment-list').innerHTML = payments.length ? payments.map((payment) => `<div class="report-row"><span><strong>${escapeHtml(payment.customer)}</strong><small>${escapeHtml(payment.payment_date)} · ${escapeHtml(payment.payment_method)}${payment.bill_id ? ` · Bill #${payment.bill_id}` : ''}</small></span><strong class="report-outstanding">₹${Number(payment.amount).toFixed(2)}</strong></div>`).join('') : '<p class="empty-state">No payments recorded yet. Payments will appear here after receiving a customer payment.</p>';
  } catch (error) { showMessage(paymentsMessage, error.message); }
}

function renderCustomers(items) {
  document.querySelector('#customer-count').textContent = `${items.length} CUSTOMERS`;
  customerList.innerHTML = items.length ? items.map((customer) => `
    <article class="customer-row">
      <div class="customer-avatar">${escapeHtml(customer.name.charAt(0).toUpperCase())}</div>
      <div class="inventory-main"><strong>${escapeHtml(customer.name)}</strong><small>${escapeHtml(customer.customer_id)} · ${escapeHtml(customer.mobile_number)}</small><small>${escapeHtml(customer.city || 'City not recorded')} · ${escapeHtml(customer.email || 'No email')}</small></div>
      <div class="customer-balance"><small>Outstanding</small><strong>₹${Number(customer.outstanding_balance).toFixed(2)}</strong></div>
      <div class="inventory-actions"><button class="text-button" data-customer-action="view" data-customer-id="${customer.id}" type="button">Profile</button><button class="text-button" data-customer-action="edit" data-customer-id="${customer.id}" type="button">Edit</button><button class="archive-button" data-customer-action="archive" data-customer-id="${customer.id}" type="button">Archive</button></div>
    </article>`).join('') : '<p class="empty-state">No customers match this search.</p>';
  customerList.querySelectorAll('[data-customer-action]').forEach((button) => button.addEventListener('click', () => handleCustomerAction(button.dataset.customerAction, Number(button.dataset.customerId))));
}

function openCustomerForm(customer = null) {
  customerForm.reset();
  customerForm.querySelector('[name="id"]').value = customer?.id || '';
  document.querySelector('#customer-form-title').textContent = customer ? 'Edit customer' : 'Add customer';
  customerFormWrap.classList.remove('hidden');
  if (customer) Object.keys(customer).forEach((key) => { const field = customerForm.querySelector(`[name="${key}"]`); if (field) field.value = customer[key] || ''; });
  customerFormWrap.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function handleCustomerAction(action, customerId) {
  const customer = customers.find((item) => item.id === customerId);
  if (action === 'edit' && customer) openCustomerForm(customer);
  if (action === 'view') await showCustomerProfile(customerId);
  if (action === 'archive' && window.confirm('Archive this customer?')) {
    try { await request(`/customers/${customerId}`, { method: 'DELETE' }); showMessage(customerMessage, 'Customer archived.', true); await loadCustomers(); }
    catch (error) { showMessage(customerMessage, error.message); }
  }
}

async function showCustomerProfile(customerId) {
  try {
    const profile = await request(`/customers/${customerId}`);
    customerDetail.classList.remove('hidden');
    customerDetail.innerHTML = `
      <div class="surface-heading"><div><p class="eyebrow">CUSTOMER PROFILE</p><h3>${escapeHtml(profile.name)}</h3><small>${escapeHtml(profile.customer_id)} · ${escapeHtml(profile.mobile_number)} · Created ${escapeHtml(profile.created_at)}</small><p class="customer-contact">${escapeHtml(profile.address || 'Address not recorded')}${profile.city ? ` · ${escapeHtml(profile.city)}` : ''}${profile.gstin ? ` · GSTIN ${escapeHtml(profile.gstin)}` : ''}</p><small>${escapeHtml(profile.notes || '')}</small></div><button class="text-button" id="close-customer-detail" type="button">Close</button></div>
      <div class="customer-stats"><span>Total purchases<strong>₹${Number(profile.total_purchases).toFixed(2)}</strong></span><span>Total payments<strong>₹${Number(profile.total_payments).toFixed(2)}</strong></span><span>Outstanding<strong>₹${Number(profile.outstanding_balance).toFixed(2)}</strong></span></div>
      <div class="customer-profile-grid"><div><h4>Purchase history / Bills</h4>${renderCustomerHistory(profile.bills, 'bill_number', 'total_amount')}</div><div><h4>Payment history</h4>${renderCustomerHistory(profile.payment_history, 'payment_method', 'amount')}</div><div><h4>Returns</h4>${renderCustomerHistory(profile.returns, 'transaction_type', 'amount')}</div><div><h4>Exchanges</h4>${renderCustomerHistory(profile.exchanges, 'transaction_type', 'amount')}</div><div><h4>Udhaar transactions</h4>${renderCustomerHistory(profile.udhaar_transactions, 'transaction_type', 'amount')}</div></div>
      <div class="customer-ledger-actions"><form id="customer-payment-form" class="form-card"><h4>Record payment</h4><label>Amount<input name="amount" type="number" min="0.01" step="0.01" required></label><label>Date<input name="payment_date" type="date" required></label><label>Method<select name="payment_method"><option>Cash</option><option>UPI</option><option>Card</option><option>Bank transfer</option></select></label><button class="primary-button" type="submit">Add payment</button></form><form id="customer-transaction-form" class="form-card"><h4>Record customer transaction</h4><label>Type<select name="transaction_type"><option value="udhaar">Udhaar</option><option value="return">Return</option><option value="exchange">Exchange</option></select></label><label>Amount<input name="amount" type="number" min="0" step="0.01" required></label><label>Date<input name="transaction_date" type="date" required></label><button class="primary-button" type="submit">Add transaction</button></form></div>`;
    document.querySelector('#close-customer-detail').addEventListener('click', () => customerDetail.classList.add('hidden'));
    document.querySelector('#customer-payment-form').addEventListener('submit', (event) => submitCustomerLedger(event, customerId, 'payment'));
    document.querySelector('#customer-transaction-form').addEventListener('submit', (event) => submitCustomerLedger(event, customerId, 'transaction'));
    customerDetail.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (error) { showMessage(customerMessage, error.message); }
}

function renderCustomerHistory(items, labelKey, amountKey) {
  return items.length ? `<div class="history-list">${items.map((item) => `<div class="history-row"><strong>${escapeHtml(item[labelKey] || item.transaction_type)}</strong><span>₹${Number(item[amountKey] || 0).toFixed(2)}</span><small>${escapeHtml(item.issue_date || item.payment_date || item.transaction_date || '')}</small></div>`).join('')}</div>` : '<p class="empty-state">No records yet.</p>';
}

async function submitCustomerLedger(event, customerId, kind) {
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = Object.fromEntries(form);
  payload.amount = Number(payload.amount);
  try { await request(`/customers/${customerId}/${kind === 'payment' ? 'payments' : 'transactions'}`, { method: 'POST', body: JSON.stringify(payload) }); showMessage(customerMessage, 'Customer ledger updated.', true); await loadCustomers(); await showCustomerProfile(customerId); }
  catch (error) { showMessage(customerMessage, error.message); }
}

async function downloadBill(billId) {
  try {
    const response = await fetch(`/jewellery/bill/${billId}/download`, {
      headers: { Authorization: `Bearer ${localStorage.getItem(tokenKey)}` },
    });
    if (!response.ok) throw new Error('Unable to download invoice.');
    const blob = await response.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `bill-${billId}.txt`;
    link.click();
    URL.revokeObjectURL(link.href);
  } catch (error) {
    showMessage(trackerMessage, error.message);
  }
}

document.querySelector('#new-inventory-button').addEventListener('click', () => openInventoryForm());
document.querySelector('#cancel-inventory-button').addEventListener('click', () => inventoryFormWrap.classList.add('hidden'));
document.querySelector('#new-customer-button').addEventListener('click', () => openCustomerForm());
document.querySelector('#cancel-customer-button').addEventListener('click', () => customerFormWrap.classList.add('hidden'));
document.querySelector('#customer-search').addEventListener('input', loadCustomers);
document.querySelector('#exchange-new-item').addEventListener('change', (event) => {
  const selected = event.target.selectedOptions[0];
  if (selected?.dataset.amount) document.querySelector('#exchange-form [name="new_jewellery_amount"]').value = selected.dataset.amount;
});
['#inventory-search', '#inventory-category', '#inventory-metal', '#inventory-purity', '#inventory-status', '#inventory-sort'].forEach((selector) => {
  document.querySelector(selector).addEventListener(selector === '#inventory-search' ? 'input' : 'change', loadInventory);
});

inventoryForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(inventoryForm);
  const numericFields = ['gross_weight', 'stone_weight', 'net_metal_weight', 'making_charges', 'wastage_percentage', 'stone_charges', 'diamond_charges', 'purchase_price', 'selling_price'];
  const payload = Object.fromEntries(form);
  numericFields.forEach((field) => {
    payload[field] = payload[field] === '' ? null : Number(payload[field]);
  });
  const itemId = payload.id;
  delete payload.id;
  try {
    await request(itemId ? `/inventory/${itemId}` : '/inventory', {
      method: itemId ? 'PUT' : 'POST',
      body: JSON.stringify(payload),
    });
    inventoryFormWrap.classList.add('hidden');
    showMessage(inventoryMessage, itemId ? 'Jewellery item updated.' : 'Jewellery item added to stock.', true);
    await loadInventory();
  } catch (error) {
    showMessage(inventoryMessage, error.message);
  }
});

customerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(customerForm);
  const payload = Object.fromEntries(form);
  const customerId = payload.id;
  delete payload.id;
  try {
    await request(customerId ? `/customers/${customerId}` : '/customers', { method: customerId ? 'PUT' : 'POST', body: JSON.stringify(payload) });
    customerFormWrap.classList.add('hidden');
    showMessage(customerMessage, customerId ? 'Customer updated.' : 'Customer added.', true);
    await loadCustomers();
  } catch (error) { showMessage(customerMessage, error.message); }
});

purchaseForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(purchaseForm);
  const payload = Object.fromEntries(form);
  ['weight', 'rate', 'total_amount'].forEach((field) => { payload[field] = Number(payload[field]); });
  try {
    await request('/trade/purchases', { method: 'POST', body: JSON.stringify(payload) });
    purchaseForm.reset();
    purchaseForm.querySelector('[name="purchase_date"]').value = new Date().toISOString().slice(0, 10);
    showMessage(purchaseMessage, 'Purchase saved and inventory increased.', true);
    await loadInventory();
    await loadTradeModules();
  } catch (error) { showMessage(purchaseMessage, error.message); }
});

exchangeForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(exchangeForm);
  const payload = Object.fromEntries(form);
  ['customer_id', 'old_jewellery_weight', 'current_metal_rate', 'new_jewellery_amount'].forEach((field) => { payload[field] = Number(payload[field]); });
  payload.new_inventory_item_id = payload.new_inventory_item_id ? Number(payload.new_inventory_item_id) : null;
  try {
    const result = await request('/trade/exchanges', { method: 'POST', body: JSON.stringify(payload) });
    const exchange = result.exchange;
    document.querySelector('#exchange-preview').innerHTML = `<div class="preview-row"><span>Old jewellery value</span><strong>₹${Number(exchange.exchange_value).toFixed(2)}</strong></div><div class="preview-row"><span>New jewellery</span><strong>₹${Number(exchange.new_jewellery_amount).toFixed(2)}</strong></div><div class="preview-row total"><span>Difference amount</span><strong>₹${Number(exchange.difference_amount).toFixed(2)}</strong></div>`;
    showMessage(exchangeMessage, 'Gold exchange saved successfully.', true);
    exchangeForm.reset();
    exchangeForm.querySelector('[name="exchange_date"]').value = new Date().toISOString().slice(0, 10);
    await loadInventory();
    await loadTradeModules();
  } catch (error) { showMessage(exchangeMessage, error.message); }
});

rateForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(rateForm);
  try {
    await request('/jewellery/rates', {
      method: 'POST',
      body: JSON.stringify({
        metal_name: form.get('metal_name'),
        rate_per_gram: Number(form.get('rate_per_gram')),
        purity_percentage: Number(form.get('purity_percentage')),
      }),
    });
    rateForm.reset();
    showMessage(trackerMessage, 'Metal rate saved successfully.', true);
    await loadDashboard();
  } catch (error) {
    showMessage(trackerMessage, error.message);
  }
});

document.querySelector('#calculator-purity').addEventListener('change', (event) => {
  document.querySelector('#custom-purity-field').classList.toggle('hidden', event.target.value !== 'Custom');
});

billForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const form = new FormData(billForm);
  const payload = Object.fromEntries(form);
  ['custom_purity_percentage', 'gross_weight', 'stone_weight', 'net_weight', 'making_charge_per_gram', 'making_charge_percentage', 'wastage_percentage', 'stone_charges', 'diamond_charges', 'discount_amount', 'gst_percent'].forEach((field) => {
    payload[field] = payload[field] === '' ? null : Number(payload[field]);
  });

  try {
    const preview = await request('/jewellery/calculate', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
    const previewBox = document.querySelector('#bill-preview');
    previewBox.classList.remove('hidden');
    previewBox.innerHTML = `
      <div class="surface-heading"><div><p class="eyebrow">AUTHORITATIVE BREAKDOWN</p><h3>${escapeHtml(preview.item_name)}</h3></div><span class="date-label">${escapeHtml(preview.metal_name)} · ${escapeHtml(preview.purity)}</span></div>
      <p class="rate-summary">Rate ₹${Number(preview.metal_rate).toFixed(2)}/g · Purity-adjusted ₹${Number(preview.purity_adjusted_rate).toFixed(2)}/g · Net ${Number(preview.net_weight).toFixed(3)}g</p>
      <div class="preview-row"><span>Net Metal Value</span><strong>₹${Number(preview.net_metal_value).toFixed(2)}</strong></div>
      <div class="preview-row"><span>+ Wastage (${Number(preview.wastage_percentage).toFixed(2)}%)</span><strong>₹${Number(preview.wastage_amount).toFixed(2)}</strong></div>
      <div class="preview-row"><span>+ Making Charges</span><strong>₹${Number(preview.making_charges).toFixed(2)}</strong></div>
      <div class="preview-row"><span>+ Stone Charges</span><strong>₹${Number(preview.stone_charges).toFixed(2)}</strong></div>
      <div class="preview-row"><span>+ Diamond Charges</span><strong>₹${Number(preview.diamond_charges).toFixed(2)}</strong></div>
      <div class="preview-row"><span>- Discount</span><strong>₹${Number(preview.discount_amount).toFixed(2)}</strong></div>
      <div class="preview-row"><span>Taxable Amount</span><strong>₹${Number(preview.taxable_amount).toFixed(2)}</strong></div>
      <div class="preview-row"><span>+ GST (${Number(preview.gst_percent).toFixed(2)}%)</span><strong>₹${Number(preview.gst_amount).toFixed(2)}</strong></div>
      <div class="preview-row total"><span>Final Payable Amount</span><strong>₹${Number(preview.final_amount).toFixed(2)}</strong></div>
    `;
    currentCalculation = preview;
    document.querySelector('#sale-details').classList.remove('hidden');
    showMessage(trackerMessage, 'Price calculated from the current metal rate.', true);
  } catch (error) {
    showMessage(trackerMessage, error.message);
  }
});

saleForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  if (!currentCalculation) return;
  const form = new FormData(saleForm);
  const payload = { record_type: form.get('record_type'), customer_id: form.get('customer_id') ? Number(form.get('customer_id')) : null, calculation: currentCalculation };
  try {
    const created = await request('/jewellery/calculate/save', { method: 'POST', body: JSON.stringify(payload) });
    showMessage(trackerMessage, `${created.message}${created.bill_number ? ` (${created.bill_number})` : ''}`, true);
    document.querySelector('#sale-details').classList.add('hidden');
    document.querySelector('#bill-preview').classList.add('hidden');
    saleForm.reset();
    currentCalculation = null;
    await loadDashboard();
    showCategory(created.bill_number ? 'bills' : 'billing');
  } catch (error) {
    showMessage(trackerMessage, error.message);
  }
});

document.querySelector('#logout-button').addEventListener('click', () => {
  localStorage.removeItem(tokenKey);
  trackerScreen.classList.add('hidden');
  authScreen.classList.remove('hidden');
  switchAuthView('login');
});

if (localStorage.getItem(tokenKey)) loadDashboard();

showCategory('overview');
