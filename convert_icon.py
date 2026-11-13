"""图标转换脚本 — logo.png → icon.icns。"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("❌ 缺少 Pillow，请先运行: pip install Pillow")
    raise SystemExit(1)


HERE = Path(__file__).parent.resolve()
src = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE / "logo.png"
dest = HERE / "icon.icns"

if not src.exists():
    print(f"❌ 未找到图片: {src}")
    raise SystemExit(1)

with Image.open(src) as source:
    image = source.convert("RGBA")
    print(f"📐 原图: {image.width}×{image.height}")
    image.save(
        dest,
        format="ICNS",
        sizes=[
            (16, 16), (32, 32), (64, 64), (128, 128),
            (256, 256), (512, 512), (1024, 1024),
        ],
    )

print(f"✅ {dest} ({dest.stat().st_size // 1024} KB) — Retina 就绪")
