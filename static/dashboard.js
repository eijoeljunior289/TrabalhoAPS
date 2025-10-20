
// Dashboard JS: fetch statistics and draw chart
async function fetchStats(){
  try {
    const resp = await fetch('/api/dashboard_data');
    if(!resp.ok) return;
    const data = await resp.json();
    document.getElementById('total').innerText = data.total;
    document.getElementById('pending').innerText = data.pending;
    document.getElementById('overdue').innerText = data.overdue;
    document.getElementById('no_notify').innerText = data.no_notify;
    const ctx = document.getElementById('chart').getContext('2d');
    const chartData = {
      labels: ['Pendentes','Atrasadas','Sem notificação'],
      datasets: [{
        label: 'Tarefas',
        data: [data.pending, data.overdue, data.no_notify],
      }]
    };
    if(window._dashboardChart) {
      window._dashboardChart.data = chartData;
      window._dashboardChart.update();
    } else {
      window._dashboardChart = new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: { responsive: true, maintainAspectRatio: false }
      });
    }
  } catch(e) {
    console.error('Erro ao buscar dashboard:', e);
  }
}

document.addEventListener('DOMContentLoaded', ()=>{
  fetchStats();
  setInterval(fetchStats, 30000);
});
