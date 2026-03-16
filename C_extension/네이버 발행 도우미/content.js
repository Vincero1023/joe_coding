// Naver Blog Auto Publisher (robust selectors, keyboard-first)
// Flow: publish button -> settings (or manual prompt) -> category -> reservation -> date/time

const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

// Safely set value for React-controlled inputs
function setNativeValue(el, value) {
    if (!el || el.tagName !== "INPUT") return;
    const valueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    const proto = Object.getPrototypeOf(el);
    const protoSetter = Object.getOwnPropertyDescriptor(proto, "value")?.set;
    (protoSetter || valueSetter)?.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
}

const isVisible = (el) => el && el.offsetParent !== null && el.offsetWidth > 0 && el.offsetHeight > 0 && !el.disabled;

function findElByText(selectors, text) {
    const list = Array.isArray(selectors) ? selectors : [selectors];
    for (const sel of list) {
        const els = document.querySelectorAll(sel);
        for (const el of els) {
            if (!isVisible(el)) continue;
            if ((el.innerText || "").replace(/\s/g, "").includes(text.replace(/\s/g, ""))) return el;
        }
    }
    return null;
}

function getNextTabbable(anchor) {
    if (!anchor) return null;
    const doc = window.top.document;
    const all = Array.from(doc.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])')).filter(isVisible);
    for (const el of all) {
        if (anchor.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING) return el;
    }
    return null;
}

function pressKey(el, key = "Enter") {
    if (!el) return;
    el.focus();
    const codes = { Enter: 13, Space: 32, ArrowLeft: 37, ArrowRight: 39 };
    const code = codes[key] || key.charCodeAt?.(0) || 13;
    const opts = { key, code: key, keyCode: code, which: code, bubbles: true, cancelable: true, view: window };
    el.dispatchEvent(new KeyboardEvent("keydown", opts));
    el.dispatchEvent(new KeyboardEvent("keypress", opts));
    el.dispatchEvent(new KeyboardEvent("keyup", opts));
    if (key === "Enter" || key === "Space") el.click();
}

// Triggers
chrome.runtime.onMessage.addListener((req) => {
    if (req.action === "TRIGGER_PUBLISH_BY_POPUP") runSequence();
});

document.addEventListener("keydown", (e) => {
    if (e.altKey && e.shiftKey && (e.key === "p" || e.key === "P")) {
        e.preventDefault(); // prevent Chrome tab group
        runSequence();
    }
});

// Main
async function runSequence() {
    const topDoc = window.top.document;
    console.log("[run] runSequence start");

    const data = await chrome.storage.local.get(["settings", "currentProfile"]);
    const profile = data.currentProfile || "default";
    const settings = (data.settings && data.settings[profile]) || {};
    if (!settings.category) return alert("\uCE74\uD14C\uACE0\uB9AC\uB97C \uC124\uC815\uD574\uC8FC\uC138\uC694.");

    let targetDate = new Date();
    if (settings.lastScheduled) {
        const last = new Date(settings.lastScheduled);
        const interval = parseInt(settings.interval || 60, 10);
        const variance = interval * 0.1;
        const randomMin = (Math.random() * variance * 2) - variance;
        last.setMinutes(last.getMinutes() + interval + randomMin);
        targetDate = last;
    } else {
        const [sh, sm] = (settings.startTime || "09:00").split(":").map(Number);
        targetDate.setHours(sh, sm, 0, 0);
        if (targetDate < new Date()) targetDate.setDate(targetDate.getDate() + 1);
    }

    if (isInBlockTime(targetDate, settings)) {
        alert("\uC124\uC815\uD55C \uAE08\uC9C0 \uC2DC\uAC04\uB300\uC785\uB2C8\uB2E4. \uC2DC\uAC04\uC744 \uC870\uC815\uD55C \uB4A4 \uB2E4\uC2DC \uC2DC\uB3C4\uD574\uC8FC\uC138\uC694.");
        return;
    }

    data.settings = data.settings || {};
    data.settings[profile] = settings;
    settings.lastScheduled = targetDate.toISOString();
    await chrome.storage.local.set({ settings: data.settings });

    const publishBtn = findPublishButton(topDoc);
    if (!publishBtn) return alert("\uBC1C\uD589 \uBC84\uD2BC\uC744 \uCC3E\uC9C0 \uBABB\uD588\uC5B4\uC694. \uD398\uC774\uC9C0\uAC00 \uC644\uC804\uD788 \uC5F4\uB838\uB294\uC9C0 \uD655\uC778\uD574\uC8FC\uC138\uC694.");
    publishBtn.click();
    await sleep(1500);

    await selectCategory(topDoc, settings.category);

    const reserveLabel = findElByText(["label", "span", "div", "button"], "\uC608\uC57D");
    if (reserveLabel) {
        const ctl = reserveLabel.closest("label")?.querySelector("input") || reserveLabel.querySelector("input") || reserveLabel;
        ctl.click();
        await sleep(500);
    }

    await setDateTime(topDoc, targetDate);

    const summary = `\uCE74\uD14C\uACE0\uB9AC: ${settings.category}\n\uC608\uC57D \uC2DC\uAC04: ${formatDateTime(targetDate)}\n\n\uBC1C\uD589\uD560\uAE4C\uC694?`;
    if (!window.confirm(summary)) return;

    const confirmBtn = findFinalPublishButton(topDoc);
    if (confirmBtn) {
        confirmBtn.click();
        await sleep(1200);
    } else {
        alert("\uBC1C\uD589 \uD655\uC778 \uBC84\uD2BC\uC744 \uCC3E\uC9C0 \uBABB\uD588\uC2B5\uB2C8\uB2E4.");
    }
}

// Helpers
function findPublishButton(doc) {
    const selectors = [
        "button.publish_btn__m9KHH[data-click-area='tpb.publish']",
        "#root > div > div.header__Ceaap > div > div.publish_btn_area__KjA2i > div:nth-child(2) > button",
        "[data-testid='seOnePublishBtn']",
        "[data-click-area*='publish']",
        ".layer_popup__i0QOY.is_show__TMSLq button",
        ".publish_btn__m9KHH",
        ".btn_publish",
        ".reserve_btn__Km5Xh",
        "button[class*='publish']",
        "button",
        "[role='button']",
        "input[type='button']",
        "input[type='submit']",
    ];
    const keywords = ["\uBC1C\uD589", "\uBC1C\uD589\uD558\uAE30", "\uC608\uC57D\uBC1C\uD589", "\uC608\uC57D", "\uB4F1\uB85D", "\uCD9C\uAC04", "publish"];
    for (const sel of selectors) {
        for (const el of doc.querySelectorAll(sel)) {
            if (!isVisible(el)) continue;
            const text = (el.innerText || el.value || el.getAttribute("aria-label") || el.getAttribute("title") || "").trim();
            if (keywords.some((k) => text.includes(k))) return el;
        }
    }
    return null;
}

function findFinalPublishButton(doc) {
    const selectors = [
        ".layer_btn_area__UzyKH .confirm_btn__WEaBq",
        "[data-testid='seOnePublishBtn']",
        ".layer_popup__i0QOY.is_show__TMSLq .confirm_btn__WEaBq",
        ".layer_popup__i0QOY.is_show__TMSLq button",
        "[data-click-area*='publish']",
        "button.confirm_btn__WEaBq",
    ];
    for (const sel of selectors) {
        const el = doc.querySelector(sel);
        if (el && isVisible(el)) return el;
    }
    return null;
}

function formatDateTime(date) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${date.getFullYear()}.${pad(date.getMonth() + 1)}.${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function isInBlockTime(date, settings = {}) {
    const enabled = settings.blockEnabled === true || settings.blockEnabled === "true" || settings.blockEnabled === "on";
    if (!enabled) return false;
    const h = (v) => {
        const n = parseInt(v, 10);
        return Number.isFinite(n) ? n : null;
    };
    const sh = h(settings.blockStartH);
    const sm = h(settings.blockStartM);
    const eh = h(settings.blockEndH);
    const em = h(settings.blockEndM);
    if (sh === null || sm === null || eh === null || em === null) return false;
    const toMin = (hr, mi) => hr * 60 + mi;
    const start = toMin(sh, sm);
    const end = toMin(eh, em);
    const cur = toMin(date.getHours(), date.getMinutes());
    if (start === end) return false;
    if (start < end) return cur >= start && cur < end;
    return cur >= start || cur < end;
}

async function selectCategory(doc, category) {
    console.log("[cat] select:", category);
    const dropdown =
        doc.querySelector(".selectbox__SD2nT button") ||
        doc.querySelector('[class*="selectbox_button"]') ||
        doc.querySelector(".input_select__") ||
        doc.querySelector(".option_category___kpJc button") ||
        doc.querySelector("[data-testid*='category']") ||
        findElByText(["button", "div", "span"], "카테고리");
    if (!dropdown) return console.warn("category dropdown not found");
    dropdown.click();
    await sleep(400);

    const norm = (s) => (s || "").replace(/\s/g, "");
    let option = null;
    const layer = doc.querySelector(".option_list_layer__YX1Tq") || doc.querySelector('[role="menu"]');
    if (layer) {
        const textEl = Array.from(layer.querySelectorAll('[data-testid^="categoryItemText_"], .item__sAGX9 .text__sraQE, .option__x0and, .option'))
            .find((el) => norm(el.innerText) === norm(category) || norm(el.innerText).includes(norm(category)));
        if (textEl) option = textEl.closest("label") || textEl.closest("li") || textEl;
        if (!option) {
            const exactLabel = layer.querySelector(`label[for*="_${category}"]`);
            if (exactLabel) option = exactLabel;
        }
        if (!option) {
            const inputMatch = layer.querySelector(`input[id*="_${category}"]`);
            if (inputMatch) option = inputMatch.closest("label") || inputMatch.closest("li") || inputMatch;
        }
        if (option) {
            const testid = option.dataset?.testid || option.querySelector("[data-testid]")?.dataset?.testid;
            if (testid && testid.startsWith("categoryItemText_")) {
                const num = testid.replace("categoryItemText_", "");
                const input = layer.querySelector(`[data-testid="categoryBtn_${num}"]`) ||
                    layer.querySelector(`input[id*="_${category}"]`) ||
                    layer.querySelector(`#${num}_${category}`);
                if (input) option = input;
            }
        }
    }
    if (!option) {
        option = Array.from(doc.querySelectorAll("label, li, button, a, div")).find(
            (el) => isVisible(el) && norm(el.innerText) === norm(category)
        );
    }
    if (option) {
        option.scrollIntoView({ block: "nearest" });
        option.click();
        const input = option.tagName === "INPUT" ? option : option.querySelector("input[type='radio']");
        if (input) {
            input.click();
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }
        await sleep(500);
    } else {
        console.warn("category option not found:", category);
    }
}

function findDateButton(doc) {
    const candidates = [
        ".input_date__QmA0s",
        ".fake_input__Y86t_",
        "[data-testid*='reserveDate']",
        "[class*='date'] input",
        "[class*='date'] button",
        "input[type='text'][value*='.']",
        "button[aria-label*='날짜']",
        "input[aria-label*='날짜']",
        "input[placeholder*='날짜']",
    ];
    for (const sel of candidates) {
        const el = doc.querySelector(sel);
        if (isVisible(el)) return el;
    }
    const reserve = findElByText(["label", "span", "div", "button"], "예약");
    const maybe = reserve ? getNextTabbable(reserve) : null;
    if (isVisible(maybe)) return maybe;
    const dateRegex = /\d{4}\.\s*\d{1,2}\.\s*\d{1,2}/;
    const valueMatch = Array.from(doc.querySelectorAll("input, button")).find(
        (el) => isVisible(el) && dateRegex.test((el.value || el.innerText || "").trim())
    );
    if (valueMatch) return valueMatch;
    return null;
}

async function pickSelectOption(targetText) {
    const layer = Array.from(document.querySelectorAll(".option_list_layer__YX1Tq, [role='menu'], .selectbox_layer, .selectbox__SD2nT"))
        .find((el) => isVisible(el));
    if (!layer) return false;
    const opt = Array.from(layer.querySelectorAll("li, label, button, a, span"))
        .find((el) => isVisible(el) && (el.innerText || "").trim() === targetText);
    if (!opt) return false;
    opt.click();
    await sleep(150);
    return true;
}

async function pickSelect(button, targetText) {
    if (!button) return false;
    button.click();
    await sleep(200);
    const ok = await pickSelectOption(targetText);
    return ok;
}

async function setDateTime(doc, targetDate) {
    console.log("[date] set start", targetDate.toString());
    let dateBtn = findDateButton(doc);
    if (!dateBtn) {
        const reserve = findElByText(["label", "span", "div", "button"], "예약");
        if (reserve) {
            reserve.click();
            await sleep(400);
            dateBtn = findDateButton(doc);
        }
    }
    if (!dateBtn) { console.warn("date input not found"); return; }

    dateBtn.focus();
    dateBtn.click();
    pressKey(dateBtn, "Enter");
    await sleep(400);

    const getCalendar = () =>
        doc.querySelector(".ui-datepicker:not([style*='display: none'])") ||
        doc.querySelector(".ui-datepicker") ||
        doc.querySelector(".layer_calendar") ||
        doc.querySelector(".calendar");

    if (!getCalendar()) {
        dateBtn.click();
        await sleep(400);
    }

    const quickBtns = Array.from(doc.querySelectorAll("button, a, span")).filter(
        (el) => isVisible(el) && ["오늘", "내일"].some((t) => (el.innerText || "").includes(t))
    );
    const today = new Date();
    const isToday = targetDate.toDateString() === today.toDateString();
    const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1);
    const isTomorrow = targetDate.toDateString() === tomorrow.toDateString();
    if (isToday || isTomorrow) {
        const label = isToday ? "오늘" : "내일";
        const qb = quickBtns.find((el) => (el.innerText || "").includes(label));
        if (qb) {
            qb.click();
            await sleep(200);
        }
    }

    const getHeaderText = () => {
        const cal = getCalendar();
        if (!cal) return "";
        const title = cal.querySelector(".ui-datepicker-title") || cal.querySelector(".ui-datepicker-header");
        return (title?.innerText || "").trim();
    };

    const parseHeader = (txt) => {
        const m = txt.match(/(\d{4}).*?(\d{1,2})/);
        if (!m) return null;
        return { year: parseInt(m[1], 10), month: parseInt(m[2], 10) }; // month 1-based
    };

    const moveMonth = async (diff) => {
        if (diff === 0) return;
        const forward = diff > 0;
        const btnSel = forward ? ".ui-datepicker-next, .btn_next" : ".ui-datepicker-prev, .btn_prev";
        const count = Math.abs(diff);
        for (let i = 0; i < count; i++) {
            const btn = doc.querySelector(btnSel);
            if (!btn) { console.warn("[date] nav button missing"); break; }
            btn.click();
            await sleep(220);
        }
    };

    const headerInfo = parseHeader(getHeaderText());
    if (headerInfo) {
        const diffMonths = (targetDate.getFullYear() - headerInfo.year) * 12 + ((targetDate.getMonth() + 1) - headerInfo.month);
        await moveMonth(diffMonths);
    } else {
        console.warn("[date] calendar header parse failed");
    }

    const cal = getCalendar();
    if (cal) {
        const dayBtn = Array.from(cal.querySelectorAll("td button, td a")).find(
            (b) => (b.textContent || "").trim() === String(targetDate.getDate())
        );
        if (dayBtn) {
            dayBtn.focus();
            dayBtn.click();
            await sleep(200);
        } else {
            console.warn("[date] day button not found");
        }
    } else {
        console.warn("[date] calendar not found after open");
    }

    const formatted = `${targetDate.getFullYear()}. ${String(targetDate.getMonth() + 1).padStart(2, "0")}. ${String(targetDate.getDate()).padStart(2, "0")}`;
    if (dateBtn && dateBtn.tagName === "INPUT") {
        setNativeValue(dateBtn, formatted);
    }

    await setTime(doc, dateBtn, targetDate);
}

function findTimeInputs(doc) {
    const isHour = (el) => {
        const hint = (el.getAttribute("aria-label") || el.getAttribute("title") || el.placeholder || el.name || el.className || "").toLowerCase();
        return hint.includes("hour") || hint.includes("time") || hint.includes("시") || hint.includes("시간");
    };
    const isMinute = (el) => {
        const hint = (el.getAttribute("aria-label") || el.getAttribute("title") || el.placeholder || el.name || el.className || "").toLowerCase();
        return hint.includes("min") || hint.includes("분");
    };
    const hour = Array.from(doc.querySelectorAll("input")).find((el) => isVisible(el) && !el.readOnly && isHour(el));
    const minute = Array.from(doc.querySelectorAll("input")).find((el) => isVisible(el) && !el.readOnly && isMinute(el));
    return { hour, minute };
}

function findTimeSelects(doc) {
    const hourSel =
        doc.querySelector("select.hour_option__J_heO") ||
        doc.querySelector(".hour__ckNMb select") ||
        doc.querySelector("select[title*='시간']") ||
        doc.querySelector("select[aria-label*='시간']") ||
        doc.querySelector("select[name*='hour']");
    const minuteSel =
        doc.querySelector("select.minute_option__Vb3xB") ||
        doc.querySelector(".minute__KXXvZ select") ||
        doc.querySelector("select[title*='분']") ||
        doc.querySelector("select[aria-label*='분']") ||
        doc.querySelector("select[name*='min']");
    return { hourSel, minuteSel };
}

function setSelectValue(sel, value) {
    if (!sel) return;
    sel.value = value;
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    sel.dispatchEvent(new Event("input", { bubbles: true }));
}

function findTimeSelectButtons(container, anchor) {
    const elems = Array.from(container.querySelectorAll("button, [role='listbox'], .selectbox_button__jb1Dt, .selectbox__SD2nT button"))
        .filter(isVisible);
    const numericBtns = elems.filter((el) => /\d{1,2}/.test((el.innerText || "").trim()));
    if (numericBtns.length >= 2) return numericBtns;
    if (anchor) {
        return elems.filter((el) => anchor.compareDocumentPosition(el) & Node.DOCUMENT_POSITION_FOLLOWING);
    }
    return elems;
}

async function setTime(doc, dateBtn, targetDate) {
    const hourText = String(targetDate.getHours()).padStart(2, "0");
    const minText = String(targetDate.getMinutes()).padStart(2, "0");

    const { hourSel, minuteSel } = findTimeSelects(doc);
    let hourSet = false;
    let minSet = false;
    if (hourSel) {
        setSelectValue(hourSel, hourText);
        if (hourSel.value !== hourText) {
            const opt = Array.from(hourSel.options || []).find((o) => o.value === hourText || (o.textContent || "").trim() === hourText);
            if (opt) { opt.selected = true; setSelectValue(hourSel, opt.value); }
        }
        hourSet = hourSel.value === hourText;
    }
    if (minuteSel) {
        setSelectValue(minuteSel, minText);
        if (minuteSel.value !== minText) {
            const opt = Array.from(minuteSel.options || []).find((o) => o.value === minText || (o.textContent || "").trim() === minText);
            if (opt) { opt.selected = true; setSelectValue(minuteSel, opt.value); }
        }
        minSet = minuteSel.value === minText;
    }

    const { hour, minute } = findTimeInputs(doc);
    if (!hourSet && hour) { setNativeValue(hour, hourText); hourSet = true; }
    if (!minSet && minute) { setNativeValue(minute, minText); minSet = true; }

    if (!hourSet || !minSet) {
        const container = dateBtn?.closest(".layer_content_set_publish__KDvaV, .layer_popup__i0QOY, .blog_seone_wrap__C5hlm") || doc;
        const selects = findTimeSelectButtons(container, dateBtn || container);
        const hourBtn = !hourSet ? selects[0] : null;
        const minBtn = !minSet ? selects[1] : null;
        if (hourBtn) {
            const ok = await pickSelect(hourBtn, hourText);
            hourSet = hourSet || ok;
        }
        if (minBtn) {
            const ok = await pickSelect(minBtn, minText);
            minSet = minSet || ok;
        }
    }

    if (!hourSet || !minSet) {
        let h = hour;
        let m = minute;
        if (!h && dateBtn) h = getNextTabbable(dateBtn);
        if (!m && h) m = getNextTabbable(h);
        if (h && !hourSet && h.tagName === "INPUT") { setNativeValue(h, hourText); hourSet = true; }
        if (m && !minSet && m.tagName === "INPUT") { setNativeValue(m, minText); minSet = true; }
    }

    if (!hourSet) console.warn("[time] hour input/select not found");
    if (!minSet) console.warn("[time] minute input/select not found");
}
