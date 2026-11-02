import argparse
from datetime import datetime as DateTime,timezone
import src.extract.youbike as youbike_module
from src.extract.youbike import extract_youbike

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True)
    parser.add_argument("--slot", type=str, required=True)
    parser.add_argument("--now", type=str, required=True)
    return parser.parse_args()


def set_worker_clock(now):
    """讓這個 worker 裡的產品程式，讀到測試指定的現在時間。"""
    # 先把 --now 的字串轉成有時區的 datetime，統一保存成 UTC。
    new_now = DateTime.fromisoformat(now.replace("Z", "+00:00"))
    if new_now.utcoffset() is None:
        raise ValueError("now must include timezone information")
    new_now = new_now.astimezone(timezone.utc)

    # 繼承原本的 datetime，保留解析日期、建立時間等能力，只改 now。
    class WorkerDateTime(DateTime):
        @staticmethod
        def now(tz=None):
            # 不需要類別資訊；tz 直接接收呼叫者指定的時區。
            # new_now 來自外層函式，每次呼叫 now 都會讀到同一個指定時間。
            if tz is None:
                return new_now.astimezone().replace(tzinfo=None)
            return new_now.astimezone(tz)

    # 產品在自己的模組內查找 DateTime，所以要替換那裡的名稱。
    # 此替換只影響目前程序，不會修改 datetime 套件或其他 worker。
    youbike_module.DateTime = WorkerDateTime


def main():
    """TODO：解析輸入、設定時鐘，呼叫原extract_youbike一次並保留失敗結果。"""
    args = parse_args()
    url = args.url
    set_worker_clock(args.now)
    slot = args.slot
    extract_youbike(url=url, scrape_time=slot)

if __name__ == "__main__":
    main()
