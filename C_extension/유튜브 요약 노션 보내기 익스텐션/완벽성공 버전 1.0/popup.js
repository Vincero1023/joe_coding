document.addEventListener('DOMContentLoaded', () => {
  const sendBtn = document.getElementById('sendBtn');
  const statusEl = document.getElementById('status');

  sendBtn.addEventListener('click', async () => {
    console.log('[Extension] 버튼 클릭됨');
    statusEl.textContent = '⏳ 데이터 추출 중...';
    statusEl.style.color = '#666';

    try {
      const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      const tab = tabs[0];

      console.log('[Extension] 현재 탭:', tab.url);

      if (!tab.url.includes('youtube.com/watch')) {
        statusEl.textContent = '❌ YouTube 영상 페이지에서만 사용 가능합니다';
        statusEl.style.color = '#f44336';
        return;
      }

      // YouTube 페이지 HTML 가져오기
      statusEl.textContent = '⏳ 채널 정보 확인 중...';
      
      let channelName = '채널명 없음';
      
      try {
        const response = await fetch(tab.url);
        const html = await response.text();
        
        // 채널명 추출 (여러 패턴 시도)
        const patterns = [
          /"ownerChannelName":"([^"]+)"/,
          /"author":"([^"]+)"/,
          /<link itemprop="name" content="([^"]+)">/,
          /"channelName":"([^"]+)"/
        ];
        
        for (const pattern of patterns) {
          const match = html.match(pattern);
          if (match && match[1]) {
            channelName = match[1];
            break;
          }
        }
        
        console.log('[Extension] 채널명:', channelName);
      } catch (error) {
        console.log('[Extension] 채널명 추출 실패:', error.message);
      }

      statusEl.textContent = '⏳ 전송 중...';
      console.log('[Extension] Webhook 전송 시작...');

      // 재시도 로직
      let lastError = null;
      const maxRetries = 3;
      
      for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
          const response = await fetch('https://josephamy2.ddns.net/webhook/youtube-summary', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              url: tab.url,
              title: tab.title.replace(' - YouTube', ''),
              channel: channelName
            }),
            signal: AbortSignal.timeout(10000)
          });

          console.log('[Extension] Webhook 응답:', response.status);

          if (response.ok) {
            statusEl.textContent = '✅ 노션에 저장 완료!';
            statusEl.style.color = '#4caf50';
            setTimeout(() => { window.close(); }, 2000);
            return;
          } else {
            throw new Error('전송 실패: ' + response.status);
          }
        } catch (error) {
          lastError = error;
          console.log(`[Extension] 시도 ${attempt}/${maxRetries} 실패:`, error.message);
          
          if (attempt < maxRetries) {
            statusEl.textContent = `⏳ 재시도 중... (${attempt}/${maxRetries})`;
            await new Promise(resolve => setTimeout(resolve, 1000));
          }
        }
      }

      throw lastError;

    } catch (error) {
      console.error('[Extension] 오류:', error);
      statusEl.textContent = '❌ 오류: ' + error.message;
      statusEl.style.color = '#f44336';
    }
  });
});