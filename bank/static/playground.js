if (new URLSearchParams(window.location.search).get('reward_result') === 'success') {
  const message = '領取成功！請至帳戶確認已領取的獎勵金。';
  document.querySelector('.hero p').textContent = message;
  window.alert(message);
  const cleanUrl = new URL(window.location.href);
  cleanUrl.searchParams.delete('reward_result');
  window.history.replaceState(null, '', cleanUrl);
}
