window.alert('尚未登入，無法領獎，系統將自動跳轉。\n請登入 DemoBank 後，再領獎一次。');
window.location.replace(document.querySelector('#reward-login').href);
