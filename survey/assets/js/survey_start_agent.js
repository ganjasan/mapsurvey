/* Use your AI assistant (openspec: agent-onboarding, #312).
 *
 * The page carries every client's panel; this script shows one, remembers the
 * choice in this browser, notices the new MCP connection by polling the status
 * endpoint, and builds the first prompt in the browser -- the goal the creator
 * types is never sent to us, only to the assistant they open.
 *
 * Events (guarded, client slugs only): agent_client_chosen,
 * agent_install_clicked, agent_connected, agent_prompt_opened.
 */
(function () {
    'use strict';

    var root = document.getElementById('agent-page');
    if (!root) return;

    var POLL_MS = 3000;
    var POLL_LIMIT_MS = 15 * 60 * 1000;
    var STORE_KEY = 'msAgentClient';

    function json(id) {
        var el = document.getElementById(id);
        try { return el ? JSON.parse(el.textContent) : {}; } catch (e) { return {}; }
    }
    var prompts = json('agent-prompts');
    var targets = json('agent-prompt-targets');
    var strings = json('agent-strings');

    var tiles = Array.prototype.slice.call(root.querySelectorAll('[data-client]'));
    var panels = Array.prototype.slice.call(root.querySelectorAll('[data-panel]'));
    var statusBox = root.querySelector('[data-status]');
    var ask = root.querySelector('[data-ask]');
    var goal = root.querySelector('[data-goal]');
    var promptOut = root.querySelector('[data-prompt]');
    var current = null;
    var connected = false;

    function track(name, props) {
        if (window.posthog && posthog.capture) posthog.capture(name, props || {});
    }

    function store(value) {
        try {
            if (value === undefined) return window.localStorage.getItem(STORE_KEY);
            window.localStorage.setItem(STORE_KEY, value);
        } catch (e) { /* private window, blocked storage: no memory, no harm */ }
        return null;
    }

    function exists(slug) {
        return !!slug && tiles.some(function (t) { return t.dataset.client === slug; });
    }

    function methodOf(slug) {
        var p = root.querySelector('[data-panel="' + slug + '"]');
        return p ? p.dataset.method : '';
    }

    function select(slug, opts) {
        opts = opts || {};
        if (!exists(slug)) return;
        current = slug;
        tiles.forEach(function (t) { t.setAttribute('aria-pressed', t.dataset.client === slug ? 'true' : 'false'); });
        panels.forEach(function (p) { p.hidden = p.dataset.panel !== slug; });
        // A client that cannot connect has nothing to wait for.
        if (statusBox && !connected) statusBox.hidden = methodOf(slug) === 'unsupported';
        updatePrompt();
        if (opts.user) {
            store(slug);
            track('agent_client_chosen', { client: slug });
            try {
                var url = new URL(window.location.href);
                url.searchParams.set('client', slug);
                window.history.replaceState(null, '', url.toString());
            } catch (e) { /* old browser: the address just stays */ }
            if (opts.scroll) {
                var panel = root.querySelector('[data-panel="' + slug + '"]');
                if (panel && panel.scrollIntoView) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }

    tiles.forEach(function (t) {
        t.addEventListener('click', function () { select(t.dataset.client, { user: true }); });
    });
    root.querySelectorAll('[data-select]').forEach(function (b) {
        b.addEventListener('click', function () { select(b.dataset.select, { user: true, scroll: true }); });
    });

    // ── copy and install ──
    function copy(text, button) {
        if (!navigator.clipboard) return;
        navigator.clipboard.writeText(text).then(function () {
            if (!button) return;
            var icon = button.querySelector('i');
            if (icon) {
                var was = icon.className;
                icon.className = 'fas fa-check';
                setTimeout(function () { icon.className = was; }, 1500);
            }
        });
    }
    root.addEventListener('click', function (e) {
        var c = e.target.closest('[data-copy]');
        if (c) copy(c.dataset.copy, c);
        var i = e.target.closest('[data-install]');
        if (i && current) track('agent_install_clicked', { client: current });
    });

    // ── step 2: the prompt ──
    function promptText(forChatGPT) {
        var g = goal ? goal.value.trim() : '';
        var text = g ? (prompts.goal || '').replace('{goal}', g) : (prompts.empty || '');
        return forChatGPT ? '@Mapsurvey ' + text : text;
    }
    function updatePrompt() {
        if (!promptOut) return;
        var forChatGPT = targets[current] === 'chatgpt';
        promptOut.textContent = promptText(forChatGPT);
        var claude = root.querySelector('[data-open="claude"]');
        var chatgpt = root.querySelector('[data-open="chatgpt"]');
        if (claude) claude.href = 'https://claude.ai/new?q=' + encodeURIComponent(promptText(false));
        if (chatgpt) chatgpt.href = 'https://chatgpt.com/?q=' + encodeURIComponent(promptText(true));
        // The selected vendor's button leads; for everyone else Claude does.
        var lead = targets[current] === 'chatgpt' ? chatgpt : claude;
        [claude, chatgpt].forEach(function (b) {
            if (!b) return;
            b.className = 'btn ' + (b === lead ? 'btn-primary' : 'btn-outline-dark');
        });
    }
    if (goal) goal.addEventListener('input', updatePrompt);
    root.querySelectorAll('[data-open]').forEach(function (a) {
        a.addEventListener('click', function () {
            track('agent_prompt_opened', { client: current, target: a.dataset.open });
        });
    });
    var copyPrompt = root.querySelector('[data-copy-prompt]');
    if (copyPrompt) copyPrompt.addEventListener('click', function () {
        copy(promptText(targets[current] === 'chatgpt'), copyPrompt);
        track('agent_prompt_opened', { client: current, target: 'copy' });
    });

    function setStep(n) {
        root.querySelectorAll('.ag-steps li').forEach(function (li) {
            var s = parseInt(li.dataset.step, 10);
            li.classList.toggle('done', s < n);
            li.classList.toggle('on', s === n);
        });
    }
    function openAsk() {
        if (!ask) return;
        ask.hidden = false;
        setStep(2);
        updatePrompt();
    }

    function markConnected(client) {
        if (connected) return;
        connected = true;
        stopPolling();
        if (statusBox) {
            statusBox.hidden = false;
            statusBox.classList.add('ok');
            while (statusBox.firstChild) statusBox.removeChild(statusBox.firstChild);
            var icon = document.createElement('i');
            icon.className = 'fas fa-check-circle';
            var text = document.createElement('span');
            text.textContent = client ? (strings.connected_to || '').replace('{client}', client) : strings.connected;
            var manage = document.createElement('a');
            manage.href = strings.manage_url;
            manage.textContent = strings.manage;
            statusBox.appendChild(icon);
            statusBox.appendChild(text);
            statusBox.appendChild(manage);
        }
        track('agent_connected', { client: current, via: client ? 'oauth' : 'token' });
        openAsk();
        if (ask && ask.scrollIntoView) ask.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    var manual = root.querySelector('[data-manual]');
    if (manual) manual.addEventListener('click', function (e) {
        e.preventDefault();
        openAsk();
        if (ask && ask.scrollIntoView) ask.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // ── polling for the new connection ──
    var timer = null;
    var started = Date.now();
    function poll() {
        if (connected || document.hidden) return;
        if (Date.now() - started > POLL_LIMIT_MS) {
            stopPolling();
            var t = statusBox && statusBox.querySelector('[data-status-text]');
            var spin = statusBox && statusBox.querySelector('.spin');
            if (spin) spin.remove();
            if (t && strings.stopped) t.textContent = strings.stopped;
            return;
        }
        var url = root.dataset.statusUrl + '?since=' + encodeURIComponent(root.dataset.since);
        fetch(url, { credentials: 'same-origin', headers: { 'Accept': 'application/json' } })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) { if (data && data.connected) markConnected(data.client); })
            .catch(function () { /* offline for a moment: the next tick tries again */ });
    }
    function stopPolling() { if (timer) { clearInterval(timer); timer = null; } }
    timer = setInterval(poll, POLL_MS);
    document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });

    // ── "Tell us which" ──
    root.querySelectorAll('[data-request]').forEach(function (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var input = form.querySelector('[name="name"]');
            var name = input ? input.value.trim() : '';
            if (!name) return;
            var body = new FormData();
            body.append('name', name);
            var csrf = root.querySelector('[name="csrfmiddlewaretoken"]');
            fetch(root.dataset.requestUrl, {
                method: 'POST', body: body, credentials: 'same-origin',
                headers: { 'X-CSRFToken': csrf ? csrf.value : '' },
            }).then(function () {
                var thanks = form.querySelector('[data-request-thanks]');
                if (thanks) thanks.hidden = false;
                if (input) input.value = '';
            }).catch(function () {});
        });
    });

    // ── first selection: ?client=, else the last choice here, else the default ──
    var first = root.dataset.requested;
    if (!exists(first)) first = store();
    if (!exists(first)) first = root.dataset.default;
    select(first);
}());
