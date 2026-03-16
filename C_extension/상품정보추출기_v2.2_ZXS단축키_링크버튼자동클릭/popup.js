async function copyToClipboard(type) {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const response = await chrome.tabs.sendMessage(tab.id, { action: type });
    
    if (response.success) {
      await navigator.clipboard.writeText(response.data);
      
      // 성공 표시
      const btnId = type === 'copyName' ? 'copyName' : type === 'copyImages' ? 'copyImages' : 'copyLink';
      const btn = document.getElementById(btnId);
      btn.classList.add('success');
      btn.querySelector('.label').textContent = '✅ 복사 완료!';
      
      setTimeout(() => {
        window.close();
      }, 800);
    } else {
      alert(response.error);
    }
  } catch (error) {
    alert('오류: ' + error.message);
  }
}

document.getElementById('copyName').addEventListener('click', () => copyToClipboard('copyName'));
document.getElementById('copyImages').addEventListener('click', () => copyToClipboard('copyImages'));
document.getElementById('copyLink').addEventListener('click', () => copyToClipboard('copyLink'));
