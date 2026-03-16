// ============================================
// 상품 정보 추출기 v3.2 - Content Script
// ============================================

console.log('Content script 로드됨 - URL:', window.location.href);

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

// 링크 URL 가져오기 (개선된 버전 - 클립보드 포커스 문제 해결)
async function getLinkUrl() {
  console.log('링크 URL 가져오기 시작...');
  
  // 방법 1: 페이지에서 공유 링크 input 요소 찾기
  const linkSelectors = [
    'input[value*="naver.me"]',
    'input[value*="smartstore.naver"]',
    'input[value*="shopping.naver"]',
    'input[readonly][value^="http"]',
    'input.share-link',
    'input[class*="link"]'
  ];
  
  for (const selector of linkSelectors) {
    try {
      const element = document.querySelector(selector);
      if (element && element.value && element.value.startsWith('http')) {
        console.log('링크 input에서 URL 찾음:', element.value);
        return element.value;
      }
    } catch (e) {
      continue;
    }
  }
  
  // 방법 2: 버튼 클릭 후 클립보드 읽기 (포커스 문제 해결)
  try {
    // 클립보드 읽기 전 상태 저장
    let beforeClipboard = '';
    try {
      window.focus();
      beforeClipboard = await navigator.clipboard.readText();
      console.log('클립보드 초기값:', beforeClipboard);
    } catch (e) {
      console.log('초기 클립보드 읽기 실패 (무시):', e.message);
    }
    
    // 버튼 클릭
    const clicked = clickLinkCopyButton();
    console.log('링크 복사 버튼 클릭:', clicked);
    
    if (clicked) {
      // 클릭 후 대기
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // 여러 번 재시도
      for (let i = 0; i < 5; i++) {
        try {
          // 페이지에 포커스 재설정
          window.focus();
          document.body.click();
          
          await new Promise(resolve => setTimeout(resolve, 200));
          
          const clipboardText = await navigator.clipboard.readText();
          console.log(`클립보드 읽기 시도 ${i + 1}:`, clipboardText);
          
          // 클립보드가 변경되었고 유효한 URL이면 반환
          if (clipboardText && 
              clipboardText !== beforeClipboard && 
              clipboardText.startsWith('http')) {
            console.log('✅ 링크 복사 성공:', clipboardText);
            return clipboardText;
          }
        } catch (e) {
          console.log(`클립보드 읽기 시도 ${i + 1} 실패:`, e.message);
          await new Promise(resolve => setTimeout(resolve, 300));
        }
      }
    }
  } catch (error) {
    console.log('링크 가져오기 오류:', error);
  }
  
  // 방법 3: 현재 페이지 URL 반환
  console.log('📍 현재 페이지 URL 사용:', window.location.href);
  return window.location.href;
}

// ============ 모든 데이터 한번에 수집 ============
async function getAllData() {
  try {
    console.log('=== 데이터 수집 시작 ===');
    
    const productName = getProductName();
    console.log('상품명:', productName);
    
    const imageUrls = getImageUrls();
    console.log('이미지 URLs:', imageUrls);
    
    const productLink = await getLinkUrl();
    console.log('상품 링크:', productLink);
    
    if (!productName) {
      return { success: false, error: '상품명을 찾을 수 없습니다.' };
    }
    
    if (!imageUrls) {
      return { success: false, error: '이미지를 찾을 수 없습니다.' };
    }
    
    return {
      success: true,
      data: {
        name: productName,
        link: productLink,
        images: imageUrls
      }
    };
  } catch (error) {
    console.error('데이터 수집 오류:', error);
    return { success: false, error: error.message };
  }
}

// ============ 이미지 개수 계산 ============
function calculateImageCount(imageUrls) {
  const imageCount = imageUrls.split('\n').filter(url => url.trim()).length;
  console.log('추출된 이미지 개수:', imageCount);
  
  let targetCount;
  if (imageCount <= 6) {
    targetCount = Math.min(imageCount + 2, 8);
    targetCount = Math.max(targetCount, 3);
  } else {
    targetCount = 8;
  }
  
  console.log('설정할 생성 이미지 개수:', targetCount);
  return targetCount;
}

// ============ 슬라이더 제어 (클릭 방식) ============
async function setSliderValue(count) {
    try {
      console.log('슬라이더 설정 시도:', count, '개');
      
      // 슬라이더 컨테이너 찾기
      const sliderContainer = document.querySelector('.chakra-slider');
      if (!sliderContainer) {
        console.error('슬라이더를 찾을 수 없습니다');
        return false;
      }
      
      // 슬라이더 트랙 (클릭 가능한 영역)
      const sliderTrack = sliderContainer.querySelector('.chakra-slider__track');
      if (!sliderTrack) {
        console.error('슬라이더 트랙을 찾을 수 없습니다');
        return false;
      }
      
      const rect = sliderTrack.getBoundingClientRect();
      
      // count 값을 1-10 범위로 제한
      count = Math.max(1, Math.min(10, count));
      
      // 1-10 범위를 0-1 비율로 변환
      const ratio = (count - 1) / 9;
      
      // 클릭할 위치 계산
      const clickX = rect.left + (rect.width * ratio);
      const clickY = rect.top + (rect.height / 2);
      
      console.log('클릭 위치:', { count, ratio, clickX, clickY, width: rect.width });
      
      // 포커스 설정
      sliderContainer.focus();
      
      // 마우스 이벤트 생성 및 발생
      const events = [
        new PointerEvent('pointerdown', {
          bubbles: true,
          cancelable: true,
          clientX: clickX,
          clientY: clickY,
          button: 0
        }),
        new MouseEvent('mousedown', {
          bubbles: true,
          cancelable: true,
          clientX: clickX,
          clientY: clickY,
          button: 0
        }),
        new PointerEvent('pointerup', {
          bubbles: true,
          cancelable: true,
          clientX: clickX,
          clientY: clickY,
          button: 0
        }),
        new MouseEvent('mouseup', {
          bubbles: true,
          cancelable: true,
          clientX: clickX,
          clientY: clickY,
          button: 0
        }),
        new MouseEvent('click', {
          bubbles: true,
          cancelable: true,
          clientX: clickX,
          clientY: clickY,
          button: 0
        })
      ];
      
      // 이벤트 순차 실행
      for (const event of events) {
        sliderTrack.dispatchEvent(event);
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      
      // 값 확인
      await new Promise(resolve => setTimeout(resolve, 200));
      const hiddenInput = sliderContainer.querySelector('input[type="hidden"]');
      const finalValue = hiddenInput ? hiddenInput.value : '?';
      console.log('슬라이더 최종 값:', finalValue);
      
      return true;
      
    } catch (error) {
      console.error('슬라이더 설정 오류:', error);
      return false;
    }
  }

// ============ Advercoder 사이트에 데이터 입력 ============
async function fillAdvercoderForm(data) {
  try {
    console.log('입력할 데이터:', data);
    
    // Helper function: 요소가 나타날 때까지 대기
    function waitForElement(selector, timeout = 5000) {
      return new Promise((resolve, reject) => {
        const element = document.querySelector(selector);
        if (element) {
          resolve(element);
          return;
        }
        
        const observer = new MutationObserver(() => {
          const element = document.querySelector(selector);
          if (element) {
            observer.disconnect();
            resolve(element);
          }
        });
        
        observer.observe(document.body, {
          childList: true,
          subtree: true
        });
        
        setTimeout(() => {
          observer.disconnect();
          reject(new Error(`요소를 찾을 수 없습니다: ${selector}`));
        }, timeout);
      });
    }
    
    // Helper function: 값 입력 및 이벤트 트리거
    function setInputValue(element, value) {
      console.log('입력:', element.id || element.className, '→', value.substring(0, 50));
      
      const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLInputElement.prototype,
        'value'
      ).set;
      const nativeTextareaValueSetter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype,
        'value'
      ).set;
      
      if (element.tagName === 'INPUT') {
        nativeInputValueSetter.call(element, value);
      } else if (element.tagName === 'TEXTAREA') {
        nativeTextareaValueSetter.call(element, value);
      } else {
        element.value = value;
      }
      
      // React 이벤트 트리거
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
      element.dispatchEvent(new Event('blur', { bubbles: true }));
    }
    
    const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));
    
    // 모든 input 요소 찾기
    console.log('모든 input 요소 찾는 중...');
    await sleep(500); // 페이지 로딩 대기
    
    const allInputs = document.querySelectorAll('input.chakra-input');
    console.log('찾은 input 개수:', allInputs.length);
    
    // 각 input의 placeholder나 label로 구분
    const inputs = {
      name: null,
      link: null
    };
    
    // Input 요소 식별
    allInputs.forEach((input, index) => {
      const placeholder = input.placeholder || '';
      const label = input.closest('.chakra-form-control')?.querySelector('label')?.textContent || '';
      
      console.log(`Input ${index}:`, {
        id: input.id,
        placeholder: placeholder,
        label: label,
        value: input.value
      });
      
      // 상품명 필드 찾기
      if (placeholder.includes('이름') || placeholder.includes('제품') || placeholder.includes('상품') ||
          label.includes('이름') || label.includes('제품') || label.includes('상품')) {
        inputs.name = input;
        console.log('→ 상품명 필드로 지정');
      }
      // 링크 필드 찾기
      else if (placeholder.includes('링크') || placeholder.includes('URL') || placeholder.includes('url') ||
               label.includes('링크') || label.includes('URL')) {
        inputs.link = input;
        console.log('→ 링크 필드로 지정');
      }
    });
    
    // 못 찾았으면 순서대로 할당
    if (!inputs.name && allInputs.length >= 1) {
      inputs.name = allInputs[0];
      console.log('순서로 상품명 필드 지정: input[0]');
    }
    if (!inputs.link && allInputs.length >= 2) {
      inputs.link = allInputs[1];
      console.log('순서로 링크 필드 지정: input[1]');
    }
    
    // 1. 이름 입력
    if (inputs.name) {
      console.log('1. 상품명 입력...');
      setInputValue(inputs.name, data.name);
      await sleep(300);
      showNotification('✅ 1/5: 상품명 입력 완료', true);
    } else {
      console.error('상품명 입력 필드를 찾을 수 없습니다');
    }
    
    // 2. 링크 입력
    if (inputs.link) {
      console.log('2. 링크 입력...');
      setInputValue(inputs.link, data.link);
      await sleep(300);
      showNotification('✅ 2/5: 링크 입력 완료', true);
    } else {
      console.error('링크 입력 필드를 찾을 수 없습니다');
    }
    
    // 3. 스위치 켜기
    console.log('3. 스위치 켜기...');
    try {
      const switchTrack = await waitForElement('span.chakra-switch__track');
      const switchLabel = switchTrack.closest('label.chakra-switch');
      
      const checkbox = switchLabel.querySelector('input[type="checkbox"]');
      const isChecked = checkbox?.checked;
      
      console.log('스위치 현재 상태:', isChecked);
      
      if (!isChecked) {
        switchTrack.click();
        await sleep(300);
        console.log('스위치 클릭 완료');
      }
      showNotification('✅ 3/5: 스위치 활성화 완료', true);
    } catch (error) {
      console.log('스위치 처리 중 오류 (무시):', error);
    }
    
    // 4. 이미지 URL 입력
    console.log('4. 이미지 URL 입력...');
    try {
      const imageTextarea = await waitForElement('textarea.chakra-textarea');
      console.log('Textarea 찾음:', imageTextarea);
      setInputValue(imageTextarea, data.images);
      await sleep(300);
      showNotification('✅ 4/5: 이미지 URL 입력 완료', true);
    } catch (error) {
      console.error('이미지 URL 입력 실패:', error);
    }
    
    // 4.5. 생성 이미지 개수 설정
    console.log('4.5. 생성 이미지 개수 설정...');
    try {
      const targetCount = calculateImageCount(data.images);
      await sleep(500); // 이 줄 추가!
      const sliderSet = await setSliderValue(targetCount); // await 추가!
      if (sliderSet) {
        await sleep(500); // 300 → 500으로 변경!
        showNotification(`✅ 생성 이미지 ${targetCount}개로 설정`, true);
      }
    } catch (error) {
      console.log('슬라이더 설정 실패 (무시):', error);
    }
    
    // 5. 완료 버튼 클릭
    console.log('5. 완료 버튼 찾는 중...');
    let finalButton = null;
    const buttons = document.querySelectorAll('button.chakra-button');
    console.log('찾은 버튼 개수:', buttons.length);
    
    buttons.forEach((btn, index) => {
      console.log(`버튼 ${index}:`, btn.textContent.trim());
    });
    
    for (let btn of buttons) {
      const text = btn.textContent.trim();
      if (text.includes('이 제품 리스트에 추가') || text.includes('추가') || text.includes('➕')) {
        finalButton = btn;
        console.log('완료 버튼 찾음:', text);
        break;
      }
    }
    
    if (finalButton) {
      finalButton.click();
      await sleep(500);
      showNotification('✅ 5/5: 리스트 추가 완료!', true);
    } else {
      console.warn('추가 버튼을 찾을 수 없습니다');
      showNotification('⚠️ 추가 버튼을 찾을 수 없습니다', false);
    }
    
    return { success: true };
    
  } catch (error) {
    console.error('입력 오류:', error);
    showNotification('❌ 입력 실패: ' + error.message, false);
    return { success: false, error: error.message };
  }
}

// ============ 메시지 리스너 ============
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  try {
    console.log('메시지 받음:', request);
    
    // Ping 응답
    if (request.action === 'ping') {
      sendResponse({ success: true, message: 'pong' });
      return true;
    }
    
    // 개별 복사 기능
    if (request.action === 'copyName') {
      const productName = getProductName();
      sendResponse({ 
        success: !!productName, 
        data: productName,
        error: productName ? null : '상품명을 찾을 수 없습니다.'
      });
    }
    
    else if (request.action === 'copyImages') {
      const imageUrls = getImageUrls();
      sendResponse({ 
        success: !!imageUrls, 
        data: imageUrls,
        error: imageUrls ? null : '이미지를 찾을 수 없습니다.'
      });
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
      return true;
    }
    
    // 모든 데이터 수집
    else if (request.action === 'getAllData') {
      getAllData().then(result => {
        sendResponse(result);
      }).catch(error => {
        sendResponse({ success: false, error: error.message });
      });
      return true;
    }
    
    // Advercoder 폼 채우기
    else if (request.action === 'fillAdvercoder') {
      fillAdvercoderForm(request.data).then(result => {
        sendResponse(result);
      }).catch(error => {
        sendResponse({ success: false, error: error.message });
      });
      return true;
    }
    
    // 단축키 처리
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

// ============ 단축키 처리 함수 ============
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

console.log('Content script 준비 완료');