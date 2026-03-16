// 단축키 명령 처리
chrome.commands.onCommand.addListener(async (command) => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  
  // Webhook URL 가져오기
  chrome.storage.sync.get(['webhookUrl'], async (data) => {
    const webhookUrl = data.webhookUrl || 'https://your-n8n-domain.com/webhook/youtube-processor';
    
    if (command === 'save-current-video') {
      if (!tab.url.includes('youtube.com/watch')) {
        alert('YouTube 영상 페이지에서만 사용 가능합니다');
        return;
      }
      
      const videoId = new URL(tab.url).searchParams.get('v');
      await sendToN8n(webhookUrl, {
        type: 'single_video',
        url: `https://www.youtube.com/watch?v=${videoId}`
      });
      
      alert('✅ 요약 시작! Notion에서 확인하세요');
    }
    
    else if (command === 'save-playlist') {
      const playlistUrl = prompt('재생목록 URL을 입력하세요:');
      if (!playlistUrl) return;
      
      const playlistId = new URL(playlistUrl).searchParams.get('list');
      await sendToN8n(webhookUrl, {
        type: 'playlist',
        playlist_id: playlistId,
        url: playlistUrl
      });
      
      alert('✅ 재생목록 처리 시작!');
    }
    
    else if (command === 'subscribe-channel-new') {
      const channelUrl = prompt('채널 URL을 입력하세요:');
      if (!channelUrl) return;
      
      await sendToN8n(webhookUrl, {
        type: 'subscribe_channel',
        mode: 'new_only',
        channel_url: channelUrl
      });
      
      alert('✅ 채널 등록 완료!');
    }
    
    else if (command === 'subscribe-channel-all') {
      const channelUrl = prompt('채널 URL을 입력하세요:');
      if (!channelUrl) return;
      
      const confirmed = confirm('채널의 모든 영상을 처리하시겠습니까?');
      if (!confirmed) return;
      
      await sendToN8n(webhookUrl, {
        type: 'subscribe_channel',
        mode: 'all_videos',
        channel_url: channelUrl
      });
      
      alert('✅ 채널 등록 및 전체 영상 처리 시작!');
    }
  });
});

// n8n으로 전송
async function sendToN8n(url, payload) {
  try {
    await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
  } catch (error) {
    console.error('전송 실패:', error);
  }
}
