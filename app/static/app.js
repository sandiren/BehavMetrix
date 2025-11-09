const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
const themeToggle = document.getElementById('themeToggle');
const syncBadge = document.getElementById('sync-status');
const storedTheme = localStorage.getItem('behavmetrix-theme');

function applyTheme(theme) {
  document.body.setAttribute('data-bs-theme', theme);
  if (themeToggle) {
    themeToggle.checked = theme === 'dark';
  }
  localStorage.setItem('behavmetrix-theme', theme);
}

applyTheme(storedTheme || (prefersDark ? 'dark' : 'light'));

if (themeToggle) {
  themeToggle.addEventListener('change', (event) => {
    applyTheme(event.target.checked ? 'dark' : 'light');
  });
}

function updateSyncStatus() {
  const online = navigator.onLine;
  document.body.classList.toggle('offline', !online);
  if (syncBadge) {
    syncBadge.textContent = online ? 'Online' : 'Offline';
    syncBadge.classList.toggle('bg-success', online);
    syncBadge.classList.toggle('bg-danger', !online);
  }
}

window.addEventListener('online', updateSyncStatus);
window.addEventListener('offline', updateSyncStatus);
updateSyncStatus();

const behaviorForm = document.getElementById('behavior-form');
if (behaviorForm) {
  const behaviorField = document.getElementById('behavior-id');
  const animalSelect = document.getElementById('animal-select');
  const behaviorSelect = document.getElementById('behavior-select');
  if (behaviorSelect && behaviorField) {
    behaviorSelect.addEventListener('change', () => {
      behaviorField.value = behaviorSelect.value;
    });
  }
  behaviorForm.querySelectorAll('[data-behavior-id]').forEach((button) => {
    button.addEventListener('click', () => {
      if (!animalSelect || !animalSelect.selectedOptions.length) {
        animalSelect?.classList.add('is-invalid');
        setTimeout(() => animalSelect?.classList.remove('is-invalid'), 1000);
        return;
      }
      if (behaviorField) {
        behaviorField.value = button.dataset.behaviorId;
      }
      if (behaviorSelect) {
        behaviorSelect.value = button.dataset.behaviorId;
      }
      behaviorForm.submit();
    });
  });
  behaviorForm.addEventListener('submit', () => {
    if (behaviorField && !behaviorField.value && behaviorSelect) {
      behaviorField.value = behaviorSelect.value;
    }
  });
}

let enrichmentStart = null;
const enrichmentForm = document.getElementById('enrichment-form');
if (enrichmentForm) {
  const startField = enrichmentForm.querySelector('input[name="start_time"]');
  const endField = enrichmentForm.querySelector('input[name="end_time"]');
  const durationField = enrichmentForm.querySelector('input[name="duration"]');
  enrichmentForm.querySelectorAll('[data-enrichment-timer]').forEach((button) => {
    button.addEventListener('click', () => {
      const action = button.dataset.enrichmentTimer;
      if (action === 'start') {
        enrichmentStart = new Date();
        if (startField) {
          startField.value = enrichmentStart.toISOString().slice(0, 16);
        }
      }
      if (action === 'stop') {
        const end = new Date();
        if (!enrichmentStart) {
          enrichmentStart = end;
        }
        if (endField) {
          endField.value = end.toISOString().slice(0, 16);
        }
        if (durationField) {
          const diff = (end.getTime() - enrichmentStart.getTime()) / 60000;
          durationField.value = Math.max(diff, 0).toFixed(1);
        }
        enrichmentStart = null;
      }
    });
  });
}
