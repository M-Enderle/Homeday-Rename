// Constants
const FLOOR_TYPES = ["Keller", "EG", "1. OG", "2. OG", "3. OG"];

// State
let currentState = {
  drives: [],
  folders: [],
  brackets: [],
  previews: [],
  types: [],
  floorTypes: [],
  externalTypes: [],
  rooms: [],
  selectedDrive: null,
  selectedFolder: null,
  classifications: {}
};

// DOM Elements
const driveSelect = document.getElementById('drive-select');
const folderSelect = document.getElementById('folder-select');
const loadBracketsBtn = document.getElementById('load-brackets-btn');
const stepSelection = document.getElementById('step-selection');
const stepClassification = document.getElementById('step-classification');
const loadingState = document.getElementById('loading-state');
const errorState = document.getElementById('error-state');
const successState = document.getElementById('success-state');
const imageGrid = document.getElementById('image-grid');
const backBtn = document.getElementById('back-btn');
const applyBtn = document.getElementById('apply-btn');
const errorDismissBtn = document.getElementById('error-dismiss-btn');
const successRestartBtn = document.getElementById('success-restart-btn');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  await initializeApp();
  setupEventListeners();
});

async function initializeApp() {
  try {
    showLoading(true);
    await Promise.all([
      loadDrives(),
      loadTypes(),
      loadRooms()
    ]);
    showLoading(false);
  } catch (error) {
    showError(`Failed to initialize: ${error.message}`);
  }
}

async function loadDrives() {
  try {
    const response = await fetch('/api/drives');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    currentState.drives = data.drives;
    populateDrivesSelect();
  } catch (error) {
    console.error('Error loading drives:', error);
    throw error;
  }
}

async function loadTypes() {
  try {
    const response = await fetch('/api/types');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    currentState.types = data.types;
    currentState.floorTypes = data.floor_types;
    currentState.externalTypes = data.external_types;
  } catch (error) {
    console.error('Error loading types:', error);
    throw error;
  }
}

async function loadRooms() {
  try {
    const response = await fetch('/api/rooms');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    currentState.rooms = data.rooms;
  } catch (error) {
    console.error('Error loading rooms:', error);
    throw error;
  }
}

function populateDrivesSelect() {
  driveSelect.innerHTML = '<option value="">-- Wählen Sie ein Laufwerk --</option>';
  currentState.drives.forEach(drive => {
    const option = document.createElement('option');
    option.value = drive;
    option.textContent = drive;
    driveSelect.appendChild(option);
  });
}

function setupEventListeners() {
  driveSelect.addEventListener('change', onDriveChange);
  folderSelect.addEventListener('change', onFolderChange);
  loadBracketsBtn.addEventListener('click', onLoadBrackets);
  backBtn.addEventListener('click', onBack);
  applyBtn.addEventListener('click', onApply);
  errorDismissBtn.addEventListener('click', dismissError);
  successRestartBtn.addEventListener('click', restartApp);
}

async function onDriveChange() {
  const drive = driveSelect.value;
  currentState.selectedDrive = drive;
  currentState.selectedFolder = null;
  folderSelect.value = '';
  
  if (!drive) {
    folderSelect.disabled = true;
    folderSelect.innerHTML = '<option value="">-- Wählen Sie erst ein Laufwerk --</option>';
    loadBracketsBtn.disabled = true;
    return;
  }

  try {
    showLoading(true);
    const response = await fetch('/api/folders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ drive })
    });
    
    if (!response.ok) {
      throw new Error('Keine Ordner mit .ARW-Dateien gefunden');
    }
    
    const data = await response.json();
    currentState.folders = data.folders;
    populateFoldersSelect();
    folderSelect.disabled = false;
    showLoading(false);
  } catch (error) {
    showLoading(false);
    showError(`Fehler beim Laden von Ordnern: ${error.message}`);
    folderSelect.disabled = true;
    folderSelect.innerHTML = '<option value="">Fehler beim Laden von Ordnern</option>';
  }
}

function populateFoldersSelect() {
  folderSelect.innerHTML = '<option value="">-- Wählen Sie einen Ordner --</option>';
  currentState.folders.forEach(folder => {
    const option = document.createElement('option');
    option.value = folder;
    option.textContent = folder.split('/').pop() || folder;
    folderSelect.appendChild(option);
  });
}

function onFolderChange() {
  const folder = folderSelect.value;
  currentState.selectedFolder = folder;
  loadBracketsBtn.disabled = !folder;
}

async function onLoadBrackets() {
  const folder = currentState.selectedFolder;
  if (!folder) {
    showError('Bitte wählen Sie einen Ordner aus');
    return;
  }

  try {
    showLoading(true);
    
    // Get brackets
    const bracketsStartTime = performance.now();
    const bracketsResponse = await fetch('/api/brackets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder })
    });
    const bracketsDuration = performance.now() - bracketsStartTime;
    
    if (!bracketsResponse.ok) {
      const error = await bracketsResponse.json();
      throw new Error(error.detail || 'Fehler beim Laden der Bildergruppen');
    }
    
    const bracketsData = await bracketsResponse.json();
    currentState.brackets = bracketsData.brackets;
    console.log(`⏱️ Brackets loaded in ${(bracketsDuration / 1000).toFixed(2)}s`);
    
    // Get previews - notify progress system of image count
    const previewsStartTime = performance.now();
    const previewsResponse = await fetch('/api/previews', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        folder,
        brackets: currentState.brackets
      })
    });
    const previewsDuration = performance.now() - previewsStartTime;
    
    if (!previewsResponse.ok) {
      throw new Error('Fehler beim Laden der Vorschaubilder');
    }
    
    const previewsData = await previewsResponse.json();
    currentState.previews = previewsData.previews;
    console.log(`⏱️ Previews loaded in ${(previewsDuration / 1000).toFixed(2)}s (${(previewsDuration / currentState.previews.length).toFixed(0)}ms per image)`);
    
    showLoading(false);
    displayClassificationUI();
  } catch (error) {
    showLoading(false);
    showError(`Fehler beim Laden der Bilder: ${error.message}`);
  }
}

function displayClassificationUI() {
  stepSelection.style.display = 'none';
  stepClassification.style.display = 'block';
  
  // Initialize classifications
  currentState.classifications = {};
  currentState.types.forEach(type => {
    currentState.classifications[type] = [];
  });
  
  // Build image grid
  imageGrid.innerHTML = '';
  currentState.brackets.forEach((bracket, idx) => {
    const card = createImageCard(idx, bracket);
    imageGrid.appendChild(card);
  });
}

function createImageCard(idx, bracket) {
  const card = document.createElement('div');
  card.className = 'card';
  
  const imageDiv = document.createElement('div');
  imageDiv.className = 'image';
  const img = document.createElement('img');
  img.src = currentState.previews[idx];
  img.alt = `Image ${idx + 1}`;
  imageDiv.appendChild(img);
  card.appendChild(imageDiv);
  
  const controlsDiv = document.createElement('div');
  controlsDiv.className = 'card-controls';
  
  // Copy button (not for first image)
  if (idx > 0) {
    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.textContent = 'Kopieren';
    copyBtn.addEventListener('click', () => copyFromPrevious(idx));
    controlsDiv.appendChild(copyBtn);
  }
  
  // Type selector
  const typeField = document.createElement('div');
  typeField.className = 'card-field';
  const typeLabel = document.createElement('label');
  typeLabel.textContent = 'Typ';
  const typeSelect = document.createElement('select');
  typeSelect.id = `type-${idx}`;
  typeSelect.innerHTML = '<option value="">-- Wählen Sie einen Typ --</option>';
  currentState.types.forEach(type => {
    const option = document.createElement('option');
    option.value = type;
    option.textContent = type;
    typeSelect.appendChild(option);
  });
  typeSelect.addEventListener('change', (e) => onTypeChange(idx, e.target.value));
  typeField.appendChild(typeLabel);
  typeField.appendChild(typeSelect);
  controlsDiv.appendChild(typeField);
  
  // Room selector (initially hidden)
  const roomField = document.createElement('div');
  roomField.className = 'card-field';
  roomField.id = `room-field-${idx}`;
  roomField.style.display = 'none';
  const roomLabel = document.createElement('label');
  roomLabel.textContent = 'Raum';
  const roomSelect = document.createElement('select');
  roomSelect.id = `room-${idx}`;
  roomSelect.innerHTML = '<option value="">-- Wählen Sie einen Raum --</option>';
  currentState.rooms.forEach(room => {
    const option = document.createElement('option');
    option.value = room;
    option.textContent = room;
    roomSelect.appendChild(option);
  });
  roomSelect.addEventListener('change', (e) => onRoomChange(idx, e.target.value));
  roomField.appendChild(roomLabel);
  roomField.appendChild(roomSelect);
  controlsDiv.appendChild(roomField);
  
  // Custom room input (initially hidden)
  const customField = document.createElement('div');
  customField.className = 'card-field';
  customField.id = `custom-field-${idx}`;
  customField.style.display = 'none';
  const customLabel = document.createElement('label');
  customLabel.textContent = 'Benutzerdefinierter Raum';
  const customInput = document.createElement('input');
  customInput.type = 'text';
  customInput.id = `custom-${idx}`;
  customInput.placeholder = 'Geben Sie den Raumnamen ein';
  customInput.addEventListener('change', (e) => onCustomRoomChange(idx, e.target.value));
  customField.appendChild(customLabel);
  customField.appendChild(customInput);
  controlsDiv.appendChild(customField);
  
  card.appendChild(controlsDiv);
  
  // Store references for easy access
  card.dataset.index = idx;
  card.dataset.bracket = JSON.stringify(bracket);
  
  return card;
}

function onTypeChange(idx, type) {
  const roomField = document.getElementById(`room-field-${idx}`);
  
  if (FLOOR_TYPES.includes(type)) {
    roomField.style.display = 'block';
  } else {
    roomField.style.display = 'none';
    document.getElementById(`room-${idx}`).value = '';
    document.getElementById(`custom-field-${idx}`).style.display = 'none';
  }
}

function onRoomChange(idx, room) {
  const customField = document.getElementById(`custom-field-${idx}`);
  
  if (room === 'Custom') {
    customField.style.display = 'block';
  } else {
    customField.style.display = 'none';
    document.getElementById(`custom-${idx}`).value = '';
  }
}

function onCustomRoomChange(idx, value) {
  // Just update the value, validation happens on apply
}

function copyFromPrevious(idx) {
  const prevType = document.getElementById(`type-${idx - 1}`).value;
  const prevRoom = document.getElementById(`room-${idx - 1}`).value;
  const prevCustom = document.getElementById(`custom-${idx - 1}`).value;
  
  document.getElementById(`type-${idx}`).value = prevType;
  onTypeChange(idx, prevType);
  
  if (prevRoom) {
    document.getElementById(`room-${idx}`).value = prevRoom;
    onRoomChange(idx, prevRoom);
    
    if (prevRoom === 'Custom' && prevCustom) {
      document.getElementById(`custom-${idx}`).value = prevCustom;
    }
  }
}

async function onApply() {
  // Validate and collect classifications
  const classifications = {};
  let hasError = false;

  for (let idx = 0; idx < currentState.brackets.length; idx++) {
    const type = document.getElementById(`type-${idx}`).value;
    
    if (!type) {
      showError(`Bitte wählen Sie einen Typ für Bild ${idx + 1} aus`);
      hasError = true;
      break;
    }
    
    if (type === 'SKIP') {
      continue;
    }
    
    let room = null;
    if (FLOOR_TYPES.includes(type)) {
      room = document.getElementById(`room-${idx}`).value;
      if (!room) {
        showError(`Bitte wählen Sie einen Raum für Bild ${idx + 1} aus`);
        hasError = true;
        break;
      }
      
      if (room === 'Custom') {
        room = document.getElementById(`custom-${idx}`).value;
        if (!room) {
          showError(`Bitte geben Sie einen benutzerdefinierten Raumnamen für Bild ${idx + 1} ein`);
          hasError = true;
          break;
        }
      }
    }
    
    if (!classifications[type]) {
      classifications[type] = [];
    }
    
    classifications[type].push({
      room_name: room,
      files: currentState.brackets[idx]
    });
  }
  
  if (hasError) {
    return;
  }
  
  try {
    showLoading(true);
    const response = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        folder: currentState.selectedFolder,
        classifications
      })
    });
    
    if (!response.ok) {
      throw new Error('Export fehlgeschlagen');
    }
    
    const result = await response.json();
    showLoading(false);
    
    if (result.success) {
      showSuccess(`${result.total_files} Dateien erfolgreich exportiert!`);
    } else {
      showError(`Export abgeschlossen mit Fehlern: ${result.errors.join(', ')}`);
    }
  } catch (error) {
    showLoading(false);
    showError(`Export fehlgeschlagen: ${error.message}`);
  }
}

function onBack() {
  stepSelection.style.display = 'block';
  stepClassification.style.display = 'none';
  imageGrid.innerHTML = '';
}

function restartApp() {
  successState.style.display = 'none';
  stepSelection.style.display = 'block';
  stepClassification.style.display = 'none';
  driveSelect.value = '';
  folderSelect.value = '';
  folderSelect.disabled = true;
  loadBracketsBtn.disabled = true;
  currentState.selectedFolder = null;
  currentState.selectedDrive = null;
}

function dismissError() {
  errorState.style.display = 'none';
}

function showLoading(show) {
  loadingState.style.display = show ? 'block' : 'none';
}



function showError(message) {
  document.getElementById('error-message').textContent = message;
  errorState.style.display = 'block';
  successState.style.display = 'none';
}

function showSuccess(message) {
  document.getElementById('success-message').textContent = message;
  successState.style.display = 'block';
  errorState.style.display = 'none';
}
