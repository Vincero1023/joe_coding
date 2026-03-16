console.log('Popup script 시작');

// 상태 체크 함수
async function checkConnection() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    
    if (!tab) {
      throw new Error('활성 탭을 찾을 수 없습니다.');
    }
    
    // Content script가 주입되었는지 확인
    try {
      await chrome.tabs.sendMessage(tab.id, { action: 'ping' });
      return { success: true, tab: tab };
    } catch (error) {
      // Content script가 없으면 주입
      console.log('Content script 주입 시도...');
      await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        files: ['content.js']
      });
      
      // 잠시 대기 후 재시도
      await new Promise(resolve => setTimeout(resolve, 500));
      return { success: true, tab: tab };
    }
  } catch (error) {
    console.error('연결 체크 실패:', error);
    return { success: false, error: error.message };
  }
}

// 개별 복사 함수
async function copyToClipboard(type) {
  try {
    const connectionCheck = await checkConnection();
    
    if (!connectionCheck.success) {
      alert('오류: ' + connectionCheck.error);
      return;
    }
    
    const tab = connectionCheck.tab;
    
    const response = await chrome.tabs.sendMessage(tab.id, { action: type });
    
    if (response && response.success) {
      await navigator.clipboard.writeText(response.data);
      
      const btnId = type === 'copyName' ? 'copyName' : type === 'copyImages' ? 'copyImages' : 'copyLink';
      const btn = document.getElementById(btnId);
      btn.classList.add('success');
      btn.querySelector('.label').textContent = '✅ 복사 완료!';
      
      setTimeout(() => {
        window.close();
      }, 800);
    } else {
      alert(response ? response.error : '응답이 없습니다. 페이지를 새로고침 해주세요.');
    }
  } catch (error) {
    console.error('복사 오류:', error);
    alert('오류: ' + error.message + '\n페이지를 새로고침(F5) 후 다시 시도해주세요.');
  }
}

// 자동 입력 실행
document.getElementById('autoFillAll').addEventListener('click', async () => {
  try {
    console.log('자동 입력 시작');
    
    const connectionCheck = await checkConnection();
    
    if (!connectionCheck.success) {
      alert('오류: ' + connectionCheck.error);
      return;
    }
    
    // 직접 background에 메시지 전송
    chrome.runtime.sendMessage({ command: 'auto-fill-all' }, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Background 통신 오류:', chrome.runtime.lastError);
        alert('오류: ' + chrome.runtime.lastError.message);
      }
    });
    
    window.close();
    
  } catch (error) {
    console.error('자동 입력 오류:', error);
    alert('오류: ' + error.message);
  }
});

document.getElementById('copyName').addEventListener('click', () => copyToClipboard('copyName'));
document.getElementById('copyImages').addEventListener('click', () => copyToClipboard('copyImages'));
document.getElementById('copyLink').addEventListener('click', () => copyToClipboard('copyLink'));

console.log('Popup script 준비 완료');