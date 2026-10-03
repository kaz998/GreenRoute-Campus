(() => {
  const theme = document.querySelector('#theme');
  const saved = localStorage.getItem('theme');
  if (saved === 'dark') document.body.classList.add('dark');
  if (theme) {
    theme.textContent = document.body.classList.contains('dark') ? '☀' : '☾';
    theme.onclick = () => {
      document.body.classList.toggle('dark');
      localStorage.setItem('theme', document.body.classList.contains('dark') ? 'dark' : 'light');
      theme.textContent = document.body.classList.contains('dark') ? '☀' : '☾';
    };
  }

  window.showToast = (message, type = 'info') => {
    let stack = document.querySelector('.toast-stack');
    if (!stack) {
      stack = document.createElement('div');
      stack.className = 'toast-stack';
      document.body.appendChild(stack);
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    stack.appendChild(toast);
    window.setTimeout(() => toast.remove(), 4200);
  };

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  }
})();
