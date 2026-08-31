"""下载 LibreOffice Portable（python requests，先直连后代理，断点续传）。"""
import os
import sys

import requests

URL = "https://download.portableapps.com/office/libreoffice_portable/LibreOfficePortable_26.2.4_MultilingualAll.paf.exe"
OUT = r"C:\Users\wangb\AppData\Local\Temp\LibreOfficePortable.paf.exe"
TARGET = 281 * 1024 * 1024  # ~281MB


def try_download(proxies=None):
    """断点续传下载，返回最终大小。"""
    size = os.path.getsize(OUT) if os.path.exists(OUT) else 0
    headers = {"Range": f"bytes={size}-"} if size else {}
    try:
        with requests.get(URL, stream=True, timeout=(15, 60), headers=headers, proxies=proxies, allow_redirects=True) as r:
            if r.status_code == 416:  # Range 已满足
                return size
            if r.status_code not in (200, 206):
                print(f"HTTP {r.status_code}")
                return size
            total = int(r.headers.get("Content-Length", 0)) + size
            mode = "ab" if size else "wb"
            with open(OUT, mode) as f:
                for chunk in r.iter_content(1024 * 256):
                    if chunk:
                        f.write(chunk)
                        size += len(chunk)
                        pct = size / total * 100 if total else 0
                        print(f"\r{size/1048576:.1f}MB / {total/1048576:.1f}MB ({pct:.0f}%)", end="")
            print()
            return size
    except Exception as e:
        print(f"下载异常: {e}")
        return size


def main():
    print(f"目标: {URL}")
    print(f"输出: {OUT}")
    # 尝试 1: 直连
    size = try_download()
    print(f"直连阶段完成: {size/1048576:.1f}MB")
    # 尝试 2: 走代理补下（若未完成）
    if size < TARGET:
        print("改用代理续传...")
        size = try_download({"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"})
    print(f"最终大小: {size/1048576:.1f}MB")
    print("DONE" if size >= TARGET * 0.99 else f"INCOMPLETE({size/1048576:.1f}MB)")


if __name__ == "__main__":
    main()
