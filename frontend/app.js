// YouTube AI Analysis Suite - Frontend
// Mit Abbrechen, Löschen und KI-Chat Funktionen

const API_BASE_URL = 'http://192.168.178.40:8000/api';
let currentJobId = null;

// API-Status prüfen
async function checkApiStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/gesundheit`);
        const data = await response.json();
        document.getElementById('api-status').textContent = `✅ API verbunden: ${data.dienst}`;
        document.getElementById('api-status').style.color = '#10b981';
    } catch (error) {
        document.getElementById('api-status').textContent = '❌ API nicht erreichbar';
        document.getElementById('api-status').style.color = '#ef4444';
    }
}

// Jobs laden
async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE_URL}/jobs/?limit=50`);
        const jobs = await response.json();
        displayJobs(jobs);
        updateStats(jobs);
    } catch (error) {
        document.getElementById('jobs-container').innerHTML = 
            '<div class="error">Fehler beim Laden der Jobs</div>';
    }
}

// Jobs anzeigen
function displayJobs(jobs) {
    const container = document.getElementById('jobs-container');
    
    if (!jobs || jobs.length === 0) {
        container.innerHTML = '<div class="no-jobs">Keine Jobs vorhanden</div>';
        return;
    }
    
    let html = '<div class="jobs-grid">';
    jobs.forEach(job => {
        const progress = job.fortschritt || 0;
        const statusClass = `status-${job.status}`;
        
        html += `
            <div class="job-card" data-job-id="${job.id}">
                <div class="job-header">
                    <span class="job-id" title="${job.id}">${job.id.substring(0,8)}...</span>
                    <span class="job-status ${statusClass}">${job.status}</span>
                </div>
                <div class="job-url" title="${job.url}">${job.url.substring(0,50)}${job.url.length > 50 ? '...' : ''}</div>
                <div class="job-progress">
                    <div class="progress-bar" style="width: ${progress}%"></div>
                    <span class="progress-text">${progress}%</span>
                </div>
                <div class="job-actions">
                    ${job.status === 'warteschlange' || job.status === 'herunterladen' || job.status === 'verarbeitung' || job.status === 'transkription' || job.status === 'zusammenfassung' ? 
                        `<button class="cancel-btn" onclick="cancelJob('${job.id}')">⏹️ Abbrechen</button>` : ''}
                    <button class="delete-btn" onclick="deleteJob('${job.id}')">🗑️ Löschen</button>
                    ${job.status === 'abgeschlossen' ? 
                        `<button class="chat-btn" onclick="openChat('${job.id}')">💬 KI-Chat</button>` : ''}
                    ${job.status === 'abgeschlossen' ? 
                        `<button class="details-btn" onclick="viewDetails('${job.id}')">📄 Details</button>` : ''}
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    // Batch-Löschen Button für fehlerhafte/abgebrochene Jobs
    const hasFailedOrCancelled = jobs.some(job => job.status === 'fehler' || job.status === 'abgebrochen');
    if (hasFailedOrCancelled) {
        html += '<div style="margin-top: 20px; text-align: right;">';
        html += '<button class="batch-delete-btn" onclick="batchDeleteFailed()">🗑️ Alle fehlerhaften/abgebrochenen Jobs löschen</button>';
        html += '</div>';
    }
    
    container.innerHTML = html;
}

// Statistiken aktualisieren
function updateStats(jobs) {
    const stats = {
        total: jobs.length,
        waiting: jobs.filter(j => j.status === 'warteschlange').length,
        active: jobs.filter(j => ['herunterladen', 'verarbeitung', 'transkription', 'zusammenfassung'].includes(j.status)).length,
        completed: jobs.filter(j => j.status === 'abgeschlossen').length,
        failed: jobs.filter(j => j.status === 'fehler').length,
        cancelled: jobs.filter(j => j.status === 'abgebrochen').length
    };
    
    let statsHtml = `
        <div class="stats-grid">
            <div class="stat-card">📊 Gesamt: ${stats.total}</div>
            <div class="stat-card">⏳ Wartend: ${stats.waiting}</div>
            <div class="stat-card">⚙️ Aktiv: ${stats.active}</div>
            <div class="stat-card">✅ Fertig: ${stats.completed}</div>
            <div class="stat-card">❌ Fehler: ${stats.failed}</div>
            <div class="stat-card">⏹️ Abgebrochen: ${stats.cancelled}</div>
        </div>
    `;
    
    const statsContainer = document.getElementById('stats-container');
    if (statsContainer) statsContainer.innerHTML = statsHtml;
}

// Job abbrechen
async function cancelJob(jobId) {
    if (!confirm('Möchtest du diesen Job wirklich abbrechen?')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}/abbrechen`, {
            method: 'POST'
        });
        
        if (response.ok) {
            showMessage('Job wird abgebrochen...', 'success');
            loadJobs(); // Reload nach kurzer Zeit
        } else {
            showError('Fehler beim Abbrechen des Jobs');
        }
    } catch (error) {
        showError('Fehler beim Abbrechen des Jobs');
    }
}

// Job löschen
async function deleteJob(jobId) {
    if (!confirm('Möchtest du diesen Job wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden!')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/jobs/${jobId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showMessage('Job gelöscht', 'success');
            loadJobs();
        } else {
            showError('Fehler beim Löschen des Jobs');
        }
    } catch (error) {
        showError('Fehler beim Löschen des Jobs');
    }
}

// Batch-Löschen aller fehlerhaften/abgebrochenen Jobs
async function batchDeleteFailed() {
    if (!confirm('Alle fehlerhaften und abgebrochenen Jobs löschen?')) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/jobs/batch/abgebrochen`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showMessage('Fehlerhafte Jobs gelöscht', 'success');
            loadJobs();
        } else {
            showError('Fehler beim Löschen');
        }
    } catch (error) {
        showError('Fehler beim Löschen');
    }
}

// KI-Chat öffnen
function openChat(jobId) {
    currentJobId = jobId;
    document.getElementById('chat-modal').style.display = 'block';
    document.getElementById('chat-job-id').textContent = `Job: ${jobId.substring(0,8)}...`;
    loadChatHistory(jobId);
}

// Chat schließen
function closeChat() {
    document.getElementById('chat-modal').style.display = 'none';
    document.getElementById('chat-messages').innerHTML = '';
    document.getElementById('chat-input').value = '';
}

// Chat-Nachricht senden
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message || !currentJobId) return;
    
    // Nachricht im Chat anzeigen
    addChatMessage('user', message);
    input.value = '';
    
    try {
        const response = await fetch(`${API_BASE_URL}/chat/${currentJobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nachricht: message })
        });
        
        const data = await response.json();
        addChatMessage('assistant', data.antwort || 'Keine Antwort erhalten');
    } catch (error) {
        addChatMessage('assistant', 'Fehler bei der KI-Antwort');
    }
}

// Chat-Verlauf laden
async function loadChatHistory(jobId) {
    try {
        // Hier müsste ein Endpunkt für Chat-Verlauf existieren
        // Für jetzt fügen wir nur eine Begrüßung hinzu
        addChatMessage('assistant', '👋 Hallo! Ich bin der KI-Assistent für dieses Video. Was möchtest du wissen?');
    } catch (error) {
        console.error('Fehler beim Laden des Chat-Verlaufs');
    }
}

// Chat-Verlauf löschen
async function clearChatHistory() {
    if (!confirm('Chat-Verlauf löschen?')) return;
    
    try {
        await fetch(`${API_BASE_URL}/chat/${currentJobId}/verlauf`, {
            method: 'DELETE'
        });
        document.getElementById('chat-messages').innerHTML = '';
        addChatMessage('assistant', '👋 Chat-Verlauf gelöscht. Stelle mir eine neue Frage!');
    } catch (error) {
        showError('Fehler beim Löschen des Chat-Verlaufs');
    }
}

// Nachricht zum Chat hinzufügen
function addChatMessage(role, content) {
    const messagesDiv = document.getElementById('chat-messages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}-message`;
    messageDiv.textContent = content;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Details anzeigen (einfache Version)
function viewDetails(jobId) {
    window.open(`${API_BASE_URL}/export/${jobId}/json`, '_blank');
}

// Neuen Job erstellen
document.getElementById('job-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const url = document.getElementById('video-url').value;
    const options = {
        whisper_modell: document.getElementById('whisper-model').value,
        zusammenfassung_erstellen: document.getElementById('summary-check').checked,
        kapitel_erkennen: document.getElementById('chapters-check').checked,
        podcast_erstellen: document.getElementById('podcast-check')?.checked || false,
        zusammenfassung_stil: document.getElementById('summary-style').value
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}/jobs/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, optionen: options })
        });
        
        if (response.ok) {
            document.getElementById('video-url').value = '';
            showMessage('Job erfolgreich erstellt!', 'success');
            loadJobs();
        } else {
            const error = await response.text();
            showError('Fehler beim Erstellen: ' + error);
        }
    } catch (error) {
        showError('Fehler beim Erstellen des Jobs');
    }
});

// Hilfsfunktionen
function showError(message) {
    const errorDiv = document.getElementById('error-message');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => { errorDiv.style.display = 'none'; }, 5000);
}

function showMessage(message, type) {
    const messageDiv = document.getElementById('success-message');
    messageDiv.textContent = message;
    messageDiv.style.display = 'block';
    messageDiv.className = `message ${type}-message`;
    setTimeout(() => { messageDiv.style.display = 'none'; }, 3000);
}

// Initialisierung
document.addEventListener('DOMContentLoaded', () => {
    checkApiStatus();
    loadJobs();
    setInterval(loadJobs, 5000); // Auto-Refresh alle 5 Sekunden
    
    // Enter-Taste im Chat
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            sendChatMessage();
        }
    });
});
