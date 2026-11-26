self.addEventListener('install',event=>{self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil(self.clients.claim())});
self.addEventListener('push',event=>{
  let data={title:'Nhắc hạn văn bản',body:'Bạn có văn bản sắp đến hạn thực hiện.',url:'/'};
  try{if(event.data)data={...data,...event.data.json()}}catch{}
  event.waitUntil(self.registration.showNotification(data.title,{body:data.body,icon:'/icon-192.png',badge:'/icon-192.png',tag:data.tag||'van-ban-reminder',renotify:true,requireInteraction:true,data:{url:data.url||'/'}}));
});
self.addEventListener('notificationclick',event=>{event.notification.close();event.waitUntil((async()=>{const url=event.notification.data?.url||'/';const list=await clients.matchAll({type:'window',includeUncontrolled:true});for(const client of list){if('focus'in client){await client.focus();return}}if(clients.openWindow)await clients.openWindow(url)})())});
