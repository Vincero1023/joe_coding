from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bs4 import BeautifulSoup

from benchmark_tool.analyzer.site_analyzer import analyze_document, merge_site_analyses
from benchmark_tool.core.loader import load_html_file


TOOL_HTML = """
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <title>키워드 도구</title>
  </head>
  <body>
    <main>
      <section>
        <h1>키워드 분석 도구</h1>
        <p>CPC, 검색량, 경쟁도를 기반으로 키워드를 분석합니다.</p>
        <input type="search" name="keyword" placeholder="키워드 입력" />
        <textarea name="seed_keywords" placeholder="확장 키워드 입력"></textarea>
        <select name="cpc_filter">
          <option>최소 CPC</option>
        </select>
        <button>분석 시작</button>
        <button>추천 키워드 확장</button>
      </section>
      <section>
        <h2>결과</h2>
        <table>
          <thead>
            <tr>
              <th>키워드</th>
              <th>검색량</th>
              <th>CPC</th>
              <th>경쟁도</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>키워드 도구</td>
              <td>1000</td>
              <td>2.3</td>
              <td>중간</td>
            </tr>
          </tbody>
        </table>
        <ul>
          <li>추천 키워드</li>
          <li>연관 키워드 확장</li>
        </ul>
      </section>
      <p>스코어 시스템은 CPC + 검색량 + 경쟁도를 반영합니다.</p>
    </main>
  </body>
</html>
"""

CONTENT_HTML = """
<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <title>키워드 가이드 블로그</title>
  </head>
  <body>
    <article>
      <h1>키워드 추천 가이드</h1>
      <p>이 블로그 글은 키워드 확장과 검색량 확인 방법을 설명합니다.</p>
      <p>article guide blog usage manual</p>
    </article>
  </body>
</html>
"""


class BenchmarkToolAnalyzerTests(unittest.TestCase):
    def test_semantic_analysis_prefers_meaning_over_counts(self) -> None:
        soup = BeautifulSoup(TOOL_HTML, "html.parser")

        analysis = analyze_document("tool.html", TOOL_HTML, soup)

        self.assertEqual(analysis["site_type"], ["keyword_tool"])
        self.assertEqual(
            analysis["core_functions"],
            ["keyword_analysis", "keyword_expansion", "scoring_system", "data_filtering"],
        )
        self.assertEqual(
            analysis["important_keywords"],
            ["CPC", "검색량", "키워드", "확장", "추천"],
        )
        self.assertEqual(analysis["monetization_model"], "CPC 기반 키워드 분석 SaaS")
        self.assertEqual(analysis["data_source"], "검색 데이터 추정")
        self.assertEqual(
            analysis["business_logic"],
            [
                "고CPC 키워드 우선 노출",
                "검색량 + 경쟁도 조합 분석",
                "CPC 기반 키워드 점수화",
                "고가 키워드 필터링",
                "연관 키워드 추천 및 확장",
            ],
        )
        self.assertEqual(
            analysis["ui_components"],
            [
                {"type": "input", "role": "keyword search"},
                {"type": "textarea", "role": "bulk keyword input"},
                {"type": "filter", "role": "data filtering"},
                {"type": "table", "role": "data results"},
                {"type": "list", "role": "keyword suggestions"},
            ],
        )
        self.assertIn(
            {"feature": "keyword_scoring", "logic": "CPC + 검색량 + 경쟁도 기반 점수 계산"},
            analysis["feature_logic"],
        )
        for item in analysis["ui_components"]:
            self.assertNotIn("count", item)
            self.assertNotIn("examples", item)

    def test_integrated_site_type_allows_keyword_tool_and_content_site(self) -> None:
        tool_analysis = analyze_document("tool.html", TOOL_HTML, BeautifulSoup(TOOL_HTML, "html.parser"))
        content_analysis = analyze_document("content.html", CONTENT_HTML, BeautifulSoup(CONTENT_HTML, "html.parser"))

        merged = merge_site_analyses(
            [
                {"source_file": "tool.html", "analysis": tool_analysis},
                {"source_file": "content.html", "analysis": content_analysis},
            ],
            content_exports=[
                {
                    "index": 1,
                    "title": "키워드 추천 가이드",
                    "source_file": "content.html",
                    "html_file": "guide_1.html",
                    "markdown_file": "guide_1.md",
                    "text_length": 999,
                    "keyword_hits": ["가이드"],
                }
            ],
        )

        self.assertEqual(merged["site_type"], ["keyword_tool", "content_site"])
        self.assertIn("content_guidance", merged["core_functions"])
        self.assertEqual(merged["monetization_model"], "CPC 기반 키워드 분석 SaaS")
        self.assertEqual(merged["data_source"], "검색 데이터 추정")
        self.assertEqual(
            merged["business_logic"],
            [
                "고CPC 키워드 우선 노출",
                "검색량 + 경쟁도 조합 분석",
                "CPC 기반 키워드 점수화",
                "고가 키워드 필터링",
                "연관 키워드 추천 및 확장",
            ],
        )
        self.assertIn({"type": "article", "role": "guide content"}, merged["ui_components"])
        self.assertIn(
            {"feature": "content_guidance", "logic": "블로그/가이드 콘텐츠로 키워드 전략과 도구 사용법을 제공"},
            merged["feature_logic"],
        )
        self.assertEqual(
            merged["content_exports"],
            [
                {
                    "index": 1,
                    "title": "키워드 추천 가이드",
                    "source_file": "content.html",
                    "html_file": "guide_1.html",
                    "markdown_file": "guide_1.md",
                }
            ],
        )
        self.assertNotIn("modules", merged)
        feature_goals = [feature["goal"] for feature in merged["features"]]
        self.assertEqual(
            feature_goals,
            [
                "키워드 검색",
                "키워드 확장",
                "점수 계산",
                "필터링",
                "콘텐츠 제공",
            ],
        )
        keyword_feature = next(feature for feature in merged["features"] if feature["goal"] == "키워드 검색")
        self.assertEqual(
            keyword_feature["description"],
            "사용자가 키워드의 검색량, CPC, 경쟁도를 확인하려고 할 때 선택하는 기능",
        )
        self.assertIn({"type": "input", "role": "keyword search"}, keyword_feature["ui"])
        self.assertIn({"type": "input", "role": "keyword seed"}, keyword_feature["inputs"])
        self.assertIn({"type": "table", "role": "keyword metrics"}, keyword_feature["outputs"])
        self.assertIn("입력 키워드의 검색량, CPC, 경쟁도 데이터를 조회", keyword_feature["logic"])
        self.assertIn("고CPC 키워드 우선 노출", keyword_feature["logic"])

        content_feature = next(feature for feature in merged["features"] if feature["goal"] == "콘텐츠 제공")
        self.assertEqual(content_feature["ui"], [{"type": "article", "role": "guide content"}])
        self.assertEqual(content_feature["inputs"], [])
        self.assertEqual(content_feature["outputs"], [{"type": "article", "role": "guide articles"}])
        self.assertIn(
            "블로그/가이드 콘텐츠로 키워드 전략과 도구 사용법을 제공",
            content_feature["logic"],
        )

    def test_loader_decodes_declared_cp949_html(self) -> None:
        with TemporaryDirectory() as tempdir:
            file_path = Path(tempdir) / "sample.html"
            html = """
            <html>
              <head>
                <meta charset="cp949">
                <title>키워드 분석</title>
              </head>
              <body>검색량 추천</body>
            </html>
            """
            file_path.write_bytes(html.encode("cp949"))

            _path, loaded_html, _soup = load_html_file(str(file_path))

        self.assertIn("키워드 분석", loaded_html)
        self.assertIn("검색량 추천", loaded_html)

    def test_data_source_prefers_naver_api_when_signals_exist(self) -> None:
        html = """
        <html>
          <body>
            <h1>네이버 키워드 분석</h1>
            <p>네이버 검색광고 API 기반으로 CPC와 검색량을 조회합니다.</p>
            <script>fetch('/api/naver/keywords')</script>
          </body>
        </html>
        """
        analysis = analyze_document("naver.html", html, BeautifulSoup(html, "html.parser"))

        self.assertEqual(analysis["data_source"], "네이버 광고 API 추정")


if __name__ == "__main__":
    unittest.main()
