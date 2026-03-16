// n8n Webhook URL (환경 변수로 관리)
let N8N_WEBHOOK_URL = 'https://your-n8n-domain.com/webhook/youtube-processor';

// 저장된 단축키 로드
chrome.storage.sync.get(['shortcuts', 'webhookUrl'], (data) => {
  if (data.webhookUrl) {
    N8N_WEBHOOK_URL = data.webhookUrl;
  }
  
  if (data.shortcuts) {
    document.getElementById('shortcut-1').textContent = data.shortcuts['save-current-video'] || 'Ctrl+Shift+Y';
    document.getElementById('shortcut-2').textContent = data.shortcuts['save-playlist'] || 'Ctrl+Shift+P';
    document.getElementById('shortcut-3').textContent = data.shortcuts['subscribe-channel-new'] || 'Ctrl+Shift+N';
    document.getElementById('shortcut-4').textContent = data.shortcuts['subscribe-channel-all'] || 'Ctrl+Shift+A';
  }
});

// 상태 메시지 표시
function showStatus(message, type) {
  const statusDiv = document.getElementById('status');
  statusDiv.textContent = message;
  statusDiv.className = `status show ${type}`;
  
  if (type !== 'loading') {
    setTimeout(() => {
      statusDiv.classList.remove('show');
    }, 3000);
  }
}

// n8n으로 데이터 전송
async function sendToN8n(payload) {
  try {
    const response = await fetch(N8N_WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (response.ok) {
      return { success: true };
    } else {
      return { success: false, error: 'HTTP Error' };
    }
  } catch (error) {
    return { success: false, error: error.message };
  }
}

// YouTube URL에서 ID 추출
function extractYouTubeId(url, type) {
  try {
    const urlObj = new URL(url);
    
    if (type === 'video') {
      return urlObj.searchParams.get('v');
    } else if (type === 'playlist') {
      return urlObj.searchParams.get('list');
    } else if (type === 'channel') {
      // @handle 형식
      const handleMatch = url.match(/@([^\/\?]+)/);
      if (handleMatch) return handleMatch[1];
      
      // /channel/ID 형식
      const channelMatch = url.match(/channel\/([^\/\?]+)/);
      if (channelMatch) return channelMatch[1];
      
      // /c/name 형식
      const customMatch = url.match(/\/c\/([^\/\?]+)/);
      if (customMatch) return customMatch[1];
    }
  } catch (e) {
    return null;
  }
  return null;
}

// 1. 현재 영상 저장
document.getElementById('save-current').addEventListener('click', async () => {
  showStatus('⏳ 처리 중...', 'loading');
  
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  if (!tab.url.includes('youtube.com/watch')) {
    showStatus('❌ YouTube 영상 페이지에서만 사용 가능합니다', 'error');
    return;
  }
  
  const videoId = extractYouTubeId(tab.url, 'video');
  if (!videoId) {
    showStatus('❌ 영상 ID를 찾을 수 없습니다', 'error');
    return;
  }
  
  const result = await sendToN8n({
    type: 'playlist',
    url: `https://www.youtube.com/playlist?list=${playlistId}`
  });
  
  if (result.success) {
    showStatus('✅ 요약 시작! Notion에서 확인하세요', 'success');
  } else {
    showStatus('❌ 전송 실패: ' + result.error, 'error');
  }
});

// 2. 재생목록 저장
document.getElementById('save-playlist').addEventListener('click', async () => {
  const playlistUrl = prompt(
    '재생목록 URL을 입력하세요:\n\n예시:\nhttps://www.youtube.com/playlist?list=PL11TYnq_c4Vl28ZDe2qbXewvc9lBJ5usI'
  );
  
  if (!playlistUrl) return;
  
  const playlistId = extractYouTubeId(playlistUrl, 'playlist');
  if (!playlistId) {
    showStatus('❌ 올바른 재생목록 URL을 입력하세요', 'error');
    return;
  }
  
  showStatus('⏳ 재생목록 처리 중... (15초 간격)', 'loading');
  
  const result = await sendToN8n({
    type: 'playlist',
    url: `https://www.youtube.com/playlist?list=${playlistId}`
  });
  
  if (result.success) {
    showStatus('✅ 재생목록 처리 시작! Notion에서 확인하세요', 'success');
  } else {
    showStatus('❌ 전송 실패: ' + result.error, 'error');
  }
});

// 3. 채널 구독 (신규만)
document.getElementById('subscribe-new').addEventListener('click', async () => {
  const channelUrl = prompt(
    '채널 URL을 입력하세요:\n\n예시:\nhttps://www.youtube.com/@cbsrenew\nhttps://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw'
  );
  
  if (!channelUrl) return;
  
  const channelId = extractYouTubeId(channelUrl, 'channel');
  if (!channelId) {
    showStatus('❌ 올바른 채널 URL을 입력하세요', 'error');
    return;
  }
  
  showStatus('⏳ 채널 등록 중...', 'loading');
  
  const result = await sendToN8n({
    type: 'subscribe_channel',
    mode: 'new_only',
    channel_id: channelId,
    channel_url: channelUrl
  });
  
  if (result.success) {
    showStatus('✅ 채널 등록 완료! 6시간마다 자동 수집됩니다', 'success');
  } else {
    showStatus('❌ 전송 실패: ' + result.error, 'error');
  }
});

// 4. 채널 구독 (전체)
document.getElementById('subscribe-all').addEventListener('click', async () => {
  const channelUrl = prompt(
    '채널 URL을 입력하세요:\n\n⚠️ 주의: 모든 영상을 처리합니다 (시간이 오래 걸릴 수 있습니다)\n\n예시:\nhttps://www.youtube.com/@cbsrenew'
  );
  
  if (!channelUrl) return;
  
  const confirmed = confirm(
    '채널의 모든 영상을 처리하시겠습니까?\n\n영상 개수에 따라 수 시간이 걸릴 수 있습니다.\n(15초 간격으로 처리됩니다)'
  );
  
  if (!confirmed) return;
  
  const channelId = extractYouTubeId(channelUrl, 'channel');
  if (!channelId) {
    showStatus('❌ 올바른 채널 URL을 입력하세요', 'error');
    return;
  }
  
  showStatus('⏳ 채널 등록 및 전체 영상 처리 중...', 'loading');
  
  const result = await sendToN8n({
    type: 'subscribe_channel',
    mode: 'all_videos',
    channel_id: channelId,
    channel_url: channelUrl
  });
  
  if (result.success) {
    showStatus('✅ 채널 등록 완료! 전체 영상 처리가 시작되었습니다', 'success');
  } else {
    showStatus('❌ 전송 실패: ' + result.error, 'error');
  }
});

// 설정 페이지 열기
document.getElementById('open-settings').addEventListener('click', () => {
  chrome.runtime.openOptionsPage();
});
