#coding=utf-8
# Legado（阅读）书源兼容引擎 —— TVBox/OK影视 PY 爬虫
# 一源一站：站点 ext 指向一个 Legado 书源 JSON（URL 或内联），本引擎执行其规则子集：
# CSS/JSoup 选择器（含 class./id./tag. 链式写法与 .N 索引）、@XPath、@Json、##正则替换##、
# 搜索 POST 选项、目录分页（nextTocUrl）、正文分页（nextContentUrl）、正文 replaceRegex 净化。
# 不支持 @js: / <js> / java.* 等需要 JS 引擎的规则（这类源会被过滤，不进内置书源包）。
# 依赖：requests + beautifulsoup4（壳内 Chaquopy requirements 自带），其余标准库。Python 3.8 兼容。
import sys
sys.path.append('..')
import re
import json
import traceback
from urllib.parse import quote_plus, urljoin

try:
    from base.spider import Spider as _Base
except Exception:
    class _Base(object):
        pass

import requests
from bs4 import BeautifulSoup

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_EXTRACTORS = ("text", "textNodes", "ownText", "html", "outerHtml", "all")
_TAGNAMES = set("a abbr address article aside b blockquote body br button caption cite code dd details div dl dt em fieldset figcaption figure footer form h1 h2 h3 h4 h5 h6 header hr i img input ins label legend li main nav ol option p pre s section select small span strong sub summary sup table tbody td textarea tfoot th thead tr u ul video audio source".split())


def _split_top(s, sep):
    """按顶层分隔符切分（跳过 [] {} () 内的）。"""
    parts, depth, cur, i = [], 0, "", 0
    while i < len(s):
        ch = s[i]
        if ch in "[{(":
            depth += 1
        elif ch in "]})":
            depth = max(0, depth - 1)
        if depth == 0 and s.startswith(sep, i):
            parts.append(cur)
            cur = ""
            i += len(sep)
            continue
        cur += ch
        i += 1
    parts.append(cur)
    return parts


class _Ctx(object):
    """一次页面求值上下文。"""
    def __init__(self, url, html, soup, jdata):
        self.url = url
        self.html = html
        self.soup = soup
        self.jdata = jdata


class Spider(_Base):

    def getName(self):
        try:
            return self.S.get("bookSourceName") or "阅读书源"
        except Exception:
            return "阅读书源"

    # ---------------- 初始化：加载书源 ----------------
    def init(self, extend=""):
        self.S = {}
        self.session = requests.Session()
        self.base = ""
        try:
            src = None
            ext = (extend or "").strip()
            if ext.startswith("http://") or ext.startswith("https://"):
                r = self.session.get(ext, headers={"User-Agent": _UA}, timeout=20)
                src = r.json()
            elif ext.startswith("{") or ext.startswith("["):
                src = json.loads(ext)
            if isinstance(src, list):
                src = src[0] if src else {}
            if isinstance(src, dict):
                self.S = src
            self.base = (self.S.get("bookSourceUrl") or "").split("#")[0].rstrip("/")
            hdr = self.S.get("header")
            if isinstance(hdr, str) and hdr.strip().startswith("{"):
                try:
                    self.hdr = json.loads(hdr)
                except Exception:
                    self.hdr = {}
            elif isinstance(hdr, dict):
                self.hdr = hdr
            else:
                self.hdr = {}
        except Exception:
            self.S = {}
        return

    # ---------------- 网络 ----------------
    def _fetch(self, url, method="GET", body=None):
        headers = {"User-Agent": _UA}
        for k, v in (getattr(self, "hdr", {}) or {}).items():
            headers[k] = v
        if self.base:
            headers.setdefault("Referer", self.base + "/")
        try:
            if method.upper() == "POST":
                r = self.session.post(url, data=body, headers=headers, timeout=18)
            else:
                r = self.session.get(url, headers=headers, timeout=18)
            text = self._decode(r)
            jdata = None
            t = text.lstrip()
            if t.startswith("{") or t.startswith("["):
                try:
                    jdata = json.loads(t)
                except Exception:
                    jdata = None
            soup = BeautifulSoup(text, "html.parser") if jdata is None else None
            return _Ctx(r.url or url, text, soup, jdata)
        except Exception:
            return _Ctx(url, "", None, None)

    def _decode(self, r):
        raw = r.content or b""
        enc = None
        ctype = r.headers.get("Content-Type", "") or ""
        m = re.search(r"charset=([\w-]+)", ctype, re.I)
        if m:
            enc = m.group(1)
        if not enc:
            m = re.search(br"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4096], re.I)
            if m:
                enc = m.group(1).decode("ascii", "ignore")
        candidates = []
        for e in (enc, "utf-8", "gb18030"):
            if e and e.lower() not in [c.lower() for c in candidates]:
                candidates.append(e)
        for e in candidates:
            try:
                return raw.decode(e)
            except Exception:
                continue
        return raw.decode("utf-8", "ignore")

    # ---------------- 规则引擎 ----------------
    def _apply_post(self, val, post):
        """##正则##替换 后处理。post 为 ## 之后的部分列表。"""
        if not post:
            return val
        try:
            pattern = post[0]
            repl = post[1] if len(post) > 1 else ""
            repl = re.sub(r"\$(\d+)", r"\\g<\1>", repl.replace("$$", "\x00")).replace("\x00", "$")
            if pattern:
                val = re.sub(pattern, repl, val)
        except Exception:
            pass
        return val

    def _eval(self, ctx, elems, rule, want, page_html=None):
        """求值入口。want: 'str' | 'list'。返回字符串或元素列表。"""
        if rule is None:
            return "" if want == "str" else []
        rule = str(rule).strip()
        if not rule:
            return "" if want == "str" else []
        # ## 后处理拆分（规则主体在第一段）
        post = None
        if "##" in rule:
            segs = rule.split("##")
            rule, post = segs[0], segs[1:]
            if not rule.strip():
                # 纯正则对页面源码提取
                try:
                    m = re.search(post[0], page_html if page_html is not None else ctx.html)
                    val = (m.group(1) if m and m.groups() else (m.group(0) if m else ""))
                except Exception:
                    val = ""
                return self._apply_post(val, post[1:]) if want == "str" else []
        # || 备选
        alts = _split_top(rule, "||")
        if len(alts) > 1:
            for alt in alts:
                r = self._eval(ctx, elems, alt.strip(), want, page_html)
                if r:
                    return r
            return "" if want == "str" else []
        # && 合并
        merges = _split_top(rule, "&&")
        if len(merges) > 1:
            if want == "list":
                out = []
                for part in merges:
                    out.extend(self._eval(ctx, elems, part.strip(), "list", page_html))
                return out
            buf = []
            for part in merges:
                buf.append(self._eval(ctx, elems, part.strip(), "str", page_html))
            return "".join(buf)
        result = self._chain(ctx, elems, rule, want)
        if want == "str" and post:
            result = self._apply_post(result, post)
        return result

    def _chain(self, ctx, elems, rule, want):
        parts = [p.strip() for p in _split_top(rule, "@")]
        # @XPath: / @Json: 前缀可能出现在整条规则开头
        cur = list(elems)
        for i, part in enumerate(parts):
            last = (i == len(parts) - 1)
            if part == "":
                continue
            low = part.lower()
            if low.startswith("@xpath:") or (i == 0 and part.startswith("//")):
                xp = part[7:] if low.startswith("@xpath:") else part
                return self._xpath(ctx, cur, xp, want, parts[i + 1:] if not last else [])
            if low.startswith("@json:") or part.startswith("$.") or part.startswith("$["):
                jp = part[6:] if low.startswith("@json:") else part
                return self._jsonpath(ctx, jp, want)
            if last and want == "str" and (part in _EXTRACTORS or self._looks_attr(part, cur)):
                return self._extract(cur, part)
            cur = self._select(ctx, cur, part)
            if not cur:
                break
        if want == "list":
            return cur
        return self._extract(cur, "text")

    def _looks_attr(self, token, elems):
        if not re.match(r"^[a-zA-Z][\w-]*$", token):
            return False
        if token in _TAGNAMES:
            return False
        if not elems:
            return True
        el = elems[0]
        try:
            return token in el.attrs or token in ("text", "href", "src")
        except Exception:
            return True

    def _extract(self, elems, how):
        if not elems:
            return ""
        el = elems[0]
        try:
            if how == "text":
                return el.get_text(" ", strip=False).strip() if hasattr(el, "get_text") else str(el).strip()
            if how in ("textNodes", "ownText"):
                texts = [t for t in el.find_all(text=True, recursive=False)] if hasattr(el, "find_all") else []
                return "".join(texts).strip()
            if how == "html":
                return el.decode_contents() if hasattr(el, "decode_contents") else str(el)
            if how == "outerHtml":
                return str(el)
            if how == "all":
                return str(el)
            v = el.get(how) if hasattr(el, "get") else None
            if isinstance(v, list):
                v = v[0] if v else ""
            return (v or "").strip()
        except Exception:
            return ""

    def _post_list(self, elems, seg):
        """Legado 列表后处理：!N 排除、[n] / [n:m] 切片。"""
        out = list(elems)
        for ex in re.findall(r"!(\d+)", seg):
            i = int(ex)
            if 0 <= i < len(out):
                out.pop(i)
        m = re.search(r"\[(-?\d+)(?::(-?\d+))?\]\s*$", seg)
        if m:
            a = int(m.group(1))
            if m.group(2) is not None:
                out = out[a:int(m.group(2))]
            else:
                out = [out[a]] if -len(out) <= a < len(out) else []
        return out

    def _select(self, ctx, elems, seg):
        """一段选择器：在每个当前元素内向下选。"""
        out = []
        # Legado 链式写法 class.xxx / id.xxx / tag.xxx
        m = re.match(r"^(class|id|tag)\.(.+)$", seg)
        if m:
            mode, rest = m.group(1), m.group(2)
            rest = re.sub(r"\[[^\]]*\]\s*$", "", rest)
            tokens = rest.split(".")
            cur = list(elems)
            for tok in tokens:
                if tok == "":
                    continue
                if re.match(r"^-?\d+$", tok):
                    idx = int(tok)
                    cur = [cur[idx]] if -len(cur) <= idx < len(cur) else []
                    continue
                nxt = []
                for el in cur:
                    if not hasattr(el, "select"):
                        continue
                    try:
                        if mode == "class":
                            nxt.extend(el.select("." + tok))
                        elif mode == "id":
                            nxt.extend(el.select("#" + tok))
                        else:
                            nxt.extend(el.select(tok))
                    except Exception:
                        pass
                cur = nxt
                if not cur:
                    break
            return self._post_list(cur, seg)
        # 普通 CSS；带尾部 .N 索引时先按原样选，空了再剥索引重试
        idx = None
        m2 = re.match(r"^(.*?)\.(-?\d+)$", seg)
        for el in elems:
            if not hasattr(el, "select"):
                continue
            try:
                got = el.select(seg)
            except Exception:
                got = []
            if not got and m2:
                try:
                    got = el.select(m2.group(1))
                    idx = int(m2.group(2))
                except Exception:
                    got = []
            out.extend(got)
        if idx is not None and out:
            out = [out[idx]] if -len(out) <= idx < len(out) else []
        return self._post_list(out, seg)

    def _xpath(self, ctx, elems, xp, want, rest):
        try:
            from lxml import etree
            html = ctx.html
            if elems and ctx.soup is not None and len(elems) == 1 and elems[0] is not ctx.soup:
                html = str(elems[0])
            tree = etree.HTML(html)
            if tree is None:
                return "" if want == "str" else []
            nodes = tree.xpath(xp)
            if want == "list":
                out = []
                for n in nodes:
                    if hasattr(n, "tag"):
                        frag = etree.tostring(n, encoding="unicode")
                        out.extend(BeautifulSoup(frag, "html.parser").find_all(True))
                return out
            for n in nodes:
                if isinstance(n, str):
                    return n.strip()
                if hasattr(n, "text_content"):
                    if rest and rest[0] in ("href", "src"):
                        v = n.get(rest[0])
                        return (v or "").strip()
                    return n.text_content().strip()
            return ""
        except Exception:
            return "" if want == "str" else []

    def _jsonpath(self, ctx, jp, want):
        data = ctx.jdata
        if data is None:
            return "" if want == "str" else []
        try:
            from jsonpath import jsonpath as _jp
            r = _jp(data, jp)
            if not r:
                return "" if want == "str" else []
            if want == "list":
                return r
            v = r[0]
            return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
        except Exception:
            # 极简 $.a.b[0] 兜底
            try:
                cur = data
                path = jp[2:] if jp.startswith("$.") else jp
                for tok in re.split(r"\.|\[", path):
                    tok = tok.strip("]").strip()
                    if tok == "":
                        continue
                    cur = cur[int(tok)] if tok.isdigit() else cur[tok]
                if want == "list":
                    return cur if isinstance(cur, list) else [cur]
                return cur if isinstance(cur, str) else json.dumps(cur, ensure_ascii=False)
            except Exception:
                return "" if want == "str" else []

    # 字段求值便捷方法
    def _s(self, ctx, elems, rule):
        v = self._eval(ctx, elems, rule, "str")
        return v.strip() if isinstance(v, str) else ""

    def _url(self, ctx, elems, rule):
        v = self._s(ctx, elems, rule)
        if v and not v.startswith("http"):
            v = urljoin(ctx.url, v)
        return v

    def _list(self, ctx, rule):
        """列表规则：返回 (elements, reversed_flag)。"""
        rev = False
        r = (rule or "").strip()
        if r.startswith("-"):
            rev = True
            r = r[1:].strip()
        elif r.startswith("+"):
            r = r[1:].strip()
        elems = self._eval(ctx, [ctx.soup] if ctx.soup is not None else [], r, "list")
        if ctx.jdata is not None and (r.startswith("$") or r.lower().startswith("@json:")):
            elems = self._eval(ctx, [], r, "list")
        if rev:
            elems = list(reversed(elems))
        return elems, rev

    # ---------------- TVBox 接口 ----------------
    def homeContent(self, filter):
        return {"class": [], "filters": {}}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        return {"list": [], "page": int(pg or 1), "pagecount": 1, "limit": 0, "total": 0}

    def searchContent(self, key, quick, pg="1"):
        try:
            return self._search(key, pg or "1")
        except Exception:
            traceback.print_exc()
            return {"list": []}

    def _search(self, key, pg):
        S = self.S
        su = S.get("searchUrl") or ""
        if not su:
            return {"list": []}
        method, body, url_tpl = "GET", None, su
        charset = "utf-8"
        m = re.search(r",\s*(\{.*\})\s*$", su, re.S)
        if m:
            opt = None
            try:
                opt = json.loads(m.group(1))
            except Exception:
                try:
                    import ast
                    opt = ast.literal_eval(m.group(1))
                except Exception:
                    opt = None
            if isinstance(opt, dict):
                url_tpl = su[:m.start()].strip()
                method = str(opt.get("method") or "GET").upper()
                body = opt.get("body")
                charset = str(opt.get("charset") or "utf-8")
                try:
                    import codecs; codecs.lookup(charset)
                except Exception:
                    charset = "utf-8"

        def tpl(s):
            if s is None:
                return None
            return (s.replace("{{key}}", quote_plus(key, encoding=charset))
                     .replace("{{page}}", str(pg))
                     .replace("{{pageSize}}", "20"))

        url = tpl(url_tpl)
        if not url.startswith("http"):
            url = urljoin(self.base + "/", url)
        send_body = tpl(body) if body else None
        if send_body is not None and charset.lower() not in ("utf-8", "utf8"):
            try:
                send_body = send_body.encode(charset, "ignore")
            except Exception:
                pass
        ctx = self._fetch(url, method, send_body)
        rule = S.get("ruleSearch") or {}
        items, _ = self._list(ctx, rule.get("bookList"))
        out = []
        for el in items:
            if isinstance(el, dict):
                def jf(rule):
                    if not rule:
                        return ""
                    r = str(rule)
                    post = None
                    if "##" in r:
                        pp = r.split("##"); r, post = pp[0], pp[1:]
                    r = r.strip()
                    if r.lower().startswith("@json:"):
                        r = r[6:]
                    v = self._jsonpath(_Ctx("", "", None, el), r, "str") if r else ""
                    if post:
                        v = self._apply_post(v, post)
                    return v.strip() if isinstance(v, str) else ""
                name = jf(rule.get("name"))
                book = jf(rule.get("bookUrl"))
                if book and not book.startswith("http"):
                    book = urljoin(ctx.url, book)
                if not name or not book:
                    continue
                author = jf(rule.get("author"))
                cov = jf(rule.get("coverUrl"))
                if cov and not cov.startswith("http"):
                    cov = urljoin(ctx.url, cov)
                out.append({"vod_id": book, "vod_name": name, "vod_pic": cov,
                            "vod_remarks": jf(rule.get("lastChapter")) or author,
                            "vod_actor": author, "vod_content": jf(rule.get("intro"))})
                continue
            ectx = [el]
            name = self._s(ctx, ectx, rule.get("name"))
            book = self._url(ctx, ectx, rule.get("bookUrl"))
            if not name or not book:
                continue
            author = self._s(ctx, ectx, rule.get("author"))
            out.append({
                "vod_id": book,
                "vod_name": name,
                "vod_pic": self._url(ctx, ectx, rule.get("coverUrl")),
                "vod_remarks": self._s(ctx, ectx, rule.get("lastChapter")) or author,
                "vod_actor": author,
                "vod_content": self._s(ctx, ectx, rule.get("intro")),
            })
        return {"list": out, "page": int(pg), "pagecount": 9999, "limit": len(out), "total": 999999}

    def detailContent(self, ids):
        try:
            return self._detail(ids[0])
        except Exception:
            traceback.print_exc()
            return {"list": []}

    def _detail(self, book_url):
        S = self.S
        ctx = self._fetch(book_url)
        info = S.get("ruleBookInfo") or {}
        root = [ctx.soup] if ctx.soup is not None else []
        name = self._s(ctx, root, info.get("name"))
        author = self._s(ctx, root, info.get("author"))
        intro = self._s(ctx, root, info.get("intro"))
        cover = self._url(ctx, root, info.get("coverUrl"))
        kind = self._s(ctx, root, info.get("kind"))
        last = self._s(ctx, root, info.get("lastChapter"))
        toc_url = self._url(ctx, root, info.get("tocUrl")) or book_url
        # 目录
        toc_rule = S.get("ruleToc") or {}
        chapters = []
        seen = set()
        cur_url = toc_url
        tctx = ctx if toc_url == book_url else self._fetch(toc_url)
        for _ in range(30):
            items, _rev = self._list(tctx, toc_rule.get("chapterList"))
            for el in items:
                ectx = [el]
                cname = self._s(tctx, ectx, toc_rule.get("chapterName"))
                curl = self._url(tctx, ectx, toc_rule.get("chapterUrl"))
                if not curl or curl in seen:
                    continue
                seen.add(curl)
                chapters.append((cname or curl, curl))
            nxt = self._url(tctx, [tctx.soup] if tctx.soup is not None else [], toc_rule.get("nextTocUrl"))
            if not nxt or nxt == cur_url or nxt in seen:
                break
            seen.add(nxt)
            cur_url = nxt
            tctx = self._fetch(nxt)
        # 顺序自检：首章序号大于尾章时自动正序（不少站点目录默认倒序）
        def _cno(nm):
            m = re.search(r"第\s*(\d+)\s*章", nm or "")
            return int(m.group(1)) if m else None
        if len(chapters) > 2:
            a, b = _cno(chapters[0][0]), _cno(chapters[-1][0])
            if a is not None and b is not None and a > b:
                chapters = list(reversed(chapters))
        play_from = re.sub(r"[\$#]", " ", S.get("bookSourceName") or "正文").strip() or "正文"
        vod = {
            "vod_id": book_url,
            "vod_name": name or book_url,
            "vod_pic": cover,
            "vod_actor": author,
            "vod_content": intro,
            "vod_remarks": last,
            "type_name": kind,
            "vod_play_from": play_from,
            "vod_play_url": "#".join("%s$%s" % (n.replace("#", " ").replace("$", " "), u) for n, u in chapters),
        }
        return {"list": [vod]}

    def playerContent(self, flag, id, vipFlags):
        try:
            text = self._chapter_text(id)
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "content": text, "text": text,
                    "header": {"User-Agent": _UA}}
        except Exception:
            traceback.print_exc()
            return {"parse": 0, "playUrl": "", "url": "", "content": "", "text": ""}

    def _chapter_text(self, url):
        S = self.S
        rule = S.get("ruleContent") or {}
        parts = []
        cur = url
        seen = set()
        for _ in range(10):
            if not cur or cur in seen:
                break
            seen.add(cur)
            ctx = self._fetch(cur)
            root = [ctx.soup] if ctx.soup is not None else []
            # 正文：先取 html 再转文本，保留段落
            raw = self._eval_raw(ctx, root, rule.get("content"))
            parts.append(self._html_to_text(raw))
            nxt = self._url(ctx, root, rule.get("nextContentUrl"))
            if not nxt or nxt == cur:
                break
            cur = nxt
        text = "\n".join(p for p in parts if p)
        repl = rule.get("replaceRegex") or S.get("replaceRegex") or ""
        if repl:
            for line in str(repl).split("\n"):
                line = line.strip()
                if not line:
                    continue
                if "##" in line:
                    p, _, r = line.partition("##")
                    r = r[1:] if r.startswith("#") else r
                elif "=>" in line:
                    p, _, r = line.partition("=>")
                else:
                    p, r = line, ""
                try:
                    text = re.sub(p.strip(), r.strip(), text)
                except Exception:
                    pass
        lines = [ln.strip() for ln in text.split("\n")]
        junk = re.compile(r"^(play|document\.|window\.|var\s|function\s|script|<!--|loadJs|console\.)")
        lines = [ln for ln in lines if ln and not junk.match(ln)]
        return "\n".join(lines)

    def _eval_raw(self, ctx, elems, rule):
        """正文专用：以 html 方式提取（忽略规则里的 @text 结尾，改取内部 HTML 后统一转文本）。"""
        if not rule:
            return ""
        r = str(rule)
        r = re.sub(r"@(text|textNodes|ownText)\s*$", "@html", r)
        return self._eval(ctx, elems, r, "str")

    def _html_to_text(self, html):
        if not html:
            return ""
        t = html
        t = re.sub(r"(?i)<br\s*/?>", "\n", t)
        t = re.sub(r"(?i)</p\s*>", "\n", t)
        t = re.sub(r"(?i)</div\s*>", "\n", t)
        t = re.sub(r"<[^>]+>", "", t)
        import html as _h
        t = _h.unescape(t)
        t = t.replace("　", " ").replace("\xa0", " ")
        return t

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass
