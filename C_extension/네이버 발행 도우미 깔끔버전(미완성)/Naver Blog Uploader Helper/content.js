// Naver Blog Auto Publisher (simplified selectors)
// Flow: Alt+Shift+P -> publish popup -> category -> reservation -> date/time -> confirm prompt

const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

const isVisible = (el) => {
    if (!el) return false;
    const rects = el.getClientRects();
    if (!rects || rects.length === 0) return false;
    const style = window.getComputedStyle(el);
    return style.display !== "none" && style.visibility !== "hidden" && !el.disabled;
};

function setNativeValue(el, value) {
    if (!el) return;
    const setter = Object.getOwnPropertyDescriptor(el.__proto__, "value")?.set || Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
    setter?.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
}

function setSelectValue(el, value) {
    if (!el || el.tagName !== "SELECT") return false;
    el.value = String(value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
}

function findPublishButton(doc) {
    const primary = doc.querySelector(".publish_btn__m9KHH");
    if (isVisible(primary)) return primary;

    const keywords = ["발행", "발행하기", "예약발행", "예약", "등록", "출간", "publish"];
    const candidates = doc.querySelectorAll("button, [role='button'], input[type='button'], input[type='submit']");
    for (const el of candidates) {
        if (!isVisible(el)) continue;
        const text = (el.innerText || el.value || el.getAttribute("aria-label") || el.getAttribute("title") || "").trim();
        if (keywords.some((k) => text.includes(k))) return el;
    }
    return null;
}

async function waitForPublishButton(doc) {
    let btn = null;
    for (let i = 0; i < 6 && !btn; i++) {
        btn = findPublishButton(doc);
        if (!btn) await sleep(700);
    }
    return btn;
}

async function selectCategory(doc, category) {
    if (!category) return;
    const dropdown = doc.querySelector("button.selectbox_button__jb1Dt") || doc.querySelector(".option_category___kpJc button.selectbox_button__jb1Dt");
    if (!dropdown || !isVisible(dropdown)) return;
    dropdown.click();
    await sleep(300);

    const norm = (s) => (s || "").replace(/\s/g, "");
    let layer = null;
    for (let i = 0; i < 5 && !layer; i++) {
        layer = doc.querySelector(".option_list_layer__YX1Tq") ||
                doc.querySelector("[role='menu']") ||
                doc.querySelector(".layer_publish__vA9PX");
        if (!layer) await sleep(200);
    }
    if (!layer) return;

    const options = layer.querySelectorAll(
        "[data-testid^='categoryItemText_'], label.radio_label__mB6ia, span.text__sraQE, input[type='radio']"
    );
    for (const el of options) {
        if (!isVisible(el)) continue;
        const text = (el.innerText || el.getAttribute("data-testid") || "").trim();
        if (norm(text) === norm(category) || norm(text).includes(norm(category))) {
            let target = el.closest("label") || el.closest("button") || el;
            if (el.tagName === "INPUT" && el.id) {
                const lbl = layer.querySelector(`label[for='${el.id}']`);
                if (lbl) target = lbl;
            }
            target.click();
            await sleep(200);
            return;
        }
    }
}

async function setReservation(doc) {
    const reserveRadio = doc.querySelector("input[data-testid='preTimeRadioBtn']") || doc.querySelector("input[name='radio_time'][value='pre']");
    if (reserveRadio && !reserveRadio.checked) {
        reserveRadio.click();
        await sleep(150);
    }
}

async function moveMonth(doc, diff) {
    if (diff === 0) return;
    const nextBtn = doc.querySelector("button.ui-datepicker-next.ui-datepicker-month-nav") || doc.querySelector(".ui-datepicker-next");
    const prevBtn = doc.querySelector("button.ui-datepicker-prev.ui-datepicker-month-nav") || doc.querySelector(".ui-datepicker-prev");
    const targetBtn = diff > 0 ? nextBtn : prevBtn;
    const count = Math.abs(diff);
    if (!targetBtn) return;
    for (let i = 0; i < count; i++) {
        if (!isVisible(targetBtn)) break;
        targetBtn.click();
        await sleep(150);
    }
}

function findDayButton(doc, day) {
    return Array.from(doc.querySelectorAll("button.ui-state-default")).find((btn) => isVisible(btn) && btn.innerText.trim() === String(day));
}

async function setDateTime(doc, targetDate) {
    const dateInput = doc.querySelector(".input_date__QmA0s");
    if (dateInput) {
        dateInput.removeAttribute("readonly");
        dateInput.click();
        await sleep(150);
    }

    const today = new Date();
    const monthDiff = (targetDate.getFullYear() - today.getFullYear()) * 12 + (targetDate.getMonth() - today.getMonth());
    await moveMonth(doc, monthDiff);

    const dayBtn = findDayButton(doc, targetDate.getDate());
    if (dayBtn) {
        dayBtn.click();
        await sleep(150);
    }

    const hourWrap = doc.querySelector("div.hour__ckNMb");
    const minuteWrap = doc.querySelector("div.minute__KXXvZ");
    const hourSelect = (hourWrap && hourWrap.querySelector("select")) || doc.querySelector(".hour_option__J_heO");
    const minuteSelect = (minuteWrap && minuteWrap.querySelector("select")) || doc.querySelector(".minute_option__Vb3xB");

    if (hourSelect) setSelectValue(hourSelect, String(targetDate.getHours()).padStart(2, "0"));
    if (minuteSelect) {
        const minutes = Math.floor(targetDate.getMinutes() / 10) * 10;
        setSelectValue(minuteSelect, String(minutes).padStart(2, "0"));
    }
}

async function runSequence() {
    const topDoc = window.top.document;
    console.log("[run] start");

    const data = await chrome.storage.local.get(["settings", "currentProfile"]);
    const profile = data.currentProfile || "default";
    const settings = (data.settings && data.settings[profile]) || {};
    if (!settings.category) return alert("카테고리를 설정해주세요.");

    let targetDate = new Date();
    if (settings.lastScheduled) {
        const last = new Date(settings.lastScheduled);
        const interval = parseInt(settings.interval || 60, 10);
        const variance = Math.max(0, Math.round(interval * 0.2));
        const randomMin = (Math.random() * (variance * 2)) - variance;
        last.setMinutes(last.getMinutes() + interval + randomMin);
        targetDate = last;
    } else {
        const [h, m] = (settings.startTime || "09:00").split(":").map(Number);
        targetDate.setHours(h || 0, m || 0, 0, 0);
        if (targetDate < new Date()) targetDate.setDate(targetDate.getDate() + 1);
    }

    data.settings = data.settings || {};
    data.settings[profile] = { ...settings, lastScheduled: targetDate.toISOString() };
    await chrome.storage.local.set({ settings: data.settings });

    const publishBtn = await waitForPublishButton(topDoc);
    if (!publishBtn) return alert("발행 버튼을 찾지 못했습니다. 페이지 로드 상태를 확인해주세요.");
    publishBtn.click();
    await sleep(800);

    await selectCategory(topDoc, settings.category);
    await setReservation(topDoc);
    await setDateTime(topDoc, targetDate);

    const hh = String(targetDate.getHours()).padStart(2, "0");
    const mm = String(Math.floor(targetDate.getMinutes() / 10) * 10).padStart(2, "0");
    const confirmMsg = `[발행 전 확인]\n카테고리: ${settings.category}\n예약시간: ${targetDate.getFullYear()}.${String(targetDate.getMonth() + 1).padStart(2, "0")}.${String(targetDate.getDate()).padStart(2, "0")} ${hh}:${mm}\n\n발행을 진행할까요?`;
    if (!confirm(confirmMsg)) return;

    const finalBtn = topDoc.querySelector("button.confirm_btn__WEaBq") || topDoc.querySelector("[data-testid='seOnePublishBtn']");
    if (finalBtn && isVisible(finalBtn)) finalBtn.click();
}

chrome.runtime.onMessage.addListener((req) => {
    if (req.action === "TRIGGER_PUBLISH_BY_POPUP") runSequence();
});

const hotkeyHandler = (e) => {
    if (e.altKey && e.shiftKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        runSequence();
    }
};

document.addEventListener("keydown", hotkeyHandler, { capture: true });
