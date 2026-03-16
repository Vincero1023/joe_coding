# Collection Strategy

## Goal
- 워드프레스 사이트에서 공개적으로 노출된 글 URL을 최대한 많이 수집한다.
- 비공개/관리자/로그인 전용 경로는 제외한다.
- 보호 우회, 프록시 우회, 식별 은닉 기능은 포함하지 않는다.

## Source Order
1. `robots.txt`와 사이트맵(`sitemap.xml`, `wp-sitemap.xml`, `sitemap_index.xml`)
2. 워드프레스 REST API(`wp-json/wp/v2/types` 기준으로 viewable 타입 조회)
3. RSS/Atom 피드(`feed`, `rss2`)
4. 공개 아카이브/목록 페이지(홈, 블로그, 아카이브, 페이지네이션)

## Rules
- 같은 사이트 호스트로만 한정한다.
- `wp-admin`, `wp-login.php`, `wp-json`, `xmlrpc.php`, `search`, `preview`, `feed`, 첨부파일 확장자는 제외한다.
- 요청은 순차 처리하고 짧은 지연을 둔다.
- 결과는 중복 제거 후 URL 목록으로 정리한다.

## Limits
- 사이트맵 최대 24개
- REST API 페이지 타입당 최대 10페이지
- 피드 최대 4개 경로
- 아카이브 페이지 최대 12개

## Notes
- 비밀번호 보호 글도 URL이 공개 소스에 노출되면 주소는 잡힐 수 있다.
- 공개 소스 어디에도 드러나지 않은 비공개 링크는 이 방식으로 찾을 수 없다.
- 이 익스텐션의 요청은 일반적으로 서버, CDN, WAF, 리버스 프록시 로그에 남을 수 있다.
