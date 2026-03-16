// DOM 요소
const feeSlider = document.getElementById('feeSlider');
const feeValue = document.getElementById('feeValue');
const discountSlider = document.getElementById('discountSlider');
const discountValue = document.getElementById('discountValue');
const priceInput = document.getElementById('priceInput');
const priceValue = document.getElementById('priceValue');

// API 요소
const apiStatus = document.getElementById('apiStatus');
const apiInputs = document.getElementById('apiInputs');
const clientIdInput = document.getElementById('clientId');
const clientSecretInput = document.getElementById('clientSecret');

// 프리셋 정의
const presets = {
  golden: { minFee: 5, minDiscount: 20, minPrice: 30000, name: '황금키워드' },
  jackpot: { minFee: 15, minDiscount: 30, minPrice: 100000, name: '한방딜' },
  steady: { minFee: 10, minDiscount: 25, minPrice: 50000, name: '스테디' },
  custom: { minFee: 10, minDiscount: 25, minPrice: 50000, name: '커스텀' }
};

let currentMode = 'and';
let currentPreset = 'custom';
let apiConnected = false;

// API 설정 토글
document.getElementById('toggleApi').addEventListener('click', () => {
  apiInputs.classList.toggle('show');
});

// API 저장
document.getElementById('saveApi').addEventListener('click', async () => {
  const clientId = clientIdInput.value.trim();
  const clientSecret = clientSecretInput.value.trim();
  
  if (!clientId || !clientSecret) {
    showStatus('⚠️ Client ID와 Secret을 모두 입력하세요', 'warning');
    return;
  }
  
  // 저장
  await chrome.storage.local.set({
    naverApiClientId: clientId,
    naverApiClientSecret: clientSecret
  });
  
  apiConnected = true;
  updateApiStatus(true);
  showStatus('✅ API 설정 저장됨', 'success');
  
  // 입력창 숨기기
  setTimeout(() => {
    apiInputs.classList.remove('show');
  }, 1000);
});

// API 테스트
document.getElementById('testApi').addEventListener('click', async () => {
  const clientId = clientIdInput.value.trim();
  const clientSecret = clientSecretInput.value.trim();
  
  if (!clientId || !clientSecret) {
    showStatus('⚠️ Client ID와 Secret을 입력하세요', 'warning');
    return;
  }
  
  showStatus('🔄 API 테스트 중...', 'info');
  
  try {
    // 테스트 검색
    const response = await fetch('https://openapi.naver.com/v1/search/blog.json?query=테스트&display=1', {
      method: 'GET',
      headers: {
        'X-Naver-Client-Id': clientId,
        'X-Naver-Client-Secret': clientSecret
      }
    });
    
    if (response.ok) {
      showStatus('✅ API 연결 성공!', 'success');
      apiConnected = true;
      updateApiStatus(true);
    } else {
      showStatus('❌ API 연결 실패 (키 확인 필요)', 'warning');
      apiConnected = false;
      updateApiStatus(false);
    }
  } catch (error) {
    showStatus('❌ 네트워크 오류', 'warning');
    apiConnected = false;
    updateApiStatus(false);
  }
});

// API 상태 업데이트
function updateApiStatus(connected) {
  if (connected) {
    apiStatus.className = 'api-status connected';
    apiStatus.textContent = '✅ API 연결됨 (실제 검색)';
  } else {
    apiStatus.className = 'api-status disconnected';
    apiStatus.textContent = '⚠️ API 미설정 (시뮬레이션 모드)';
  }
}

// 저장된 API 설정 불러오기
chrome.storage.local.get(['naverApiClientId', 'naverApiClientSecret'], (result) => {
  if (result.naverApiClientId && result.naverApiClientSecret) {
    clientIdInput.value = result.naverApiClientId;
    clientSecretInput.value = result.naverApiClientSecret;
    apiConnected = true;
    updateApiStatus(true);
  }
});

// 슬라이더 이벤트
feeSlider.addEventListener('input', (e) => {
  feeValue.textContent = e.target.value;
  currentPreset = 'custom';
  updatePresetButtons();
});

discountSlider.addEventListener('input', (e) => {
  discountValue.textContent = e.target.value;
  currentPreset = 'custom';
  updatePresetButtons();
});

priceInput.addEventListener('input', (e) => {
  const value = parseInt(e.target.value) || 0;
  priceValue.textContent = value.toLocaleString();
  currentPreset = 'custom';
  updatePresetButtons();
});

// 프리셋 버튼
document.querySelectorAll('.preset-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const preset = btn.dataset.preset;
    applyPreset(preset);
  });
});

function applyPreset(presetName) {
  const preset = presets[presetName];
  feeSlider.value = preset.minFee;
  feeValue.textContent = preset.minFee;
  discountSlider.value = preset.minDiscount;
  discountValue.textContent = preset.minDiscount;
  priceInput.value = preset.minPrice;
  priceValue.textContent = preset.minPrice.toLocaleString();
  
  currentPreset = presetName;
  updatePresetButtons();
  saveSettings();
  
  showStatus(`📋 "${preset.name}" 프리셋 적용됨`, 'success');
}

function updatePresetButtons() {
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.preset === currentPreset);
  });
}

// 조건 모드
document.querySelectorAll('.mode-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    currentMode = btn.dataset.mode;
    document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    saveSettings();
    
    const modeText = currentMode === 'and' ? 'AND (모두 만족)' : 'OR (하나만 만족)';
    showStatus(`🔀 모드 변경: ${modeText}`, 'info');
  });
});

// 설정 저장
function saveSettings() {
  const settings = {
    minFee: parseInt(feeSlider.value),
    minDiscount: parseInt(discountSlider.value),
    minPrice: parseInt(priceInput.value) || 0,
    mode: currentMode,
    preset: currentPreset
  };
  chrome.storage.local.set({ filterSettings: settings });
  return settings;
}

// 설정 불러오기
chrome.storage.local.get(['filterSettings'], (result) => {
  if (result.filterSettings) {
    const settings = result.filterSettings;
    feeSlider.value = settings.minFee || 10;
    feeValue.textContent = settings.minFee || 10;
    discountSlider.value = settings.minDiscount || 25;
    discountValue.textContent = settings.minDiscount || 25;
    priceInput.value = settings.minPrice || 50000;
    priceValue.textContent = (settings.minPrice || 50000).toLocaleString();
    currentMode = settings.mode || 'and';
    currentPreset = settings.preset || 'custom';
    
    document.querySelectorAll('.mode-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === currentMode);
    });
    updatePresetButtons();
  }
});

// 상태 메시지
function showStatus(message, type = 'info') {
  const status = document.getElementById('status');
  status.textContent = message;
  status.className = `status show ${type}`;
  
  if (type === 'success') {
    setTimeout(() => {
      status.classList.remove('show');
    }, 3000);
  }
}

// 버튼 활성화/비활성화
function enableButton(btnId, enabled = true) {
  const btn = document.getElementById(btnId);
  if (btn) {
    btn.disabled = !enabled;
  }
}

// 1차 필터링
document.getElementById('startFilter').addEventListener('click', async () => {
  const settings = saveSettings();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  showStatus('🔍 1차 필터링 시작...', 'info');
  enableButton('startFilter', false);
  enableButton('deepAnalysis', false);
  enableButton('exportExcel', false);
  
  chrome.tabs.sendMessage(tab.id, {
    action: 'startFilter',
    settings: settings
  }, (response) => {
    if (response && response.success) {
      showStatus('✅ 1차 필터링 진행 중...', 'info');
    } else {
      showStatus('⚠️ 페이지를 확인해주세요', 'warning');
      enableButton('startFilter', true);
    }
  });
});

// 정밀 분석
document.getElementById('deepAnalysis').addEventListener('click', async () => {
  if (!apiConnected) {
    showStatus('⚠️ 실제 검색을 위해 API를 설정하세요', 'warning');
    apiInputs.classList.add('show');
    return;
  }
  
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  showStatus('🔬 TOP 20 정밀 분석 시작...', 'info');
  enableButton('deepAnalysis', false);
  
  chrome.tabs.sendMessage(tab.id, {
    action: 'deepAnalysis'
  }, (response) => {
    if (response && response.success) {
      showStatus(`✅ 분석 완료! TOP ${response.count}개 발견`, 'success');
      enableButton('exportExcel', true); // 엑셀 버튼 활성화
      enableButton('deepAnalysis', true); // 다시 분석 가능하게
    } else {
      showStatus('⚠️ 분석 실패', 'warning');
      enableButton('deepAnalysis', true);
    }
  });
});

// 엑셀 내보내기
document.getElementById('exportExcel').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  showStatus('📊 엑셀 생성 중...', 'info');
  
  chrome.tabs.sendMessage(tab.id, {
    action: 'exportExcel'
  }, (response) => {
    if (response && response.success) {
      showStatus(`✅ TOP ${response.count}개 엑셀로 내보냄!`, 'success');
    } else {
      showStatus('⚠️ 내보내기 실패', 'warning');
    }
  });
});

// 중지
document.getElementById('stopFilter').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  chrome.tabs.sendMessage(tab.id, {
    action: 'stopFilter'
  }, (response) => {
    if (response && response.success) {
      showStatus(`⏸️ 중지됨 (${response.matchCount}개 발견)`, 'success');
      enableButton('startFilter', true);
      if (response.matchCount > 0) {
        enableButton('deepAnalysis', true);
      }
    }
  });
});

// 초기화
document.getElementById('resetFilter').addEventListener('click', async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  chrome.tabs.sendMessage(tab.id, {
    action: 'resetFilter'
  }, (response) => {
    if (response && response.success) {
      showStatus('🔄 초기화 완료', 'success');
      enableButton('startFilter', true);
      enableButton('deepAnalysis', false);
      enableButton('exportExcel', false);
    }
  });
});

// content script에서 오는 메시지 수신
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'filterComplete') {
    showStatus(`✅ 1차 완료! ${request.count}개 발견`, 'success');
    enableButton('startFilter', true);
    if (request.count > 0) {
      enableButton('deepAnalysis', true);
    }
  } else if (request.action === 'analysisProgress') {
    showStatus(`🔬 분석 중... ${request.current}/${request.total}`, 'info');
  }
});
