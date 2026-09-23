/* Service worker do app de gravação.
 *
 * Guarda só a casca (HTML, JS, CSS, ícones) para o app abrir sem o PC ligado.
 * Rede primeiro, sempre revalidando: servir casca velha em cache já fez uma
 * correção "não funcionar" neste projeto. /app-api/ nunca passa por aqui.
 */
const CACHE = 'signlab-app-v1';
const CASCA = ['./', 'index.html', 'app.js', 'app.css', 'manifest.webmanifest', 'icone-192.png', 'icone-512.png'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CASCA)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((nomes) => Promise.all(nomes.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin || !url.pathname.startsWith('/app/')) return;
  e.respondWith(
    fetch(e.request, { cache: 'no-cache' })
      .then((resposta) => {
        const copia = resposta.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copia));
        return resposta;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true })),
  );
});
