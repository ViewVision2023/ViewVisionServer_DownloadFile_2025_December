/**
 * SRT Gateway Forms Module
 * Handles form submissions and validations
 */

class SRTGatewayForms {
    constructor(api, ui) {
        this.api = api;
        this.ui = ui;
        this.routes = [];
    }

    /**
     * Initialize form handlers
     */
    init() {
        this.setupFormListeners();
    }

    /**
     * Setup form event listeners
     */
    setupFormListeners() {
        // Session form submission
        const sessionForm = document.getElementById('session-form');
        if (sessionForm) {
            sessionForm.addEventListener('submit', (e) => this.handleSessionSubmit(e));
        }

        // Add route button
        const addRouteBtn = document.getElementById('add-route-btn');
        if (addRouteBtn) {
            addRouteBtn.addEventListener('click', () => this.addRouteField());
        }

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => this.closeModal(e.target.closest('.modal')));
        });

        // Click outside modal to close
        window.addEventListener('click', (e) => {
            if (e.target.classList.contains('modal')) {
                this.closeModal(e.target);
            }
        });
    }

    /**
     * Handle session form submission
     */
    async handleSessionSubmit(event) {
        event.preventDefault();
        
        const form = event.target;
        const formData = new FormData(form);
        const isEdit = form.dataset.mode === 'edit';
        const rxPort = formData.get('rx_port');

        // Build session data object
        const sessionData = {
            name: formData.get('name'),
            rx_mode: formData.get('rx_mode'),
            rx_port: parseInt(rxPort),
            rx_ip: formData.get('rx_ip') || '0.0.0.0',
            latency: parseInt(formData.get('latency')) || 120,
            passphrase: formData.get('passphrase') || '',
            routes: this.collectRoutes(formData)
        };

        // Validate form data
        const validation = this.validateSessionData(sessionData);
        if (!validation.valid) {
            this.ui.showError(validation.error);
            return;
        }

        try {
            let result;
            if (isEdit) {
                result = await this.api.updateSession(rxPort, sessionData);
            } else {
                result = await this.api.createSession(sessionData);
            }

            if (result.ok) {
                this.ui.showSuccess(`Route ${isEdit ? 'updated' : 'created'} successfully`);
                this.closeModal(document.getElementById('session-modal'));
                await this.ui.loadSessions();
            } else {
                this.ui.showError(result.message || 'Failed to save route');
            }
        } catch (error) {
            this.ui.showError(`Error: ${error.message}`);
        }
    }

    /**
     * Collect routes from form data
     */
    collectRoutes(formData) {
        const routes = [];
        const routeCount = parseInt(formData.get('route_count')) || 0;

        for (let i = 0; i < routeCount; i++) {
            const route = {
                name: formData.get(`route_${i}_name`),
                tx_mode: formData.get(`route_${i}_tx_mode`),
                tx_ip: formData.get(`route_${i}_tx_ip`),
                tx_port: parseInt(formData.get(`route_${i}_tx_port`)),
                latency: parseInt(formData.get(`route_${i}_latency`)) || 120,
                passphrase: formData.get(`route_${i}_passphrase`) || '',
                fec: formData.get(`route_${i}_fec`) || 'none'
            };

            if (route.tx_ip && route.tx_port) {
                routes.push(route);
            }
        }

        return routes;
    }

    /**
     * Validate session data
     */
    validateSessionData(data) {
        if (!data.name || data.name.trim() === '') {
            return { valid: false, error: 'Route name is required' };
        }

        if (!data.rx_port || data.rx_port < 1 || data.rx_port > 65535) {
            return { valid: false, error: 'Invalid RX port (must be 1-65535)' };
        }

        if (!data.rx_mode || !['listener', 'caller'].includes(data.rx_mode)) {
            return { valid: false, error: 'Invalid RX mode' };
        }

        if (data.routes.length === 0) {
            return { valid: false, error: 'At least one destination route is required' };
        }

        // Validate each route
        for (let i = 0; i < data.routes.length; i++) {
            const route = data.routes[i];
            
            if (!route.tx_ip || !this.isValidIP(route.tx_ip)) {
                return { valid: false, error: `Invalid IP address in destination ${i + 1}` };
            }

            if (!route.tx_port || route.tx_port < 1 || route.tx_port > 65535) {
                return { valid: false, error: `Invalid port in destination ${i + 1}` };
            }

            if (!route.tx_mode || !['listener', 'caller'].includes(route.tx_mode)) {
                return { valid: false, error: `Invalid mode in destination ${i + 1}` };
            }
        }

        return { valid: true };
    }

    /**
     * Validate IP address
     */
    isValidIP(ip) {
        const ipPattern = /^(\d{1,3}\.){3}\d{1,3}$/;
        if (!ipPattern.test(ip)) return false;

        const parts = ip.split('.');
        return parts.every(part => {
            const num = parseInt(part);
            return num >= 0 && num <= 255;
        });
    }

    /**
     * Add a new route field to the form
     */
    addRouteField() {
        const routesContainer = document.getElementById('routes-container');
        if (!routesContainer) return;

        const index = this.routes.length;
        const routeField = document.createElement('div');
        routeField.className = 'route-field';
        routeField.dataset.index = index;
        
        routeField.innerHTML = `
            <div class="route-field-header">
                <h4>Destination ${index + 1}</h4>
                <button type="button" class="btn-icon btn-danger" onclick="forms.removeRouteField(${index})">
                    🗑
                </button>
            </div>
            <div class="form-grid">
                <div class="form-group">
                    <label>Destination Name</label>
                    <input type="text" name="route_${index}_name" placeholder="e.g., Primary Output" required>
                </div>
                <div class="form-group">
                    <label>Mode</label>
                    <select name="route_${index}_tx_mode" required>
                        <option value="caller">Caller</option>
                        <option value="listener">Listener</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>IP Address</label>
                    <input type="text" name="route_${index}_tx_ip" placeholder="192.168.1.100" required>
                </div>
                <div class="form-group">
                    <label>Port</label>
                    <input type="number" name="route_${index}_tx_port" min="1" max="65535" placeholder="9000" required>
                </div>
                <div class="form-group">
                    <label>Latency (ms)</label>
                    <input type="number" name="route_${index}_latency" value="120" min="0" max="8000">
                </div>
                <div class="form-group">
                    <label>FEC</label>
                    <select name="route_${index}_fec">
                        <option value="none">None</option>
                        <option value="fec">FEC</option>
                    </select>
                </div>
                <div class="form-group form-group-full">
                    <label>Passphrase (optional)</label>
                    <input type="password" name="route_${index}_passphrase" placeholder="Leave empty for no encryption">
                </div>
            </div>
        `;

        routesContainer.appendChild(routeField);
        this.routes.push(routeField);
        
        // Update route count
        this.updateRouteCount();
    }

    /**
     * Remove a route field
     */
    removeRouteField(index) {
        const routeField = document.querySelector(`.route-field[data-index="${index}"]`);
        if (routeField) {
            routeField.remove();
            this.routes = this.routes.filter((_, i) => i !== index);
            this.updateRouteCount();
            this.renumberRouteFields();
        }
    }

    /**
     * Update route count hidden field
     */
    updateRouteCount() {
        const countInput = document.getElementById('route-count');
        if (countInput) {
            countInput.value = this.routes.length;
        }
    }

    /**
     * Renumber route fields after deletion
     */
    renumberRouteFields() {
        const routeFields = document.querySelectorAll('.route-field');
        routeFields.forEach((field, newIndex) => {
            field.dataset.index = newIndex;
            
            // Update header
            const header = field.querySelector('.route-field-header h4');
            if (header) {
                header.textContent = `Destination ${newIndex + 1}`;
            }

            // Update all input names
            const inputs = field.querySelectorAll('input, select');
            inputs.forEach(input => {
                const name = input.getAttribute('name');
                if (name) {
                    const newName = name.replace(/route_\d+_/, `route_${newIndex}_`);
                    input.setAttribute('name', newName);
                }
            });

            // Update delete button
            const deleteBtn = field.querySelector('.btn-danger');
            if (deleteBtn) {
                deleteBtn.setAttribute('onclick', `forms.removeRouteField(${newIndex})`);
            }
        });

        this.routes = Array.from(routeFields);
    }

    /**
     * Populate form with session data (for editing)
     */
    populateForm(session) {
        const form = document.getElementById('session-form');
        if (!form) return;

        form.dataset.mode = 'edit';
        form.dataset.rxPort = session.rx_port;

        // Populate basic fields
        const fields = ['name', 'rx_mode', 'rx_port', 'rx_ip', 'latency', 'passphrase'];
        fields.forEach(field => {
            const input = form.elements[field];
            if (input && session[field] !== undefined) {
                input.value = session[field];
            }
        });

        // Clear existing routes
        const routesContainer = document.getElementById('routes-container');
        if (routesContainer) {
            routesContainer.innerHTML = '';
            this.routes = [];
        }

        // Add routes
        if (session.routes && session.routes.length > 0) {
            session.routes.forEach((route, index) => {
                this.addRouteField();
                
                // Populate route fields
                Object.keys(route).forEach(key => {
                    const input = form.elements[`route_${index}_${key}`];
                    if (input) {
                        input.value = route[key];
                    }
                });
            });
        }
    }

    /**
     * Reset form to create mode
     */
    resetForm() {
        const form = document.getElementById('session-form');
        if (form) {
            form.dataset.mode = 'create';
            delete form.dataset.rxPort;
            form.reset();
            
            const routesContainer = document.getElementById('routes-container');
            if (routesContainer) {
                routesContainer.innerHTML = '';
                this.routes = [];
            }
        }
    }

    /**
     * Close modal
     */
    closeModal(modal) {
        if (modal) {
            modal.style.display = 'none';
            this.resetForm();
        }
    }

    /**
     * Open session modal for create
     */
    openCreateModal() {
        this.resetForm();
        const modal = document.getElementById('session-modal');
        const title = document.getElementById('modal-title');
        
        if (title) {
            title.textContent = 'Create New Route';
        }
        
        if (modal) {
            modal.style.display = 'block';
        }

        // Add initial route field
        if (this.routes.length === 0) {
            this.addRouteField();
        }
    }

    /**
     * Open session modal for edit
     */
    async openEditModal(rxPort) {
        try {
            const data = await this.api.getSession(rxPort);
            
            if (data.ok) {
                this.populateForm(data.session);
                
                const modal = document.getElementById('session-modal');
                const title = document.getElementById('modal-title');
                
                if (title) {
                    title.textContent = 'Edit Route';
                }
                
                if (modal) {
                    modal.style.display = 'block';
                }
            }
        } catch (error) {
            this.ui.showError(`Failed to load session: ${error.message}`);
        }
    }
}

// Initialize forms when DOM is ready
let forms;
document.addEventListener('DOMContentLoaded', () => {
    forms = new SRTGatewayForms(api, ui);
    forms.init();
});
