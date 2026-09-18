async function sendLead(form, messageEl, source, propertyId) {
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    data.source = source;
    if (propertyId) {
        data.property_id = propertyId;
    }

    try {
        const response = await fetch('/api/consultation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();

        if (result.status === 'success') {
            messageEl.innerHTML = `<div class="alert alert-success">${result.message}</div>`;
            form.reset();
        } else {
            messageEl.innerHTML = `<div class="alert alert-danger">${result.message}</div>`;
        }
    } catch (error) {
        messageEl.innerHTML = '<div class="alert alert-danger">Ошибка соединения. Попробуйте позже.</div>';
        console.error('Ошибка отправки:', error);
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const consultationForm = document.getElementById('consultationForm');
    if (consultationForm) {
        consultationForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const messageEl = document.getElementById('consultationMessage');
            sendLead(this, messageEl, 'main');
        });
    }

    const callbackForm = document.getElementById('callbackForm');
    if (callbackForm) {
        callbackForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const messageEl = document.getElementById('callbackMessage');
            const propertyId = this.getAttribute('data-property-id');
            sendLead(this, messageEl, 'property', propertyId);
        });
    }

    const catalogForm = document.getElementById('catalogForm');
    if (catalogForm) {
        catalogForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const messageEl = document.getElementById('catalogMessage');
            sendLead(this, messageEl, 'catalog');
        });
    }
});