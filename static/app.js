
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
                else tryPlayNotificationSound(); alert('Tarefa: ' + item.title + '\nPrioridade: ' + item.priority);
              });
            } else {
              tryPlayNotificationSound(); alert('Tarefa: ' + item.title + '\nPrioridade: ' + item.priority);
            }
          } catch (e) {
            tryPlayNotificationSound(); alert('Tarefa: ' + item.title + '\nPrioridade: ' + item.priority);
          }
        });
      }
    }).catch(()=>{});
  }
  checkNotifications();
  setInterval(checkNotifications, 30000);
});


// Audio notification (attempt to play; browser may block autoplay until user interacts)
const _notifyAudio = new Audio('/static/notify.mp3');
function tryPlayNotificationSound(){
  try {
    // best-effort play
    _notifyAudio.currentTime = 0;
    const p = _notifyAudio.play();
    if (p !== undefined) {
      p.catch(()=>{ /* autoplay blocked */ });
    }
  } catch(e){}
}

// Listener for Ativar som button
document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('enable-sound');
  if (btn) {
    btn.addEventListener('click', () => {
      const audio = new Audio('/static/notify.mp3');
      audio.play().then(() => {
        alert('Som ativado com sucesso! As próximas notificações terão som.');
      }).catch(() => {
        alert('Não foi possível ativar o som automaticamente. Clique novamente ou interaja com a página.');
      });
    });
  }
});
