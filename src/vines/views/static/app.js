const SEARCH_INDEX = __SEARCH_INDEX__;
const GRAPH_DATA = __GRAPH_DATA__;

function initTheme() {
    const savedTheme = localStorage.getItem('garden-theme');
    if (savedTheme) document.body.setAttribute('data-theme', savedTheme);
    const btn = document.getElementById('theme-toggle');
    if (btn) {
        btn.addEventListener('click', () => {
            const current = document.body.getAttribute('data-theme');
            const target = current === 'dark' ? 'light' : 'dark';
            document.body.setAttribute('data-theme', target);
            localStorage.setItem('garden-theme', target);
        });
    }
}

function initSidebarToggles() {
    const leftBtn = document.getElementById('toggle-left-btn');
    const rightBtn = document.getElementById('toggle-right-btn');
    if (localStorage.getItem('garden-hide-left') === 'true') document.body.classList.add('hide-left-sidebar');
    if (localStorage.getItem('garden-hide-right') === 'true') document.body.classList.add('hide-right-sidebar');

    if (leftBtn) {
        leftBtn.addEventListener('click', () => {
            document.body.classList.toggle('hide-left-sidebar');
            localStorage.setItem('garden-hide-left', document.body.classList.contains('hide-left-sidebar'));
        });
    }
    if (rightBtn) {
        rightBtn.addEventListener('click', () => {
            document.body.classList.toggle('hide-right-sidebar');
            localStorage.setItem('garden-hide-right', document.body.classList.contains('hide-right-sidebar'));
        });
    }
}

function initSearch() {
    const input = document.getElementById('search-input');
    const results = document.getElementById('search-results');
    if (!input || !results) return;

    input.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        if (!query) { results.style.display = 'none'; return; }
        const matches = SEARCH_INDEX.filter(item =>
            item.title.toLowerCase().includes(query) || item.snippet.toLowerCase().includes(query)
        ).slice(0, 6);

        if (matches.length === 0) {
            results.innerHTML = '<div style="padding:0.6rem; font-size:0.85rem; opacity:0.6;">No notes found</div>';
        } else {
            results.innerHTML = matches.map(m => `
                <a href="${m.url}" class="search-result-item">
                    <div class="search-result-title">${m.title}</div>
                    <div class="search-result-snippet">${m.snippet}</div>
                </a>
            `).join('');
        }
        results.style.display = 'block';
    });
    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !results.contains(e.target)) results.style.display = 'none';
    });
}

function initCodeCopy() {
    document.querySelectorAll('pre').forEach(pre => {
        const btn = document.createElement('button');
        btn.className = 'code-copy-btn';
        btn.innerText = 'Copy';
        btn.addEventListener('click', () => {
            const code = pre.querySelector('code') ? pre.querySelector('code').innerText : pre.innerText;
            navigator.clipboard.writeText(code).then(() => {
                btn.innerText = 'Copied!';
                setTimeout(() => btn.innerText = 'Copy', 2000);
            });
        });
        pre.appendChild(btn);
    });
}

function initLightbox() {
    const modal = document.createElement('div');
    modal.className = 'lightbox-modal';
    modal.innerHTML = '<img id="lightbox-img" src="" alt="Zoomed view">';
    document.body.appendChild(modal);
    const imgTarget = document.getElementById('lightbox-img');

    document.querySelectorAll('.article-body img:not(.obsidian-embed-pdf)').forEach(img => {
        img.addEventListener('click', () => {
            imgTarget.src = img.src;
            modal.classList.add('active');
        });
    });
    modal.addEventListener('click', () => modal.classList.remove('active'));
}

function initHoverCards() {
    const card = document.createElement('div');
    card.className = 'hover-preview-card';
    document.body.appendChild(card);

    document.querySelectorAll('a.wikilink').forEach(link => {
        link.addEventListener('mouseenter', (e) => {
            const targetUrl = link.getAttribute('href');
            const match = SEARCH_INDEX.find(item => item.url.endsWith(targetUrl) || targetUrl.endsWith(item.url));
            if (!match) return;

            card.innerHTML = `<strong>${match.title}</strong><p style="margin-top:0.4rem;">${match.snippet}...</p>`;
            card.style.display = 'block';

            const rect = link.getBoundingClientRect();
            let left = rect.left;
            let top = rect.bottom + 8;
            if (left + 320 > window.innerWidth) left = window.innerWidth - 330;
            if (top + 210 > window.innerHeight) top = rect.top - 210;
            card.style.left = `${Math.max(10, left)}px`;
            card.style.top = `${Math.max(10, top)}px`;
        });
        link.addEventListener('mouseleave', () => { card.style.display = 'none'; });
    });
}

function initGraph() {
    const canvas = document.getElementById('graph-canvas');
    if (!canvas || !GRAPH_DATA.nodes.length) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width = canvas.parentElement.clientWidth;
    const height = canvas.height = 260;

    let currentPath = window.location.pathname.replace(/\\/g, '/');
    if (currentPath.endsWith('/') || !currentPath.split('/').pop().includes('.')) {
        if (!currentPath.endsWith('/')) currentPath += '/';
        currentPath += 'index.html';
    }

    const currentNote = GRAPH_DATA.nodes.find(n => currentPath.endsWith(n.id));

    let rawNodes = GRAPH_DATA.nodes;
    let rawLinks = GRAPH_DATA.links;
    let centerId = null;

    if (currentNote) {
        centerId = currentNote.id;
        const neighborIds = new Set([centerId]);
        rawLinks.forEach(l => {
            if (l.source === centerId) neighborIds.add(l.target);
            if (l.target === centerId) neighborIds.add(l.source);
        });
        rawNodes = GRAPH_DATA.nodes.filter(n => neighborIds.has(n.id));
        rawLinks = GRAPH_DATA.links.filter(l => neighborIds.has(l.source) && neighborIds.has(l.target));
    }

    const currentDepth = currentNote ? currentNote.id.split('/').slice(0, -1).length : 0;
    const rootOffset = '../'.repeat(currentDepth);

    const nodes = rawNodes.map(n => ({
        ...n,
        x: Math.random() * (width - 80) + 40,
        y: Math.random() * (height - 80) + 40,
        vx: 0,
        vy: 0,
        isCenter: n.id === centerId
    }));

    const nodeMap = new Map(nodes.map(n => [n.id, n]));
    const links = rawLinks.map(l => ({ source: nodeMap.get(l.source), target: nodeMap.get(l.target) })).filter(l => l.source && l.target);

    if (centerId && nodeMap.has(centerId)) {
        const cNode = nodeMap.get(centerId);
        cNode.x = width / 2;
        cNode.y = height / 2;

        const otherNodes = nodes.filter(n => !n.isCenter);
        otherNodes.forEach((n, idx) => {
            const angle = (idx / Math.max(1, otherNodes.length)) * Math.PI * 2;
            const radius = Math.min(width, height) * 0.3;
            n.x = width / 2 + Math.cos(angle) * radius;
            n.y = height / 2 + Math.sin(angle) * radius;
        });
    }

    function stepPhysics() {
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                const dx = nodes[j].x - nodes[i].x;
                const dy = nodes[j].y - nodes[i].y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                if (dist < 120) {
                    const force = (120 - dist) / dist * 0.05;
                    nodes[i].vx -= dx * force; nodes[i].vy -= dy * force;
                    nodes[j].vx += dx * force; nodes[j].vy += dy * force;
                }
            }
        }
        links.forEach(l => {
            const dx = l.target.x - l.source.x;
            const dy = l.target.y - l.source.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const force = (dist - 60) * 0.01;
            l.source.vx += dx * force; l.source.vy += dy * force;
            l.target.vx -= dx * force; l.target.vy -= dy * force;
        });
        nodes.forEach(n => {
            if (n.isCenter) {
                n.vx += (width / 2 - n.x) * 0.1;
                n.vy += (height / 2 - n.y) * 0.1;
            } else {
                n.vx += (width / 2 - n.x) * 0.002;
                n.vy += (height / 2 - n.y) * 0.002;
            }
            n.vx *= 0.85; n.vy *= 0.85;
            n.x = Math.max(20, Math.min(width - 20, n.x + n.vx));
            n.y = Math.max(20, Math.min(height - 20, n.y + n.vy));
        });
    }

    function draw() {
        ctx.clearRect(0, 0, width, height);
        const borderColor = getComputedStyle(document.body).getPropertyValue('--border-color').trim() || '#ccc';
        const accentColor = getComputedStyle(document.body).getPropertyValue('--accent-color').trim() || '#7c3aed';
        const textColor = getComputedStyle(document.body).getPropertyValue('--text-color').trim() || '#000';
        const surfaceColor = getComputedStyle(document.body).getPropertyValue('--surface-color').trim() || '#fff';

        links.forEach(l => {
            ctx.beginPath();
            ctx.strokeStyle = (l.source.isCenter || l.target.isCenter) ? accentColor : borderColor;
            ctx.lineWidth = (l.source.isCenter || l.target.isCenter) ? 1.5 : 1;
            ctx.moveTo(l.source.x, l.source.y);
            ctx.lineTo(l.target.x, l.target.y);
            ctx.stroke();
        });

        nodes.forEach(n => {
            ctx.beginPath();
            const radius = n.isCenter ? 8 : 5;
            ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = accentColor;
            ctx.fill();

            if (n.isCenter) {
                ctx.lineWidth = 2;
                ctx.strokeStyle = textColor;
                ctx.stroke();
            }
        });

        nodes.forEach(n => {
            const labelX = n.x + (n.isCenter ? 12 : 9);
            const labelY = n.y + 4;

            ctx.font = n.isCenter ? 'bold 12px sans-serif' : '11px sans-serif';

            ctx.strokeStyle = surfaceColor;
            ctx.lineWidth = 4;
            ctx.lineJoin = 'round';
            ctx.miterLimit = 2;
            ctx.strokeText(n.title, labelX, labelY);

            ctx.fillStyle = textColor;
            ctx.fillText(n.title, labelX, labelY);
        });
    }

    let frames = 0;
    function animate() {
        if (frames < 120) { stepPhysics(); draw(); frames++; requestAnimationFrame(animate); }
        else { draw(); }
    }
    animate();

    canvas.addEventListener('click', (e) => {
        const rect = canvas.getBoundingClientRect();
        const hit = nodes.find(n => Math.hypot(n.x - (e.clientX - rect.left), n.y - (e.clientY - rect.top)) < 12);
        if (hit) {
            const targetUrl = rootOffset + hit.id;
            window.location.href = targetUrl;
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme(); initSidebarToggles(); initSearch();
    initCodeCopy(); initLightbox(); initHoverCards(); initGraph();
});