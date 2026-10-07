"""원고(.md)를 네이버 스마트에디터에 붙여 넣을 '붙여넣기 화면'(.html)으로 바꾼다.

ChatGPT 코드 인터프리터에서도, 내 PC 파이썬에서도 돈다(표준 라이브러리만 씀).

    python 원고_변환.py 원고.md                    # 원고.html 생성
    python 원고_변환.py 원고.md --accent "#2563eb" --always-tags "#태그1 #태그2"

만들어지는 화면:
- 맨 위: 제목·카테고리·태그 복사 버튼, 사진 목록, 남은 [확인 필요] 경고
- 가운데: 본문. [본문 복사] 버튼 → 네이버 글쓰기 본문 칸에 Ctrl+V
- 사진·소스코드·스티커 자리는 본문에 [사진 1 …] 같은 표시로 남는다 → 네이버에서 그 자리에 직접 넣고 표시를 지운다.

네이버 에디터에서 알게 된 것(서식이 깨지지 않게 하는 이유):
- 글자마다 크기·색을 직접 적어야 한다. 안 적으면 바로 앞 줄 서식(19px 소제목, 회색 줄)이 다음 줄로 번진다.
- span 안에 span 을 넣으면 안쪽 색이 버려진다 → 같은 줄의 조각은 나란히 둔다.
- <h2>·<h3> 는 그냥 굵은 글이 된다 → 소제목은 '빈 줄 + 19px 굵게'로 만든다.
- <pre> 코드는 한 줄로 뭉개진다 → 코드는 에디터의 '소스코드' 칸에 따로 넣는다.
- 목록 항목 안의 줄바꿈은 항목을 둘로 쪼갠다 → 긴 설명은 '↳' 줄로 쓴다.
"""
import argparse
import html
import re
import sys
from pathlib import Path

BLACK, GRAY = "#000000", "#6b7280"
BODY, SMALL, HEAD = 15, 13, 19


def esc(s):
    return html.escape(s, quote=False)


def run(text, size, color, bold=False, href=None):
    span = f'<span style="font-size:{size}px;color:{color}">{esc(text)}</span>'
    if href:
        span = f'<a href="{html.escape(href)}">{span}</a>'
    return f"<b>{span}</b>" if bold else span


def inline(s, accent, size=BODY, color=BLACK, bold=False):
    """`==강조==` 굵게(+강조색), `**굵게**`, `[글](주소)` 링크, `코드` 는 기호만 뺀다."""
    s = s.replace("`", "")
    out, pos = [], 0
    for m in re.finditer(r"==(.+?)==|\*\*(.+?)\*\*|\[([^\]]+)\]\((https?://[^)\s]+)\)", s):
        if m.start() > pos:
            out.append(run(s[pos:m.start()], size, color, bold))
        if m.group(1) is not None:
            out.append(run(m.group(1), size, accent or color, True))
        elif m.group(2) is not None:
            out.append(run(m.group(2), size, color, True))
        else:
            out.append(run(m.group(3), size, "#2563eb", bold, href=m.group(4)))
        pos = m.end()
    if pos < len(s):
        out.append(run(s[pos:], size, color, bold))
    return "".join(out) or "<br>"


def marker(label):
    """네이버에서 직접 채울 자리. 눈에 띄게, 붙여 넣은 뒤 지우기 쉽게."""
    return (f'<p><b><span style="font-size:{BODY}px;color:#b45309;background:#fef3c7">'
            f'{esc(label)}</span></b></p>')


def parse(text):
    meta, body = {}, text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            _, fm, body = parts
            for line in fm.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
    return meta, body.strip("\n").splitlines()


def convert(md_path, accent, always_tags):
    meta, lines = parse(Path(md_path).read_text(encoding="utf-8"))

    # 마지막 '#태그 #태그' 줄은 본문이 아니라 태그 칸으로 보낸다.
    tags = []
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and re.fullmatch(r"(#\S+\s*)+", lines[-1].strip()):
        tags = [t.lstrip("#") for t in lines.pop().split()]
    for t in always_tags:
        if t not in tags:
            tags.append(t)

    out, images, codes, warnings = [], [], [], []
    list_tag, in_code, code_buf, code_lang = None, False, [], ""

    def close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    def spacer():
        if out and out[-1] != "<p><br></p>":
            out.append("<p><br></p>")

    for raw in lines:
        line = raw.rstrip()
        s = line.strip()

        if in_code:
            if s.startswith("```"):
                codes.append({"lang": code_lang or "코드", "code": "\n".join(code_buf)})
                out.append(marker(f"[소스코드 {len(codes)} 넣기 — 위 '소스코드 {len(codes)}' 복사 → 에디터 '소스코드' 칸]"))
                in_code, code_buf = False, []
            else:
                code_buf.append(line)
            continue
        if s.startswith("```"):
            close_list()
            in_code, code_lang = True, s[3:].strip()
            continue

        if "[확인 필요" in s:
            warnings.append(s)

        img = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", s)
        if img:
            close_list()
            images.append({"alt": img.group(1), "path": img.group(2)})
            first = " · 대표 사진" if len(images) == 1 else ""
            out.append(marker(f"[사진 {len(images)}{first} — {img.group(1) or img.group(2)} ({Path(img.group(2)).name})]"))
            continue

        if s == "{sticker}":
            close_list()
            out.append(marker("[스티커 넣기]"))
            continue

        if not s:
            close_list()
            if out and not out[-1].startswith("<p><b><span style=\"font-size:19px"):
                spacer()
            continue

        m = re.match(r"#{2,3}\s+(.*)", s)
        if m:
            close_list()
            spacer()
            out.append(f"<p>{inline(m.group(1), accent, HEAD, BLACK, True)}</p>")
            continue

        if s.startswith("↳"):
            close_list()
            out.append(f"<p>{inline(s, accent, SMALL, GRAY)}</p>")
            continue

        if s.startswith(">"):
            close_list()
            out.append(f'<blockquote><p>{inline(s.lstrip("> "), accent)}</p></blockquote>')
            continue

        m = re.match(r"(?:[-*]|(\d+)\.)\s+(.*)", s)
        if m:
            tag = "ol" if m.group(1) else "ul"
            if list_tag != tag:
                close_list()
                out.append(f"<{tag}>")
                list_tag = tag
            out.append(f"<li>{inline(m.group(2), accent)}</li>")
            continue

        close_list()
        out.append(f"<p>{inline(s, accent)}</p>")

    close_list()
    if in_code:
        warnings.append("닫히지 않은 ``` 코드 칸이 있습니다.")
    if len(tags) > 30:
        warnings.append(f"태그가 {len(tags)}개입니다. 네이버는 30개까지만 들어갑니다.")
    return meta, "\n".join(out), images, codes, tags, warnings


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_esc} · 붙여넣기</title>
<style>
  :root {{ --bg:#f4f5f7; --card:#fff; --ink:#0c0f14; --ink2:#5c6371; --blue:#2563eb;
          --shadow:0 1px 2px rgba(12,15,20,.04),0 14px 34px -18px rgba(12,15,20,.16); }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink); font-family:'Malgun Gothic','Apple SD Gothic Neo',sans-serif; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:28px 16px 80px; }}
  .card {{ background:var(--card); border-radius:16px; box-shadow:var(--shadow); padding:22px 24px; margin-bottom:18px; }}
  h1 {{ font-size:22px; margin:0 0 6px; }} .meta {{ color:var(--ink2); font-size:14px; margin:0 0 14px; }}
  .row {{ display:flex; flex-wrap:wrap; gap:8px; }}
  button {{ font:inherit; font-size:14px; font-weight:700; border:0; border-radius:10px; padding:10px 14px; cursor:pointer; background:#e6ecff; color:var(--blue); }}
  button.main {{ background:var(--blue); color:#fff; }}
  button.done {{ background:#dcfce7; color:#15803d; }}
  .warn {{ background:#fef3c7; color:#92400e; border-radius:12px; padding:12px 14px; font-size:14px; margin-top:14px; }}
  .warn li {{ margin:4px 0; }}
  ol.steps {{ margin:12px 0 0; padding-left:20px; color:var(--ink2); font-size:14px; line-height:1.7; }}
  .label:first-child {{ margin-top:0; }}
  .label {{ font-size:13px; color:var(--ink2); font-weight:700; margin:16px 0 8px; }}
  .imgs {{ font-size:14px; line-height:1.8; margin:0; padding-left:20px; }}
  pre {{ background:#f4f5f7; border-radius:10px; padding:12px; overflow:auto; font-size:13px; margin:8px 0 0; }}
  #post {{ line-height:1.8; word-break:keep-all; }}
  #post p {{ margin:0; }} #post blockquote {{ margin:8px 0; padding:8px 14px; background:#f4f5f7; border-radius:10px; }}
</style></head>
<body><div class="wrap">

<div class="card">
  <h1>{title_esc}</h1>
  <p class="meta">카테고리: {category_esc} · 사진 {n_img}장 · 소스코드 {n_code}개 · 태그 {n_tag}개</p>
  <div class="row">
    <button class="main" data-copy-node="post">본문 복사</button>
    <button data-copy-text="title">제목 복사</button>
    <button data-copy-text="tags">태그 복사</button>
  </div>
  {warn_html}
  <ol class="steps">
    <li>네이버 블로그 글쓰기 → 제목 칸에 <b>제목 복사</b> 붙여넣기</li>
    <li>본문 칸 클릭 → <b>본문 복사</b> 후 Ctrl+V</li>
    <li>노란 표시 자리마다 사진·소스코드·스티커를 넣고 표시 줄은 지우기 (첫 사진이 대표 사진)</li>
    <li>발행 설정에서 카테고리·태그 확인 → <b>임시저장</b>까지만. 발행은 직접 판단해서</li>
  </ol>
</div>

{imgs_html}
{codes_html}

<div class="card"><div id="post">
{body}
</div></div>

</div>
<textarea id="title" hidden>{title_esc}</textarea>
<textarea id="tags" hidden>{tags_esc}</textarea>
{code_areas}
<script>
function flash(b) {{ const t = b.textContent; b.textContent = '복사됨'; b.classList.add('done');
  setTimeout(() => {{ b.textContent = t; b.classList.remove('done'); }}, 1400); }}
function copyNode(id) {{
  const sel = getSelection(), r = document.createRange();
  r.selectNodeContents(document.getElementById(id));
  sel.removeAllRanges(); sel.addRange(r); document.execCommand('copy'); sel.removeAllRanges();
}}
function copyText(id) {{
  const v = document.getElementById(id).value;
  if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(v);
  const t = document.createElement('textarea'); t.value = v; document.body.appendChild(t);
  t.select(); document.execCommand('copy'); t.remove();
}}
document.addEventListener('click', e => {{
  const b = e.target.closest('button'); if (!b) return;
  if (b.dataset.copyNode) copyNode(b.dataset.copyNode);
  if (b.dataset.copyText) copyText(b.dataset.copyText);
  flash(b);
}});
</script>
</body></html>
"""


def build(md_path, out_path, accent, always_tags):
    meta, body, images, codes, tags, warnings = convert(md_path, accent, always_tags)
    title = meta.get("제목", Path(md_path).stem)
    category = meta.get("카테고리", "(원고에 없음)")

    warn_html = ""
    if warnings:
        items = "".join(f"<li>{esc(w)}</li>" for w in warnings)
        warn_html = f'<div class="warn"><b>넣기 전에 확인할 것 {len(warnings)}건</b><ul>{items}</ul></div>'

    imgs_html = ""
    if images:
        items = "".join(f"<li>{esc(i['alt'] or '사진')} — <code>{esc(i['path'])}</code></li>" for i in images)
        imgs_html = f'<div class="card"><div class="label">사진 넣을 순서</div><ol class="imgs">{items}</ol></div>'

    codes_html, code_areas = "", ""
    if codes:
        blocks = []
        for n, c in enumerate(codes, 1):
            blocks.append(f'<div class="label">소스코드 {n} ({esc(c["lang"])}) '
                          f'<button data-copy-text="code{n}">복사</button></div><pre>{esc(c["code"])}</pre>')
            code_areas += f'<textarea id="code{n}" hidden>{esc(c["code"])}</textarea>\n'
        codes_html = f'<div class="card">{"".join(blocks)}</div>'

    page = PAGE.format(
        title_esc=esc(title), category_esc=esc(category),
        n_img=len(images), n_code=len(codes), n_tag=len(tags),
        warn_html=warn_html, imgs_html=imgs_html, codes_html=codes_html,
        body=body, tags_esc=esc(", ".join(tags)), code_areas=code_areas,
    )
    Path(out_path).write_text(page, encoding="utf-8")
    return title, images, codes, tags, warnings


def main():
    ap = argparse.ArgumentParser(description="원고 .md → 네이버 붙여넣기 화면 .html")
    ap.add_argument("md")
    ap.add_argument("-o", "--output", help="결과 .html 경로 (기본: 원고와 같은 이름)")
    ap.add_argument("--accent", default=None, help="==강조 구절== 색, 예: \"#2563eb\" (없으면 굵게만)")
    ap.add_argument("--always-tags", default="", help='모든 글에 붙일 태그, 예: "#태그1 #태그2"')
    a = ap.parse_args()

    out = a.output or str(Path(a.md).with_suffix(".html"))
    always = [t.lstrip("#") for t in a.always_tags.split()]
    title, images, codes, tags, warnings = build(a.md, out, a.accent, always)
    print(f"만듦: {out}")
    print(f"제목: {title}")
    print(f"사진 {len(images)}장 · 소스코드 {len(codes)}개 · 태그 {len(tags)}개")
    for w in warnings:
        print(f"확인 필요: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
