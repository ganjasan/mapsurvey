/**
 * RangeSlider — reusable range selection overlay for Chart.js containers.
 *
 * Usage:
 *   var slider = new RangeSlider(containerEl, {
 *       formatValue: function(pct) { return ...; },  // pct (0–1) → display string
 *       onFilter:    function(left, right) { ... },   // called on drag end / input change
 *       onReset:     function() { ... },              // optional: extra cleanup on reset
 *   });
 *
 *   slider.parseInput = function(lo, hi) { return { left: pct, right: pct }; };
 *   slider.reset();           // programmatic reset
 *   slider.getRange();        // → { left: 0–1, right: 0–1 }
 */
(function() {
    'use strict';

    function RangeSlider(container, opts) {
        opts = opts || {};
        this.container = container;
        this.formatValue = opts.formatValue || function(pct) { return (pct * 100).toFixed(0) + '%'; };
        this.onFilter = opts.onFilter || function() {};
        this.onReset = opts.onReset || function() {};
        this.parseInput = opts.parseInput || null;
        this.rangeLeft = 0;
        this.rangeRight = 1;
        this._dragging = null;

        this._buildDOM();
        this._bindEvents();
        this._positionHandles();
    }

    RangeSlider.prototype._buildDOM = function() {
        // Shades
        this.shadeL = _el('div', {
            position: 'absolute', top: 0, left: 0, bottom: 0,
            background: 'rgba(79,70,229,0.06)', pointerEvents: 'none',
            display: 'none', borderRight: '2px solid var(--accent)',
        });
        this.shadeR = _el('div', {
            position: 'absolute', top: 0, right: 0, bottom: 0,
            background: 'rgba(79,70,229,0.06)', pointerEvents: 'none',
            display: 'none', borderLeft: '2px solid var(--accent)',
        });

        // Handles with tooltips
        var handleStyle = {
            position: 'absolute', top: 0, bottom: 0, width: '8px',
            background: 'var(--accent)', cursor: 'ew-resize',
            borderRadius: '3px', opacity: '0.6', zIndex: 2,
        };
        this.handleL = _el('div', handleStyle);
        this.handleR = _el('div', handleStyle);

        var tooltipStyle = {
            display: 'none', position: 'absolute',
            bottom: 'calc(100% + 4px)', left: '50%',
            transform: 'translateX(-50%)', background: '#1f2937',
            color: '#fff', fontSize: '0.7rem', padding: '2px 6px',
            borderRadius: '4px', whiteSpace: 'nowrap',
            pointerEvents: 'none', zIndex: 10,
        };
        this.tooltipL = _el('span', tooltipStyle);
        this.tooltipR = _el('span', tooltipStyle);
        this.handleL.appendChild(this.tooltipL);
        this.handleR.appendChild(this.tooltipR);

        // Clean up any existing slider elements
        _removeByClass(this.container, 'rs-shade');
        _removeByClass(this.container, 'rs-handle');

        this.shadeL.classList.add('rs-shade');
        this.shadeR.classList.add('rs-shade');
        this.handleL.classList.add('rs-handle');
        this.handleR.classList.add('rs-handle');

        this.container.appendChild(this.shadeL);
        this.container.appendChild(this.shadeR);
        this.container.appendChild(this.handleL);
        this.container.appendChild(this.handleR);

        // Input row — built with DOM methods
        this._inputRow = document.createElement('div');
        Object.assign(this._inputRow.style, {
            display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.35rem',
        });
        this._inputRow.classList.add('rs-input-row');

        var label = document.createElement('label');
        Object.assign(label.style, { fontSize: '0.72rem', color: '#9ca3af', margin: '0' });
        label.textContent = 'Range:';

        this.inputMin = document.createElement('input');
        this.inputMin.type = 'number';
        this.inputMin.step = 'any';
        this.inputMin.placeholder = 'min';
        this.inputMin.className = 'rs-range-min form-control form-control-sm';
        Object.assign(this.inputMin.style, { width: '75px', fontSize: '0.75rem', padding: '2px 4px' });

        var sep = document.createElement('span');
        Object.assign(sep.style, { fontSize: '0.72rem', color: '#9ca3af' });
        sep.textContent = '\u2013';

        this.inputMax = document.createElement('input');
        this.inputMax.type = 'number';
        this.inputMax.step = 'any';
        this.inputMax.placeholder = 'max';
        this.inputMax.className = 'rs-range-max form-control form-control-sm';
        Object.assign(this.inputMax.style, { width: '75px', fontSize: '0.75rem', padding: '2px 4px' });

        this._inputRow.appendChild(label);
        this._inputRow.appendChild(this.inputMin);
        this._inputRow.appendChild(sep);
        this._inputRow.appendChild(this.inputMax);

        // Insert after container
        this.container.parentNode.insertBefore(this._inputRow, this.container.nextSibling);
    };

    RangeSlider.prototype._positionHandles = function() {
        var w = this.container.offsetWidth;
        var lx = Math.round(this.rangeLeft * w);
        var rx = Math.round(this.rangeRight * w);
        this.handleL.style.left = (lx - 4) + 'px';
        this.handleR.style.left = (rx - 4) + 'px';

        var noSel = this.rangeLeft <= 0.001 && this.rangeRight >= 0.999;
        this.shadeL.style.display = noSel ? 'none' : 'block';
        this.shadeR.style.display = noSel ? 'none' : 'block';
        if (!noSel) {
            this.shadeL.style.width = lx + 'px';
            this.shadeR.style.width = (w - rx) + 'px';
        }

        // Tooltips
        this.tooltipL.textContent = this.formatValue(this.rangeLeft);
        this.tooltipR.textContent = this.formatValue(this.rangeRight);

        // Sync inputs
        if (!noSel) {
            this.inputMin.value = this.formatValue(this.rangeLeft);
            this.inputMax.value = this.formatValue(this.rangeRight);
        } else {
            this.inputMin.value = '';
            this.inputMax.value = '';
        }
    };

    RangeSlider.prototype._bindEvents = function() {
        var self = this;

        this.handleL.addEventListener('mousedown', function(e) { e.preventDefault(); self._startDrag('left'); });
        this.handleR.addEventListener('mousedown', function(e) { e.preventDefault(); self._startDrag('right'); });

        this.handleL.addEventListener('touchstart', function(e) { e.preventDefault(); self._startDrag('left', true); }, { passive: false });
        this.handleR.addEventListener('touchstart', function(e) { e.preventDefault(); self._startDrag('right', true); }, { passive: false });

        this.inputMin.addEventListener('change', function() { self._onInputChange(); });
        this.inputMax.addEventListener('change', function() { self._onInputChange(); });

        window.addEventListener('resize', function() { self._positionHandles(); });
    };

    RangeSlider.prototype._startDrag = function(side, isTouch) {
        var self = this;
        this._dragging = side;
        var tooltip = side === 'left' ? this.tooltipL : this.tooltipR;
        tooltip.style.display = 'block';

        var moveEvent = isTouch ? 'touchmove' : 'mousemove';
        var endEvent = isTouch ? 'touchend' : 'mouseup';

        function onMove(e) {
            if (!self._dragging) return;
            var clientX = isTouch ? e.touches[0].clientX : e.clientX;
            var rect = self.container.getBoundingClientRect();
            var pct = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
            if (self._dragging === 'left') {
                self.rangeLeft = Math.min(pct, self.rangeRight - 0.01);
            } else {
                self.rangeRight = Math.max(pct, self.rangeLeft + 0.01);
            }
            self._positionHandles();
        }

        function onEnd() {
            if (!self._dragging) return;
            self.tooltipL.style.display = 'none';
            self.tooltipR.style.display = 'none';
            self._dragging = null;
            document.removeEventListener(moveEvent, onMove);
            document.removeEventListener(endEvent, onEnd);
            self._fireFilter();
        }

        document.addEventListener(moveEvent, onMove);
        document.addEventListener(endEvent, onEnd);
    };

    RangeSlider.prototype._fireFilter = function() {
        this.onFilter(this.rangeLeft, this.rangeRight);
    };

    RangeSlider.prototype._onInputChange = function() {
        var lo = this.inputMin.value;
        var hi = this.inputMax.value;
        var loNum = parseFloat(lo);
        var hiNum = parseFloat(hi);

        if ((lo === '' || isNaN(loNum)) && (hi === '' || isNaN(hiNum))) {
            this.reset();
            return;
        }

        if (this.parseInput) {
            var range = this.parseInput(lo, hi);
            this.rangeLeft = range.left;
            this.rangeRight = range.right;
        }
        if (this.rangeRight - this.rangeLeft < 0.01) {
            this.rangeRight = Math.min(1, this.rangeLeft + 0.01);
        }
        this._positionHandles();
        this._fireFilter();
    };

    RangeSlider.prototype.reset = function() {
        this.rangeLeft = 0;
        this.rangeRight = 1;
        this.inputMin.value = '';
        this.inputMax.value = '';
        this._positionHandles();
        this.onReset();
    };

    RangeSlider.prototype.getRange = function() {
        return { left: this.rangeLeft, right: this.rangeRight };
    };

    /** Switch inputs to datetime-local mode. */
    RangeSlider.prototype.setDatetimeMode = function() {
        this.inputMin.type = 'datetime-local';
        this.inputMax.type = 'datetime-local';
        this.inputMin.style.width = 'auto';
        this.inputMax.style.width = 'auto';
        this.inputMin.removeAttribute('step');
        this.inputMax.removeAttribute('step');
    };

    // Helpers
    function _el(tag, styles) {
        var el = document.createElement(tag);
        for (var k in styles) {
            if (styles.hasOwnProperty(k)) {
                el.style[k] = typeof styles[k] === 'number' ? styles[k] + 'px' : String(styles[k]);
            }
        }
        return el;
    }

    function _removeByClass(parent, cls) {
        var els = parent.querySelectorAll('.' + cls);
        for (var i = 0; i < els.length; i++) els[i].remove();
    }

    window.RangeSlider = RangeSlider;
})();
