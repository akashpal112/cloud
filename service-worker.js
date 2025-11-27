/* Service Worker for Caching Static Assets */

const CACHE_NAME = 'akshu-cloud-v1';

// List of files to cache on installation
const urlsToCache = [
  '/',
  '/index.html',
  '/login.html',
  '/register.html',
  '/gallery.html',
  '/thankyou.html',
  '/style.css',
  '/login.css',
  '/gallery.css',
  '/script.js',
  // Add icon path
  '/icons/icon-192x192.png',
  // Add external library URLs (important for offline use)
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// 1. Installation: Cache static files
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache and pre-caching assets.');
        return cache.addAll(urlsToCache);
      })
  );
});

// 2. Fetch: Serve cached content when available
self.addEventListener('fetch', event => {
  // Only intercept GET requests for stability
  if (event.request.method !== 'GET') {
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Cache hit - return response
        if (response) {
          return response;
        }
        
        // No cache hit - fetch from network
        return fetch(event.request);
      })
      .catch(() => {
        // If fetch fails (e.g., completely offline), you can return an offline page here
        // return caches.match('/offline.html');
      })
  );
});

// 3. Activation: Clean up old caches
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});