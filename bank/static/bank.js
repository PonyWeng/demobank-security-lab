document.querySelectorAll('[data-copy]').forEach(button => {
  button.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(button.dataset.copy); button.textContent = '已複製'; }
    catch { button.textContent = '請手動選取帳號'; }
  });
});
