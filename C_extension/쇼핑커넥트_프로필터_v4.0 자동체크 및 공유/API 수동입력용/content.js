// 전역 상태
let isFiltering = false;
let filterSettings = null;
let matchCount = 0;
let scrollInterval = null;
let checkInterval = null;
let allProducts = [];
let naverApiClientId = null;
let naverApiClientSecret = null;
let blacklist = { common: [], main_account: [], sub_account_1: [] };
let currentAccount = 'common';

// API 설정 불러오기
async function loadApiSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(['naverApiClientId', 'naverApiClientSecret'], (result) => {
      naverApiClientId = result.naverApiClientId;
      naverApiClientSecret = result.naverApiClientSecret;
      resolve(!!naverApiClientId && !!naverApiClientSecret);
    });
  });
}

// 블랙리스트 불러오기
async function loadBlacklist() {
  try {
    const stored = await chrome.storage.local.get('blacklist');
    
    if (stored.blacklist) {
      blacklist = stored.blacklist;
      console.log('[블랙리스트] Storage에서 불러옴:', Object.keys(blacklist).map(k => `${k}: ${(blacklist[k] || []).length}개`));
    }
    
    try {
      const response = await fetch(chrome.runtime.getURL('blacklist.json'));
      const fileData = await response.json();
      
      if (fileData.updated > (blacklist.updated || '2000-01-01')) {
        blacklist = fileData;
        await chrome.storage.local.set({ blacklist: blacklist });
        console.log('[블랙리스트] 파일에서 불러옴 (더 최신)');
      }
    } catch (error) {
      console.log('[블랙리스트] 파일 없음, Storage 사용');
    }
    
  } catch (error) {
    console.error('[오류] 블랙리스트 로드:', error);
    blacklist = { common: [], main_account: [], sub_account_1: [], updated: new Date().toISOString() };
  }
}

// 블랙리스트 저장
async function saveBlacklist() {
  blacklist.updated = new Date().toISOString();
  await chrome.storage.local.set({ blacklist: blacklist });
  console.log('[블랙리스트] 저장 완료');
}

// 블랙리스트 체크
function isInBlacklist(productName) {
  const list = blacklist[currentAccount] || [];
  return list.some(name => name === productName || productName.includes(name) || name.includes(productName));
}

// 블랙리스트에 추가
async function addToBlacklist(productNames) {
  if (!blacklist[currentAccount]) {
    blacklist[currentAccount] = [];
  }
  
  let addedCount = 0;
  productNames.forEach(name => {
    if (!blacklist[currentAccount].includes(name)) {
      blacklist[currentAccount].push(name);
      addedCount++;
    }
  });
  
  await saveBlacklist();
  return addedCount;
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
    
    if (isInBlacklist(data.name)) {
      console.log(`[건너뜀] ${data.name} - 이미 작성함`);
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

// 상품 검색
function checkVisibleProducts() {
  if (!isFiltering) return;
  
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
    const rect = product.getBoundingClientRect();
    if (rect.top >= -300 && rect.top <= window.innerHeight + 300) {
      checkProduct(product);
    }
  });
}

// 자동 스크롤
function autoScroll() {
  if (!isFiltering) return;
  
  const currentScroll = window.scrollY;
  const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
  
  if (currentScroll < maxScroll - 100) {
    window.scrollBy({ top: 400, behavior: 'smooth' });
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

// TOP 20 정밀 분석
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
  
  const top20 = allProducts.slice(0, Math.min(20, allProducts.length));
  
  console.log(`[정밀 분석] TOP ${top20.length}개 상품 ${hasApi ? '실제' : '시뮬레이션'} 분석 시작`);
  showFloatingNotification(`정밀 분석 시작... 0/${top20.length}`);
  
  for (let i = 0; i < top20.length; i++) {
    const product = top20[i];
    
    try {
      product.blogCount = await searchBlogReal(product.name);
      product.analyzed = true;
      
      calculateFinalScore(product);
      
      showFloatingNotification(`정밀 분석 중... ${i + 1}/${top20.length}`);
      
      chrome.runtime.sendMessage({
        action: 'analysisProgress',
        current: i + 1,
        total: top20.length
      });
      
      console.log(`[분석 ${i+1}/${top20.length}] ${product.name}`);
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
  
  return { success: true, count: top20.length };
}

// TOP 20 패널 생성
function createTop20Panel() {
  const existing = document.getElementById('top20-panel');
  if (existing) existing.remove();
  
  const panel = document.createElement('div');
  panel.id = 'top20-panel';
  panel.className = 'top20-panel';
  
  panel.innerHTML = `
    <div class="top20-header">
      <span>🏆 TOP 20</span>
      <button class="top20-close">×</button>
    </div>
    <div class="top20-list" id="top20-list"></div>
    <div class="top20-footer">
      <button class="btn-mark-completed" id="markCompleted" disabled>
        ✅ 작성 완료 처리 (0개)
      </button>
      <div class="blacklist-info">
        📋 작성 완료: <span id="blacklistCount">0</span>개
      </div>
    </div>
  `;
  
  document.body.appendChild(panel);
  
  panel.querySelector('.top20-close').addEventListener('click', () => {
    panel.classList.remove('show');
  });
  
  document.getElementById('markCompleted').addEventListener('click', handleMarkCompleted);
  
  return panel;
}

// 작성 완료 처리
async function handleMarkCompleted() {
  const selectedProducts = allProducts.filter(p => p.selected);
  
  if (selectedProducts.length === 0) {
    showFloatingNotification('선택된 상품이 없습니다');
    return;
  }
  
  const productNames = selectedProducts.map(p => p.name);
  const addedCount = await addToBlacklist(productNames);
  
  showFloatingNotification(`✅ ${addedCount}개 상품 작성 완료 처리!`);
  
  updateTop20Panel();
  updateBlacklistCount();
  
  if (addedCount > 0) {
    setTimeout(() => {
      if (confirm('blacklist.json을 다운로드하여 익스텐션 폴더에 복사하시겠습니까?\n(다른 컴퓨터와 동기화하려면 필요합니다)')) {
        const blob = new Blob([JSON.stringify(blacklist, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'blacklist.json';
        link.click();
        URL.revokeObjectURL(url);
      }
    }, 1000);
  }
}

// 블랙리스트 개수 업데이트
function updateBlacklistCount() {
  const count = (blacklist[currentAccount] || []).length;
  const el = document.getElementById('blacklistCount');
  if (el) {
    el.textContent = count;
  }
}

// TOP 20 패널 업데이트
function updateTop20Panel() {
  const panel = document.getElementById('top20-panel') || createTop20Panel();
  const list = document.getElementById('top20-list');
  
  if (!list) return;
  
  const top20 = allProducts.slice(0, Math.min(20, allProducts.length));
  
  if (top20.length === 0) {
    panel.classList.remove('show');
    return;
  }
  
  list.innerHTML = '';
  
  top20.forEach((product, index) => {
    const wrapper = document.createElement('div');
    wrapper.className = `top20-item-wrapper rank-${index + 1}`;
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
        <span style="display: inline-block; background: #ff1744; color: white; width: 28px; height: 28px; border-radius: 50%; text-align: center; line-height: 28px; font-weight: bold; font-size: 14px; flex-shrink: 0;">${index + 1}</span>
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
    
    // 버튼 클릭 이벤트
    const toggleBtn = content.querySelector('.toggle-check-btn');
    toggleBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      product.selected = !product.selected;
      
      // UI 업데이트
      if (product.selected) {
        wrapper.style.background = '#e8f5e9';
        wrapper.style.border = '3px solid #4CAF50';
        toggleBtn.style.background = '#4CAF50';
        toggleBtn.textContent = '✅ 작성완료';
      } else {
        wrapper.style.background = '#f8f9fa';
        wrapper.style.border = '2px solid transparent';
        toggleBtn.style.background = '#ff9800';
        toggleBtn.textContent = '📝 작성체크';
      }
      
      updateMarkButton();
      console.log(`[${product.selected ? '✅ 선택' : '❌ 해제'}] ${product.name}`);
    });
    
    // 내용 클릭 시 스크롤
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
  updateMarkButton();
  updateBlacklistCount();
}

// 작성 완료 버튼 업데이트
function updateMarkButton() {
  const selectedCount = allProducts.filter(p => p.selected).length;
  const btn = document.getElementById('markCompleted');
  if (btn) {
    btn.textContent = `✅ 작성 완료 처리 (${selectedCount}개)`;
    btn.disabled = selectedCount === 0;
  }
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
  
  updateTop20Panel();
  
  console.log('[TOP 10] 하이라이트 완료');
}

// 엑셀 내보내기
async function exportToExcel() {
  if (allProducts.length === 0) {
    showFloatingNotification('내보낼 데이터가 없습니다');
    return { success: false };
  }
  
  const top20 = allProducts.slice(0, Math.min(20, allProducts.length));
  
  let csv = '순위,상품명,상품링크,이미지URL,점수,수수료,할인율,가격\n';
  
  top20.forEach((product, index) => {
    const row = [
      index + 1,
      `"${product.name.replace(/"/g, '""')}"`,
      product.link,
      product.imageUrl,
      product.analyzed ? product.finalScore : product.basicScore,
      product.fee,
      product.discount,
      product.price
    ];
    csv += row.join(',') + '\n';
  });
  
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  
  const date = new Date().toISOString().slice(0, 10);
  link.download = `쇼핑커넥트_TOP20_${date}.csv`;
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
  
  console.log('[엑셀] TOP 20 내보내기 완료');
  showFloatingNotification(`✅ TOP ${top20.length}개 엑셀 저장 완료!`);
  
  return { success: true, count: top20.length };
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
  console.log(`[블랙리스트] ${(blacklist[currentAccount] || []).length}개 상품 제외됨`);
  showFloatingNotification('1차 필터링 시작...');
  
  document.querySelectorAll('[data-filter-checked]').forEach(el => {
    el.removeAttribute('data-filter-checked');
  });
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
  
  checkInterval = setInterval(checkVisibleProducts, 500);
  scrollInterval = setInterval(autoScroll, 1500);
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
    const badge = el.querySelector('.top-badge');
    if (badge) badge.remove();
  });
  
  const notification = document.getElementById('filter-notification');
  if (notification) notification.remove();
  
  const panel = document.getElementById('top20-panel');
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
      
    } else if (request.action === 'getBlacklistCount') {
      const count = (blacklist[currentAccount] || []).length;
      sendResponse({ success: true, count: count });
    }
  } catch (error) {
    console.error('[오류] 메시지 처리:', error);
    sendResponse({ success: false, error: error.message });
  }
  
  return true;
});

// 초기화
Promise.all([
  loadApiSettings(),
  loadBlacklist()
]).then(([hasApi]) => {
  console.log(`[로드] 쇼핑커넥트 프로 필터 v3.4 준비 완료`);
  console.log(`[API] ${hasApi ? '실제 검색' : '시뮬레이션'} 모드`);
  console.log(`[블랙리스트] ${(blacklist[currentAccount] || []).length}개 상품 제외`);
});
