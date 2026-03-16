// background.js - 네이버 쇼핑커넥트 TOP 50 확장 프로그램
// 버전: 3.7

console.log('[Background] 네이버 쇼핑커넥트 TOP 50 백그라운드 스크립트 로드됨');

// 메시지 리스너 - 모든 액션 처리
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[TOP 50] Background가 메시지 받음:', request.action);
  
  // 1. 블로그 검색 API 호출 처리 (CORS 우회)
  if (request.action === 'searchBlog') {
    const { query, clientId, clientSecret } = request;
    
    fetch(`https://openapi.naver.com/v1/search/blog.json?query=${encodeURIComponent(query)}&display=100&sort=date`, {
      method: 'GET',
      headers: {
        'X-Naver-Client-Id': clientId,
        'X-Naver-Client-Secret': clientSecret
      }
    })
    .then(response => response.json())
    .then(data => {
      console.log(`[블로그 검색 성공] "${query}" → ${data.total}건`);
      sendResponse({ success: true, data: data });
    })
    .catch(error => {
      console.error(`[블로그 검색 실패] "${query}":`, error);
      sendResponse({ success: false, error: error.message });
    });
    
    return true; // 비동기 응답 대기
  }
  
  // 2. 애드버코더 자동화 실행
  if (request.action === 'autoAdvercoder') {
    const productLink = request.productLink;
    console.log('[애드버코더 자동화] 시작:', productLink);
    
    // 2-1. 상품 상세 페이지를 새 탭으로 열기 (비활성 상태)
    chrome.tabs.create({ url: productLink, active: false }, (productTab) => {
      console.log('[애드버코더 자동화] 상품 탭 열림:', productTab.id);
      
      // 2-2. 3초 대기 후 상품 정보 추출
      setTimeout(() => {
        chrome.tabs.sendMessage(productTab.id, { action: 'extractProductInfo' }, (productInfo) => {
          if (chrome.runtime.lastError) {
            console.error('[애드버코더 자동화] 상품 정보 추출 실패:', chrome.runtime.lastError.message);
            chrome.tabs.remove(productTab.id);
            sendResponse({ success: false, error: '상품 정보 추출 실패' });
            return;
          }
          
          console.log('[애드버코더 자동화] 상품 정보 추출 완료:', productInfo);
          
          // 2-3. 애드버코더 탭 찾기
          chrome.tabs.query({ url: 'https://advercoder.com/project/nsc*' }, (tabs) => {
            if (tabs.length === 0) {
              console.error('[애드버코더 자동화] 애드버코더 탭을 찾을 수 없습니다.');
              chrome.tabs.remove(productTab.id);
              sendResponse({ success: false, error: '애드버코더 탭을 열어주세요' });
              return;
            }
            
            const advercoderTab = tabs[0];
            console.log('[애드버코더 자동화] 애드버코더 탭 찾음:', advercoderTab.id);
            
            // 2-4. 애드버코더 탭 활성화
            chrome.tabs.update(advercoderTab.id, { active: true }, () => {
              console.log('[애드버코더 자동화] 애드버코더 탭 활성화 완료');
              
              // 2-5. 폼 자동 입력
              chrome.tabs.sendMessage(advercoderTab.id, {
                action: 'auto-fill-all',
                data: productInfo
              }, (fillResponse) => {
                if (chrome.runtime.lastError) {
                  console.error('[애드버코더 자동화] 폼 입력 실패:', chrome.runtime.lastError.message);
                  chrome.tabs.remove(productTab.id);
                  sendResponse({ success: false, error: '폼 입력 실패' });
                  return;
                }
                
                console.log('[애드버코더 자동화] 폼 입력 완료:', fillResponse);
                
                // 2-6. 상품 탭 닫기
                chrome.tabs.remove(productTab.id, () => {
                  console.log('[애드버코더 자동화] 상품 탭 닫힘');
                  
                  // 2-7. 완료 알림
                  chrome.notifications.create({
                    type: 'basic',
                    iconUrl: 'icon48.png',
                    title: '애드버코더 자동화 완료',
                    message: `${productInfo.name || '상품'} 정보가 입력되었습니다.`
                  });
                  
                  sendResponse({ success: true });
                });
              });
            });
          });
        });
      }, 3000);
    });
    
    return true; // 비동기 응답 대기
  }
  
  // 3. 새 탭 열기
  if (request.action === 'openProductTab') {
    chrome.tabs.create({ url: request.url, active: false }, (tab) => {
      console.log('[새 탭 열림]', tab.id, request.url);
      sendResponse({ success: true, tabId: tab.id });
    });
    return true;
  }
  
  // 4. 탭 닫기
  if (request.action === 'closeTab') {
    chrome.tabs.remove(request.tabId, () => {
      console.log('[탭 닫힘]', request.tabId);
      sendResponse({ success: true });
    });
    return true;
  }
  
  // 5. 애드버코더 탭 찾기
  if (request.action === 'findAdvercoderTab') {
    chrome.tabs.query({ url: 'https://advercoder.com/project/nsc*' }, (tabs) => {
      if (tabs.length > 0) {
        console.log('[애드버코더 탭 찾음]', tabs[0].id);
        sendResponse({ success: true, tabId: tabs[0].id });
      } else {
        console.log('[애드버코더 탭 없음]');
        sendResponse({ success: false, error: '애드버코더 탭을 찾을 수 없습니다.' });
      }
    });
    return true;
  }
  
  // 6. 탭 활성화
  if (request.action === 'activateTab') {
    chrome.tabs.update(request.tabId, { active: true }, () => {
      console.log('[탭 활성화]', request.tabId);
      sendResponse({ success: true });
    });
    return true;
  }
  
  // 7. 탭에 메시지 전송
  if (request.action === 'sendMessageToTab') {
    chrome.tabs.sendMessage(request.tabId, request.message, (response) => {
      if (chrome.runtime.lastError) {
        console.error('[탭 메시지 전송 실패]', chrome.runtime.lastError.message);
        sendResponse({ success: false, error: chrome.runtime.lastError.message });
      } else {
        console.log('[탭 메시지 전송 성공]', response);
        sendResponse({ success: true, response: response });
      }
    });
    return true;
  }
  
  // 8. 최신 상품 탭 찾기 (새로 열린 탭)
  if (request.action === 'findLatestProductTab') {
    chrome.tabs.query({ url: '*://smartstore.naver.com/*' }, (tabs) => {
      if (tabs.length > 0) {
        // 가장 최근에 열린 탭 찾기
        const latestTab = tabs.sort((a, b) => b.id - a.id)[0];
        console.log('[최신 상품 탭 찾음]', latestTab.id);
        sendResponse({ success: true, tabId: latestTab.id });
      } else {
        console.log('[상품 탭 없음]');
        sendResponse({ success: false, error: '상품 탭을 찾을 수 없습니다.' });
      }
    });
    return true;
  }
  
  // 9. 탭 ID로 상품 정보 추출 및 애드버코더 자동화
  if (request.action === 'autoAdvercoderWithTab') {
    const productTabId = request.tabId;
    console.log('[애드버코더 자동화 with Tab] 시작:', productTabId);
    
    // 2초 대기 후 상품 정보 추출
    setTimeout(() => {
      chrome.tabs.sendMessage(productTabId, { action: 'extractProductInfo' }, (productInfo) => {
        if (chrome.runtime.lastError) {
          console.error('[애드버코더 자동화] 상품 정보 추출 실패:', chrome.runtime.lastError.message);
          sendResponse({ success: false, error: '상품 정보 추출 실패' });
          return;
        }
        
        console.log('[애드버코더 자동화] 상품 정보 추출 완료:', productInfo);
        
        // 애드버코더 탭 찾기
        chrome.tabs.query({ url: 'https://advercoder.com/project/nsc*' }, (tabs) => {
          if (tabs.length === 0) {
            console.error('[애드버코더 자동화] 애드버코더 탭을 찾을 수 없습니다.');
            sendResponse({ success: false, error: '애드버코더 탭을 열어주세요' });
            return;
          }
          
          const advercoderTab = tabs[0];
          console.log('[애드버코더 자동화] 애드버코더 탭 찾음:', advercoderTab.id);
          
          // 애드버코더 탭 활성화
          chrome.tabs.update(advercoderTab.id, { active: true }, () => {
            console.log('[애드버코더 자동화] 애드버코더 탭 활성화 완료');
            
            // 폼 자동 입력
            chrome.tabs.sendMessage(advercoderTab.id, {
              action: 'auto-fill-all',
              data: productInfo
            }, (fillResponse) => {
              if (chrome.runtime.lastError) {
                console.error('[애드버코더 자동화] 폼 입력 실패:', chrome.runtime.lastError.message);
                sendResponse({ success: false, error: '폼 입력 실패' });
                return;
              }
              
              console.log('[애드버코더 자동화] 폼 입력 완료:', fillResponse);
              
              // 상품 탭 닫기
              chrome.tabs.remove(productTabId, () => {
                console.log('[애드버코더 자동화] 상품 탭 닫힘');
                
                // 완료 알림
                chrome.notifications.create({
                  type: 'basic',
                  iconUrl: 'icon48.png',
                  title: '애드버코더 자동화 완료',
                  message: `${productInfo.name || '상품'} 정보가 입력되었습니다.`
                });
                
                sendResponse({ success: true });
              });
            });
          });
        });
      });
    }, 2000);
    
    return true; // 비동기 응답 대기
  }
});

console.log('[Background] 메시지 리스너 등록 완료');
