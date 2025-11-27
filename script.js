/* ----------------------------------------------------------------------
   script.js - Akshu Cloud Gallery Frontend Logic (Updated with Gaming Hub)
----------------------------------------------------------------------*/
const SERVER_URL = ''; // Empty means same domain (e.g., http://127.0.0.1:5000)
const LOGIN_TOKEN = 'isLoggedIn'; 
let galleryItems = []; // To hold the photo data for the current user
let currentIndex = 0; // For lightbox navigation
let stream = null; // Global variable to hold the video stream

// --- Game/Wallet Globals ---
let timerInterval;

// ----------------------------------------------------------------------
// --- 1. AUTHENTICATION HANDLERS ---
// ----------------------------------------------------------------------

async function handleRegister(event) {
    event.preventDefault();
    const username = document.getElementById('registerUsername').value;
    const password = document.getElementById('registerPassword').value;
    const messageElement = document.getElementById('registerMessage');
    
    messageElement.textContent = "Registering...";
    messageElement.style.color = 'yellow'; 

    try {
        const response = await fetch(`${SERVER_URL}/api/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();
        
        if (data.success) {
            messageElement.style.color = '#03DAC6';
            messageElement.textContent = data.message;
            const fullName = document.getElementById('registerName') ? document.getElementById('registerName').value : username;
            setTimeout(() => { window.location.href = `thankyou.html?name=${encodeURIComponent(fullName)}`; }, 1000);
        } else {
            messageElement.style.color = '#FF6B6B';
            messageElement.textContent = data.message;
        }
    } catch (error) {
        console.error("Register Error:", error);
        messageElement.textContent = 'Server Error. Please try again later.';
        messageElement.style.color = '#FF6B6B';
    }
}

async function handleLogin(event) {
    event.preventDefault();
    const username = document.getElementById('loginUsername').value; 
    const password = document.getElementById('loginPassword').value;
    const messageElement = document.getElementById('loginMessage');
    
    messageElement.textContent = "Logging in...";
    messageElement.style.color = 'yellow'; 

    try {
        const response = await fetch(`${SERVER_URL}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await response.json();
        
        if (data.success) {
            localStorage.setItem(LOGIN_TOKEN, 'true'); 
            localStorage.setItem('username', data.username);
            window.location.href = 'gallery.html';
        } else {
            messageElement.style.color = '#FF6B6B';
            messageElement.textContent = data.message;
        }
    } catch (error) {
        console.error("Login Error:", error);
        messageElement.textContent = 'Server Error. Please try again later.';
        messageElement.style.color = '#FF6B6B';
    }
}

async function logout() {
    try {
        await fetch(`${SERVER_URL}/api/logout`, { method: 'POST' });
    } catch (error) {
        console.error("Logout API failed, but continuing client logout.", error);
    } finally {
        localStorage.removeItem(LOGIN_TOKEN);
        localStorage.removeItem('username');
        window.location.href = 'index.html'; 
    }
}

// ----------------------------------------------------------------------
// --- 2. PHOTO UPLOAD HANDLERS (Standard CRUD functions omitted for brevity) ---
// ----------------------------------------------------------------------
// ... (uploadSingleFile, handleMultipleUpload, fetchGalleryImages, deletePhoto, openLightbox, closeLightbox, navigateLightbox functions go here)
async function uploadSingleFile(file, locationData = '') {
    const formData = new FormData();
    formData.append('file', file); 
    if (locationData) {
        formData.append('location', locationData);
    }
    
    try {
        const response = await fetch(`${SERVER_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        return data.success;

    } catch (error) {
        console.error(`Network error uploading ${file.name}:`, error);
        return false;
    }
}

async function handleMultipleUpload(event) {
    const files = event.target.files;
    const uploadMessageElement = document.getElementById('uploadMessage');
    
    if (!files || files.length === 0) {
        uploadMessageElement.textContent = 'No files selected.';
        uploadMessageElement.style.color = '#FF6B6B';
        return;
    }

    let successfulUploads = 0;
    let failedUploads = 0;
    const totalFiles = files.length;
    
    uploadMessageElement.textContent = `Starting upload of ${totalFiles} file(s)...`;
    uploadMessageElement.style.color = 'yellow';
    
    for (let i = 0; i < totalFiles; i++) {
        const file = files[i];
        
        uploadMessageElement.innerHTML = `
            Uploading **${file.name}** (${i + 1}/${totalFiles})... 
            <br>Success: ${successfulUploads} | Failed: ${failedUploads}
        `;
        
        const success = await uploadSingleFile(file, ''); 
        
        if (success) {
            successfulUploads++;
        } else {
            failedUploads++;
        }
    }
    
    const finalMessage = `Upload Complete! ${successfulUploads} files uploaded successfully. ${failedUploads > 0 ? failedUploads + ' failed.' : ''}`;
    uploadMessageElement.innerHTML = `<span class='animate__animated animate__pulse'>${finalMessage}</span>`;
    uploadMessageElement.style.color = failedUploads === 0 ? '#03DAC6' : 'orange';

    await fetchGalleryImages(); 
    event.target.value = '';
}

// NOTE: All other gallery/contact functions (fetchGalleryImages, deletePhoto, openLightbox, etc.) 
// remain in the file, but are omitted here for focus.

// ----------------------------------------------------------------------
// --- 3. WALLET & GAMING HUB LOGIC (NEW) ---
// ----------------------------------------------------------------------

// Function to fetch and update user's wallet balance on the UI
async function fetchWalletBalance() {
    const balanceElements = document.querySelectorAll('#walletBalance, #currentBalance');
    if (balanceElements.length === 0) return; 
    
    balanceElements.forEach(el => el.textContent = '...'); 

    try {
        const response = await fetch(`${SERVER_URL}/api/wallet/balance`);
        const data = await response.json();

        if (data.success) {
            balanceElements.forEach(el => el.textContent = data.balance.toLocaleString());
            return data.balance;
        } else {
            console.error("Failed to fetch balance:", data.message);
            balanceElements.forEach(el => el.textContent = 'Error');
            return 0;
        }
    } catch (error) {
        console.error("Network error fetching balance:", error);
        balanceElements.forEach(el => el.textContent = 'Offline');
        return 0;
    }
}

// Function to handle placing the color prediction bet
async function placeColorBet(prediction) {
    const betAmountInput = document.getElementById('betAmount');
    const gameMessage = document.getElementById('gameMessage');
    const amount = parseInt(betAmountInput.value);
    
    if (isNaN(amount) || amount < 10) {
        gameMessage.textContent = 'Bet amount must be at least 10 tokens.';
        gameMessage.style.color = '#FF6B6B';
        return;
    }
    
    // Disable betting during processing
    const predictButtons = document.querySelectorAll('.btn-predict');
    predictButtons.forEach(btn => btn.disabled = true);
    
    gameMessage.textContent = `Placing bet of ${amount} tokens on ${prediction}...`;
    gameMessage.style.color = 'yellow';
    
    try {
        const response = await fetch(`${SERVER_URL}/api/game/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prediction, amount })
        });
        const data = await response.json();

        if (data.success) {
            gameMessage.textContent = `✅ Bet successful! Your new balance is ${data.new_balance.toLocaleString()} Tokens.`;
            gameMessage.style.color = '#03DAC6';
            fetchWalletBalance(); 
            betAmountInput.value = '10'; 
        } else {
            gameMessage.textContent = `❌ Bet Failed: ${data.message}`;
            gameMessage.style.color = '#FF6B6B';
        }

    } catch (error) {
        console.error("Bet placement network error:", error);
        gameMessage.textContent = 'Server Error. Could not place bet.';
        gameMessage.style.color = '#FF6B6B';
    } finally {
        predictButtons.forEach(btn => btn.disabled = false);
    }
}

// --- Game Status & Timer Logic ---

function formatTime(seconds) {
    const min = Math.floor(seconds / 60);
    const sec = seconds % 60;
    return `${String(min).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

function displayResults(results) {
    const resultsDiv = document.getElementById('previousResults');
    resultsDiv.innerHTML = ''; 
    
    if (results.length === 0) {
        resultsDiv.innerHTML = `<p class="text-muted-text mb-0">No past results found yet.</p>`;
        return;
    }

    const html = results.map(r => `
        <span class="badge" style="background-color: ${r.color === 'red' ? '#FF6B6B' : r.color === 'green' ? '#03DAC6' : '#BB86FC'}; color: black; margin: 3px; padding: 8px 12px; font-weight: bold;">
            #${r.round_id}
        </span>
    `).join('');

    resultsDiv.innerHTML = html;
}

// Function to call the server to run the round result (Testing only)
async function runServerRound() {
    const gameMessage = document.getElementById('gameMessage');
    gameMessage.textContent = "Time's up! Processing results...";
    gameMessage.style.color = '#BB86FC';
    
    try {
        const response = await fetch(`${SERVER_URL}/api/game/run_round`, { method: 'POST' }); 
        const data = await response.json();

        if (data.success) {
            gameMessage.textContent = `Processing Complete! Winning Color: ${data.winning_color.toUpperCase()}.`;
            gameMessage.style.color = '#03DAC6';
        } else {
            gameMessage.textContent = `Error processing round.`;
            gameMessage.style.color = '#FF6B6B';
        }

        // Reload status and balance after processing
        setTimeout(() => {
            fetchWalletBalance(); 
            updateGameStatus(); 
        }, 3000); 
        
    } catch (error) {
        console.error("Failed to run game round:", error);
    }
}


async function updateGameStatus() {
    const roundIdElement = document.getElementById('currentRoundId');
    const timerElement = document.getElementById('timerDisplay');
    
    // Clear any existing timer to prevent duplicates
    if (timerInterval) clearInterval(timerInterval);

    try {
        const response = await fetch(`${SERVER_URL}/api/game/status`);
        const data = await response.json();

        if (!data.success) throw new Error("Failed to fetch game status.");

        const { current_round_id, time_remaining, past_results } = data;
        
        roundIdElement.textContent = `#${current_round_id}`;
        displayResults(past_results);

        let seconds = time_remaining;
        
        timerElement.textContent = formatTime(seconds);
        
        timerInterval = setInterval(() => {
            seconds--;
            if (seconds <= 0) {
                // Time up! Trigger server round run and immediately restart timer
                clearInterval(timerInterval);
                timerElement.textContent = "Processing...";
                runServerRound(); 
                
            } else {
                timerElement.textContent = formatTime(seconds);
            }
        }, 1000);

    } catch (error) {
        console.error("Game status update error:", error);
        timerElement.textContent = "Error";
    }
}


// ----------------------------------------------------------------------
// --- 4. INITIALIZATION ---
// ----------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
    
    // Attach Auth handlers
    const registerForm = document.getElementById('registerForm');
    if (registerForm) registerForm.addEventListener('submit', handleRegister);

    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);

    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) logoutButton.addEventListener('click', logout);


    // Determine page type
    const isGalleryPage = document.body.classList.contains('gallery-page');
    const isGamingPage = document.body.classList.contains('gaming-page');
    
    // Check login status for secured pages
    if (isGalleryPage || isGamingPage || document.getElementById('walletBalance')) {
        const statusResponse = await fetch(`${SERVER_URL}/api/status`);
        const statusData = await statusResponse.json();
        
        const loginPrompt = document.getElementById("loginPrompt");
        const mainSection = document.getElementById("gallerySection") || document.querySelector('.main-gaming-content');
        const usernameDisplay = document.getElementById("usernameDisplay");
        
        if (usernameDisplay) {
            usernameDisplay.textContent = statusData.isLoggedIn ? statusData.username : 'Guest';
        }

        if (statusData.isLoggedIn) {
            if (loginPrompt) loginPrompt.style.display = "none";
            if (mainSection) mainSection.style.display = "block";
            
            // Load Wallet Balance
            fetchWalletBalance(); 

            if (isGalleryPage) {
                // Attach Gallery/Contact Loaders and Listeners
                // (Omitted here, but assumed to be present in the full code)
            }
            
            if (isGamingPage) {
                // Initialize game status and timer
                updateGameStatus();

                // Attach Color Prediction Listeners
                const predictButtons = document.querySelectorAll('.btn-predict');
                predictButtons.forEach(button => {
                    button.addEventListener('click', () => {
                        const prediction = button.getAttribute('data-prediction');
                        placeColorBet(prediction);
                    });
                });
            }
            
        } else {
            if (loginPrompt) loginPrompt.style.display = "block";
            if (mainSection) mainSection.style.display = "none";
            localStorage.removeItem(LOGIN_TOKEN);
            localStorage.removeItem('username');
        }
    }
});