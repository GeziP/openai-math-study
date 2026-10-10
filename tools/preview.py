# -*- coding: utf-8 -*-
"""本地预览：把构建好的站点放在「子路径」下提供服务，模拟 GitHub Pages 项目站点（https://<用户>.github.io/<仓库>/）。

为什么要带子路径：站点所有链接都是相对路径，放在根目录下一切正常、放进 /仓库名/ 下却可能悄悄坏掉。
在这里按子路径访问，能提前发现这类问题；访问不存在的页面时返回 404.html，和 Pages 一致。

用法
    python tools/build.py                      # 先构建到 _site/
    python tools/preview.py                    # 然后访问 http://127.0.0.1:8770/openai-math-study/
    python tools/preview.py --port 9000 --prefix / --dir _site
"""
import argparse
import functools
import http.server
import os
import posixpath
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map)
    extensions_map.update({
        ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml",
        ".woff2": "font/woff2", ".json": "application/json", ".xml": "application/xml", ".txt": "text/plain; charset=utf-8",
        ".html": "text/html; charset=utf-8", ".png": "image/png", ".webp": "image/webp",
    })

    def __init__(self, *a, prefix="/", **kw):
        self.prefix = prefix
        super().__init__(*a, **kw)

    def translate_path(self, path):
        path = urllib.parse.urlsplit(path).path
        path = posixpath.normpath(urllib.parse.unquote(path))      # 注意：normpath 会去掉结尾的 /
        if self.prefix != "/":
            if path + "/" == self.prefix:                          # 站点根（/openai-math-study/）
                path = "/"
            elif path.startswith(self.prefix):
                path = "/" + path[len(self.prefix):]
            else:
                return os.path.join(self.directory, "__not_under_prefix__")   # 一个肯定不存在的文件名 → 404
        parts = [p for p in path.split("/") if p and p not in (".", "..")]
        return os.path.join(self.directory, *parts)

    def do_GET(self):
        p = urllib.parse.urlsplit(self.path).path
        if self.prefix != "/" and p in ("/", self.prefix.rstrip("/")):
            self.send_response(302)
            self.send_header("Location", self.prefix)
            self.end_headers()
            return
        super().do_GET()

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            page = os.path.join(self.directory, "404.html")
            if os.path.exists(page):
                body = open(page, "rb").read()
                self.send_response(404)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)
                return
        super().send_error(code, message, explain)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        if self.server.quiet:
            return
        super().log_message(fmt, *args)


class Server(http.server.ThreadingHTTPServer):
    quiet = False


def main():
    ap = argparse.ArgumentParser(description="在子路径下预览构建好的站点")
    ap.add_argument("--dir", default=os.path.join(HERE, "..", "_site"), help="站点目录（默认 _site/）")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--prefix", default="/openai-math-study/", help="模拟 Pages 的子路径；填 / 则放在根目录")
    ap.add_argument("--quiet", action="store_true", help="不打印每个请求")
    a = ap.parse_args()
    d = os.path.abspath(a.dir)
    if not os.path.isfile(os.path.join(d, "index.html")):
        sys.exit("找不到 %s/index.html，请先运行 python tools/build.py" % d)
    prefix = "/" + a.prefix.strip("/") + "/" if a.prefix.strip("/") else "/"
    srv = Server(("127.0.0.1", a.port), functools.partial(Handler, directory=d, prefix=prefix))
    srv.quiet = a.quiet
    print("预览 %s → http://127.0.0.1:%d%s   （Ctrl+C 停止）" % (d, a.port, prefix), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")


if __name__ == "__main__":
    main()
