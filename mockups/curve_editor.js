/**
 * Interactive Curve Editor for Monthly Profiles
 * 
 * Creates an SVG-based interactive chart with 12 draggable points
 * for editing monthly values like coal prices or use factors.
 * 
 * Features:
 * - Draggable points for each month
 * - Smooth curve connecting points
 * - Real-time value display
 * - Preset patterns (Flat, Seasonal, Quarterly)
 * - Undo/redo support
 * - Syncs with hidden form inputs
 */

(function() {
    'use strict';
    
    // Month labels
    const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    
    // Preset patterns
    const PRESETS = {
        flat: () => Array(12).fill(1.0),
        seasonal: () => [0.95, 0.93, 0.90, 0.88, 0.92, 1.05, 1.10, 1.12, 1.08, 0.98, 0.95, 0.96],
        quarterly: () => [0.95, 0.95, 0.95, 0.98, 0.98, 0.98, 1.02, 1.02, 1.02, 1.05, 1.05, 1.05],
        summer_peak: () => [0.85, 0.85, 0.90, 0.95, 1.05, 1.15, 1.20, 1.18, 1.10, 0.95, 0.85, 0.82],
        winter_peak: () => [1.15, 1.12, 1.05, 0.95, 0.85, 0.82, 0.85, 0.88, 0.92, 1.00, 1.08, 1.15],
    };
    
    /**
     * CurveEditor class
     */
    class CurveEditor {
        constructor(container, options = {}) {
            this.container = typeof container === 'string' 
                ? document.querySelector(container) 
                : container;
            
            if (!this.container) {
                console.error('CurveEditor: Container not found');
                return;
            }
            
            // Options
            this.options = {
                width: options.width || 400,
                height: options.height || 200,
                baseValue: options.baseValue || 100,
                minMultiplier: options.minMultiplier || 0.5,
                maxMultiplier: options.maxMultiplier || 1.5,
                unit: options.unit || '',
                decimals: options.decimals || 2,
                color: options.color || '#2d4a6f',
                inputPrefix: options.inputPrefix || 'monthly_',
                onChange: options.onChange || null,
                ...options
            };
            
            // State
            this.values = options.initialValues || Array(12).fill(this.options.baseValue);
            this.history = [this.values.slice()];
            this.historyIndex = 0;
            this.isDragging = false;
            this.activePoint = null;
            
            // Build the editor
            this.render();
            this.attachEvents();
        }
        
        /**
         * Render the SVG editor
         */
        render() {
            const { width, height, color } = this.options;
            const padding = { top: 20, right: 20, bottom: 40, left: 50 };
            const chartWidth = width - padding.left - padding.right;
            const chartHeight = height - padding.top - padding.bottom;
            
            this.container.innerHTML = `
                <div class="curve-editor" style="width: ${width}px;">
                    <div class="curve-editor-toolbar">
                        <select class="curve-preset-select">
                            <option value="">Apply Preset...</option>
                            <option value="flat">Flat (same each month)</option>
                            <option value="seasonal">Seasonal (summer/winter peaks)</option>
                            <option value="quarterly">Quarterly Step-Up</option>
                            <option value="summer_peak">Summer Peak</option>
                            <option value="winter_peak">Winter Peak</option>
                        </select>
                        <button type="button" class="curve-undo-btn" disabled title="Undo (Ctrl+Z)">↩</button>
                        <button type="button" class="curve-redo-btn" disabled title="Redo (Ctrl+Y)">↪</button>
                        <button type="button" class="curve-reset-btn" title="Reset to flat">Reset</button>
                    </div>
                    <svg class="curve-svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
                        <defs>
                            <linearGradient id="areaGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                                <stop offset="0%" style="stop-color:${color};stop-opacity:0.2"/>
                                <stop offset="100%" style="stop-color:${color};stop-opacity:0.02"/>
                            </linearGradient>
                        </defs>
                        
                        <!-- Grid lines -->
                        <g class="curve-grid"></g>
                        
                        <!-- Axes -->
                        <g class="curve-axes">
                            <line x1="${padding.left}" y1="${padding.top}" 
                                  x2="${padding.left}" y2="${height - padding.bottom}" 
                                  stroke="#e5e7eb" stroke-width="1"/>
                            <line x1="${padding.left}" y1="${height - padding.bottom}" 
                                  x2="${width - padding.right}" y2="${height - padding.bottom}" 
                                  stroke="#e5e7eb" stroke-width="1"/>
                        </g>
                        
                        <!-- Y-axis labels -->
                        <g class="curve-y-labels"></g>
                        
                        <!-- X-axis labels (months) -->
                        <g class="curve-x-labels"></g>
                        
                        <!-- Area fill -->
                        <path class="curve-area" fill="url(#areaGradient)"/>
                        
                        <!-- Line -->
                        <path class="curve-line" fill="none" stroke="${color}" stroke-width="2"/>
                        
                        <!-- Points -->
                        <g class="curve-points"></g>
                        
                        <!-- Tooltip -->
                        <g class="curve-tooltip" style="display: none;">
                            <rect x="0" y="0" width="60" height="24" rx="4" fill="#1f2937"/>
                            <text x="30" y="16" text-anchor="middle" fill="white" font-size="12"></text>
                        </g>
                    </svg>
                    <div class="curve-values-row"></div>
                    
                    <!-- Hidden inputs for form submission -->
                    <div class="curve-hidden-inputs"></div>
                </div>
                
                <style>
                    .curve-editor {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    }
                    .curve-editor-toolbar {
                        display: flex;
                        gap: 8px;
                        margin-bottom: 12px;
                    }
                    .curve-preset-select {
                        padding: 6px 10px;
                        font-size: 13px;
                        border: 1px solid #d1d5db;
                        border-radius: 6px;
                        background: white;
                        flex: 1;
                    }
                    .curve-undo-btn, .curve-redo-btn, .curve-reset-btn {
                        padding: 6px 12px;
                        font-size: 13px;
                        border: 1px solid #d1d5db;
                        border-radius: 6px;
                        background: white;
                        cursor: pointer;
                    }
                    .curve-undo-btn:disabled, .curve-redo-btn:disabled {
                        opacity: 0.5;
                        cursor: not-allowed;
                    }
                    .curve-undo-btn:hover:not(:disabled), 
                    .curve-redo-btn:hover:not(:disabled),
                    .curve-reset-btn:hover {
                        background: #f3f4f6;
                    }
                    .curve-svg {
                        display: block;
                        cursor: crosshair;
                    }
                    .curve-point {
                        cursor: grab;
                        transition: r 0.15s ease;
                    }
                    .curve-point:hover, .curve-point.active {
                        r: 8;
                    }
                    .curve-point.active {
                        cursor: grabbing;
                    }
                    .curve-values-row {
                        display: flex;
                        justify-content: space-between;
                        padding: 8px 50px 0 50px;
                        font-size: 11px;
                        color: #6b7280;
                    }
                    .curve-value-cell {
                        text-align: center;
                        min-width: 24px;
                    }
                    .curve-value-cell input {
                        width: 40px;
                        padding: 2px 4px;
                        text-align: center;
                        font-size: 11px;
                        border: 1px solid transparent;
                        border-radius: 4px;
                        background: transparent;
                    }
                    .curve-value-cell input:hover {
                        border-color: #d1d5db;
                    }
                    .curve-value-cell input:focus {
                        outline: none;
                        border-color: #2d4a6f;
                        background: white;
                    }
                </style>
            `;
            
            // Store references
            this.svg = this.container.querySelector('.curve-svg');
            this.gridGroup = this.svg.querySelector('.curve-grid');
            this.yLabels = this.svg.querySelector('.curve-y-labels');
            this.xLabels = this.svg.querySelector('.curve-x-labels');
            this.areaPath = this.svg.querySelector('.curve-area');
            this.linePath = this.svg.querySelector('.curve-line');
            this.pointsGroup = this.svg.querySelector('.curve-points');
            this.tooltip = this.svg.querySelector('.curve-tooltip');
            this.valuesRow = this.container.querySelector('.curve-values-row');
            this.hiddenInputs = this.container.querySelector('.curve-hidden-inputs');
            this.presetSelect = this.container.querySelector('.curve-preset-select');
            this.undoBtn = this.container.querySelector('.curve-undo-btn');
            this.redoBtn = this.container.querySelector('.curve-redo-btn');
            this.resetBtn = this.container.querySelector('.curve-reset-btn');
            
            // Store dimensions
            this.padding = padding;
            this.chartWidth = chartWidth;
            this.chartHeight = chartHeight;
            
            // Draw static elements
            this.drawGrid();
            this.drawAxes();
            
            // Initial update
            this.updateChart();
        }
        
        /**
         * Draw grid lines
         */
        drawGrid() {
            const { minMultiplier, maxMultiplier } = this.options;
            const { padding, chartWidth, chartHeight } = this;
            
            let html = '';
            
            // Horizontal grid lines (5 lines)
            for (let i = 0; i <= 4; i++) {
                const y = padding.top + (chartHeight * i / 4);
                html += `<line x1="${padding.left}" y1="${y}" x2="${padding.left + chartWidth}" y2="${y}" 
                         stroke="#f3f4f6" stroke-width="1"/>`;
            }
            
            // Vertical grid lines (12 months)
            for (let i = 0; i < 12; i++) {
                const x = padding.left + (chartWidth * i / 11);
                html += `<line x1="${x}" y1="${padding.top}" x2="${x}" y2="${padding.top + chartHeight}" 
                         stroke="#f3f4f6" stroke-width="1" stroke-dasharray="2,2"/>`;
            }
            
            this.gridGroup.innerHTML = html;
        }
        
        /**
         * Draw axis labels
         */
        drawAxes() {
            const { baseValue, minMultiplier, maxMultiplier, unit } = this.options;
            const { padding, chartWidth, chartHeight } = this;
            
            // Y-axis labels
            let yHtml = '';
            const range = maxMultiplier - minMultiplier;
            for (let i = 0; i <= 4; i++) {
                const multiplier = maxMultiplier - (range * i / 4);
                const value = baseValue * multiplier;
                const y = padding.top + (chartHeight * i / 4);
                yHtml += `<text x="${padding.left - 8}" y="${y + 4}" 
                          text-anchor="end" font-size="11" fill="#9ca3af">
                          ${value.toFixed(0)}${unit}
                          </text>`;
            }
            this.yLabels.innerHTML = yHtml;
            
            // X-axis labels
            let xHtml = '';
            for (let i = 0; i < 12; i++) {
                const x = padding.left + (chartWidth * i / 11);
                xHtml += `<text x="${x}" y="${padding.top + chartHeight + 20}" 
                          text-anchor="middle" font-size="10" fill="#9ca3af">
                          ${MONTHS[i]}
                          </text>`;
            }
            this.xLabels.innerHTML = xHtml;
        }
        
        /**
         * Update chart visualization
         */
        updateChart() {
            const { baseValue, minMultiplier, maxMultiplier, color, decimals } = this.options;
            const { padding, chartWidth, chartHeight } = this;
            const range = maxMultiplier - minMultiplier;
            
            // Calculate point positions
            const points = this.values.map((value, i) => {
                const multiplier = value / baseValue;
                const x = padding.left + (chartWidth * i / 11);
                const y = padding.top + chartHeight - ((multiplier - minMultiplier) / range * chartHeight);
                return { x, y, value, multiplier };
            });
            
            // Draw area path
            const areaPoints = points.map(p => `${p.x},${p.y}`).join(' L');
            const areaBottom = padding.top + chartHeight;
            this.areaPath.setAttribute('d', 
                `M${points[0].x},${areaBottom} L${areaPoints} L${points[11].x},${areaBottom} Z`);
            
            // Draw line path with curve
            const linePath = this.createSmoothPath(points);
            this.linePath.setAttribute('d', linePath);
            
            // Draw points
            let pointsHtml = '';
            points.forEach((p, i) => {
                pointsHtml += `
                    <circle class="curve-point" data-index="${i}" 
                            cx="${p.x}" cy="${p.y}" r="6" 
                            fill="${color}" stroke="white" stroke-width="2"/>
                `;
            });
            this.pointsGroup.innerHTML = pointsHtml;
            
            // Update values row
            let valuesHtml = '';
            this.values.forEach((value, i) => {
                valuesHtml += `
                    <div class="curve-value-cell">
                        <input type="number" value="${value.toFixed(decimals)}" 
                               data-index="${i}" step="0.01" style="width: 50px;">
                    </div>
                `;
            });
            this.valuesRow.innerHTML = valuesHtml;
            
            // Update hidden inputs
            let hiddenHtml = '';
            this.values.forEach((value, i) => {
                const name = `${this.options.inputPrefix}${i + 1}`;
                hiddenHtml += `<input type="hidden" name="${name}" value="${value.toFixed(decimals)}">`;
            });
            this.hiddenInputs.innerHTML = hiddenHtml;
            
            // Trigger change callback
            if (this.options.onChange) {
                this.options.onChange(this.values.slice());
            }
        }
        
        /**
         * Create smooth bezier curve path
         */
        createSmoothPath(points) {
            if (points.length < 2) return '';
            
            let path = `M${points[0].x},${points[0].y}`;
            
            for (let i = 0; i < points.length - 1; i++) {
                const p0 = points[i === 0 ? i : i - 1];
                const p1 = points[i];
                const p2 = points[i + 1];
                const p3 = points[i + 2 < points.length ? i + 2 : i + 1];
                
                const cp1x = p1.x + (p2.x - p0.x) / 6;
                const cp1y = p1.y + (p2.y - p0.y) / 6;
                const cp2x = p2.x - (p3.x - p1.x) / 6;
                const cp2y = p2.y - (p3.y - p1.y) / 6;
                
                path += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${p2.x},${p2.y}`;
            }
            
            return path;
        }
        
        /**
         * Attach event listeners
         */
        attachEvents() {
            // Point dragging
            this.pointsGroup.addEventListener('mousedown', this.handleMouseDown.bind(this));
            document.addEventListener('mousemove', this.handleMouseMove.bind(this));
            document.addEventListener('mouseup', this.handleMouseUp.bind(this));
            
            // Touch support
            this.pointsGroup.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
            document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
            document.addEventListener('touchend', this.handleTouchEnd.bind(this));
            
            // Value input changes
            this.valuesRow.addEventListener('change', this.handleInputChange.bind(this));
            
            // Presets
            this.presetSelect.addEventListener('change', this.handlePresetChange.bind(this));
            
            // Undo/redo
            this.undoBtn.addEventListener('click', this.undo.bind(this));
            this.redoBtn.addEventListener('click', this.redo.bind(this));
            this.resetBtn.addEventListener('click', this.reset.bind(this));
            
            // Keyboard shortcuts
            document.addEventListener('keydown', (e) => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
                    if (this.container.contains(document.activeElement)) {
                        e.preventDefault();
                        this.undo();
                    }
                }
                if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.key === 'z' && e.shiftKey))) {
                    if (this.container.contains(document.activeElement)) {
                        e.preventDefault();
                        this.redo();
                    }
                }
            });
        }
        
        handleMouseDown(e) {
            const point = e.target.closest('.curve-point');
            if (!point) return;
            
            this.isDragging = true;
            this.activePoint = parseInt(point.dataset.index);
            point.classList.add('active');
            
            this.showTooltip(this.activePoint);
        }
        
        handleMouseMove(e) {
            if (!this.isDragging || this.activePoint === null) return;
            
            const rect = this.svg.getBoundingClientRect();
            const y = e.clientY - rect.top;
            
            this.updatePointFromY(this.activePoint, y);
        }
        
        handleMouseUp() {
            if (this.isDragging) {
                this.saveHistory();
                this.isDragging = false;
                this.activePoint = null;
                this.hideTooltip();
                
                this.pointsGroup.querySelectorAll('.curve-point').forEach(p => {
                    p.classList.remove('active');
                });
            }
        }
        
        handleTouchStart(e) {
            const point = e.target.closest('.curve-point');
            if (!point) return;
            
            e.preventDefault();
            this.isDragging = true;
            this.activePoint = parseInt(point.dataset.index);
            point.classList.add('active');
        }
        
        handleTouchMove(e) {
            if (!this.isDragging || this.activePoint === null) return;
            
            e.preventDefault();
            const touch = e.touches[0];
            const rect = this.svg.getBoundingClientRect();
            const y = touch.clientY - rect.top;
            
            this.updatePointFromY(this.activePoint, y);
        }
        
        handleTouchEnd() {
            this.handleMouseUp();
        }
        
        updatePointFromY(index, y) {
            const { baseValue, minMultiplier, maxMultiplier } = this.options;
            const { padding, chartHeight } = this;
            const range = maxMultiplier - minMultiplier;
            
            // Clamp y to chart bounds
            y = Math.max(padding.top, Math.min(padding.top + chartHeight, y));
            
            // Convert y to multiplier
            const multiplier = maxMultiplier - ((y - padding.top) / chartHeight * range);
            const value = baseValue * multiplier;
            
            this.values[index] = Math.max(baseValue * minMultiplier, 
                                          Math.min(baseValue * maxMultiplier, value));
            
            this.updateChart();
            this.showTooltip(index);
        }
        
        handleInputChange(e) {
            const input = e.target;
            if (!input.dataset.index) return;
            
            const index = parseInt(input.dataset.index);
            const value = parseFloat(input.value);
            
            if (!isNaN(value)) {
                const { baseValue, minMultiplier, maxMultiplier } = this.options;
                this.values[index] = Math.max(baseValue * minMultiplier, 
                                              Math.min(baseValue * maxMultiplier, value));
                this.saveHistory();
                this.updateChart();
            }
        }
        
        handlePresetChange(e) {
            const preset = e.target.value;
            if (!preset || !PRESETS[preset]) return;
            
            const pattern = PRESETS[preset]();
            this.values = pattern.map(m => this.options.baseValue * m);
            this.saveHistory();
            this.updateChart();
            
            e.target.value = '';
        }
        
        showTooltip(index) {
            const point = this.pointsGroup.querySelector(`[data-index="${index}"]`);
            if (!point) return;
            
            const x = parseFloat(point.getAttribute('cx'));
            const y = parseFloat(point.getAttribute('cy'));
            const value = this.values[index];
            
            this.tooltip.style.display = 'block';
            this.tooltip.querySelector('rect').setAttribute('x', x - 30);
            this.tooltip.querySelector('rect').setAttribute('y', y - 32);
            this.tooltip.querySelector('text').setAttribute('x', x);
            this.tooltip.querySelector('text').setAttribute('y', y - 16);
            this.tooltip.querySelector('text').textContent = 
                value.toFixed(this.options.decimals) + this.options.unit;
        }
        
        hideTooltip() {
            this.tooltip.style.display = 'none';
        }
        
        saveHistory() {
            // Remove any redo history
            this.history = this.history.slice(0, this.historyIndex + 1);
            
            // Add current state
            this.history.push(this.values.slice());
            this.historyIndex = this.history.length - 1;
            
            // Limit history
            if (this.history.length > 50) {
                this.history.shift();
                this.historyIndex--;
            }
            
            this.updateHistoryButtons();
        }
        
        undo() {
            if (this.historyIndex > 0) {
                this.historyIndex--;
                this.values = this.history[this.historyIndex].slice();
                this.updateChart();
                this.updateHistoryButtons();
            }
        }
        
        redo() {
            if (this.historyIndex < this.history.length - 1) {
                this.historyIndex++;
                this.values = this.history[this.historyIndex].slice();
                this.updateChart();
                this.updateHistoryButtons();
            }
        }
        
        reset() {
            this.values = Array(12).fill(this.options.baseValue);
            this.saveHistory();
            this.updateChart();
        }
        
        updateHistoryButtons() {
            this.undoBtn.disabled = this.historyIndex <= 0;
            this.redoBtn.disabled = this.historyIndex >= this.history.length - 1;
        }
        
        /**
         * Get current values
         */
        getValues() {
            return this.values.slice();
        }
        
        /**
         * Set values externally
         */
        setValues(values) {
            if (Array.isArray(values) && values.length === 12) {
                this.values = values.slice();
                this.saveHistory();
                this.updateChart();
            }
        }
    }
    
    // Export to global scope
    window.CurveEditor = CurveEditor;
    
    /**
     * Auto-initialize editors with data attributes
     */
    function initAutoEditors() {
        document.querySelectorAll('[data-curve-editor]').forEach(container => {
            const options = {};
            
            // Parse data attributes
            if (container.dataset.baseValue) options.baseValue = parseFloat(container.dataset.baseValue);
            if (container.dataset.unit) options.unit = container.dataset.unit;
            if (container.dataset.inputPrefix) options.inputPrefix = container.dataset.inputPrefix;
            if (container.dataset.width) options.width = parseInt(container.dataset.width);
            if (container.dataset.height) options.height = parseInt(container.dataset.height);
            if (container.dataset.minMultiplier) options.minMultiplier = parseFloat(container.dataset.minMultiplier);
            if (container.dataset.maxMultiplier) options.maxMultiplier = parseFloat(container.dataset.maxMultiplier);
            
            new CurveEditor(container, options);
        });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAutoEditors);
    } else {
        initAutoEditors();
    }
})();

