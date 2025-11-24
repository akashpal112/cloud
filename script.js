/* ----------------------------------------------------------------------
   script.js - Akshu Cloud Gallery Frontend Logic (Updated for Tabs & Modals)
----------------------------------------------------------------------*/
const SERVER_URL = ''; // Empty means same domain (e.g., http://127.0.0.1:5000)
const LOGIN_TOKEN = 'isLoggedIn'; 
let galleryItems = []; // To hold the photo data for the current user
let currentIndex = 0; // For modal navigation

// Initialize Bootstrap Modal instance globally
const imageModal = new bootstrap.Modal(document.getElementById('imageViewModal'), {
    keyboard: true
});


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
        messageElement.style.color = data.success ? '#28a745' : '#dc3545';
        messageElement.textContent = data.message;
        if (data.success) {
            setTimeout(() => { window.location.href = 'login.html'; }, 2000);
        }
    } catch (error) {
        console.error("Register Error:", error);
        messageElement.textContent = 'Server Error. Please try again later.';
        messageElement.style.color = '#dc3545';
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
            messageElement.style.color = '#dc3545';
            messageElement.textContent = data.message;
        }
    } catch (error) {
        console.error("Login Error:", error);
        messageElement.textContent = 'Server Error. Please try again later.';
        messageElement.style.color = '#dc3545';
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

// --- 2. PHOTO UPLOAD HANDLERS ---

async function uploadSingleFile(file) {
    const formData = new FormData();
    formData.append('file', file); 
    
    try {
        const response = await fetch(`${SERVER_URL}/api/upload`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        return { success: data.success, filename: file.name };

    } catch (error) {
        console.error(`Network error uploading ${file.name}:`, error);
        return { success: false, filename: file.name };
    }
}

async function handleMultipleUpload(event) {
    const files = event.target.files;
    const uploadMessageElement = document.getElementById('uploadMessage');
    
    if (!files || files.length === 0) {
        uploadMessageElement.textContent = 'No files selected.';
        uploadMessageElement.style.color = '#dc3545';
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
        
        const result = await uploadSingleFile(file); 
        
        if (result.success) {
            successfulUploads++;
        } else {
            failedUploads++;
        }
    }
    
    // Final status update
    const finalMessage = `Upload Complete! ${successfulUploads} files uploaded successfully. ${failedUploads > 0 ? failedUploads + ' failed.' : ''}`;
    uploadMessageElement.innerHTML = `<span class='animate__animated animate__pulse'>${finalMessage}</span>`;
    uploadMessageElement.style.color = failedUploads === 0 ? '#28a745' : 'orange';

    // Reload gallery to show newly uploaded photos
    if (successfulUploads > 0) {
        await fetchGalleryImages(); 
    }

    // Reset the input field
    event.target.value = '';
}


// --- 3. GALLERY MANAGEMENT & MODAL HANDLERS ---

async function fetchGalleryImages() {
    const galleryDiv = document.getElementById('imageGallery');
    const imageCountSpan = document.getElementById('imageCount');
    const imageCountFooterSpan = document.getElementById('imageCountFooter');
    const galleryEmptyMessage = document.getElementById('galleryEmptyMessage');
    
    if (galleryDiv) { 
        galleryDiv.innerHTML = `
            <div class="col-12 text-center p-5 animate__animated animate__fadeIn">
                <i class="fas fa-spinner fa-spin fa-3x text-warning"></i> 
                <p class="mt-3 text-white-75">Loading your precious memories...</p>
            </div>
        `;
        galleryEmptyMessage.style.display = "none";
    }
    
    try {
        const response = await fetch(`${SERVER_URL}/api/photos`);
        const data = await response.json();

        if (response.status === 401) throw new Error(data.message || "Unauthorized access.");
        
        galleryItems = data.photos;
        
        if (imageCountSpan) imageCountSpan.textContent = galleryItems.length;
        if (imageCountFooterSpan) imageCountFooterSpan.textContent = galleryItems.length;

        if (galleryDiv) {
            galleryDiv.innerHTML = ''; 
            if (galleryItems.length === 0) {
                galleryEmptyMessage.style.display = "block";
                galleryDiv.innerHTML = '';
            } else {
                galleryEmptyMessage.style.display = "none";
                galleryItems.forEach((photo, index) => {
                    // Use new card structure
                    const card = document.createElement('div');
                    card.className = 'image-card animate__animated animate__zoomIn';
                    card.setAttribute('data-index', index);
                    card.onclick = () => openImageModal(index); // Open modal on card click

                    // Extract the filename from the URL for display (simple method)
                    const filenameMatch = photo.url.match(/([^/]+)\.(jpg|jpeg|png|gif|webp)$/i);
                    const displayName = filenameMatch ? filenameMatch[1] : 'Image';

                    card.innerHTML = `
                        <img src="${photo.url}" alt="User Photo" loading="lazy">
                        <div class="image-info">
                            <p class="text-white-75 mb-0" style="font-size:0.75rem;">Click to View</p>
                        </div>
                    `;
                    galleryDiv.appendChild(card);
                });
            }
        }

    } catch (error) {
        console.error("Fetch Gallery Error:", error);
        if (galleryDiv) galleryDiv.innerHTML = `
            <div class="col-12 text-center p-5 alert alert-danger animate__animated animate__shakeX">
                <i class="fas fa-exclamation-triangle fa-3x mb-3"></i>
                <p class="fs-5 text-white">Error loading photos: ${error.message}</p>
            </div>
        `;
    }
}

function updateModalContent(index) {
    if (galleryItems.length === 0) return;
    
    currentIndex = index;
    const currentPhoto = galleryItems[currentIndex];
    
    const modalImage = document.getElementById('modalImage');
    const modalDeleteBtn = document.getElementById('modalDeleteBtn');
    const modalTitle = document.getElementById('imageViewModalLabel');
    
    modalImage.src = currentPhoto.url;
    
    // Update delete button data attributes
    modalDeleteBtn.setAttribute('data-photo-id', currentPhoto._id);
    modalDeleteBtn.setAttribute('data-public-id', currentPhoto.public_id);
    
    modalTitle.textContent = `Image Preview (${currentIndex + 1}/${galleryItems.length})`;
}

function openImageModal(index) {
    if (galleryItems.length === 0) return;
    
    updateModalContent(index);
    imageModal.show();
}

function navigateModal(direction) {
    currentIndex += direction;
    
    if (currentIndex < 0) {
        currentIndex = galleryItems.length - 1;
    } else if (currentIndex >= galleryItems.length) {
        currentIndex = 0;
    }
    
    // Smooth transition
    const modalImage = document.getElementById('modalImage');
    modalImage.style.opacity = 0;
    setTimeout(() => {
        updateModalContent(currentIndex);
        modalImage.style.opacity = 1;
    }, 200); 
}

async function deletePhotoFromModal() {
    const modalDeleteBtn = document.getElementById('modalDeleteBtn');
    const photoId = modalDeleteBtn.getAttribute('data-photo-id');
    const publicId = modalDeleteBtn.getAttribute('data-public-id');

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
            uploadMessageElement.style.color = '#28a745';
            
            // Hide modal and refresh gallery
            imageModal.hide();
            fetchGalleryImages();
            
            // Switch to gallery tab if not already there
            document.getElementById('gallery-tab').click(); 
        } else {
            uploadMessageElement.textContent = `Deletion Failed: ${data.message}`;
            uploadMessageElement.style.color = '#dc3545';
        }
        
    } catch (error) {
        console.error("Delete Error:", error);
        uploadMessageElement.textContent = 'An unexpected error occurred during photo deletion.';
        uploadMessageElement.style.color = '#dc3545';
    }
}


// ----------------------------------------------------------------------
// --- 4. PRIVATE CONTACTS HANDLERS ---
// ----------------------------------------------------------------------

async function fetchContacts() {
    const contactsListDiv = document.getElementById('contactsList');
    const contactCountSpan = document.getElementById('contactCount');
    const contactCountFooterSpan = document.getElementById('contactCountFooter');
    
    if (contactsListDiv) {
        contactsListDiv.innerHTML = `
            <div class="text-center p-4">
                <i class="fas fa-spinner fa-spin fa-2x text-warning"></i> 
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
                const contactItem = document.createElement('div');
                contactItem.className = 'list-group-item d-flex justify-content-between align-items-center animate__animated animate__fadeInUp';
                
                // Content (Name, Phone, Email)
                const content = document.createElement('div');
                content.innerHTML = `
                    <strong>${contact.name}</strong><br>
                    <small><i class="fas fa-phone-alt me-1"></i> ${contact.phone}</small>
                    ${contact.email && contact.email !== 'N/A' ? `<br><small><i class="fas fa-envelope me-1"></i> ${contact.email}</small>` : ''}
                `;

                // Delete Button
                const deleteBtn = document.createElement('button');
                deleteBtn.className = 'btn btn-sm btn-danger';
                deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i>';
                deleteBtn.onclick = () => deleteContact(contact._id);
                
                contactItem.appendChild(content);
                contactItem.appendChild(deleteBtn);
                contactsListDiv.appendChild(contactItem);
            });
            
            if (contactCountSpan) contactCountSpan.textContent = data.contacts.length;
            if (contactCountFooterSpan) contactCountFooterSpan.textContent = data.contacts.length;

        } else if (contactsListDiv) {
             contactsListDiv.innerHTML = `
                <div class="text-center p-3 text-white-75">
                    <i class="fas fa-address-book fa-3x text-warning mb-2"></i>
                    <p class="fs-6 mb-0">No private contacts saved yet. Use the form or import a VCF file.</p>
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
        messageElement.style.color = '#dc3545';
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
            messageElement.style.color = '#28a745';
            document.getElementById('addContactForm').reset();
            fetchContacts();
        } else {
            messageElement.textContent = data.message;
            messageElement.style.color = '#dc3545';
        }
    } catch (error) {
        console.error("Add Contact Error:", error);
        messageElement.textContent = 'Server Error. Failed to save contact.';
        messageElement.style.color = '#dc3545';
    }
}

async function deleteContact(contactId) {
    if (!confirm('Are you sure you want to permanently delete this contact?')) return;
    
    const messageElement = document.getElementById('contactMessage') || document.getElementById('vcfUploadMessage');
    messageElement.textContent = 'Deleting contact...';
    messageElement.style.color = 'yellow';
    
    try {
        const response = await fetch(`${SERVER_URL}/api/contacts/${contactId}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            messageElement.textContent = data.message;
            messageElement.style.color = '#28a745';
            fetchContacts();
        } else {
            messageElement.textContent = data.message;
            messageElement.style.color = '#dc3545';
        }
    } catch (error) {
        console.error("Delete Contact Error:", error);
        messageElement.textContent = 'An unexpected error occurred during contact deletion.';
        messageElement.style.color = '#dc3545';
    }
}


/* ----------------------------------------------------------------------
   VCF Upload Handler
----------------------------------------------------------------------*/

async function handleVcfUpload(event) {
    event.preventDefault();
    const vcfFileInput = document.getElementById('vcfFileInput');
    const vcfUploadMessage = document.getElementById('vcfUploadMessage');
    const file = vcfFileInput.files[0];

    if (!file) {
        vcfUploadMessage.textContent = "Please select a VCF file.";
        vcfUploadMessage.style.color = '#dc3545';
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
        
        vcfUploadMessage.style.color = data.success ? '#28a745' : '#dc3545';
        vcfUploadMessage.textContent = data.message;
        
        if (data.success) {
            // Refresh contacts list after successful upload
            fetchContacts();
            vcfFileInput.value = ''; // Clear file input
        }

    } catch (error) {
        console.error('Error importing VCF:', error);
        vcfUploadMessage.textContent = 'An error occurred during VCF upload.';
        vcfUploadMessage.style.color = '#dc3545';
    }
}


// --- 5. INITIALIZATION & EVENT LISTENERS ---

document.addEventListener('DOMContentLoaded', async () => {
    
    // Attach Auth handlers
    const registerForm = document.getElementById('registerForm');
    if (registerForm) registerForm.addEventListener('submit', handleRegister);

    const loginForm = document.getElementById('loginForm');
    if (loginForm) loginForm.addEventListener('submit', handleLogin);

    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) logoutButton.addEventListener('click', logout);
    
    // Check if we are on the gallery page
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
            if (gallerySection) gallerySection.style.display = "flex"; // Use flex for better layout on big screens
            
            // Load Gallery and Contacts on initial load
            fetchGalleryImages(); 
            fetchContacts();

            // Attach Upload Listener 
            const uploadInput = document.getElementById('uploadInput');
            if(uploadInput) uploadInput.addEventListener('change', handleMultipleUpload);
            
            // Attach Contact Form Listener
            const addContactForm = document.getElementById('addContactForm');
            if(addContactForm) addContactForm.addEventListener('submit', handleAddContact);
            
            // Attach VCF Upload Listener
            const vcfUploadForm = document.getElementById('vcfUploadForm');
            if(vcfUploadForm) vcfUploadForm.addEventListener('submit', handleVcfUpload);

            // Attach Modal Delete Button Listener
            const modalDeleteBtn = document.getElementById('modalDeleteBtn');
            if(modalDeleteBtn) modalDeleteBtn.addEventListener('click', deletePhotoFromModal);
            
        } else {
            if (loginPrompt) loginPrompt.style.display = "block";
            if (gallerySection) gallerySection.style.display = "none";
            localStorage.removeItem(LOGIN_TOKEN);
            localStorage.removeItem('username');
        }
    }
});