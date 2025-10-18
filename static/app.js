
document.addEventListener('DOMContentLoaded', function(){
  // Poll notifications every 30s
  function checkNotifications(){
    fetch('/api/notifications').then(r=>r.json()).then(data=>{
      if(Array.isArray(data) && data.length){
        data.forEach(item=>{
          // simple browser alert for prototype
          try {
            if (Notification && Notification.permission === 'granted') {
              new Notification('Tarefa: ' + item.title, { body: 'Prioridade: ' + item.priority });
            } else if (Notification && Notification.permission !== 'denied') {
              Notification.requestPermission().then(permission => {
                if(permission === 'granted') new Notification('Tarefa: ' + item.title, { body: 'Prioridade: ' + item.priority });
                else alert('Tarefa: ' + item.title + '\nPrioridade: ' + item.priority);
              });
            } else {
              alert('Tarefa: ' + item.title + '\nPrioridade: ' + item.priority);
            }
          } catch (e) {
            alert('Tarefa: ' + item.title + '\nPrioridade: ' + item.priority);
          }
        });
      }
    }).catch(()=>{});
  }
  checkNotifications();
  setInterval(checkNotifications, 30000);
});
