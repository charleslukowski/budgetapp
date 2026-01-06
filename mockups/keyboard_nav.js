/**
 * Keyboard Navigation for Fuel Forecast Workflow
 * 
 * Features:
 * - Tab through inputs (native HTML)
 * - Enter to submit forms
 * - Ctrl/Cmd+Enter to save from anywhere
 * - Escape to close modals/dialogs
 * - Arrow keys to navigate option cards
 * - Visible focus indicators
 */

(function() {
    'use strict';
    
    // =============================================================================
    // Configuration
    // =============================================================================
    
    const CONFIG = {
        // Selectors
        formSelector: 'form',
        optionCardSelector: '.option-card',
        modalSelector: '.modal, [role="dialog"]',
        submitBtnSelector: '.btn-primary[type="submit"], .btn-success[type="submit"]',
        saveBtnSelector: 'button[name="action"][value="save"]',
        cancelBtnSelector: '.btn-secondary',
        inputSelector: 'input, select, textarea',
        
        // Classes
        focusVisibleClass: 'focus-visible',
    };
    
    // =============================================================================
    // Focus Management
    // =============================================================================
    
    /**
     * Add focus-visible polyfill for browsers that don't support it
     */
    function initFocusVisible() {
        let hadKeyboardEvent = false;
        
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                hadKeyboardEvent = true;
            }
        });
        
        document.addEventListener('mousedown', () => {
            hadKeyboardEvent = false;
        });
        
        document.addEventListener('focusin', (e) => {
            if (hadKeyboardEvent && e.target.matches('a, button, input, select, textarea, [tabindex]')) {
                e.target.classList.add(CONFIG.focusVisibleClass);
            }
        });
        
        document.addEventListener('focusout', (e) => {
            e.target.classList.remove(CONFIG.focusVisibleClass);
        });
    }
    
    // =============================================================================
    // Form Submission Shortcuts
    // =============================================================================
    
    /**
     * Handle Ctrl/Cmd+Enter to save from anywhere
     */
    function handleSaveShortcut(e) {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            
            // Find save button first, then submit button
            const saveBtn = document.querySelector(CONFIG.saveBtnSelector);
            if (saveBtn && !saveBtn.disabled) {
                saveBtn.click();
                return;
            }
            
            const submitBtn = document.querySelector(CONFIG.submitBtnSelector);
            if (submitBtn && !submitBtn.disabled) {
                submitBtn.click();
            }
        }
    }
    
    /**
     * Handle Enter key on inputs to move to next or submit
     */
    function handleInputEnter(e) {
        if (e.key !== 'Enter' || e.ctrlKey || e.metaKey || e.shiftKey) {
            return;
        }
        
        const target = e.target;
        
        // Don't interfere with textareas (allow newlines)
        if (target.tagName === 'TEXTAREA') {
            return;
        }
        
        // For inputs, either move to next or submit
        if (target.tagName === 'INPUT') {
            e.preventDefault();
            
            // Find all focusable inputs in the form
            const form = target.closest('form');
            if (!form) return;
            
            const inputs = Array.from(form.querySelectorAll(CONFIG.inputSelector + ':not([type="hidden"])'));
            const currentIndex = inputs.indexOf(target);
            
            // If last input, submit the form
            if (currentIndex === inputs.length - 1) {
                const submitBtn = form.querySelector(CONFIG.submitBtnSelector);
                if (submitBtn && !submitBtn.disabled) {
                    submitBtn.click();
                }
            } else {
                // Move to next input
                const nextInput = inputs[currentIndex + 1];
                if (nextInput) {
                    nextInput.focus();
                    if (nextInput.type === 'text' || nextInput.type === 'number') {
                        nextInput.select();
                    }
                }
            }
        }
    }
    
    // =============================================================================
    // Modal/Dialog Handling
    // =============================================================================
    
    /**
     * Handle Escape to close modals
     */
    function handleEscape(e) {
        if (e.key !== 'Escape') return;
        
        // Close any open modals
        const openModal = document.querySelector(CONFIG.modalSelector + '.open, ' + CONFIG.modalSelector + ':not([hidden])');
        if (openModal) {
            e.preventDefault();
            
            // Look for close button
            const closeBtn = openModal.querySelector('.modal-close, [data-dismiss="modal"], .btn-close');
            if (closeBtn) {
                closeBtn.click();
            } else {
                // Hide directly
                openModal.classList.remove('open');
                openModal.hidden = true;
            }
            return;
        }
        
        // Close any open details/collapsible sections
        const openDetails = document.querySelector('details[open]');
        if (openDetails && document.activeElement && openDetails.contains(document.activeElement)) {
            openDetails.open = false;
        }
    }
    
    // =============================================================================
    // Option Card Navigation
    // =============================================================================
    
    /**
     * Handle arrow key navigation for option cards
     */
    function handleOptionCardNavigation(e) {
        if (!['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
            return;
        }
        
        const activeElement = document.activeElement;
        const optionCard = activeElement.closest(CONFIG.optionCardSelector);
        
        if (!optionCard) return;
        
        e.preventDefault();
        
        const group = optionCard.closest('.option-group');
        if (!group) return;
        
        const cards = Array.from(group.querySelectorAll(CONFIG.optionCardSelector));
        const currentIndex = cards.indexOf(optionCard);
        
        let newIndex;
        if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') {
            newIndex = currentIndex > 0 ? currentIndex - 1 : cards.length - 1;
        } else {
            newIndex = currentIndex < cards.length - 1 ? currentIndex + 1 : 0;
        }
        
        const newCard = cards[newIndex];
        const radio = newCard.querySelector('input[type="radio"]');
        
        if (radio) {
            radio.focus();
            radio.checked = true;
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            newCard.focus();
        }
    }
    
    /**
     * Handle Space/Enter on option cards to select
     */
    function handleOptionCardSelect(e) {
        if (e.key !== ' ' && e.key !== 'Enter') return;
        
        const optionCard = e.target.closest(CONFIG.optionCardSelector);
        if (!optionCard) return;
        
        // Don't interfere if focus is on the radio itself
        if (e.target.type === 'radio') return;
        
        e.preventDefault();
        
        const radio = optionCard.querySelector('input[type="radio"]');
        if (radio) {
            radio.checked = true;
            radio.dispatchEvent(new Event('change', { bubbles: true }));
        }
        
        optionCard.click();
    }
    
    // =============================================================================
    // Skip Links for Accessibility
    // =============================================================================
    
    /**
     * Create skip links for keyboard users
     */
    function createSkipLinks() {
        const skipLink = document.createElement('a');
        skipLink.href = '#main-content';
        skipLink.className = 'skip-link';
        skipLink.textContent = 'Skip to main content';
        skipLink.style.cssText = `
            position: fixed;
            top: -100px;
            left: 16px;
            z-index: 10000;
            padding: 12px 24px;
            background: #1e3a5f;
            color: white;
            text-decoration: none;
            border-radius: 0 0 8px 8px;
            transition: top 0.2s ease;
        `;
        
        skipLink.addEventListener('focus', () => {
            skipLink.style.top = '0';
        });
        
        skipLink.addEventListener('blur', () => {
            skipLink.style.top = '-100px';
        });
        
        document.body.insertBefore(skipLink, document.body.firstChild);
        
        // Add id to main content area
        const mainContent = document.querySelector('.step-content, .main-content, main');
        if (mainContent && !mainContent.id) {
            mainContent.id = 'main-content';
        }
    }
    
    // =============================================================================
    // Keyboard Shortcuts Help
    // =============================================================================
    
    /**
     * Show keyboard shortcuts on ? key
     */
    function handleShowShortcuts(e) {
        if (e.key !== '?' || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }
        
        // Check if help modal already exists
        let helpModal = document.getElementById('keyboard-shortcuts-modal');
        
        if (!helpModal) {
            helpModal = document.createElement('div');
            helpModal.id = 'keyboard-shortcuts-modal';
            helpModal.className = 'modal';
            helpModal.setAttribute('role', 'dialog');
            helpModal.setAttribute('aria-label', 'Keyboard Shortcuts');
            helpModal.innerHTML = `
                <div class="modal-backdrop" onclick="this.parentElement.hidden = true"></div>
                <div class="modal-content" style="
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: white;
                    padding: 24px;
                    border-radius: 12px;
                    box-shadow: 0 20px 50px rgba(0,0,0,0.3);
                    z-index: 10001;
                    max-width: 400px;
                    width: 90%;
                ">
                    <h3 style="margin: 0 0 16px 0; font-size: 18px;">Keyboard Shortcuts</h3>
                    <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
                        <tr><td style="padding: 8px 0;"><kbd>Tab</kbd></td><td>Move to next field</td></tr>
                        <tr><td style="padding: 8px 0;"><kbd>Shift</kbd> + <kbd>Tab</kbd></td><td>Move to previous field</td></tr>
                        <tr><td style="padding: 8px 0;"><kbd>Enter</kbd></td><td>Next field or submit</td></tr>
                        <tr><td style="padding: 8px 0;"><kbd>Ctrl</kbd> + <kbd>Enter</kbd></td><td>Save/Submit form</td></tr>
                        <tr><td style="padding: 8px 0;"><kbd>↑</kbd> <kbd>↓</kbd></td><td>Navigate options</td></tr>
                        <tr><td style="padding: 8px 0;"><kbd>Esc</kbd></td><td>Close modal</td></tr>
                        <tr><td style="padding: 8px 0;"><kbd>?</kbd></td><td>Show this help</td></tr>
                    </table>
                    <button onclick="this.closest('.modal').hidden = true" style="
                        margin-top: 16px;
                        padding: 8px 16px;
                        background: #2563eb;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        cursor: pointer;
                        width: 100%;
                    ">Close</button>
                </div>
                <style>
                    #keyboard-shortcuts-modal kbd {
                        background: #f3f4f6;
                        padding: 2px 6px;
                        border-radius: 4px;
                        border: 1px solid #d1d5db;
                        font-family: monospace;
                        font-size: 12px;
                    }
                    #keyboard-shortcuts-modal .modal-backdrop {
                        position: fixed;
                        inset: 0;
                        background: rgba(0,0,0,0.5);
                        z-index: 10000;
                    }
                </style>
            `;
            document.body.appendChild(helpModal);
        }
        
        helpModal.hidden = !helpModal.hidden;
    }
    
    // =============================================================================
    // Initialization
    // =============================================================================
    
    function init() {
        // Focus visible polyfill
        initFocusVisible();
        
        // Skip links
        createSkipLinks();
        
        // Global keyboard handlers
        document.addEventListener('keydown', handleSaveShortcut);
        document.addEventListener('keydown', handleEscape);
        document.addEventListener('keydown', handleShowShortcuts);
        
        // Input-specific handlers
        document.addEventListener('keydown', handleInputEnter);
        
        // Option card navigation
        document.addEventListener('keydown', handleOptionCardNavigation);
        document.addEventListener('keydown', handleOptionCardSelect);
        
        console.log('Keyboard navigation initialized. Press ? for help.');
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

