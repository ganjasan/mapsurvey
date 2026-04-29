/* editor_clipboard.js — issue #16
 *
 * Provides Clipboard (localStorage-backed) and KeyboardShortcuts modules
 * for the WYSIWYG survey editor. Public surface:
 *
 *   Clipboard.copy(kind, surveyUuid, id, label, inputType?)
 *   Clipboard.peek()                       -> {kind, source_survey_uuid, source_id, label, input_type, copied_at} | null
 *   Clipboard.clear()
 *   Clipboard.pasteQuestion(targetSurveyUuid, targetSectionId, parentQuestionId?, csrfToken)
 *   Clipboard.pasteSection(targetSurveyUuid, csrfToken)
 *   Clipboard.refreshButtons()             — show/hide all .paste-* buttons based on peek()
 *   ActiveCard.bind()                      — delegated click sets data-active="true"
 *   ActiveCard.getActive()                 -> {kind, id} | null
 *   KeyboardShortcuts.bind(getSurveyUuid, getCurrentSectionId, csrfToken, isReadOnly)
 *
 * The clipboard is intentionally simple: a single JSON entry under
 * localStorage.editor_clipboard. Cross-tab sync is automatic since
 * localStorage is shared by same-origin tabs.
 */
(function (window) {
    'use strict';

    var STORAGE_KEY = 'editor_clipboard';
    var SUBQUESTION_DISALLOWED = ['point', 'line', 'polygon'];

    // ─── Clipboard ──────────────────────────────────────────────────────────
    var Clipboard = {
        copy: function (kind, surveyUuid, id, label, inputType) {
            var entry = {
                kind: kind,                          // 'question' | 'section'
                source_survey_uuid: surveyUuid,
                source_id: Number(id),
                label: label || '',
                input_type: inputType || null,       // only meaningful for kind=question
                copied_at: new Date().toISOString(),
            };
            try {
                localStorage.setItem(STORAGE_KEY, JSON.stringify(entry));
            } catch (e) {
                console.error('Clipboard write failed', e);
                return;
            }
            Clipboard.refreshButtons();
        },

        peek: function () {
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            try {
                var entry = JSON.parse(raw);
                if (!entry || !entry.kind || !entry.source_survey_uuid || !entry.source_id) {
                    return null;
                }
                return entry;
            } catch (e) {
                return null;
            }
        },

        clear: function () {
            localStorage.removeItem(STORAGE_KEY);
            Clipboard.refreshButtons();
        },

        _post: function (url, body, csrfToken) {
            return fetch(url, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify(body),
            }).then(function (resp) {
                if (resp.status === 404) {
                    Clipboard.clear();
                    var msg = 'Source survey or item is no longer accessible — clipboard cleared.';
                    if (window.alert) window.alert(msg);
                    throw new Error('source_unavailable');
                }
                if (!resp.ok) {
                    return resp.text().then(function (text) {
                        var msg = text || ('Paste failed (HTTP ' + resp.status + ')');
                        if (window.alert) window.alert(msg);
                        throw new Error('paste_failed');
                    });
                }
                return resp;
            });
        },

        pasteQuestion: function (targetSurveyUuid, targetSectionId, parentQuestionId, csrfToken) {
            var entry = Clipboard.peek();
            if (!entry || entry.kind !== 'question') {
                return Promise.reject(new Error('no_question_in_clipboard'));
            }
            if (parentQuestionId != null && entry.input_type
                && SUBQUESTION_DISALLOWED.indexOf(entry.input_type) !== -1) {
                if (window.alert) {
                    window.alert('Sub-question cannot be a geo-type question.');
                }
                return Promise.reject(new Error('geo_subquestion_blocked'));
            }
            var url = '/editor/surveys/' + targetSurveyUuid + '/sections/' + targetSectionId + '/paste-question/';
            return Clipboard._post(url, {
                source_survey_uuid: entry.source_survey_uuid,
                source_question_id: entry.source_id,
                parent_question_id: parentQuestionId != null ? Number(parentQuestionId) : null,
            }, csrfToken).then(function (resp) {
                return resp.text().then(function (html) {
                    return { html: html, parent_question_id: parentQuestionId };
                });
            });
        },

        pasteSection: function (targetSurveyUuid, csrfToken) {
            var entry = Clipboard.peek();
            if (!entry || entry.kind !== 'section') {
                return Promise.reject(new Error('no_section_in_clipboard'));
            }
            var url = '/editor/surveys/' + targetSurveyUuid + '/paste-section/';
            return Clipboard._post(url, {
                source_survey_uuid: entry.source_survey_uuid,
                source_section_id: entry.source_id,
            }, csrfToken).then(function (resp) {
                return resp.text();
            });
        },

        refreshButtons: function () {
            var entry = Clipboard.peek();
            var hasQuestion = !!(entry && entry.kind === 'question');
            var hasSection = !!(entry && entry.kind === 'section');
            var sourceIsGeo = !!(entry && entry.input_type
                && SUBQUESTION_DISALLOWED.indexOf(entry.input_type) !== -1);

            document.querySelectorAll('.paste-question-btn').forEach(function (btn) {
                btn.style.display = hasQuestion ? '' : 'none';
                if (hasQuestion) btn.title = _tooltip(entry);
            });
            document.querySelectorAll('.paste-section-btn').forEach(function (btn) {
                btn.style.display = hasSection ? '' : 'none';
                if (hasSection) btn.title = _tooltip(entry);
            });
            document.querySelectorAll('.paste-as-subquestion-btn').forEach(function (btn) {
                var visible = hasQuestion && !sourceIsGeo;
                btn.style.display = visible ? '' : 'none';
                if (visible) btn.title = _tooltip(entry);
            });
        },
    };

    function _tooltip(entry) {
        var ago = _agoLabel(entry.copied_at);
        var label = entry.label || '(untitled)';
        return 'Clipboard: "' + label + '" — copied ' + ago;
    }

    function _agoLabel(iso) {
        if (!iso) return 'just now';
        var diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return Math.floor(diff / 60) + ' min ago';
        if (diff < 86400) return Math.floor(diff / 3600) + ' h ago';
        return Math.floor(diff / 86400) + ' d ago';
    }

    // ─── Active-card tracking ───────────────────────────────────────────────
    var ActiveCard = {
        bind: function () {
            document.addEventListener('click', function (e) {
                // Skip clicks on action regions — they have their own behaviour and
                // shouldn't change the active card. Each named region is listed
                // explicitly; a generic `button` catch-all would over-suppress.
                if (e.target.closest('.q-actions') || e.target.closest('.section-delete')
                    || e.target.closest('.section-action')
                    || e.target.closest('.add-question-btn')
                    || e.target.closest('.add-subquestion-wrap')
                    || e.target.closest('.paste-question-btn')
                    || e.target.closest('.paste-section-btn')
                    || e.target.closest('.paste-as-subquestion-btn')) {
                    return;
                }
                var qItem = e.target.closest('.question-item');
                var sItem = e.target.closest('.section-item');
                var target = qItem || sItem;
                if (!target) return;
                _setActive(target);
            });
            document.body.addEventListener('htmx:afterSettle', ActiveCard._restoreAfterSwap);
        },

        _restoreAfterSwap: function () {
            var saved = ActiveCard.getActive();
            if (!saved) return;
            var selector = saved.kind === 'question'
                ? '.question-item[data-question-id="' + saved.id + '"]'
                : '.section-item[data-section-id="' + saved.id + '"]';
            var node = document.querySelector(selector);
            if (node) _setActive(node);
        },

        getActive: function () {
            var q = document.querySelector('.question-item[data-active="true"]');
            if (q) return { kind: 'question', id: q.dataset.questionId, node: q };
            var s = document.querySelector('.section-item[data-active="true"]');
            if (s) return { kind: 'section', id: s.dataset.sectionId, node: s };
            return null;
        },
    };

    function _setActive(node) {
        document.querySelectorAll('.question-item[data-active="true"], .section-item[data-active="true"]')
            .forEach(function (el) { el.removeAttribute('data-active'); });
        node.setAttribute('data-active', 'true');
    }

    // ─── Keyboard shortcuts ─────────────────────────────────────────────────
    var KeyboardShortcuts = {
        bind: function (getSurveyUuid, getCurrentSectionId, csrfToken, isReadOnly) {
            if (isReadOnly) return;
            document.addEventListener('keydown', function (e) {
                var mod = navigator.platform.indexOf('Mac') !== -1 ? e.metaKey : e.ctrlKey;
                if (!mod) return;
                var key = e.key.toLowerCase();
                if (key !== 'd' && key !== 'c' && key !== 'v') return;

                var active = ActiveCard.getActive();
                var hasSelection = window.getSelection && window.getSelection().toString() !== '';

                if (key === 'd' && active) {
                    e.preventDefault();
                    _triggerDuplicate(active, getSurveyUuid(), csrfToken);
                    return;
                }
                if (key === 'c' && active && !hasSelection) {
                    e.preventDefault();
                    _triggerCopy(active, getSurveyUuid());
                    return;
                }
                if (key === 'v') {
                    var entry = Clipboard.peek();
                    if (!entry) return;
                    var sectionId = active && active.kind === 'section'
                        ? active.id
                        : getCurrentSectionId();
                    if (entry.kind === 'question' && sectionId) {
                        e.preventDefault();
                        _triggerPasteQuestion(getSurveyUuid(), sectionId, csrfToken);
                    } else if (entry.kind === 'section') {
                        e.preventDefault();
                        _triggerPasteSection(getSurveyUuid(), csrfToken);
                    }
                }
            });
        },
    };

    function _triggerDuplicate(active, surveyUuid, csrfToken) {
        var url = active.kind === 'question'
            ? '/editor/surveys/' + surveyUuid + '/questions/' + active.id + '/duplicate/'
            : '/editor/surveys/' + surveyUuid + '/sections/' + active.id + '/duplicate/';
        if (window.htmx) {
            // Insert clone immediately AFTER the active card — matches the
            // duplicate button's hx-swap="afterend" behaviour.
            window.htmx.ajax('POST', url, {
                target: active.node,
                swap: 'afterend',
                headers: { 'X-CSRFToken': csrfToken },
            });
        }
    }

    function _triggerCopy(active, surveyUuid) {
        var label = '';
        var inputType = null;
        if (active.kind === 'question') {
            var nameEl = active.node.querySelector('.q-name');
            label = nameEl ? nameEl.textContent.trim() : '';
            inputType = active.node.dataset.inputType || null;
        } else {
            var titleEl = active.node.querySelector('.section-title');
            label = titleEl ? titleEl.textContent.trim() : '';
        }
        Clipboard.copy(active.kind, surveyUuid, active.id, label, inputType);
    }

    function _triggerPasteQuestion(surveyUuid, sectionId, csrfToken) {
        Clipboard.pasteQuestion(surveyUuid, sectionId, null, csrfToken).then(function (result) {
            var list = document.getElementById('questions-list');
            if (list) list.insertAdjacentHTML('beforeend', result.html);
        }).catch(function () { /* alerted in _post */ });
    }

    function _triggerPasteSection(surveyUuid, csrfToken) {
        Clipboard.pasteSection(surveyUuid, csrfToken).then(function (html) {
            var list = document.getElementById('sections-list');
            if (list) list.insertAdjacentHTML('beforeend', html);
        }).catch(function () { /* alerted in _post */ });
    }

    // ─── Delegated copy buttons ─────────────────────────────────────────────
    function _bindCopyDelegation() {
        document.addEventListener('click', function (e) {
            var btn = e.target.closest('.copy-question-btn, .copy-section-btn');
            if (!btn || btn.disabled) return;
            e.preventDefault();
            e.stopPropagation();
            var kind = btn.classList.contains('copy-question-btn') ? 'question' : 'section';
            var surveyUuid = btn.dataset.surveyUuid;
            var id = kind === 'question' ? btn.dataset.questionId : btn.dataset.sectionId;
            var label = kind === 'question'
                ? (btn.dataset.questionName || '')
                : (btn.dataset.sectionTitle || '');
            var inputType = kind === 'question' ? (btn.dataset.inputType || null) : null;
            Clipboard.copy(kind, surveyUuid, id, label, inputType);
        });
    }

    // ─── Wire up automatic refresh on storage change (cross-tab sync) ───────
    window.addEventListener('storage', function (e) {
        if (e.key === STORAGE_KEY) Clipboard.refreshButtons();
    });

    // Refresh after every HTMX swap (newly-rendered cards may have paste buttons).
    document.addEventListener('DOMContentLoaded', function () {
        Clipboard.refreshButtons();
        ActiveCard.bind();
        _bindCopyDelegation();
    });
    document.body && document.body.addEventListener('htmx:afterSettle', function () {
        Clipboard.refreshButtons();
    });

    window.Clipboard = Clipboard;
    window.ActiveCard = ActiveCard;
    window.KeyboardShortcuts = KeyboardShortcuts;
})(window);
