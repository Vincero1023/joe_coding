// 기본값
const DEFAULT_SETTINGS = {
  webhookUrl: 'http://josephamy2.ddns.net:5678/webhook/youtube-processor', 
  shortcuts: {
    'save-current-video': 'Ctrl+Shift+Y',
    'save-playlist': 'Ctrl+Shift+P',
    'subscribe-channel-new': 'Ctrl+Shift+N',
    'subscribe-channel-all': 'Ctrl+Shift+A'
  }
};

// 저장된 설정 로드
chrome.storage.sync.get(['webhookUrl', 'shortcuts'], (data) => {
  document.getElementById('webhook-url').value = data.webhookUrl || DEFAULT_SETTINGS.webhookUrl;
  
  const shortcuts = data.shortcuts || DEFAULT_SETTINGS.shortcuts;
  document.getElementById('shortcut-1').value = shortcuts['save-current-video'];
  document.getElementById('shortcut-2').value = shortcuts['save-playlist'];
  document.getElementById('shortcut-3').value = shortcuts['subscribe-channel-new'];
  document.getElementById('shortcut-4').value = shortcuts['subscribe-channel-all'];
});

// 상태 메시지 표시
function showStatus(message, type) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  statusDiv.className = `status show ${type}`;
  
  setTimeout(() => {
    statusDiv.classList.remove('show');
  }, 3000);
}

// 저장 버튼
document.getElementById('save').addEventListener('click', () => {
  const webhookUrl = document.getElementById('webhook-url').value.trim();
  
  const shortcuts = {
    'save-current-video': document.getElementById('shortcut-1').value.trim(),
    'save-playlist': document.getElementById('shortcut-2').value.trim(),
    'subscribe-channel-new': document.getElementById('shortcut-3').value.trim(),
    'subscribe-channel-all': document.getElementById('shortcut-4').value.trim()
  };
  
  // 단축키 형식 검증
  const shortcutPattern = /^(Ctrl|Alt|Command)\+Shift\+[A-Z]$/i;
  for (const [key, value] of Object.entries(shortcuts)) {
    if (!shortcutPattern.test(value)) {
      showStatus(`❌ 올바르지 않은 단축키 형식: ${value}`, 'error');
      return;
    }
  }
  
  // 저장
  chrome.storage.sync.set({ webhookUrl, shortcuts }, () => {
    // 단축키 업데이트
    for (const [command, shortcut] of Object.entries(shortcuts)) {
      chrome.commands.update({
        name: command,
        shortcut: shortcut
      });
    }
    
    showStatus('✅ 설정이 저장되었습니다', 'success');
  });
});

// 초기화 버튼
document.getElementById('reset').addEventListener('click', () => {
  if (confirm('모든 설정을 초기화하시겠습니까?')) {
    document.getElementById('webhook-url').value = DEFAULT_SETTINGS.webhookUrl;
    document.getElementById('shortcut-1').value = DEFAULT_SETTINGS.shortcuts['save-current-video'];
    document.getElementById('shortcut-2').value = DEFAULT_SETTINGS.shortcuts['save-playlist'];
    document.getElementById('shortcut-3').value = DEFAULT_SETTINGS.shortcuts['subscribe-channel-new'];
    document.getElementById('shortcut-4').value = DEFAULT_SETTINGS.shortcuts['subscribe-channel-all'];
    
    showStatus('✅ 기본값으로 초기화되었습니다', 'success');
  }
});
