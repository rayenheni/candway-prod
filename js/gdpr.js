(function() {
    if (localStorage.getItem('candway_cookie_consent') || localStorage.getItem('candway_cookies_accepted')) return;

    const style = document.createElement('style');
    style.innerHTML = `
        #candway-gdpr-banner button:hover { transform: translateY(-1px); }
    `;
    document.head.appendChild(style);

    const banner = document.createElement('div');
    banner.id = 'candway-gdpr-banner';
    banner.style.cssText = `
        position: fixed;
        bottom: 24px;
        left: 24px;
        right: 24px;
        max-width: 500px;
        background: #0F172A;
        color: white;
        padding: 24px;
        border-radius: 16px;
        z-index: 10000;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.15);
        display: flex;
        flex-direction: column;
        gap: 16px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        animation: slideUp 0.5s cubic-bezier(0.16, 1, 0.3, 1);
    `;

    banner.innerHTML = `
        <div style="display:flex; gap:12px; align-items:start;">
            <div style="width:40px; height:40px; border-radius:10px; background:rgba(99, 102, 241, 0.1); display:flex; align-items:center; justify-content:center; color:#6366F1; flex-shrink:0;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5"></path><path d="M8.5 8.5v.01"></path><path d="M16 15.5v.01"></path><path d="M12 12v.01"></path><path d="M11 17v.01"></path><path d="M7 14v.01"></path></svg>
            </div>
            <div>
                <h4 style="margin:0 0 4px 0; font-size:16px; font-weight:700;">Data Privacy &amp; Cookies</h4>
                <p style="margin:0; font-size:13px; color:#94A3B8; line-height:1.5;">We use cookies to improve your experience and analyze our traffic, in accordance with <b>APDP</b> (Tunisia) and <b>GDPR</b> regulations. See our <a href="/privacy.html" style="color:#6366F1; text-decoration:none; font-weight:600;">Privacy Policy</a>.</p>
            </div>
        </div>
        <div style="display:flex; gap:12px;">
            <button id="gdpr-accept" style="flex:1; padding:10px; border-radius:8px; background:#6366F1; color:white; border:none; font-weight:600; cursor:pointer; transition:all 0.2s;">Accept All</button>
            <button id="gdpr-essential" style="padding:10px; border-radius:8px; background:transparent; color:#94A3B8; border:1px solid #334155; font-weight:600; cursor:pointer; transition:all 0.2s;">Essential Only</button>
            <button id="gdpr-decline" style="padding:10px; border-radius:8px; background:transparent; color:#64748B; border:1px solid #1e293b; font-weight:600; cursor:pointer; transition:all 0.2s;">Decline</button>
        </div>
        <style>
            @keyframes slideUp {
                from { transform: translateY(100%); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            #gdpr-accept:hover { background: #4F46E5; }
            #gdpr-essential:hover { color: white; border-color: #475569; }
            #gdpr-decline:hover { color: #94A3B8; border-color: #334155; }
        </style>
    `;

    document.body.appendChild(banner);

    function dismiss(type) {
        localStorage.setItem('candway_cookie_consent', JSON.stringify({
            accepted: type !== 'decline',
            type: type,
            timestamp: new Date().toISOString()
        }));
        localStorage.setItem('candway_cookies_accepted', type !== 'decline' ? 'true' : 'false');
        banner.style.opacity = '0';
        banner.style.transform = 'translateY(20px)';
        setTimeout(() => banner.remove(), 300);
    }

    document.getElementById('gdpr-accept').addEventListener('click', () => dismiss('all'));
    document.getElementById('gdpr-essential').addEventListener('click', () => dismiss('essential'));
    document.getElementById('gdpr-decline').addEventListener('click', () => dismiss('decline'));
})();
