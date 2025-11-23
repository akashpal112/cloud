/* ----------------------------------------------------------------------
   script.js - Akshu Cloud Gallery Frontend Logic (Multi-Upload & Contacts)
----------------------------------------------------------------------*/
const SERVER_URL = ''; // Empty means same domain (e.g., http://127.0.0.1:5000)
const LOGIN_TOKEN = 'isLoggedIn'; 
let galleryItems = []; // To hold the photo data for the current user
let currentIndex = 0; // For lightbox navigation

// --- 1. AUTHENTICATION HANDLERS ---

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
        messageElement.style.color = data.success ? '#03DAC6' : '#FF6B6B';
        messageElement.textContent = data.message;
        if (data.success) {
            setTimeout(() => { window.location.href = 'login.html'; }, 2000);
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

// --- 2. PHOTO UPLOAD HANDLERS (FIXED LOADING/DISPLAY ISSUE) ---

async function uploadSingleFile(file) {
    const formData = new FormData();
    formData.append('file', file); 
    
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
    
    // Process files sequentially
    for (let i = 0; i < totalFiles; i++) {
        const file = files[i];
        
        uploadMessageElement.innerHTML = `
            Uploading **${file.name}** (${i + 1}/${totalFiles})... 
            <br>Success: ${successfulUploads} | Failed: ${failedUploads}
        `;
        
        const success = await uploadSingleFile(file); 
        
        if (success) {
            successfulUploads++;
        } else {
            failedUploads++;
        }
    }
    
    // Final status update
    const finalMessage = `Upload Complete! ${successfulUploads} files uploaded successfully. ${failedUploads > 0 ? failedUploads + ' failed.' : ''}`;
    uploadMessageElement.innerHTML = `<span class='animate__animated animate__pulse'>${finalMessage}</span>`;
    uploadMessageElement.style.color = failedUploads === 0 ? '#03DAC6' : 'orange';

    // Reload gallery to show newly uploaded photos
    await fetchGalleryImages(); 

    // Reset the input field
    event.target.value = '';
}


// --- 3. GALLERY MANAGEMENT ---

async function fetchGalleryImages() {
    const galleryDiv = document.getElementById('gallery');
    const imageCountSpan = document.getElementById('imageCount');
    
    // Show loading spinner ONLY in the gallery area
    if (galleryDiv) { 
        galleryDiv.innerHTML = `
            <div class="text-center p-5 animate__animated animate__fadeIn">
                <i class="fas fa-spinner fa-spin fa-3x text-gold-gradient"></i> 
                <p class="mt-3 text-white-75">Loading your precious memories...</p>
            </div>
        `;
    }
    
    try {
        const response = await fetch(`${SERVER_URL}/api/photos`);
        const data = await response.json();

        if (response.status === 401) throw new Error(data.message || "Unauthorized access.");
        
        galleryItems = data.photos;
        
        if (imageCountSpan) imageCountSpan.textContent = galleryItems.length;

        if (galleryDiv) {
            galleryDiv.innerHTML = ''; 
            if (galleryItems.length === 0) {
                galleryDiv.innerHTML = `
                    <div class="col-12 text-center p-5 animate__animated animate__fadeIn">
                        <i class="fas fa-box-open fa-5x text-gold-gradient mb-3"></i>
                        <p class="fs-4 text-white-75">Your private gallery is empty. Upload your first photo!</p>
                    </div>
                `;
            } else {
                galleryItems.forEach((photo, index) => {
                    const card = document.createElement('div');
                    card.className = 'gallery-card animate__animated animate__zoomIn';
                    card.setAttribute('data-index', index);
                    
                    card.innerHTML = `
                        <img src="${photo.url}" alt="User Photo" class="img-fluid" loading="lazy" onclick="openLightbox(${index})">
                        <div class="card-overlay">
                            <span class="delete-btn" onclick="event.stopPropagation(); deletePhoto('${photo._id}', '${photo.public_id}')">
                                <i class="fas fa-trash-alt"></i> Delete
                            </span>
                            <span class="view-btn" onclick="openLightbox(${index})">
                                <i class="fas fa-expand"></i> View
                            </span>
                        </div>
                    `;
                    galleryDiv.appendChild(card);
                });
            }
        }

    } catch (error) {
        console.error("Fetch Gallery Error:", error);
        if (galleryDiv) galleryDiv.innerHTML = `
            <div class="col-12 text-center p-5 text-danger-light animate__animated animate__shakeX">
                <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                <p class="fs-4 text-danger">Error loading photos: ${error.message}</p>
            </div>
        `;
    }
}

async function deletePhoto(photoId, publicId) {
    if (!confirm('Are you sure you want to permanently delete this photo?')) return;
    
    const uploadMessageElement = document.getElementById('uploadMessage');
    uploadMessageElement.textContent = 'Deleting photo...';
    uploadMessageElement.style.color = 'yellow';

    try {
        const response = await fetch(`${SERVER_URL}/api/photos/${photoId}`, {
            method: 'DELETE',
            headers: { 'Content-ID': publicId }
        });
        
        const data = await response.json();

        if (data.success) {
            uploadMessageElement.textContent = data.message;
            uploadMessageElement.style.color = '#03DAC6';
            closeLightbox(); 
            fetchGalleryImages();
        } else {
            uploadMessageElement.textContent = `Deletion Failed: ${data.message}`;
            uploadMessageElement.style.color = '#FF6B6B';
        }
        
    } catch (error) {
        console.error("Delete Error:", error);
        uploadMessageElement.textContent = 'An unexpected error occurred during photo deletion.';
        uploadMessageElement.style.color = '#FF6B6B';
    }
}


// --- 4. LIGHTBOX HANDLERS ---

function openLightbox(index) {
    if (galleryItems.length === 0) return;
    
    currentIndex = index;
    const lightbox = document.getElementById('lightbox');
    const lightboxImg = document.getElementById('lightbox-img');

    lightboxImg.src = galleryItems[currentIndex].url;
    lightbox.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeLightbox() {
    const lightbox = document.getElementById('lightbox');
    lightbox.classList.remove('active');
    document.body.style.overflow = 'auto';
}

function navigateLightbox(direction) {
    currentIndex += direction;
    
    if (currentIndex < 0) {
        currentIndex = galleryItems.length - 1;
    } else if (currentIndex >= galleryItems.length) {
        currentIndex = 0;
    }
    
    const lightboxImg = document.getElementById('lightbox-img');
    lightboxImg.style.opacity = 0;
    setTimeout(() => {
        lightboxImg.src = galleryItems[currentIndex].url;
        lightboxImg.style.opacity = 1;
    }, 200); 
}


// ----------------------------------------------------------------------
// --- 5. PRIVATE CONTACTS HANDLERS (UPDATED SECTION) ---
// ----------------------------------------------------------------------

async function fetchContacts() {
    const contactsListDiv = document.getElementById('contactsList');
    const contactCountSpan = document.getElementById('contactCount');
    const contactCountFooterSpan = document.getElementById('contactCountFooter');
    
    if (contactsListDiv) {
        contactsListDiv.innerHTML = `
            <div class="text-center p-4">
                <i class="fas fa-spinner fa-spin fa-2x text-gold-gradient"></i> 
                <p class="mt-2 text-white-75">Loading private contacts...</p>
            </div>
        `;
    }

    try {
        const response = await fetch(`${SERVER_URL}/api/contacts`);
        const data = await response.json();

        if (contactsListDiv) {
            contactsListDiv.innerHTML = '';
        }
        
        if (data.success && data.contacts.length > 0) {
            data.contacts.forEach(contact => {
                const contactCard = document.createElement('div');
                contactCard.className = 'contact-card animate__animated animate__fadeInUp';
                contactCard.innerHTML = `
                    <div class="contact-info">
                        <h5><i class="fas fa-user-circle me-2"></i> ${contact.name}</h5>
                        <p><i class="fas fa-phone-alt me-2"></i> ${contact.phone}</p>
                        ${contact.email && contact.email !== 'N/A' ? `<p><i class="fas fa-envelope me-2"></i> ${contact.email}</p>` : ''}
                    </div>
                    <button class="btn btn-sm btn-danger delete-contact-btn" onclick="deleteContact('${contact._id}')">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                `;
                contactsListDiv.appendChild(contactCard);
            });
            
            if (contactCountSpan) contactCountSpan.textContent = data.contacts.length;
            if (contactCountFooterSpan) contactCountFooterSpan.textContent = data.contacts.length;

        } else if (contactsListDiv) {
             contactsListDiv.innerHTML = `
                <div class="text-center p-5">
                    <i class="fas fa-address-book fa-5x text-gold-gradient mb-3"></i>
                    <p class="fs-4 text-white-75">No private contacts saved yet. Add one!</p>
                </div>
            `;
             if (contactCountSpan) contactCountSpan.textContent = 0;
             if (contactCountFooterSpan) contactCountFooterSpan.textContent = 0;
        }

    } catch (error) {
        console.error("Fetch Contacts Error:", error);
        if (contactsListDiv) contactsListDiv.innerHTML = `<p class="text-danger p-4">Error loading contacts: ${error.message}</p>`;
    }
}

async function handleAddContact(event) {
    event.preventDefault();
    const name = document.getElementById('contactName').value;
    const phone = document.getElementById('contactPhone').value;
    const email = document.getElementById('contactEmail').value;
    const messageElement = document.getElementById('contactMessage');
    
    if (!name || !phone) {
        messageElement.textContent = "Name and Phone are required.";
        messageElement.style.color = '#FF6B6B';
        return;
    }
    
    messageElement.textContent = "Saving contact...";
    messageElement.style.color = 'yellow';

    try {
        const response = await fetch(`${SERVER_URL}/api/contacts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, phone, email })
        });
        const data = await response.json();
        
        if (data.success) {
            messageElement.textContent = data.message;
            messageElement.style.color = '#03DAC6';
            document.getElementById('addContactForm').reset();
            fetchContacts();
        } else {
            messageElement.textContent = data.message;
            messageElement.style.color = '#FF6B6B';
        }
    } catch (error) {
        console.error("Add Contact Error:", error);
        messageElement.textContent = 'Server Error. Failed to save contact.';
        messageElement.style.color = '#FF6B6B';
    }
}

async function deleteContact(contactId) {
    if (!confirm('Are you sure you want to permanently delete this contact?')) return;
    
    const messageElement = document.getElementById('contactMessage');
    messageElement.textContent = 'Deleting contact...';
    messageElement.style.color = 'yellow';
    
    try {
        const response = await fetch(`${SERVER_URL}/api/contacts/${contactId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            messageElement.textContent = data.message;
            messageElement.style.color = '#03DAC6';
            fetchContacts();
        } else {
            messageElement.textContent = data.message;
            messageElement.style.color = '#FF6B6B';
        }
    } catch (error) {
        console.error("Delete Contact Error:", error);
        messageElement.textContent = 'An unexpected error occurred during contact deletion.';
        messageElement.style.color = '#FF6B6B';
    }
}


/* ----------------------------------------------------------------------
   script.js - VCF Upload Handler (NEW)
----------------------------------------------------------------------*/

async function handleVcfUpload(event) {
    event.preventDefault();
    const vcfFileInput = document.getElementById('vcfFileInput');
    const vcfUploadMessage = document.getElementById('vcfUploadMessage');
    const file = vcfFileInput.files[0];

    if (!file) {
        vcfUploadMessage.textContent = "Please select a VCF file.";
        vcfUploadMessage.style.color = '#FF6B6B';
        return;
    }

    vcfUploadMessage.textContent = "Processing VCF file...";
    vcfUploadMessage.style.color = 'yellow';

    const formData = new FormData();
    formData.append('vcf_file', file);

    try {
        const response = await fetch(`${SERVER_URL}/api/import_vcf`, {
            method: 'POST',
            body: formData,
        });

        const data = await response.json();
        
        vcfUploadMessage.style.color = data.success ? '#03DAC6' : '#FF6B6B';
        vcfUploadMessage.textContent = data.message;
        
        if (data.success) {
            // Refresh contacts list after successful upload
            fetchContacts();
            vcfFileInput.value = ''; // Clear file input
        }

    } catch (error) {
        console.error('Error importing VCF:', error);
        vcfUploadMessage.textContent = 'An error occurred during VCF upload.';
        vcfUploadMessage.style.color = '#FF6B6B';
    }
}


// --- 6. INITIALIZATION ---

document.addEventListener('DOMContentLoaded', async () => {
    
    // Attach Auth handlers
    const registerForm = document.getElementById('registerForm');
    if (registerForm) registerForm.addEventListener('submit', handleRegister);

    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);

    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) logoutButton.addEventListener('click', logout);


    // Gallery Initialization
    if (document.body.classList.contains('gallery-page')) {
        const statusResponse = await fetch(`${SERVER_URL}/api/status`);
        const statusData = await statusResponse.json();
        
        const loginPrompt = document.getElementById("loginPrompt");
        const gallerySection = document.getElementById("gallerySection");
        const usernameDisplay = document.getElementById("usernameDisplay");
        
        if (usernameDisplay) {
            usernameDisplay.textContent = statusData.isLoggedIn ? statusData.username : 'Guest';
        }

        if (statusData.isLoggedIn) {
            if (loginPrompt) loginPrompt.style.display = "none";
            if (gallerySection) gallerySection.style.display = "block";
            
            // Load Gallery and Contacts
            fetchGalleryImages(); 
            fetchContacts();

            // Attach Upload Listener 
            const uploadInput = document.getElementById('uploadInput');
            if(uploadInput) uploadInput.addEventListener('change', handleMultipleUpload);
            
            // Attach Contact Form Listener
            const addContactForm = document.getElementById('addContactForm');
            if(addContactForm) addContactForm.addEventListener('submit', handleAddContact);
            
            // Attach VCF Upload Listener (NEW)
            const vcfUploadForm = document.getElementById('vcfUploadForm');
            if(vcfUploadForm) vcfUploadForm.addEventListener('submit', handleVcfUpload);
            
        } else {
            if (loginPrompt) loginPrompt.style.display = "block";
            if (gallerySection) gallerySection.style.display = "none";
            localStorage.removeItem(LOGIN_TOKEN);
            localStorage.removeItem('username');
        }
    }
});