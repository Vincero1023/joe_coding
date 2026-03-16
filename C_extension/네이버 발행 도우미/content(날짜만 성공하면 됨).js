// === 네이버 블로그 스마트 발행기 (Final Chaining Fix) ===

// ----------------------------------------------------
// [0] 유틸리티
// ----------------------------------------------------
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// 텍스트로 요소 찾기 (Top Frame)
function findElementByText(text) {
    const doc = window.top.document; 
    const cleanTarget = text.replace(/\s/g, '');
    const all = doc.querySelectorAll('label, span, strong, b, div, p, h3, h4, li, a, button');
    
    for (let el of all) {
        if (el.innerText.replace(/\s/g, '').includes(cleanTarget) && el.offsetParent !== null) {
            if (el.childElementCount === 0) return el;
        }
    }
    return null;
}

// 탭(Tab) 이동: 기준 요소 바로 다음의 '입력 가능 요소' 반환
function getNextTabbable(anchor) {
    if (!anchor) return null;
    const doc = window.top.document;
    
    // 탭 가능한 모든 요소 (화면에 보이는 것만)
    const all = Array.from(doc.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])'))
        .filter(el => el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled);

    for (let el of all) {
        if (anchor.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) {
            return el;
        }
    }
    return null;
}

// 키보드 누르기
function pressKey(element, key = 'Enter') {
    if (!element) return;
    element.focus();

    let code = 13;
    if (key === 'Space') code = 32;
    if (key === 'ArrowLeft') code = 37;
    if (key === 'ArrowRight') code = 39;

    const opts = { key: key, code: key, keyCode: code, which: code, bubbles: true, cancelable: true, view: window };
    
    element.dispatchEvent(new KeyboardEvent('keydown', opts));
    element.dispatchEvent(new KeyboardEvent('keypress', opts));
    element.dispatchEvent(new KeyboardEvent('keyup', opts));
    
    if(key === 'Enter' || key === 'Space') element.click();
}

function setNativeValue(element, value) {
  if (!element || !(element instanceof window.HTMLInputElement)) {
      console.error("❌ 입력 가능한 요소가 아닙니다:", element);
      return;
  }
  
  const proto = window.HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
  if (setter) setter.call(element, value);
  else element.value = value;
  element.dispatchEvent(new Event('input', { bubbles: true }));
}

// ----------------------------------------------------
// [1] 실행 리스너
// ----------------------------------------------------
document.addEventListener('keydown', (e) => {
  if (e.altKey && e.shiftKey && (e.key === 'p' || e.key === 'P')) {
    e.preventDefault();
    window.top.postMessage({ type: "REQ_PUBLISH_EXTENSION" }, "*");
  }
});

window.addEventListener("message", (event) => {
  if (event.data && event.data.type === "REQ_PUBLISH_EXTENSION" && window === window.top) {
      runSequence();
  }
});

chrome.runtime.onMessage.addListener((request) => {
  if (request.action === "TRIGGER_PUBLISH_BY_POPUP" && window === window.top) {
      runSequence();
  }
});

// ----------------------------------------------------
// [2] 메인 로직
// ----------------------------------------------------
async function runSequence() {
  const topDoc = window.top.document;

  // [1] 발행 버튼
  let publishBtn = topDoc.querySelector('.btn_publish');
  if (!publishBtn) {
      const allBtns = topDoc.querySelectorAll('button');
      for(let b of allBtns) {
          if(b.innerText.trim() === '발행' && b.offsetParent !== null) { publishBtn = b; break; }
      }
  }
  if (!publishBtn) return alert("❌ 발행 버튼을 못 찾았습니다.");

  console.log("⌨️ [1] 발행 버튼 엔터");
  pressKey(publishBtn, 'Enter');

  // 설정 로드
  const data = await chrome.storage.local.get(['settings', 'currentProfile']);
  const settings = (data.settings && data.settings[data.currentProfile || 'default']) || {};
  if (!settings.category) return alert("❌ 설정 없음");

  // 날짜 계산
  const [sh, sm] = (settings.startTime || '09:00').split(':').map(Number);
  let targetDate = new Date();
  if(settings.lastScheduled) {
      const last = new Date(settings.lastScheduled);
      const interval = parseInt(settings.interval || 60);
      const variance = interval * 0.2; 
      const randomMin = (Math.random() * (variance * 2)) - variance;
      last.setMinutes(last.getMinutes() + interval + randomMin);
      targetDate = last;
  } else {
      targetDate.setHours(sh, sm);
      if(targetDate < new Date()) targetDate.setDate(targetDate.getDate() + 1);
  }
  
  // 저장
  const currentProfile = data.currentProfile || 'default';
  if(!data.settings[currentProfile]) data.settings[currentProfile] = {};
  data.settings[currentProfile].lastScheduled = targetDate.toISOString();
  await chrome.storage.local.set({ settings: data.settings });


  // [2] 팝업 대기
  console.log("⏳ 팝업 대기 (2초)...");
  await sleep(2000);

  // [3] 카테고리 설정
  const catLabel = findElementByText('카테고리');
  if (catLabel) {
      const dropdown = getNextTabbable(catLabel); // Tab 1
      if (dropdown) {
          console.log("⌨️ [2] 드롭다운 엔터");
          pressKey(dropdown, 'Enter');
          await sleep(1000);
          
          const catItem = findElementByText(settings.category);
          if (catItem) {
              console.log(`⌨️ [3] 항목 선택: ${settings.category}`);
              pressKey(catItem, 'Enter');
              console.log("⏳ 리렌더링 대기 (2.5초)...");
              await sleep(2500);
          }
      }
  }

  // [4] 예약 설정 (사용자 매뉴얼: 발행시간 -> 탭 1 -> 탭 2 -> 날짜)
  console.log("🔍 '발행 시간' 검색");
  let anchor = findElementByText('발행시간') || findElementByText('예약시간');

  if (anchor) {
      // Tab 1 (건너뜀)
      const tab1 = getNextTabbable(anchor);
      // Tab 2 (날짜 버튼)
      const dateBtn = getNextTabbable(tab1);

      if (dateBtn) {
          console.log("⌨️ [4] 날짜 버튼 발견 (Tab x2) -> 설정 시작");
          
          // 날짜 설정 로직 실행
          await setDateManual(dateBtn, targetDate);
          
          // 4. 시간 입력 (날짜 설정 후 포커스가 DateBtn에 있을 확률 높음)
          const hourInput = getNextTabbable(dateBtn); // Tab 3
          const minInput = getNextTabbable(hourInput); // Tab 4

          if (hourInput && minInput) {
              const HH = targetDate.getHours();
              const mm = Math.round(targetDate.getMinutes() / 10) * 10;
              console.log(`⌨️ [5] 시간 입력: ${HH}:${mm}`);
              
              setNativeValue(hourInput, String(HH).padStart(2,'0'));
              setNativeValue(minInput, String(mm).padStart(2,'0'));
          } else {
              console.log("⚠️ 시간 입력칸(Tab 3, 4) 탐색 실패");
          }
      } else {
          console.log("⚠️ Tab 2번 위치가 날짜 버튼이 아닙니다.");
      }
  } else {
      console.log("⚠️ '발행 시간' 글자 못 찾음");
  }

  // [5] 최종 확인
  await sleep(1000);
  const confirmMsg = `
  [설정 확인]
  카테고리: ${settings.category}
  예약시간: ${targetDate.getMonth()+1}/${targetDate.getDate()} ${targetDate.getHours()}:${Math.round(targetDate.getMinutes()/10)*10}
  
  발행할까요?`;

  if(confirm(confirmMsg)) {
      const allBtns = topDoc.querySelectorAll('button');
      let finalBtn = null;
      let maxTop = 0;
      for(let b of allBtns) {
          if(b.innerText.trim() === '발행' && !b.className.includes('btn_publish') && b.offsetParent !== null) {
              const rect = b.getBoundingClientRect();
              if(rect.top > maxTop) { maxTop = rect.top; finalBtn = b; }
          }
      }
      if(finalBtn) {
          console.log("🚀 최종 발행 엔터!");
          pressKey(finalBtn, 'Enter');
      }
  }
}

// 날짜 설정 (사용자 매뉴얼)
async function setDateManual(dateBtn, targetDate) {
    console.log("⌨️ 날짜 버튼 엔터 (달력 열기)");
    pressKey(dateBtn, 'Enter');
    await sleep(500);

    const topDoc = window.top.document;
    const prevBtn = topDoc.querySelector('.layer_calendar .btn_prev, .calendar .btn_prev');
    
    if (prevBtn) {
        console.log("⌨️ 초기화: [Space] x 3");
        prevBtn.focus();
        for(let i=0; i<3; i++) {
            pressKey(prevBtn, 'Space');
            await sleep(150);
        }
    }

    console.log("⌨️ 초기화 후 엔터");
    if(topDoc.activeElement) pressKey(topDoc.activeElement, 'Enter');
    await sleep(300);

    // 날짜 선택 (탭 이동)
    const today = new Date();
    const isToday = targetDate.getDate() === today.getDate();
    const isTomorrow = targetDate.getDate() === today.getDate() + 1;

    let tabCount = isToday ? 1 : (isTomorrow ? 2 : targetDate.getDate());
    
    console.log(`⌨️ 날짜 탭 이동 x ${tabCount}`);
    
    let currentEl = topDoc.activeElement;
    for(let i=0; i<tabCount; i++) {
        currentEl = getNextTabbable(currentEl);
        if(currentEl) currentEl.focus();
    }

    if(topDoc.activeElement) {
        pressKey(topDoc.activeElement, 'Space');
    }
    
    await sleep(300);
}