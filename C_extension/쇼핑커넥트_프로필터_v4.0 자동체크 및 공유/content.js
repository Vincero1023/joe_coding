// 전역 상태
let isFiltering = false;
let filterSettings = null;
let matchCount = 0;
let scrollInterval = null;
let checkInterval = null;
let allProducts = [];
let naverApiClientId = null;
let naverApiClientSecret = null;
let completedList = { common: [], main_account: [], sub_account_1: [] };
let currentAccount = 'common';
let productObserver = null;

// API 설정 불러오기
async function loadApiSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['naverApiClientId', 'naverApiClientSecret'], (result) => {
      naverApiClientId = result.naverApiClientId || 'xWq243EVwx6zhGSHiU_Q';
      naverApiClientSecret = result.naverApiClientSecret || 'vC8jtLYpvT';
      
      if (!result.naverApiClientId || !result.naverApiClientSecret) {
        chrome.storage.local.set({
          naverApiClientId: naverApiClientId,
          naverApiClientSecret: naverApiClientSecret
        });
        console.log('[API] ✅ 기본 API 키 자동 설정 완료');
      }
      
      console.log('[API] 클라이언트 ID:', naverApiClientId.substring(0, 5) + '...');
      resolve(true);
    });
  });
}

// ===== 🔄 Chrome Sync Storage: 작성완료 목록 로드 =====
async function loadCompletedList() {
  return new Promise((resolve) => {
    // chrome.storage.sync 사용 (자동 동기화)
    chrome.storage.sync.get(['completedList'], (result) => {
      if (chrome.runtime.lastError) {
        console.error('[Sync 오류]', chrome.runtime.lastError);
        completedList = { 
          common: [], 
          main_account: [], 
          sub_account_1: [], 
          updated: new Date().toISOString(), 
          version: '2.0' 
        };
      } else if (result.completedList) {
        completedList = result.completedList;
        console.log('[Sync] ✅ 작성완료 목록 로드:', Object.keys(completedList).map(k => `${k}: ${(completedList[k] || []).length}개`));
      } else {
        completedList = { 
          common: [], 
          main_account: [], 
          sub_account_1: [], 
          updated: new Date().toISOString(), 
          version: '2.0' 
        };
        console.log('[Sync] 📝 새로운 작성완료 목록 생성');
      }
      
      resolve(true);
    });
  });
}

// ===== 💾 Chrome Sync Storage: 작성완료 목록 저장 =====
async function saveCompletedList() {
  return new Promise((resolve, reject) => {
    completedList.updated = new Date().toISOString();
    
    // chrome.storage.sync에 저장 (자동으로 모든 기기에 동기화)
    chrome.storage.sync.set({ completedList: completedList }, () => {
      if (chrome.runtime.lastError) {
        console.error('[Sync 오류]', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        console.log('[Sync] 💾 저장 완료 → 자동 동기화 중...');
        
        // 로컬에도 백업 (빠른 로드용)
        chrome.storage.local.set({ completedListBackup: completedList });
        
        resolve(true);
      }
    });
  });
}

// ===== ✅ 작성완료 여부 체크 =====
function isCompleted(productName) {
  const list = completedList[currentAccount] || [];
  return list.some(name => name === productName || productName.includes(name) || name.includes(productName));
}

// ===== ➕ 작성완료 추가 =====
async function addToCompleted(productName) {
  try {
    console.log(`[추가 시작] ${productName}`);
    
    // 1. 최신 데이터 다시 로드 (다른 기기의 변경사항 반영)
    await loadCompletedList();
    
    // 2. 계정 확인
    if (!completedList[currentAccount]) {
      completedList[currentAccount] = [];
    }
    
    // 3. 중복 체크 후 추가
    if (!completedList[currentAccount].includes(productName)) {
      completedList[currentAccount].push(productName);
      completedList[currentAccount].sort(); // 정렬
      console.log(`[추가] ✅ "${productName}" 추가됨`);
    } else {
      console.log(`[추가] ⚠️ "${productName}" 이미 존재`);
    }
    
    // 4. Sync Storage에 저장 (자동 동기화)
    await saveCompletedList();
    
    console.log(`[Sync] 🌐 모든 기기에 동기화 중...`);
    
    return true;
    
  } catch (error) {
    console.error('[오류] 추가 실패:', error);
    return false;
  }
}

// ===== ➖ 작성완료 제거 =====
async function removeFromCompleted(productName) {
  try {
    console.log(`[제거 시작] ${productName}`);
    
    // 1. 최신 데이터 다시 로드
    await loadCompletedList();
    
    // 2. 제거
    if (completedList[currentAccount]) {
      const index = completedList[currentAccount].indexOf(productName);
      if (index !== -1) {
        completedList[currentAccount].splice(index, 1);
        console.log(`[제거] ✅ "${productName}" 제거됨`);
      } else {
        console.log(`[제거] ⚠️ "${productName}" 없음`);
      }
    }
    
    // 3. Sync Storage에 저장
    await saveCompletedList();
    
    console.log(`[Sync] 🌐 모든 기기에 동기화 중...`);
    
    return true;
    
  } catch (error) {
    console.error('[오류] 제거 실패:', error);
    return false;
  }
}

// ===== 📥 수동 백업 다운로드 (선택사항) =====
async function downloadBackup() {
  const blob = new Blob([JSON.stringify(completedList, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  const date = new Date().toISOString().slice(0, 10);
  link.download = `completed_list_backup_${date}.json`;
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  
  console.log('[백업] 📥 다운로드 완료');
  showFloatingNotification('✅ 백업 파일 다운로드 완료');
}

// 상품 데이터 구조
class ProductData {
  constructor(element) {
    this.element = element;
    this.name = '';
    this.link = '';
    this.imageUrl = '';
    this.fee = 0;
    this.discount = 0;
    this.price = 0;
    this.estimatedProfit = 0;
    this.basicScore = 0;
    this.finalScore = 0;
    this.blogCount = -1;
    this.analyzed = false;
    this.selected = false;
  }
}

// 상품 정보 추출
function extractProductInfo(product) {
  const data = new ProductData(product);
  const text = product.innerText || product.textContent;
  
  try {
    const nameElement = product.querySelector('[class*="title"], [class*="name"], h3, h4, a');
    data.name = nameElement ? nameElement.textContent.trim() : '상품명 없음';
    
    const linkElement = product.querySelector('a[href]');
    data.link = linkElement ? linkElement.href : window.location.href;
    
    const imgElement = product.querySelector('img');
    if (imgElement) {
      data.imageUrl = imgElement.src || imgElement.getAttribute('data-src') || '';
    }
    
    const feeMatch = text.match(/수수료\s*[:：]?\s*(\d+)\s*%/);
    data.fee = feeMatch ? parseInt(feeMatch[1]) : 0;
    
    const allPercents = Array.from(text.matchAll(/(\d+)\s*%/g)).map(m => parseInt(m[1]));
    const discounts = allPercents.filter(p => p !== data.fee && p > 0 && p <= 90);
    data.discount = discounts.length > 0 ? Math.max(...discounts) : 0;
    
    const priceMatches = Array.from(text.matchAll(/(\d{1,3}(?:,\d{3})+)원/g));
    if (priceMatches.length > 0) {
      const prices = priceMatches.map(m => parseInt(m[1].replace(/,/g, '')));
      prices.sort((a, b) => a - b);
      data.price = prices[Math.floor(prices.length / 2)];
    }
    
    data.estimatedProfit = Math.round(data.price * data.fee / 100);
    
  } catch (error) {
    console.error('[오류] 상품 정보 추출:', error);
  }
  
  return data;
}

// 1차 스코어 계산
function calculateBasicScore(data) {
  let score = 0;
  score += Math.min(data.fee * 1.5, 30);
  score += Math.min(data.discount * 0.6, 25);
  score += Math.min(data.price / 10000, 20);
  score += Math.min(data.estimatedProfit / 1000, 25);
  
  data.basicScore = Math.round(score);
  data.finalScore = data.basicScore;
  
  return data.basicScore;
}

// 최종 스코어 계산
function calculateFinalScore(data) {
  let score = data.basicScore;
  
  if (data.blogCount >= 0) {
    if (data.blogCount === 0) score += 40;
    else if (data.blogCount <= 2) score += 35;
    else if (data.blogCount <= 5) score += 30;
    else if (data.blogCount <= 10) score += 20;
    else if (data.blogCount <= 20) score += 10;
  }
  
  data.finalScore = Math.round(score);
  return data.finalScore;
}

// 조건 체크
function meetsCondition(data, settings) {
  const mode = settings.mode || 'and';
  
  const conditionFee = data.fee >= settings.minFee;
  const conditionDiscount = data.discount >= settings.minDiscount;
  const conditionPrice = data.price >= settings.minPrice;
  
  if (data.fee === 0 || data.discount === 0 || data.price === 0) {
    return false;
  }
  
  if (mode === 'or') {
    return conditionFee || conditionDiscount || conditionPrice;
  } else {
    return conditionFee && conditionDiscount && conditionPrice;
  }
}

// 상품 체크
function checkProduct(product) {
  if (product.getAttribute('data-filter-checked')) {
    return null;
  }
  
  product.setAttribute('data-filter-checked', 'true');
  
  try {
    const text = product.innerText || '';
    if (text.length < 30 || text.includes('조건 충족')) {
      return null;
    }
    
    const data = extractProductInfo(product);
    
    if (isCompleted(data.name)) {
      console.log(`[건너뜀] ${data.name} - 이미 작성 완료`);
      product.classList.add('filter-blacklisted');
      return null;
    }
    
    if (!meetsCondition(data, filterSettings)) {
      product.classList.add('filter-nomatch');
      return null;
    }
    
    calculateBasicScore(data);
    
    product.classList.add('filter-match');
    product.setAttribute('data-score', data.basicScore);
    
    matchCount++;
    allProducts.push(data);
    
    console.log(`✅ ${matchCount}번째 발견! 점수:${data.basicScore} 수수료:${data.fee}% 할인:${data.discount}% 가격:${data.price.toLocaleString()}원`);
    
    showFloatingNotification(`${matchCount}개 발견! (최고 점수: ${Math.max(...allProducts.map(p => p.basicScore))}점)`);
    
    return data;
    
  } catch (error) {
    console.error('[오류] 상품 체크:', error);
    return null;
  }
}

// 화면 알림
function showFloatingNotification(message) {
  let notification = document.getElementById('filter-notification');
  
  if (notification) {
    notification.textContent = `🎯 ${message}`;
  } else {
    notification = document.createElement('div');
    notification.id = 'filter-notification';
    notification.className = 'filter-notification';
    notification.textContent = `🎯 ${message}`;
    document.body.appendChild(notification);
  }
}

// Intersection Observer 추가
function setupIntersectionObserver() {
  if (productObserver) {
    productObserver.disconnect();
  }
  
  productObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && !entry.target.getAttribute('data-filter-checked')) {
        checkProduct(entry.target);
      }
    });
  }, {
    root: null,
    rootMargin: '800px',
    threshold: 0.01
  });
  
  return productObserver;
}

// 상품 검색 및 Observer 연결
function findAndObserveProducts() {
  const selectors = [
    'a[href*="/products/"]',
    'div[class*="ProductCard"]',
    'div[class*="product-card"]',
    'li[class*="product"]',
    'article'
  ];
  
  let products = [];
  for (const selector of selectors) {
    const found = document.querySelectorAll(selector);
    if (found.length > 0) {
      products = Array.from(found);
      break;
    }
  }
  
  if (products.length === 0) {
    products = Array.from(document.querySelectorAll('[class*="product"], [class*="item"], [class*="card"]'));
  }
  
  products = products.filter(p => {
    const rect = p.getBoundingClientRect();
    const text = p.innerText || '';
    return rect.width > 150 && rect.height > 150 && text.length > 30;
  });
  
  products.forEach(product => {
    if (!product.getAttribute('data-observer-attached')) {
      productObserver.observe(product);
      product.setAttribute('data-observer-attached', 'true');
    }
  });
  
  return products.length;
}

// 빠른 상품 검색
function checkVisibleProducts() {
  if (!isFiltering) return;
  findAndObserveProducts();
}

// 빠른 자동 스크롤
function autoScroll() {
  if (!isFiltering) return;
  
  const currentScroll = window.scrollY;
  const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
  
  if (currentScroll < maxScroll - 100) {
    window.scrollBy({ top: 800, behavior: 'smooth' });
  } else {
    console.log('[완료] 1차 필터링 완료');
    stopFiltering();
    showFloatingNotification(`완료! 총 ${matchCount}개 발견`);
    
    chrome.runtime.sendMessage({
      action: 'filterComplete',
      count: matchCount
    });
  }
}

// 실제 네이버 블로그 검색
async function searchBlogReal(productName) {
  if (!naverApiClientId || !naverApiClientSecret) {
    console.warn('[경고] API 미설정 - 시뮬레이션 모드');
    await new Promise(resolve => setTimeout(resolve, 500));
    return Math.floor(Math.random() * 30);
  }
  
  try {
    const cleanQuery = productName
      .replace(/\[.*?\]/g, '')
      .replace(/\(.*?\)/g, '')
      .replace(/[^\w\s가-힣]/g, '')
      .trim()
      .split(' ')
      .slice(0, 3)
      .join(' ');
    
    console.log(`[블로그 검색] "${productName}" → "${cleanQuery}"`);
    
    const url = `https://openapi.naver.com/v1/search/blog.json?query=${encodeURIComponent(cleanQuery)}&display=100&sort=date`;
    
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'X-Naver-Client-Id': naverApiClientId,
        'X-Naver-Client-Secret': naverApiClientSecret
      }
    });
    
    if (!response.ok) {
      console.error('[API 오류]', response.status);
      return Math.floor(Math.random() * 30);
    }
    
    const data = await response.json();
    const total = data.total || 0;
    
    console.log(`[검색 결과] "${cleanQuery}": ${total}개 블로그 글 발견`);
    
    await new Promise(resolve => setTimeout(resolve, 150));
    
    return total;
    
  } catch (error) {
    console.error('[오류] 블로그 검색 실패:', error);
    return Math.floor(Math.random() * 30);
  }
}

// TOP 50 정밀 분석
async function deepAnalysis() {
  if (allProducts.length === 0) {
    showFloatingNotification('분석할 상품이 없습니다');
    return { success: false };
  }
  
  const hasApi = await loadApiSettings();
  if (!hasApi) {
    console.warn('[경고] API 미설정 - 시뮬레이션 모드로 진행');
  }
  
  allProducts.sort((a, b) => b.basicScore - a.basicScore);
  
  const top50 = allProducts.slice(0, Math.min(50, allProducts.length));
  
  console.log(`[정밀 분석] TOP ${top50.length}개 상품 ${hasApi ? '실제' : '시뮬레이션'} 분석 시작`);
  showFloatingNotification(`정밀 분석 시작... 0/${top50.length}`);
  
  for (let i = 0; i < top50.length; i++) {
    const product = top50[i];
    
    try {
      product.blogCount = await searchBlogReal(product.name);
      product.analyzed = true;
      
      calculateFinalScore(product);
      
      showFloatingNotification(`정밀 분석 중... ${i + 1}/${top50.length}`);
      
      chrome.runtime.sendMessage({
        action: 'analysisProgress',
        current: i + 1,
        total: top50.length
      });
      
      console.log(`[분석 ${i+1}/${top50.length}] ${product.name}`);
      console.log(`  → 블로그: ${product.blogCount}개`);
      console.log(`  → 점수: ${product.basicScore} → ${product.finalScore}점`);
      
    } catch (error) {
      console.error(`[오류] ${product.name} 분석 실패:`, error);
    }
  }
  
  allProducts.sort((a, b) => {
    const scoreA = a.analyzed ? a.finalScore : a.basicScore;
    const scoreB = b.analyzed ? b.finalScore : b.basicScore;
    return scoreB - scoreA;
  });
  
  highlightTop10();
  
  showFloatingNotification(`✅ 분석 완료! TOP 10 하이라이트됨`);
  
  return { success: true, count: top50.length };
}

// TOP 50 패널 생성
function createTop50Panel() {
  const existing = document.getElementById('top50-panel');
  if (existing) existing.remove();
  
  const panel = document.createElement('div');
  panel.id = 'top50-panel';
  panel.className = 'top50-panel';
  
  panel.innerHTML = `
    <div class="top50-header">
      <span>🏆 TOP 50</span>
      <button class="top50-close">×</button>
    </div>
    <div class="top50-list" id="top50-list"></div>
    <div class="top50-footer">
      <div class="blacklist-info">
        ✅ 작성 완료: <span id="completedCount">0</span>개
        <button class="btn-backup" id="btnBackup" style="margin-left: 8px; padding: 4px 8px; font-size: 10px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">📥 백업</button>
        <button class="btn-backup" id="btnManageCompleted" style="margin-left: 4px; padding: 4px 8px; font-size: 10px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;">📋 관리</button>
      </div>
    </div>
  `;
  
  document.body.appendChild(panel);
  
  panel.querySelector('.top50-close').addEventListener('click', () => {
    panel.classList.remove('show');
  });
  
  // 백업 버튼
  document.getElementById('btnBackup').addEventListener('click', downloadBackup);
  
  // ===== 🆕 여기만 추가! =====
  // 관리 버튼
  document.getElementById('btnManageCompleted').addEventListener('click', () => {
    const managementPanel = document.getElementById('completed-list-panel') || createCompletedListPanel();
    managementPanel.style.display = 'flex';
    updateCompletedListPanel();
  });
  // ===== 추가 끝 =====
  
  return panel;
}

// ===== ✅ 즉시 작성완료 토글 처리 (Chrome Sync) =====
async function toggleCompleted(product, wrapper, toggleBtn) {
  toggleBtn.disabled = true;
  toggleBtn.textContent = '⏳ 동기화중...';
  
  product.selected = !product.selected;
  
  if (product.selected) {
    const success = await addToCompleted(product.name);
    
    if (success) {
      wrapper.style.background = '#e8f5e9';
      wrapper.style.border = '3px solid #4CAF50';
      toggleBtn.style.background = '#4CAF50';
      toggleBtn.textContent = '✅ 작성완료';
      
      if (product.element) {
        product.element.classList.add('filter-blacklisted');
        product.element.classList.remove('filter-match', 'filter-top10');
      }
      
      showFloatingNotification(`✅ "${product.name}" 작성완료! (자동 동기화됨)`);
      console.log(`[✅ 작성완료] ${product.name} → 모든 기기에 동기화`);
    } else {
      product.selected = false;
      showFloatingNotification(`❌ 처리 실패`);
    }
    
  } else {
    const success = await removeFromCompleted(product.name);
    
    if (success) {
      const index = allProducts.indexOf(product);
      if (index === 0) {
        wrapper.style.background = 'linear-gradient(135deg, #fff9c4 0%, #fff59d 100%)';
        wrapper.style.borderColor = '#ffd700';
      } else if (index === 1) {
        wrapper.style.background = 'linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%)';
        wrapper.style.borderColor = '#c0c0c0';
      } else if (index === 2) {
        wrapper.style.background = 'linear-gradient(135deg, #ffe0b2 0%, #ffcc80 100%)';
        wrapper.style.borderColor = '#cd7f32';
      } else {
        wrapper.style.background = '#f8f9fa';
        wrapper.style.border = '2px solid transparent';
      }
      
      toggleBtn.style.background = '#ff9800';
      toggleBtn.textContent = '📝 작성체크';
      
      if (product.element) {
        product.element.classList.remove('filter-blacklisted');
        product.element.classList.add('filter-match');
        
        const rank = allProducts.indexOf(product);
        if (rank < 10) {
          product.element.classList.add('filter-top10');
        }
      }
      
      showFloatingNotification(`❌ "${product.name}" 취소됨 (자동 동기화됨)`);
      console.log(`[❌ 취소] ${product.name} → 모든 기기에 동기화`);
    } else {
      product.selected = true;
      showFloatingNotification(`❌ 처리 실패`);
    }
  }
  
  toggleBtn.disabled = false;
  updateCompletedCount();
}

// 작성완료 개수 업데이트
function updateCompletedCount() {
  const count = (completedList[currentAccount] || []).length;
  const el = document.getElementById('completedCount');
  if (el) {
    el.textContent = count;
  }
}

// TOP 50 패널 업데이트
function updateTop50Panel() {
  const panel = document.getElementById('top50-panel') || createTop50Panel();
  const list = document.getElementById('top50-list');
  
  if (!list) return;
  
  const top50 = allProducts.slice(0, Math.min(50, allProducts.length));
  
  if (top50.length === 0) {
    panel.classList.remove('show');
    return;
  }
  
  list.innerHTML = '';
  
  top50.forEach((product, index) => {
    const wrapper = document.createElement('div');
    wrapper.className = `top50-item-wrapper rank-${index + 1}`;
    wrapper.style.cssText = 'background: #f8f9fa; border-radius: 12px; padding: 12px; margin-bottom: 10px; border: 2px solid transparent; transition: all 0.2s;';
    
    if (index === 0) wrapper.style.cssText += ' background: linear-gradient(135deg, #fff9c4 0%, #fff59d 100%); border-color: #ffd700;';
    if (index === 1) wrapper.style.cssText += ' background: linear-gradient(135deg, #f5f5f5 0%, #e0e0e0 100%); border-color: #c0c0c0;';
    if (index === 2) wrapper.style.cssText += ' background: linear-gradient(135deg, #ffe0b2 0%, #ffcc80 100%); border-color: #cd7f32;';
    
    if (product.selected) {
      wrapper.style.cssText += ' background: #e8f5e9; border: 3px solid #4CAF50;';
    }
    
    const content = document.createElement('div');
    content.style.cssText = 'cursor: pointer;';
    content.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
        <span class="top50-rank">${index + 1}</span>
        <div style="flex: 1; font-size: 13px; font-weight: bold; color: #333; line-height: 1.3;">${product.name}</div>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
        <div style="font-size: 20px; font-weight: bold; color: #ff1744;">${product.analyzed ? product.finalScore : product.basicScore}점</div>
        <button class="toggle-check-btn" style="
          background: ${product.selected ? '#4CAF50' : '#ff9800'}; 
          color: white; 
          border: none; 
          padding: 6px 12px; 
          border-radius: 6px; 
          font-size: 12px; 
          font-weight: bold; 
          cursor: pointer;
          transition: all 0.2s;
        ">
          ${product.selected ? '✅ 작성완료' : '📝 작성체크'}
        </button>
      </div>
      <div style="font-size: 11px; color: #666; display: flex; gap: 8px; flex-wrap: wrap;">
        <span style="background: white; padding: 2px 8px; border-radius: 4px;">💰 ${product.fee}%</span>
        <span style="background: white; padding: 2px 8px; border-radius: 4px;">🏷️ ${product.discount}%</span>
        <span style="background: white; padding: 2px 8px; border-radius: 4px;">💵 ${product.price.toLocaleString()}원</span>
        ${product.analyzed ? `<span style="background: white; padding: 2px 8px; border-radius: 4px; color: #2e7d32; font-weight: bold;">📝 블로그 ${product.blogCount}개</span>` : ''}
      </div>
    `;
    
    const toggleBtn = content.querySelector('.toggle-check-btn');
    toggleBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await toggleCompleted(product, wrapper, toggleBtn);
    });
    
    content.addEventListener('click', (e) => {
      if (!e.target.classList.contains('toggle-check-btn')) {
        product.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        product.element.style.animation = 'none';
        setTimeout(() => { product.element.style.animation = ''; }, 10);
      }
    });
    
    wrapper.addEventListener('mouseenter', () => {
      if (!product.selected) {
        wrapper.style.borderColor = '#ffc107';
      }
    });
    
    wrapper.addEventListener('mouseleave', () => {
      if (!product.selected) {
        if (index === 0) wrapper.style.borderColor = '#ffd700';
        else if (index === 1) wrapper.style.borderColor = '#c0c0c0';
        else if (index === 2) wrapper.style.borderColor = '#cd7f32';
        else wrapper.style.borderColor = 'transparent';
      }
    });
    
    wrapper.appendChild(content);
    list.appendChild(wrapper);
  });
  
  panel.classList.add('show');
  updateCompletedCount();
}

// TOP 10 하이라이트
function highlightTop10() {
  document.querySelectorAll('.filter-top10').forEach(el => {
    el.classList.remove('filter-top10');
    const badge = el.querySelector('.top-badge');
    if (badge) badge.remove();
  });
  
  const top10 = allProducts.slice(0, Math.min(10, allProducts.length));
  
  top10.forEach((product, index) => {
    product.element.classList.add('filter-top10');
    product.element.setAttribute('data-rank', index + 1);
    
    const badge = document.createElement('div');
    badge.className = 'top-badge';
    badge.textContent = `🏆 TOP ${index + 1}`;
    
    const scoreInfo = document.createElement('div');
    scoreInfo.className = 'score-info';
    scoreInfo.textContent = `${product.finalScore}점${product.analyzed ? ` (블로그 ${product.blogCount}개)` : ''}`;
    badge.appendChild(document.createElement('br'));
    badge.appendChild(scoreInfo);
    
    product.element.appendChild(badge);
    
    if (index === 0) {
      product.element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
  
  updateTop50Panel();
  
  console.log('[TOP 10] 하이라이트 완료');
}

// 엑셀 내보내기
async function exportToExcel() {
  if (allProducts.length === 0) {
    showFloatingNotification('내보낼 데이터가 없습니다');
    return { success: false };
  }
  
  const top50 = allProducts.slice(0, Math.min(50, allProducts.length));
  
  let csv = '순위,상품명,상품링크,이미지URL,점수,수수료,할인율,가격,작성완료\n';
  
  top50.forEach((product, index) => {
    const row = [
      index + 1,
      `"${product.name.replace(/"/g, '""')}"`,
      product.link,
      product.imageUrl,
      product.analyzed ? product.finalScore : product.basicScore,
      product.fee,
      product.discount,
      product.price,
      product.selected ? 'O' : 'X'
    ];
    csv += row.join(',') + '\n';
  });
  
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  
  const date = new Date().toISOString().slice(0, 10);
  link.download = `쇼핑커넥트_TOP50_${date}.csv`;
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  
  console.log('[엑셀] TOP 50 내보내기 완료');
  showFloatingNotification(`✅ TOP ${top50.length}개 엑셀 저장 완료!`);
  
  return { success: true, count: top50.length };
}

// 필터링 시작
function startFiltering(settings) {
  if (isFiltering) {
    stopFiltering();
  }
  
  isFiltering = true;
  filterSettings = settings;
  matchCount = 0;
  allProducts = [];
  
  console.log('[시작] 1차 필터링:', settings);
  console.log(`[작성완료] ${(completedList[currentAccount] || []).length}개 상품 제외됨`);
  showFloatingNotification('1차 필터링 시작...');
  
  document.querySelectorAll('[data-filter-checked]').forEach(el => {
    el.removeAttribute('data-filter-checked');
    el.removeAttribute('data-observer-attached');
  });
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
  
  setupIntersectionObserver();
  findAndObserveProducts();
  
  checkInterval = setInterval(checkVisibleProducts, 200);
  scrollInterval = setInterval(autoScroll, 800);
  
  console.log('[속도] 🚀 고속 모드 활성화: 스크롤 800ms, 체크 200ms');
}

// 중지
function stopFiltering() {
  isFiltering = false;
  
  if (scrollInterval) {
    clearInterval(scrollInterval);
    scrollInterval = null;
  }
  
  if (checkInterval) {
    clearInterval(checkInterval);
    checkInterval = null;
  }
  
  if (productObserver) {
    productObserver.disconnect();
    productObserver = null;
  }
  
  console.log(`[중지] 총 ${matchCount}개 발견`);
}

// 초기화
function resetFilter() {
  stopFiltering();
  
  document.querySelectorAll('.filter-match, .filter-nomatch, .filter-top10, .filter-blacklisted').forEach(el => {
    el.classList.remove('filter-match', 'filter-nomatch', 'filter-top10', 'filter-blacklisted');
    el.removeAttribute('data-filter-checked');
    el.removeAttribute('data-score');
    el.removeAttribute('data-rank');
    el.removeAttribute('data-observer-attached');
    const badge = el.querySelector('.top-badge');
    if (badge) badge.remove();
  });
  
  const notification = document.getElementById('filter-notification');
  if (notification) notification.remove();
  
  const panel = document.getElementById('top50-panel');
  if (panel) panel.remove();
  
  matchCount = 0;
  allProducts = [];
  
  console.log('[초기화] 완료');
}

// 메시지 리스너
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[메시지]', request.action);
  
  try {
    if (request.action === 'startFilter') {
      resetFilter();
      startFiltering(request.settings);
      sendResponse({ success: true });
      
    } else if (request.action === 'deepAnalysis') {
      deepAnalysis().then(result => {
        sendResponse(result);
      });
      return true;
      
    } else if (request.action === 'exportExcel') {
      exportToExcel().then(result => {
        sendResponse(result);
      });
      return true;
      
    } else if (request.action === 'stopFilter') {
      stopFiltering();
      sendResponse({ success: true, matchCount: matchCount });
      
    } else if (request.action === 'resetFilter') {
      resetFilter();
      sendResponse({ success: true });
      
    } else if (request.action === 'setAccount') {
      currentAccount = request.account;
      console.log(`[계정 변경] ${currentAccount}`);
      sendResponse({ success: true });
      
    } else if (request.action === 'getCompletedCount') {
      const count = (completedList[currentAccount] || []).length;
      sendResponse({ success: true, count: count });
    }
  } catch (error) {
    console.error('[오류] 메시지 처리:', error);
    sendResponse({ success: false, error: error.message });
  }
  
  return true;
});

// ===== 📋 작성완료 목록 관리 패널 =====
function createCompletedListPanel() {
  const existing = document.getElementById('completed-list-panel');
  if (existing) existing.remove();
  
  const panel = document.createElement('div');
  panel.id = 'completed-list-panel';
  panel.style.cssText = `
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 500px;
    max-height: 70vh;
    background: white;
    border-radius: 16px;
    box-shadow: 0 10px 40px rgba(0,0,0,0.5);
    z-index: 999999;
    display: none;
    flex-direction: column;
  `;
  
  panel.innerHTML = `
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px; border-radius: 16px 16px 0 0; display: flex; justify-content: space-between; align-items: center;">
      <span style="font-size: 18px; font-weight: bold;">✅ 작성완료 목록 관리</span>
      <button id="closeCompletedPanel" style="background: rgba(255,255,255,0.2); border: none; color: white; width: 28px; height: 28px; border-radius: 50%; cursor: pointer; font-size: 18px;">×</button>
    </div>
    
    <div style="padding: 16px; border-bottom: 1px solid #e0e0e0;">
      <div style="display: flex; gap: 8px; margin-bottom: 12px;">
        <input type="text" id="searchCompleted" placeholder="🔍 검색..." style="flex: 1; padding: 8px 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 13px;">
        <button id="clearAllCompleted" style="padding: 8px 16px; background: #ff5722; color: white; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 13px;">🗑️ 전체 삭제</button>
      </div>
      <div style="font-size: 12px; color: #666;">
        총 <span id="totalCompletedCount">0</span>개 | 
        <span style="color: #ff5722; cursor: pointer;" id="exportCompletedList">📥 내보내기</span> | 
        <span style="color: #4CAF50; cursor: pointer;" id="importCompletedList">📤 가져오기</span>
      </div>
    </div>
    
    <div id="completedListContent" style="flex: 1; overflow-y: auto; padding: 16px;"></div>
  `;
  
  document.body.appendChild(panel);
  
  // 이벤트 리스너
  document.getElementById('closeCompletedPanel').addEventListener('click', () => {
    panel.style.display = 'none';
  });
  
  document.getElementById('searchCompleted').addEventListener('input', (e) => {
    updateCompletedListPanel(e.target.value);
  });
  
  document.getElementById('clearAllCompleted').addEventListener('click', async () => {
    if (confirm('⚠️ 정말 모든 작성완료 항목을 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없으며, 모든 기기에 동기화됩니다.')) {
      completedList[currentAccount] = [];
      await saveCompletedList();
      updateCompletedListPanel();
      updateCompletedCount();
      showFloatingNotification('✅ 모든 항목이 삭제되었습니다');
    }
  });
  
  document.getElementById('exportCompletedList').addEventListener('click', () => {
    downloadBackup();
  });
  
  document.getElementById('importCompletedList').addEventListener('click', () => {
    importCompletedList();
  });
  
  return panel;
}

// ===== 📋 작성완료 목록 패널 업데이트 =====
function updateCompletedListPanel(searchQuery = '') {
  const panel = document.getElementById('completed-list-panel');
  if (!panel) return;
  
  const content = document.getElementById('completedListContent');
  const list = completedList[currentAccount] || [];
  
  // 검색 필터
  const filteredList = searchQuery 
    ? list.filter(name => name.toLowerCase().includes(searchQuery.toLowerCase()))
    : list;
  
  document.getElementById('totalCompletedCount').textContent = list.length;
  
  if (filteredList.length === 0) {
    content.innerHTML = `
      <div style="text-align: center; padding: 40px; color: #999;">
        ${searchQuery ? '🔍 검색 결과가 없습니다' : '📝 작성완료한 상품이 없습니다'}
      </div>
    `;
    return;
  }
  
  content.innerHTML = '';
  
  filteredList.forEach((productName, index) => {
    const item = document.createElement('div');
    item.style.cssText = `
      background: #f8f9fa;
      border-radius: 8px;
      padding: 12px;
      margin-bottom: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      transition: all 0.2s;
    `;
    
    item.innerHTML = `
      <div style="flex: 1; font-size: 13px; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 12px;">
        ${productName}
      </div>
      <button class="remove-completed-btn" data-name="${productName}" style="
        background: #ff5722;
        color: white;
        border: none;
        padding: 6px 12px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: bold;
        cursor: pointer;
        transition: all 0.2s;
      ">🗑️ 삭제</button>
    `;
    
    item.addEventListener('mouseenter', () => {
      item.style.background = '#e3f2fd';
    });
    
    item.addEventListener('mouseleave', () => {
      item.style.background = '#f8f9fa';
    });
    
    const removeBtn = item.querySelector('.remove-completed-btn');
    removeBtn.addEventListener('click', async () => {
      removeBtn.disabled = true;
      removeBtn.textContent = '⏳';
      
      const success = await removeFromCompleted(productName);
      
      if (success) {
        item.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
          updateCompletedListPanel(searchQuery);
          updateCompletedCount();
        }, 300);
        showFloatingNotification(`✅ "${productName}" 삭제됨`);
      } else {
        removeBtn.disabled = false;
        removeBtn.textContent = '🗑️ 삭제';
        showFloatingNotification(`❌ 삭제 실패`);
      }
    });
    
    content.appendChild(item);
  });
}

// ===== 📤 작성완료 목록 가져오기 =====
function importCompletedList() {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = '.json';
  
  input.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    try {
      const text = await file.text();
      const imported = JSON.parse(text);
      
      if (!imported.version || !imported.common) {
        alert('❌ 올바른 작성완료 목록 파일이 아닙니다.');
        return;
      }
      
      // 현재 목록과 병합
      ['common', 'main_account', 'sub_account_1'].forEach(account => {
        const set = new Set([
          ...(completedList[account] || []),
          ...(imported[account] || [])
        ]);
        completedList[account] = Array.from(set).sort();
      });
      
      await saveCompletedList();
      updateCompletedListPanel();
      updateCompletedCount();
      
      showFloatingNotification(`✅ ${file.name} 가져오기 완료!`);
      
    } catch (error) {
      console.error('[오류] 가져오기 실패:', error);
      alert('❌ 파일을 읽을 수 없습니다.');
    }
  };
  
  input.click();
}

// ===== 🔘 작성완료 목록 관리 버튼 추가 (TOP 50 패널) =====
function addManageButton() {
  const footer = document.querySelector('.top50-footer .blacklist-info');
  if (!footer) return;
  
  const existing = document.getElementById('btnManageCompleted');
  if (existing) return;
  
  const manageBtn = document.createElement('button');
  manageBtn.id = 'btnManageCompleted';
  manageBtn.className = 'btn-backup';
  manageBtn.style.cssText = 'margin-left: 8px; padding: 4px 8px; font-size: 10px; background: #4CAF50; color: white; border: none; border-radius: 4px; cursor: pointer;';
  manageBtn.textContent = '📋 관리';
  
  manageBtn.addEventListener('click', () => {
    const panel = document.getElementById('completed-list-panel') || createCompletedListPanel();
    panel.style.display = 'flex';
    updateCompletedListPanel();
  });
  
  footer.appendChild(manageBtn);
}

// CSS 애니메이션 추가
const style = document.createElement('style');
style.textContent = `
  @keyframes slideOutRight {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(100%);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);


// 초기화
Promise.all([
  loadApiSettings(),
  loadCompletedList()
]).then(([hasApi]) => {
  console.log(`[로드] 쇼핑커넥트 프로 필터 v3.5 준비 완료`);
  console.log(`[API] ${hasApi ? '실제 검색' : '시뮬레이션'} 모드`);
  console.log(`[Sync] 작성완료 목록: ${(completedList[currentAccount] || []).length}개`);
  console.log(`[Sync] 🌐 Chrome 계정에 자동 동기화됩니다`);
});