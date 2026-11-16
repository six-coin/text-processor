"""文本处理器入口。这个文件保持薄：真正的启动逻辑在 ``app/ui/app.py``。"""

import sys

from app.ui.app import main

if __name__ == "__main__":
    sys.exit(main())
