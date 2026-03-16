// 단축키 명령 리스너
chrome.commands.onCommand.addListener((command) => {
  // 현재 활성 탭에 메시지 전송
  chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, {command: command});
    }
  });
});
