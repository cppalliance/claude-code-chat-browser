// Shared UI utilities — imported by route modules.

export function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

export function truncate(s, max) {
    if (!s) return '';
    return s.length > max ? s.slice(0, max) + '...' : s;
}

export function formatTs(ts) {
    try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return ts;
        const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
        const dd = String(d.getUTCDate()).padStart(2, '0');
        const yyyy = d.getUTCFullYear();
        let hh = d.getUTCHours();
        const ampm = hh >= 12 ? 'PM' : 'AM';
        hh = hh % 12 || 12;
        const hhStr = String(hh).padStart(2, '0');
        const min = String(d.getUTCMinutes()).padStart(2, '0');
        const ss = String(d.getUTCSeconds()).padStart(2, '0');
        return `${mm}/${dd}/${yyyy} ${hhStr}:${min}:${ss} ${ampm}`;
    } catch { return ts; }
}

export function formatDate(ts) {
    try {
        const d = new Date(ts);
        if (isNaN(d.getTime())) return ts ? ts.slice(0, 10) : '';
        const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
        const dd = String(d.getUTCDate()).padStart(2, '0');
        const yyyy = d.getUTCFullYear();
        return `${mm}/${dd}/${yyyy}`;
    } catch { return ts ? ts.slice(0, 10) : ''; }
}

export function formatSize(bytes) {
    if (bytes == null) return '?';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

// Smooth content swap — fades out old content, swaps HTML, fades in new content
export function smoothSet(el, html) {
    el.classList.remove('content-ready');
    el.classList.add('content-enter');
    void el.offsetHeight;
    el.innerHTML = html;
    requestAnimationFrame(() => {
        el.classList.remove('content-enter');
        el.classList.add('content-ready');
    });
}

export function showToast(message, type = 'info') {
    const icons = { success: '\u2713', error: '\u2717', info: '\u2139' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const iconSpan = document.createElement('span');
    iconSpan.className = 'toast-icon';
    iconSpan.textContent = icons[type] || icons.info;
    const textSpan = document.createElement('span');
    textSpan.className = 'toast-text';
    textSpan.textContent = message;
    const closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.textContent = '\u00d7';
    const progress = document.createElement('div');
    progress.className = 'toast-progress';
    toast.append(iconSpan, textSpan, closeBtn, progress);
    document.body.appendChild(toast);
    closeBtn.addEventListener('click', () => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); });
    requestAnimationFrame(() => toast.classList.add('show'));
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

export function showConfirm(message, onConfirm) {
    const overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    const dialog = document.createElement('div');
    dialog.className = 'confirm-dialog';
    const header = document.createElement('div');
    header.className = 'confirm-header';
    header.innerHTML = '<span class="confirm-icon">?</span><span class="confirm-title">Confirm Action</span>';
    const msgEl = document.createElement('p');
    msgEl.className = 'confirm-message';
    msgEl.textContent = message;
    const actions = document.createElement('div');
    actions.className = 'confirm-actions';
    actions.innerHTML = '<button class="confirm-btn confirm-cancel">Cancel</button><button class="confirm-btn confirm-ok">Confirm</button>';
    dialog.append(header, msgEl, actions);
    overlay.appendChild(dialog);
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('show'));
    const close = () => { overlay.classList.remove('show'); setTimeout(() => overlay.remove(), 200); document.removeEventListener('keydown', onKey); };
    const onKey = (e) => { if (e.key === 'Escape') close(); if (e.key === 'Enter') { close(); onConfirm(); } };
    document.addEventListener('keydown', onKey);
    dialog.querySelector('.confirm-cancel').addEventListener('click', close);
    dialog.querySelector('.confirm-ok').addEventListener('click', () => { close(); onConfirm(); });
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    dialog.querySelector('.confirm-ok').focus();
}

// Top loading bar — created once at module load time
export const loadingBar = (() => {
    const bar = document.createElement('div');
    bar.className = 'loading-bar';
    document.documentElement.appendChild(bar);
    return {
        start() { bar.classList.remove('done'); bar.classList.add('active'); },
        done()  { bar.classList.remove('active'); bar.classList.add('done'); setTimeout(() => bar.classList.remove('done'), 400); },
    };
})();

export function setHamburgerVisible(visible) {
    const btn = document.getElementById('hamburger-btn');
    if (btn) btn.style.display = visible ? 'flex' : 'none';
}

export function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (!sidebar) return;
    sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('active', sidebar.classList.contains('open'));
}

export function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
}
