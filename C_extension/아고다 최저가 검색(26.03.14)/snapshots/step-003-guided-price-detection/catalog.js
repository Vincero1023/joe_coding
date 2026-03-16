const AGODA_DEFAULT_TAG = "4f122210-314e-4c70-b18b-ac93fc25b69f";

const AGODA_MARKET = {
  language: "ko-kr",
  currency: "KRW",
  userCountry: "KR",
  finalPriceView: "1",
  isShowMobileAppPrice: "false",
  defaultTag: AGODA_DEFAULT_TAG
};

const AGODA_CATALOG = {
  traffic: [
    { id: "scanner-default", label: "기본", group: "traffic", groupLabel: "기본/유입", cid: "1439847" },
    { id: "google-maps-1", label: "구글 지도 1", group: "traffic", groupLabel: "기본/유입", cid: "1833981" },
    { id: "google-maps-2", label: "구글 지도 2", group: "traffic", groupLabel: "기본/유입", cid: "1917614" },
    { id: "google-maps-3", label: "구글 지도 3", group: "traffic", groupLabel: "기본/유입", cid: "1829968" },
    { id: "google-search-1", label: "구글 검색 1", group: "traffic", groupLabel: "기본/유입", cid: "1908612" },
    { id: "google-search-2", label: "구글 검색 2", group: "traffic", groupLabel: "기본/유입", cid: "1922868" },
    { id: "google-search-3", label: "구글 검색 3", group: "traffic", groupLabel: "기본/유입", cid: "1776688" },
    { id: "naver-search-1", label: "네이버 검색 1", group: "traffic", groupLabel: "기본/유입", cid: "1729890" }
  ],
  cards: [
    { id: "hyundai-card", label: "현대카드", group: "cards", groupLabel: "카드/결제", cid: "1895693", tag: "A100692912" },
    { id: "kb-card", label: "국민카드", group: "cards", groupLabel: "카드/결제", cid: "1563295" },
    { id: "unionpay", label: "유니온페이", group: "cards", groupLabel: "카드/결제", cid: "1937712", tag: "A100692912" },
    { id: "kakaopay", label: "카카오페이", group: "cards", groupLabel: "카드/결제", cid: "1942636", tag: "A100692912" },
    { id: "woori-card", label: "우리카드", group: "cards", groupLabel: "카드/결제", cid: "1654104" },
    { id: "woori-master", label: "우리(마스터)", group: "cards", groupLabel: "카드/결제", cid: "1932810" },
    { id: "bc-card", label: "BC카드", group: "cards", groupLabel: "카드/결제", cid: "1748498" },
    { id: "shinhan-master", label: "신한(마스터)", group: "cards", groupLabel: "카드/결제", cid: "1917257" },
    { id: "shinhan-card", label: "신한카드", group: "cards", groupLabel: "카드/결제", cid: "1760133" },
    { id: "toss", label: "토스", group: "cards", groupLabel: "카드/결제", cid: "1917334" },
    { id: "hana-card", label: "하나", group: "cards", groupLabel: "카드/결제", cid: "1729471" },
    { id: "mastercard", label: "마스터카드", group: "cards", groupLabel: "카드/결제", cid: "1889572" },
    { id: "visa", label: "비자", group: "cards", groupLabel: "카드/결제", cid: "1889319" }
  ],
  airlines: [
    { id: "korean-air", label: "대한항공(적립)", group: "airlines", groupLabel: "항공사", cid: "1904827" },
    { id: "asiana", label: "아시아나항공(적립)", group: "airlines", groupLabel: "항공사", cid: "1806212" },
    { id: "air-seoul", label: "에어서울", group: "airlines", groupLabel: "항공사", cid: "1800120" }
  ]
};

const AGODA_DEFAULT_SELECTIONS = {
  traffic: AGODA_CATALOG.traffic.map((entry) => entry.id),
  cards: [],
  airlines: []
};
