console.log('Background script 시작됨');

// 단축키 명령 리스너
chrome.commands.onCommand.addListener((command) => {
  console.log('단축키 실행:', command);
  
  if (command === 'auto-fill-all') {
    autoFillAllData();
  } else {
    // 기존 개별 복사 명령
    chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
      if (tabs[0]) {
        chrome.tabs.sendMessage(tabs[0].id, {command: command});
      }
    });
  }
});

// 메시지 리스너 추가
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('Background가 메시지 받음:', request);
  
  if (request.command === 'auto-fill-all') {
    autoFillAllData();
    sendResponse({ success: true });
  }
  
  return true;
});

// 자동 입력 메인 함수
async function autoFillAllData() {
  try {
    console.log('=== 자동 입력 시작 ===');
    
    // 1. 현재 활성 탭(쇼핑커넥트)에서 데이터 수집
    const [sourceTab] = await chrome.tabs.query({ active: true, currentWindow: true });
    console.log('현재 탭:', sourceTab);
    
    if (!sourceTab) {
      showError('현재 탭을 찾을 수 없습니다.');
      return;
    }
    
    console.log('데이터 수집 시작...');
    const response = await chrome.tabs.sendMessage(sourceTab.id, { action: 'getAllData' });
    console.log('수집 응답:', response);
    
    if (!response.success) {
      showError('데이터 수집 실패: ' + response.error);
      return;
    }
    
    console.log('수집된 데이터:', response.data);
    
    // 2. advercoder 탭 찾기
    console.log('애드버코더 탭 검색 중...');
    const tabs = await chrome.tabs.query({ url: "https://advercoder.com/project/nsc*" });
    console.log('찾은 탭들:', tabs);
    
    if (tabs.length === 0) {
      showError('애드버코더 탭을 찾을 수 없습니다.\nhttps://advercoder.com/project/nsc 탭을 열어주세요.');
      return;
    }
    
    const targetTab = tabs[0];
    console.log('목표 탭 찾음:', targetTab.id);
    
    // 3. 목표 탭으로 전환
    console.log('탭 전환 중...');
    await chrome.tabs.update(targetTab.id, { active: true });
    await chrome.windows.update(targetTab.windowId, { focused: true });
    
    // 잠시 대기 (탭 전환 시간)
    await sleep(500);
    
    // 4. 목표 탭에 데이터 입력
    console.log('데이터 입력 시작...');
    const fillResult = await chrome.tabs.sendMessage(targetTab.id, {
      action: 'fillAdvercoder',
      data: response.data
    });
    console.log('입력 결과:', fillResult);
    
    if (fillResult.success) {
      // 성공 알림
      chrome.notifications.create({
        type: 'basic',
        iconUrl: 'icon.png',
        title: '자동 입력 완료!',
        message: '상품 정보가 성공적으로 입력되었습니다.'
      });
      console.log('✅ 자동 입력 완료!');
    } else {
      showError('입력 실패: ' + fillResult.error);
    }
    
  } catch (error) {
    console.error('자동화 오류:', error);
    showError('오류 발생: ' + error.message);
  }
}

function showError(message) {
  console.error('에러:', message);
  chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icon.png',
    title: '오류 발생',
    message: message
  });
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

console.log('Background script 준비 완료');
