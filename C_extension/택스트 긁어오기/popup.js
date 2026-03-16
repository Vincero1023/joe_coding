const statusEl = document.getElementById("status");

function setStatus(text, isError = false) {
  statusEl.textContent = text;
  statusEl.style.color = isError ? "#c62828" : "#2e7d32";
}

async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("활성 탭을 찾지 못했습니다.");
  return tab;
}

document.getElementById("copySelection").addEventListener("click", async () => {
  try {
    const tab = await getCurrentTab();
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => (window.getSelection()?.toString() || "").trim()
    });

    if (!result) {
      setStatus("선택된 텍스트가 없습니다.", true);
      return;
    }

    await navigator.clipboard.writeText(result);
    setStatus(`복사 완료 (${result.length}자)`);
  } catch (err) {
    setStatus(`실패: ${err.message}`, true);
  }
});

document.getElementById("downloadPageText").addEventListener("click", async () => {
  try {
    const tab = await getCurrentTab();
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => (document.body?.innerText || "").trim()
    });

    if (!result) {
      setStatus("페이지 텍스트가 비어 있습니다.", true);
      return;
    }

    const blob = new Blob([result], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");

    await chrome.downloads.download({
      url,
      filename: `page_text_${timestamp}.txt`,
      saveAs: true
    });

    setStatus(`저장 완료 (${result.length}자)`);
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  } catch (err) {
    setStatus(`실패: ${err.message}`, true);
  }
});
