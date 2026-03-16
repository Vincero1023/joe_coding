// 알림 표시 함수
function showNotification(message, isSuccess = true) {
  const notification = document.createElement('div');
  notification.textContent = message;
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    background: ${isSuccess ? '#4CAF50' : '#f44336'};
    color: white;
    padding: 15px 25px;
    border-radius: 5px;
    z-index: 999999;
    font-size: 14px;
    font-weight: bold;
    box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    animation: slideIn 0.3s ease-out;
  `;
  
  // 애니메이션 추가
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from {
        transform: translateX(400px);
        opacity: 0;
      }
      to {
        transform: translateX(0);
        opacity: 1;
      }
    }
  `;
  document.head.appendChild(style);
  
  document.body.appendChild(notification);
  setTimeout(() => {
    notification.style.transition = 'all 0.3s';
    notification.style.opacity = '0';
    notification.style.transform = 'translateX(400px)';
    setTimeout(() => notification.remove(), 300);
  }, 2000);
}

// 클립보드에 복사하는 함수
async function copyToClipboard(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch (error) {
    console.error('클립보드 복사 실패:', error);
    return false;
  }
}

// 상품명 추출
function getProductName() {
  const productName = document.querySelector('.ProductDetail_title___k3l6');
  if (productName) {
    return productName.textContent.trim();
  }
  return null;
}

// 이미지 URL 추출
function getImageUrls() {
  const imageSrcs = Array.from(document.querySelectorAll('.ProductDetail_img__TLpyf img'))
    .map(img => {
      let url = img.src || img.getAttribute('data-src');
      if (url && url.includes('data-src=')) {
        url = url.replace(/data-src="([^"]+)"/, '$1');
      }
      return url;
    })
    .filter(src => src && src.startsWith('http'));
  
  return imageSrcs.length > 0 ? imageSrcs.join('\n') : null;
}

// 링크 복사 버튼 클릭
function clickLinkCopyButton() {
  // 여러 가능한 선택자로 링크 복사 버튼 찾기
  const possibleSelectors = [
    'button:contains("링크 복사")',
    'button:contains("링크복사")',
    'button:contains("링크 발급")',
    'button:contains("링크발급")',
    '[class*="link"][class*="copy"]',
    '[class*="LinkCopy"]',
    'button[class*="Button"]'
  ];
  
  // 모든 버튼 검색
  const buttons = document.querySelectorAll('button');
  for (let button of buttons) {
    const text = button.textContent.trim();
    if (text.includes('링크') && (text.includes('복사') || text.includes('발급'))) {
      button.click();
      return true;
    }
  }
  
  return false;
}

// 링크 URL 가져오기 (버튼 클릭 후 클립보드 확인)
async function getLinkUrl() {
  // 먼저 버튼 클릭 시도
  const clicked = clickLinkCopyButton();
  
  if (clicked) {
    // 버튼 클릭 후 잠시 대기 (클립보드에 복사되는 시간)
    await new Promise(resolve => setTimeout(resolve, 300));
    
    // 클립보드에서 읽기 시도
    try {
      const clipboardText = await navigator.clipboard.readText();
      if (clipboardText && clipboardText.startsWith('http')) {
        return clipboardText;
      }
    } catch (e) {
      console.log('클립보드 읽기 실패:', e);
    }
  }
  
  // 버튼 클릭 실패 시 현재 URL 반환
  return window.location.href;
}

// 메시지 리스너 (팝업에서의 요청 처리)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  try {
    if (request.action === 'copyName') {
      const productName = getProductName();
      
      if (productName) {
        sendResponse({ 
          success: true, 
          data: productName
        });
      } else {
        sendResponse({ 
          success: false, 
          error: '상품명을 찾을 수 없습니다.' 
        });
      }
    }
    
    else if (request.action === 'copyImages') {
      const imageUrls = getImageUrls();
      
      if (imageUrls) {
        sendResponse({ 
          success: true, 
          data: imageUrls
        });
      } else {
        sendResponse({ 
          success: false, 
          error: '이미지를 찾을 수 없습니다.' 
        });
      }
    }
    
    else if (request.action === 'copyLink') {
      getLinkUrl().then(url => {
        sendResponse({ 
          success: true, 
          data: url
        });
      }).catch(error => {
        sendResponse({ 
          success: false, 
          error: error.message 
        });
      });
      return true; // 비동기 응답을 위해 true 반환
    }
    
    // 단축키에서의 요청 처리
    else if (request.command) {
      handleShortcut(request.command);
    }
  } catch (error) {
    sendResponse({ 
      success: false, 
      error: error.message 
    });
  }
  
  return true;
});

// 단축키 처리 함수
async function handleShortcut(command) {
  let text = null;
  let label = '';
  
  switch(command) {
    case 'copy-name':
      text = getProductName();
      label = '상품명';
      break;
    case 'copy-images':
      text = getImageUrls();
      label = '이미지 URL';
      break;
    case 'copy-link':
      text = await getLinkUrl();
      label = '링크';
      break;
  }
  
  if (text) {
    const success = await copyToClipboard(text);
    if (success) {
      showNotification(`✅ ${label} 복사 완료!`, true);
    } else {
      showNotification(`❌ ${label} 복사 실패`, false);
    }
  } else {
    showNotification(`❌ ${label}을(를) 찾을 수 없습니다`, false);
  }
}
