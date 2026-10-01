const CACHE='qvc-pwa-v3';
const APP_SHELL=['/','/manifest.webmanifest','/icon-192.png','/icon-512.png'];
self.addEventListener('install',e=>{self.skipWaiting();e.waitUntil(caches.open(CACHE).then(c=>c.addAll(APP_SHELL)).catch(()=>{}));});
self.addEventListener('activate',e=>{e.waitUntil(clients.claim());});
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{const copy=r.clone();caches.open(CACHE).then(c=>c.put(e.request,copy)).catch(()=>{});return r;}).catch(()=>caches.match(e.request).then(r=>r||caches.match('/'))));});
self.addEventListener('push',e=>{
  let data={title:'Nhắc hạn',body:'Bạn có công việc cần chú ý.',type:'upcoming',url:'/'};
  try{if(e.data)data={...data,...e.data.json()};}catch{}
  const overdue=data.type==='overdue';
  const options={body:data.body,icon:'/icon-192.png',badge:'/icon-192.png',tag:'qvc-'+(data.type||'notice')+'-'+Date.now(),renotify:true,requireInteraction:true,silent:false,data:{url:data.url||'/'}};
  e.waitUntil(self.registration.showNotification(data.title,options).then(()=>self.registration.getNotifications().then(ns=>{if(self.registration.setAppBadge) self.registration.setAppBadge(ns.length).catch(()=>{});})).catch(()=>{}));
});
self.addEventListener('notificationclick',e=>{e.notification.close();if(self.registration.clearAppBadge)self.registration.clearAppBadge().catch(()=>{});const url=e.notification.data?.url||'/';e.waitUntil(clients.matchAll({type:'window',includeUncontrolled:true}).then(list=>{for(const c of list){if('focus' in c)return c.focus();}return clients.openWindow(url);}));});
