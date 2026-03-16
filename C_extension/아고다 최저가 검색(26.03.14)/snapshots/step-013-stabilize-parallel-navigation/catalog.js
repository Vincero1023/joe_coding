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
    {
      id: "google-search-a",
      label: "구글 검색A",
      group: "traffic",
      groupLabel: "검색 경로",
      cid: "GOOGLE_ADS",
      description: "Google 광고 경유"
    },
    {
      id: "google-search-b",
      label: "구글 검색B",
      group: "traffic",
      groupLabel: "검색 경로",
      cid: "GOOGLE_ORGANIC",
      description: "Google 자연검색"
    },
    {
      id: "google-search-c",
      label: "구글 검색C",
      group: "traffic",
      groupLabel: "검색 경로",
      cid: "GOOGLE_AFFILIATE",
      description: "Google 제휴 검색"
    },
    {
      id: "google-maps-a",
      label: "구글지도A",
      group: "traffic",
      groupLabel: "검색 경로",
      cid: "GOOGLE_MAPS_SEARCH",
      description: "Google Maps 호텔검색"
    },
    {
      id: "google-maps-b",
      label: "구글지도B",
      group: "traffic",
      groupLabel: "검색 경로",
      cid: "GOOGLE_MAPS_PLACE",
      description: "Google Maps 장소페이지"
    },
    {
      id: "google-maps-c",
      label: "구글지도C",
      group: "traffic",
      groupLabel: "검색 경로",
      cid: "GOOGLE_MAPS_BOOK",
      description: "Google Maps 예약버튼"
    },
    {
      id: "naver-search",
      label: "네이버 검색",
      group: "traffic",
      groupLabel: "검색 경로",
      cid: "NAVER_SEARCH",
      description: "Naver 검색 경유"
    }
  ],
  cards: [
    {
      id: "bc-card",
      label: "BC카드",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "BC_CARD_PROMO",
      description: "BC 제휴 할인"
    },
    {
      id: "kb-card",
      label: "국민카드",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "KB_CARD_PROMO",
      description: "KB 제휴 할인"
    },
    {
      id: "mastercard",
      label: "마스터카드",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "MASTERCARD_KR",
      description: "Mastercard 코리아"
    },
    {
      id: "visa",
      label: "비자",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "VISA_KR",
      description: "Visa Korea 할인"
    },
    {
      id: "shinhan-master",
      label: "신한(마스터)",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "SHINHAN_MASTER",
      description: "신한 Master 브랜드"
    },
    {
      id: "shinhan-card",
      label: "신한카드",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "SHINHAN_CARD",
      description: "신한 제휴 할인"
    },
    {
      id: "toss",
      label: "토스",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "TOSS_PROMO",
      description: "토스 제휴"
    },
    {
      id: "hyundai-card",
      label: "현대카드",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "HYUNDAI_CARD",
      description: "현대카드 할인"
    },
    {
      id: "hana-card",
      label: "하나",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "HANA_CARD",
      description: "하나카드 할인"
    },
    {
      id: "woori-master",
      label: "우리(마스터)",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "WOORI_MASTER",
      description: "우리 Master 브랜드"
    },
    {
      id: "woori-card",
      label: "우리카드",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "WOORI_CARD",
      description: "우리카드 할인"
    },
    {
      id: "unionpay",
      label: "유니온페이",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "UNIONPAY_KR",
      description: "UnionPay 할인"
    },
    {
      id: "kakaopay",
      label: "카카오페이",
      group: "cards",
      groupLabel: "카드/결제",
      cid: "KAKAOPAY",
      description: "카카오페이 결제 할인"
    }
  ],
  airlines: [
    {
      id: "korean-air",
      label: "대한항공(적립)",
      group: "airlines",
      groupLabel: "항공사/적립",
      cid: "KOREAN_AIR_SKYPASS",
      description: "SkyPass 마일리지 적립"
    },
    {
      id: "asiana",
      label: "아시아나항공(적립)",
      group: "airlines",
      groupLabel: "항공사/적립",
      cid: "ASIANA_MILEAGE",
      description: "Asiana 마일리지 적립"
    },
    {
      id: "air-seoul",
      label: "에어서울",
      group: "airlines",
      groupLabel: "항공사/적립",
      cid: "AIRSEOUL_PROMO",
      description: "Air Seoul 제휴"
    }
  ],
  promos: [
    {
      id: "promo-bc-card",
      label: "BC카드",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../bc-card-promo",
      description: "BC카드 일반 프로모션 페이지"
    },
    {
      id: "promo-kb-card",
      label: "국민",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../kb-card-promo",
      description: "KB 일반 프로모션 페이지"
    },
    {
      id: "promo-korean-air",
      label: "대한항공",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../korean-air-promo",
      description: "대한항공 일반 프로모션 페이지"
    },
    {
      id: "promo-mastercard",
      label: "마스터카드",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../mastercard-promo",
      description: "Mastercard 일반 프로모션 페이지"
    },
    {
      id: "promo-visa",
      label: "비자",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../visa-promo",
      description: "Visa 일반 프로모션 페이지"
    },
    {
      id: "promo-shinhan",
      label: "신한",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../shinhan-promo",
      description: "신한 일반 프로모션 페이지"
    },
    {
      id: "promo-shinhan-master",
      label: "신한(마스터)",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../shinhan-master-promo",
      description: "신한 Master 일반 프로모션 페이지"
    },
    {
      id: "promo-asiana",
      label: "아시아나",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../asiana-promo",
      description: "아시아나 일반 프로모션 페이지"
    },
    {
      id: "promo-unionpay",
      label: "유니온페이",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../unionpay-promo",
      description: "UnionPay 일반 프로모션 페이지"
    },
    {
      id: "promo-woori",
      label: "우리",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../woori-promo",
      description: "우리 일반 프로모션 페이지"
    },
    {
      id: "promo-woori-master",
      label: "우리(마스터)",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../woori-master-promo",
      description: "우리 Master 일반 프로모션 페이지"
    },
    {
      id: "promo-kakaopay",
      label: "카카오페이",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../kakaopay-promo",
      description: "카카오페이 일반 프로모션 페이지"
    },
    {
      id: "promo-toss",
      label: "토스",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../toss-promo",
      description: "토스 일반 프로모션 페이지"
    },
    {
      id: "promo-hana",
      label: "하나",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../hana-promo",
      description: "하나 일반 프로모션 페이지"
    },
    {
      id: "promo-hyundai",
      label: "현대",
      group: "promos",
      groupLabel: "제휴 프로모션",
      mode: "promo-page",
      promoUrl: "https://www.agoda.com/.../hyundai-promo",
      description: "현대 일반 프로모션 페이지"
    }
  ]
};

const AGODA_DEFAULT_SELECTIONS = {
  traffic: AGODA_CATALOG.traffic.map((entry) => entry.id),
  cards: [],
  airlines: [],
  promos: []
};
