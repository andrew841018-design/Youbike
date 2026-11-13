# YouBike 工程筆記

歷史紀錄（2026-09-23）：新專案設計起點，當時尚無實作驗收。最新進度見 [project_state.md](project_state.md)；以下依 Andrew 授權累積具體問題與重點，不把筆記交付算成閉卷掌握。

整理說明（2026-11-13）：Andrew 要求把重複的概念整合。筆記改成依主題分組：每個主題開頭的「主題重點」整合了各則的結論；原本各則保留在主題底下（含日期、範例和核對依據），重複的段落改成指向主題重點或相關小節。新的筆記照主題放進對應的段落。

## 目錄

- 1. 環境設定與 import
- 2. Python 語法
- 3. pytest：fixture、收尾與 HTTP 失敗測試
- 4. 受控時鐘
- 5. Airflow 重試與排程對帳
- 6. Pydantic 來源模型
- 7. dbt

## 1. 環境設定與 import

### 主題重點

- `monkeypatch.setenv` 只負責設定環境變數；`NO_PROXY` 是逗號分隔的免代理名單，Requests 讀到後對名單內的目的地直接連線，本機測試伺服器就靠它不走代理。
- `from config import ...` 找不找得到，看程式怎麼啟動：在 `Youbike` 根目錄用 `-m` 啟動，`sys.path` 第一個就是根目錄；用檔案路徑跑時，第一個是那個檔案所在的資料夾。
- 引用路徑一律從根目錄寫起（`from src.source_id import Source`）；兩個檔案不要在最上面互相 `from ... import` 對方。

### 2026-09-26：setenv、NO_PROXY 與 Requests 的分工

#### 一句話重點

`NO_PROXY` 的用途像一份「免代理名單」：實際儲存的是逗號分隔的字串，Requests 讀取後，會對符合名單的目的地略過代理、直接連線。

#### setenv 始終只負責設定值

目前測試中的兩行：

```python
monkeypatch.setenv("YOUBIKE_DATABASE_URL", test_dsn)
monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
```

兩次都是設定環境變數；已存在就覆寫，不存在就建立。`setenv()` 不會因為名稱是 `NO_PROXY` 而改變功能，也不會發出任何連線。

| 環境變數名稱 | 存入的值 | 誰讀取、如何使用 |
|---|---|---|
| `YOUBIKE_DATABASE_URL` | `test_dsn` 的字串值 | 產品程式讀出後交给 `psycopg.connect()`，作為資料庫連線設定 |
| `NO_PROXY` | 字串 `"127.0.0.1,localhost"` | Requests 內部讀取，解讀成免代理地址清單 |

#### 為什麼沒有程式去「連 NO_PROXY」？

`NO_PROXY` 是設定的名稱，並非主機名稱。產品程式不用自己寫讀取它的邏輯，Requests 套件內部已經會做。

```text
1. setenv 設好 NO_PROXY = "127.0.0.1,localhost"
2. extract_youbike(url="http://127.0.0.1:8000/") 指定真正目的地
3. 函式內的 requests.get(url) 準備發送 HTTP 請求
4. Requests 讀取免代理設定，發現目的地 127.0.0.1 符合清單
5. 直接連本機 8000 port，略過代理
```

即使 URL 已指定本機，Requests 仍可能受到環境中的代理設定影響。這行是為了避免本機故障測試被代理干擾；若原本就沒有代理，直接連本機即可，這行不會帶來額外效果。

#### 三個容易混淆的地方

- **像清單，但不是 Python `list`**：環境變數存的是字串 `"127.0.0.1,localhost"`；Requests 再依逗號拆開使用。這是兩個地址，不是一個名叫 `127.0.0.1,localhost` 的主機。
- **覆寫，不是追加**：這個 `setenv()` 呼叫把整個值設成指定字串，不會自動保留舊名單再加入兩個地址。
- **設定暫時生效**：pytest 的 `monkeypatch` fixture 結束時會還原原值；原本不存在就移除。它不會修改 `.env`，也沒有模擬 HTTP 回應或逾時。

本機 Requests 實作補充：若小寫 `no_proxy` 已有非空值，會優先於大寫 `NO_PROXY`。因此不能把「只設定大寫」理解成一定覆蓋所有代理設定。

對照位置：[正式測試的環境設定](../tests/unit/test_youbike_extract.py)、本機 Requests 的 `utils.should_bypass_proxies()` 與 pytest 的 `MonkeyPatch.setenv()`／fixture 清理行為。本次為概念筆記，不新增驗收項目。

### 2026-11-08：from config import 為什麼有時找得到、有時找不到

問題：任何位置都能只靠 `from config import get_env_variable` 拿到 function 嗎？為什麼好像 `src` 底下可以，其他資料夾不行？

結論：**找不找得到，看的是程式怎麼啟動，不是寫 import 的檔案放在哪個資料夾。** Python 啟動時會建一份搜尋清單 `sys.path`，整個程式共用這一份；`from config import ...` 就照這份清單找 `config.py`。在 `Youbike` 根目錄用 `-m` 啟動，清單第一個就是根目錄，任何資料夾裡的檔案都找得到根目錄的 `config.py`。`src` 沒有特別。

#### 清單第一個資料夾怎麼決定

| 啟動方式 | `sys.path[0]` |
|---|---|
| `python 資料夾/檔案.py` | 那個檔案所在的資料夾 |
| `python -m 模組名` | 目前所在的資料夾 |
| Airflow 跑 DAG | DAG 自己插進去的 `Youbike` 根目錄（`dags/youbike_realtime.py` 第 5–6 行） |

#### 範例 1：同一個檔案，換啟動方式結果就不同

`helper.py` 放在根目錄，內容是 `def hello(): return "found helper"`。

```python
# pkg/run.py
import sys
print("sys.path[0] =", repr(sys.path[0]))
from helper import hello
print(hello())
```

```python
# pkg/run_insert.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helper import hello
print(hello())
```

```text
-- 1 by path, from root
    from helper import hello
ModuleNotFoundError: No module named 'helper'
-- 2 with -m, from root
sys.path[0] = '<root>'
found helper
-- 3 insert root first, from /tmp
found helper
```

- **跑法 1（在根目錄執行 `python pkg/run.py`）：** 用檔案路徑跑，清單第一個是 `pkg/`，找不到上一層的 `helper.py`。
- **跑法 2（在根目錄執行 `python -m pkg.run`）：** 清單第一個是目前所在的根目錄，找得到。
- **跑法 3（在 `/tmp` 執行 `run_insert.py`）：** DAG 的做法。`parents[1]` 是檔案往上兩層，也就是根目錄；先插進清單，從哪裡跑都找得到。

#### 範例 2：不同資料夾的檔案都找得到

`tools/a.py` 和 `reports/deep/b.py` 內容一樣：先印出自己所在的資料夾和 `sys.path[0]`，再 `from helper import hello`。四次都在根目錄執行：

```text
-- python -m tools.a
file folder: tools | sys.path[0]: '<root>'
found helper
-- python -m reports.deep.b
file folder: reports/deep | sys.path[0]: '<root>'
found helper
-- python tools/a.py
file folder: tools | sys.path[0]: '<root>/tools'
ModuleNotFoundError: No module named 'helper'
-- python reports/deep/b.py
file folder: reports/deep | sys.path[0]: '<root>/reports/deep'
ModuleNotFoundError: No module named 'helper'
```

用 `-m` 啟動時，檔案放在 `tools` 或更深的 `reports/deep` 都找得到；用路徑啟動時都找不到。

#### 在專案裡怎麼寫

在 `Youbike` 根目錄用 `-m` 啟動後，任何檔案都能用「從根目錄算起的路徑」引用別的檔案：資料夾用 `.` 連起來，不寫 `.py`。

| 檔案位置 | 引用寫法 |
|---|---|
| `config.py` | `from config import get_env_variable` |
| `src/source_id.py` | `from src.source_id import Source` |
| `src/extract/youbike.py` | `from src.extract.youbike import extract_youbike` |

`src/extract/youbike.py` 第 8 行的 `from src.source_id import Source` 早就是這種寫法。

目前的入口都在 `Youbike` 根目錄執行：`python -m pytest`、`python -m src.schedule_reconciliation`。Airflow 不受從哪裡啟動影響，因為 DAG 自己把根目錄插進清單。

#### 注意

1. **路徑一律從根目錄寫起：** `youbike.py` 雖然在 `src/extract/` 裡，也要寫 `from src.source_id import Source`，不能只寫 `from source_id import Source`。
2. **兩個檔案不要在最上面互相 `from ... import` 對方：** 會因為循環引用出現 `ImportError`。`config.py` 沒有引用專案裡的其他檔案，所以沒有這個問題。
3. **編輯器的「執行檔案」按鈕通常用檔案路徑跑：** 子資料夾裡的檔案會出現 `No module named ...`，改在終端機用 `-m` 執行。
4. **撞名：** 清單前面如果有別的 `config` 模組，會先被找到。2026-11-04 查過 `.venv` 和 Airflow 環境都沒有。
5. **專案變大後：** 常見做法是把專案安裝成套件，或在 pytest 設定搜尋路徑，從哪裡執行都可以。目前不用改。

一句話記法：import 找檔案靠的是啟動時的 `sys.path`；在 `Youbike` 根目錄用 `-m` 啟動，就能用「根目錄起算的路徑」引用任何檔案。

核對依據：兩個範例都在本機 Youbike/.venv（Python 3.9.6）實跑，`<root>` 是範例資料夾。專案入口的說法依 `dags/youbike_realtime.py` 第 5–6 行，以及 2026-11-04 的實跑結果（`python src/schedule_reconciliation.py` 出現 `No module named 'src'`，改用 `-m` 可以）。本筆記不增加驗收完成數。

## 2. Python 語法

### 主題重點

- `*args` 收沒寫名字的值（tuple），`**kwargs` 收寫了名字的值（dict）；兩者都是傳值，差別在呼叫時有沒有寫參數名稱。
- `@classmethod` 的 `cls` 是呼叫它的那個類別，由 Python 自動傳入，不是關鍵字，也不用自己建立。

### 2026-09-26：`*args`、`**kwargs` 與傳入參數的方式

#### 核心觀念

兩種都是傳入值，差別在呼叫時有沒有寫出參數名稱；不是「傳參數進 args、傳值進 kwargs」。

在 `def f(*args, **kwargs)` 這種寫法中：

| 呼叫方式 | 種類 | 收到哪裡 |
|---|---|---|
| `f("apple", 10)` | 位置參數，沒有寫 `名稱=` | `args` 是 tuple：`("apple", 10)` |
| `f(name="apple", quantity=10)` | 具名參數，有寫 `名稱=值` | `kwargs` 是 dict：`{"name": "apple", "quantity": 10}` |

#### 變數名稱不等於具名參數

```python
url = "http://127.0.0.1:8000/"

f(url)      # 位置參數：把 url 變數的值放進 args
f(url=url)  # 具名參數：把值放進 kwargs 的 "url" 欄位
```

`url=url` 左邊是傳給函式的參數名稱，右邊是目前變數的值。只寫 `url` 時，雖然它是變數名稱，呼叫方式仍是位置參數。

#### 對照目前的 HTTP 呼叫

產品程式使用：

```python
requests.get(url, stream=True, timeout=(5, 10))
```

測試將它暫時替換成：

```python
lambda *args, **kwargs: response
```

這個替身接到的內容相當於：

```python
args = (url,)  # tuple 裡存的是 url 變數的值
kwargs = {"stream": True, "timeout": (5, 10)}
```

`*args`、`**kwargs` 分別接住兩種傳法；這個 lambda 不使用它們的內容，只回傳準備好的 `response`。

#### 為什麼不能只寫 `*args`？

```python
def fake_get(*args):
    return response
```

這個版本只接位置參數。產品仍傳入 `stream=True`、`timeout=(5, 10)`，就會遇到 `TypeError`，指出不接受 `stream` 這個具名參數。

所以「能接很多個」不代表兩種傳法都能接；目前替身使用兩者，是為了配合產品既有的呼叫方式。

對照位置：[測試的 http_200_response](../tests/unit/test_youbike_extract.py) 與 [產品的 requests.get 呼叫](../src/extract/youbike.py)。本節只記錄概念，不修改程式或增加測試要求。

### 2026-10-16：classmethod 的 cls 代表誰，為什麼使用它

`cls` 是普通參數名稱，慣例上取自 class 的縮寫。它不是 Python 關鍵字，不是時間，也不是要另外建立的變數。`@classmethod` 讓 Python 在呼叫類別方法時，自動把呼叫的類別交給第一個參數。

```python
class Counter:
    value = 0

    @classmethod
    def add_one(cls):
        cls.value = cls.value + 1
        return cls.value

print(Counter.add_one())
print(Counter.add_one())
```

輸出為整數 1、2。`class Counter:` 建立類別，內部的 `value = 0` 建立類別屬性，因此 `Counter.value` 起初是 0。定義 `add_one` 時尚未執行加法。

第一次呼叫 `Counter.add_one()` 時，`@classmethod` 讓 Python 自動將 Counter 類別交給 cls。方法內 `cls.value` 此時就是 `Counter.value`。賦值先計算右邊，讀到 0、加 1 得到 1，再寫回左邊；return 將 1 交回呼叫處，外面的 print 才印出 1。第二次從保留的 1 加到 2；不會每次呼叫都重新執行類別內的 `value = 0`。

如果只用這一個類別，寫死 `Counter.value` 也能得到上述結果。使用 cls 的用途，是讓同一個方法依「這次由哪個類別呼叫」操作該類別的資料；子類別沿用方法時，差異就會顯現。

先前只 `return "09:00"` 的 DemoClock 範例沒有使用 cls，只能展示自動傳參，無法充分展示用途。如果方法不需要類別資料或類別行為，也不必為形式硬加 classmethod。

接續繼承的完整可執行例及逐步說明見 [D11 引導第5節](d11_function_guide.md)。本筆記不代表 Andrew 已獨立掌握，不增加 D11 驗收完成數；Counter 範例已獨立執行核對 1、2。

## 3. pytest：fixture、收尾與 HTTP 失敗測試

### 主題重點

- fixture：測試在參數列寫它的名字就會執行；`return`／`yield` 的值交給測試，都沒有時是 None；`yield` 後面的程式在測試結束後才執行，用來收尾。
- 收尾：assert 失敗會立刻丟例外，接著一定先執行 `finally`；會「等」的是帶 timeout 的呼叫。`finally` 要收什麼得自己寫：先放行、再 kill、最後 communicate。
- HTTP 失敗路徑：容量和時間的判斷用 `MagicMock` 回應、替換 `monotonic` 測邏輯；讀取逾時（T4）用真實的本機 TCP 連線，只連上不回應。
- 每個案例只改一個值：`dict(基準, 欄位=新值)` 複製一份再改，案例之間不互相污染（例子見主題 6 的 test_station_model_quantity）。

### 2026-10-14：pytest fixture 的設定、回傳值與 yield 清理

問題：fixture 內已用 monkeypatch.setenv 設定環境，拿掉 yield 是否仍會套用設定？

結論：會。只要測試有要求使用這個 fixture（或由其他 fixture 依賴它／設定 autouse），pytest 就會執行它的設定程式。沒有 return 或 yield 時，函式執行完隱含回傳 None；設定的副作用仍存在，測試的同名 fixture 參數則收到 None。

#### 三種寫法的差別

| fixture 最後的寫法 | 測試收到的值 | 執行方式 |
|---|---|---|
| 不寫 return／yield | None | 設定程式執行完，接著執行測試 |
| return tmp_path | pathlib.Path 路徑物件 | 設定程式執行完，將路徑交給測試 |
| yield tmp_path | pathlib.Path 路徑物件 | 執行到 yield 暫停，將路徑交給測試；測試結束後接續執行 yield 後面的清理程式 |

yield 在這裡是 pytest 的 fixture setup／teardown 機制：yield 前是準備，yield 提供測試使用的值，yield 後是清理。return 是一般函式回傳，return 後的程式不會繼續執行。只需要提供值、沒有自訂清理時，可以使用 return。

#### monkeypatch 自己負責還原

```python
import pytest

@pytest.fixture
def report_mode(monkeypatch):
    monkeypatch.setenv("REPORT_MODE", "preview")
```

這是不同情境的語法範例，不要求放入 YouBike 專案。測試使用 report_mode 時，REPORT_MODE 在測試期間為 preview；report_mode 參數本身是 None。

使用 pytest 提供的 monkeypatch fixture，環境變數會在其生命週期結束時自動還原：原本有值就恢復原值，原本不存在就移除。這由 monkeypatch 自己的清理負責，不依賴上面 report_mode 是否寫 yield；也不會修改 .env 檔案。

因此只設定測試環境、不需要把物件交給測試、也沒有其他資源要自行清理時，不必寫 yield。若 fixture 額外啟動 HTTP 服務或子程序，這些資源仍需安排自己的清理，monkeypatch 不會自動替它們關閉。

#### 與 dotenv_values 的接線

dotenv_values("report.env") 讀取設定並回傳類字典的 mapping，本身不設定 os.environ。fixture 從 mapping 取出字串，再傳給 monkeypatch.setenv，才會暫時改變程序環境。相對檔案路徑以執行當下的工作目錄為基準。

核對依據：本機 Youbike/.venv 的 pytest 原始實作 _pytest.fixtures.call_fixture_func、_teardown_yield_fixture，以及 _pytest.monkeypatch.monkeypatch（內部 yield mpatch 後執行 mpatch.undo）。這是概念筆記與來源核對，不代表新增正式測試、實作完成或增加 D11 驗收。

### 2026-11-01：測試裡的 try／finally，assert 失敗時會卡住還是進 finally

問題：D11 第一個排他測試把「啟動 A 到最後檢查」用 try 包住後，其中一個 assert 失敗，是會卡死，還是會進 finally？

結論：**會進 finally，assert 本身不會卡。** 會「等」的是 assert 裡面呼叫的東西（`Event.wait`、`Popen.communicate`），它們帶 timeout，最久等到逾時就失敗，一樣進 finally。進了 finally 也不代表子程序被收掉，收回要自己寫。

#### 機制：Python 的規則，不是 pytest 特例

1. `assert` 條件為 False 就立刻拋 `AssertionError`，不等待；條件為 True 就往下一行。
2. try 區塊內只要有一行拋例外，Python 會跳過 try 剩下的行，直接執行 finally；finally 做完，原本的例外才繼續往外丟，pytest 這時才把測試判成 failed。
3. 如果 finally 自己也拋例外，外面看到的是 finally 的例外；原本的例外退到「During handling of the above exception, another exception occurred」上面那一段。

#### 範例 1：等不到訊號的 assert

```python
import time
from threading import Event

received = Event()                    # 沒人會 set，模擬「A 一直沒到 HTTP」
start = time.monotonic()
try:
    print("1. 進入 try")
    assert received.wait(timeout=0.5), "等不到 A 的請求"
    print("2. 這行不會執行")
finally:
    print(f"3. 進入 finally（距離開始 {time.monotonic() - start:.1f} 秒）")
```

實際輸出：

```text
1. 進入 try
3. 進入 finally（距離開始 0.5 秒）
Traceback (most recent call last):
  File "note_ex1_wait_assert.py", line 8, in <module>
    assert received.wait(timeout=0.5), "等不到 A 的請求"
AssertionError: 等不到 A 的請求
```

- `Event()` 的內部狀態一開始是 False，也沒有人呼叫 `set()`。
- `received.wait(timeout=0.5)` 因為狀態是 False 所以等；0.5 秒到了還沒訊號，回傳 `False`（bool）。等待只發生在這一步，而且有上限。
- `assert False, "…"` 立刻拋出 `AssertionError`，逗號後面是訊息。
- `print("2. …")` 被跳過，所以輸出沒有 2。
- finally 印出 3，距離開始 0.5 秒：進 finally 前沒有多等。
- finally 結束後 `AssertionError` 才往外丟，所以 Traceback 出現在 3 之後。整段約 0.53 秒。

#### 範例 2：finally 自己出錯，會蓋掉真正的失敗

```python
def check():
    try:
        assert False, "A 沒有到 HTTP"
        b = "worker B"
    finally:
        print(b)


check()
```

實際輸出（Python 3.9.6）：

```text
Traceback (most recent call last):
  File "note_ex2_unbound.py", line 3, in check
    assert False, "A 沒有到 HTTP"
AssertionError: A 沒有到 HTTP

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "note_ex2_unbound.py", line 9, in <module>
    check()
  File "note_ex2_unbound.py", line 6, in check
    print(b)
UnboundLocalError: local variable 'b' referenced before assignment
```

- assert 在 `b = "worker B"` 之前就失敗，所以 `b` 還沒賦值。
- finally 讀 `b`，拋出 `UnboundLocalError`。pytest 看到的主要錯誤變成它，真正的原因（`AssertionError`）被擠到「During handling…」上面。新版 Python 的訊息措辭可能不同，錯誤名稱不變。
- 做法：try 之前先 `b = None`，finally 內用 `if b is not None` 判斷後再處理。

#### 範例 3：收回還在跑的子程序

```python
import subprocess
import sys

worker = None
try:
    worker = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    assert False, "中途檢查失敗"
finally:
    if worker is not None and worker.poll() is None:
        try:
            worker.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            print("等 1 秒還沒結束 → kill")
            worker.kill()
            worker.communicate()
        print("returncode:", worker.returncode)
```

實際輸出：

```text
等 1 秒還沒結束 → kill
returncode: -9
Traceback (most recent call last):
  File "note_ex3_reap.py", line 7, in <module>
    assert False, "中途檢查失敗"
AssertionError: 中途檢查失敗
```

- `worker = None`：先讓名稱存在，finally 才能判斷有沒有啟動過。
- `Popen([... sleep(30)])`：啟動一個會跑 30 秒的子程序，回傳 Popen 物件。
- `assert False`：模擬中途檢查失敗，直接跳到 finally。
- `worker.poll() is None`：子程序還在跑。
- `communicate(timeout=1)`：最多等 1 秒；到期還沒結束就拋 `TimeoutExpired`，**但不會終止子程序**。
- `kill()`：送出 SIGKILL，程序無法忽略；接著的 `communicate()` 等它結束並回收輸出，這次不會卡。
- `returncode: -9`：負數表示被訊號 9 終止。
- 整段約 1.04 秒，沒有等滿 30 秒；事後沒有殘留的 sleep 程序。

#### 對照本專案

`tests/unit/test_youbike_scheduling.py::test_two_youbike_workers_enter_at_same_time` 有三個等待點，都有 timeout：

| 呼叫 | 在等什麼 | 逾時後 |
|---|---|---|
| `assert control["received"].wait(timeout=5)` | A 的 HTTP 請求到達本機 server | 回傳 False → AssertionError |
| `b.communicate(timeout=5)` | B 結束（B 應在 HTTP 之前因搶不到鎖而退出） | 拋 TimeoutExpired，B 還活著 |
| `a.communicate(timeout=5)` | 放行後 A 結束 | 拋 TimeoutExpired，A 還活著 |

其餘 assert（B 的退出碼、`a.poll() is None`、A 的退出碼、GET 次數、raw／response 筆數）都是立刻判斷，沒有等待。三種失敗都是例外，都會進 finally。

卡住的是 A，不是 assert：A 是另一個程序，可能正在 HTTP 等 `release`，但 pytest 這邊的 assert 照樣判斷、照樣進 finally。所以 finally 第一件事要先 `release.set()` 讓 A 不再卡，再收回仍在跑的 A／B。不先放行的話，A 會等到 handler 的 `release.wait(timeout=5)` 逾時、回 504，之後以非 0 結束。

#### 容易混淆的地方

1. **assert 失敗不是卡死。** 真正會永遠卡住的是沒有 timeout 的等待，例如對還在跑的程序呼叫不帶 timeout 的 `communicate()`。
2. **進 finally 不等於子程序被收掉。** `release.set()` 只負責放行；`communicate(timeout)` 逾時不會殺程序；要自己 `kill()`，再 `communicate()` 回收。
3. **finally 本身不能出錯**，否則真正的失敗原因會被蓋掉：先設 `None`，用 `is not None` 判斷。
4. **正常路徑沒有東西要收。** 主體裡已經等過 A、B 並檢查退出碼，finally 對已結束的程序什麼都不做。

一句話記法：assert 只負責立刻失敗；等待交給有 timeout 的呼叫；失敗後 finally 一定先跑，但跑什麼要自己寫：先放行、再 kill、最後 communicate。

核對依據：三個範例在本機 Youbike/.venv（Python 3.9.6）獨立執行，沒有啟動專案程式、HTTP server、DB 或正式 pytest；專案內的位置依 2026-11-01 14:23 的存檔。與 [重點整理.md](重點整理.md) KH-014 第 13 節互補：該節從 fixture 收尾的角度談逾時，本篇談測試本體的 try／finally。這是概念筆記，不代表第一個排他測試已完成，不增加 D11 驗收完成數。

### 2026-09-26：模擬 HTTP 回應、容量與時間測試

以下對照目前 [test_youbike_extract.py](../tests/unit/test_youbike_extract.py)。T5／T6已依 Andrew 要求簡化成邏輯測試；舊的 `local_body_server`、Thread、Event、contextmanager 配套已移除，不再列為目前程式或學習門檻。

#### http_200_response：提供可控制的回應

```python
response = MagicMock()
response.status_code = 200
response.__enter__.return_value = response
monkeypatch.setattr("src.extract.youbike.requests.get", lambda *args, **kwargs: response)
return response
```

- `MagicMock()` 建立可設定屬性、方法回傳值的測試替身。
- `status_code = 200` 讓產品通過既有 HTTP 狀態檢查。
- 產品使用 `with requests.get(...) as response`；Python會呼叫 `__enter__()`，設定它回傳自己，讓 `as response` 取得同一個替身。
- `.return_value` 是 mock 方法被呼叫時的回傳值設定；fixture 最後的 `return response` 則把物件交給測試的同名參數。
- `monkeypatch.setattr()` 暫時替換產品使用的 `requests.get`，所以這兩個測試不發真實 HTTP 請求。測試結束會還原。
- 測試自行設定 `iter_content.return_value`，決定產品迴圈收到哪些 bytes。例外仍由真正的產品判斷拋出，沒有直接模擬那個例外。

#### T5 test_response_size_limit：累積超過 5 MiB

```python
http_200_response.iter_content.return_value = [b"x" * (64 * 1024)] * 80 + [b"x"]
```

拆開理解：`b"x"` 是1 byte；內層乘法產生一塊64 KiB資料；外層清單乘法重複80塊，剛好5 MiB；最後再加一塊1 byte。共81塊，總量是 **5 MiB＋1 byte（5,242,881 bytes）**。

產品前80塊累積剛好上限，第81塊讓 `len(buffer) + len(chunk) > size_limit` 成立，因此在加入buffer之前拋出 `ValueError("Response size limit exceeded")`。

`pytest.raises(ValueError, match=r"^Response size limit exceeded$")` 同時檢查錯誤類別及訊息。未拋錯、錯誤類別不對或訊息不符合，都會讓測試失敗。這是固定T5的一個案例，沒有新增獨立邊界測試。

#### T6 test_stream_time_budget：指定時間讀值跨過 30 秒

```python
http_200_response.iter_content.return_value = [b"x"]
monkeypatch.setattr("src.extract.youbike.monotonic", MagicMock(side_effect=[0, 31]))
```

提供1 byte讓產品進入一次chunk迴圈，避免容量限制先觸發。

| 產品執行位置 | mock回傳值 | 結果 |
|---|---|---|
| `start_time = monotonic()` | 第一次回傳0 | 起點記為0 |
| 迴圈內呼叫 `monotonic()` | 第二次回傳31 | `31 - 0 >= 30` 成立 |

`side_effect=[0, 31]` 是依呼叫順序回傳兩個讀值，不是等待31秒。替換 `src.extract.youbike.monotonic` 是因為產品以 `from time import monotonic` 匯入，應替換產品實際使用的名稱。

產品自己拋出內建 `TimeoutError("Time limit exceeded")`，由 `pytest.raises` 驗證。這只確認現有迴圈的時間判斷，沒有新增總下載硬截止，也不代表實際網路等待31秒。

### 2026-09-26：T4 test_http_read_timeout 的真實連線逾時

T4保留真實TCP連線與Requests讀取逾時；沒有使用 `http_200_response` fixture，也沒有替換時鐘。

```python
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    with pytest.raises(requests.exceptions.ReadTimeout):
        extract_youbike(url=f"http://127.0.0.1:{port}/")
```

- `AF_INET` 選IPv4；`SOCK_STREAM` 在這裡建立TCP socket。
- `bind(("127.0.0.1", 0))` 綁在本機，port 0表示請作業系統選空閒port。
- `listen(1)` 開始監聽，參數1是待accept連線佇列的backlog設定，不是1秒，也不是一生只能連一次。
- `getsockname()` 回傳目前綁定的 `(地址, port)`，`[1]` 取出實際port。
- listener仍開著，作業系統可以完成TCP連線並放入等待佇列；測試沒有呼叫accept處理請求，也沒有送HTTP回應。
- `extract_youbike()` 的 Requests 因此連得上，但等不到HTTP回應；依產品原本 `timeout=(5, 10)` 的10秒讀取等待設定，拋出 `requests.exceptions.ReadTimeout`。
- `pytest.raises` 確認例外類型；離開外層with時socket自動關閉，pytest結束時monkeypatch還原環境。

T4的 `requests.exceptions.ReadTimeout` 是Requests實際等待回應逾時；T6的內建 `TimeoutError` 是產品自行檢查時間預算後拋出的錯誤。兩個案例的失敗位置不同。本次只整理重點，不修改測試或新增驗收。

#### 2026-09-27補充：這次沒有連到YouBike官方

關鍵在呼叫時傳入的URL：

```python
extract_youbike(url=f"http://127.0.0.1:{port}/")
```

`extract_youbike()` 不傳URL時會使用函式定義中的官方網址；這次明確傳入本機網址，因此產品內的 `requests.get(url, ...)` 會連到本機測試端點。函式名稱叫YouBike，不代表每次都固定連官方。

| 呼叫方式 | 實際目的地 | 誰決定回應 |
|---|---|---|
| `extract_youbike()` | 預設的YouBike官方API | 官方服務 |
| `extract_youbike(url=本機網址)` | 測試自己建立的listener | 本機測試程式；此案例刻意沒有回應動作 |

因此能預期讀取逾時，是因為測試控制了本機端點，沒有程式送出HTTP回應；不是預測YouBike官方不會回應，也不是反覆請求官方等待隨機故障。「真實TCP／HTTP客戶端行為」不等於「連官方API」。

#### 正常服務與逾時測試的流程差異

正常服務端流程（實際服務框架通常會代做這些步驟）：

```text
bind綁定地址／port → listen監聽
→ 客戶端建立TCP連線
→ accept接手連線 → 讀取GET請求
→ 送出HTTP狀態與標頭 → 送出body
```

產品使用 `stream=True`，取得回應標頭後先檢查狀態，再以 `iter_content()` 讀取body；TCP連線成功本身不代表已收到HTTP回應。

本機逾時測試流程：

```text
listener完成bind及listen，保持開啟
→ extract_youbike連到本機端點並送出GET
→ 作業系統完成TCP連線，但測試沒有accept處理或傳送HTTP回應
→ Requests持續等待回應
→ 約10秒後拋出ReadTimeout
→ pytest.raises確認例外，離開with時關閉listener
```

這是測試刻意安排的故障條件。既有實測約10.00秒觸發；如果實際發生其他錯誤，或沒有拋出預期的ReadTimeout，測試仍會失敗，不會直接假定通過。本補充僅釐清目的地與流程，不新增驗收。

## 4. 受控時鐘

### 主題重點

- 產品自己讀系統時間時，測試要換掉產品模組裡的時間名稱（例如 `DateTime`），讓 `now()` 回傳指定時間；不改標準函式庫。
- 同一個程序裡用 `monkeypatch.setattr` 換；worker 子程序在自己的程序裡換（`set_worker_clock`）。
- missing 測試把 now 凍結在 slot＋30 分鐘，才測得到「剛好滿 30 分鐘就算過期」，界線含等號。

### 2026-10-16：直接閱讀實作的受控時鐘

Andrew本次明確授權Codex代寫set_worker_clock，供閱讀理解；其他函式與正式tests的分工不外推。

實作位於tests/helpers/youbike_worker.py第14行：先把--now解析為aware datetime並存成UTC；內層WorkerDateTime繼承datetime，覆寫classmethod now，持續讀取外層fixed_now；最後將產品模組的DateTime名稱指向新類別。return fixed_now只是維持舊回傳介面，真正影響產品的是模組名稱替換。

cls由Python自動傳入，此方法無須另外使用。fixed_now不是方法參數，它來自外層函式；內層方法保留對它的引用，所以set_worker_clock回傳後，now仍能取得該指定時間。替換影響目前程序；不改stdlib、磁碟上的產品檔或其他worker。

修改前確認「函式回傳指定時間，但產品now仍是真實時間」；修改後一次性核對產品引用、UTC／UTC+8、繼承解析與建構、無tz、非法輸入及再次設定，通過。輸入2040-01-01T11:10:00+02:00，產品UTC為09:10、UTC+8為17:10。沒有執行HTTP、DB或正式pytest；D11仍未完成。完整閱讀順序見[d11_function_guide.md](d11_function_guide.md)第5節。

### 2026-11-02：missing 測試為什麼要凍結產品時鐘

問題：D11 第三個測試（`test_expired_without_raw_is_missing`）為什麼要寫一個繼承 `datetime` 的類別，讓 `now()` 固定回傳 slot＋30 分鐘，再用 `monkeypatch.setattr` 換掉產品模組的 `DateTime`？只要「過期」的話，直接用過去的 slot，或「現在−30 分鐘」不行嗎？

結論：**改的是產品自己讀到的「現在」，目的是讓產品剛好站在過期界線上做判斷。** 產品判斷過期要兩個值：`expire_at` 由傳進去的 slot 決定，測試控制得到；`DateTime.now(...)` 是產品自己讀系統時鐘，測試原本控制不到。把 `now` 凍結在 slot＋30 分鐘，才測得到「剛好滿 30 分鐘就算過期」；只用過去的 slot，只能證明「早就過期」。

#### 規則與目的

- **為什麼要有 missing：** API 只給當下的資料。slot 過了時段才去抓（重試、延遲、手動補跑），抓回來的是後面時段的資料，卻記在舊 slot 底下，時間序列就錯了。所以過期又沒有 raw 就記 missing，留下看得見的缺口，不拿現在的資料冒充過去。2026-10-28 曾有 15:30 的 slot 因看門狗重啟延到 15:43、第 3 次嘗試才完成；若晚過 16:00 就必須記 missing。
- **界線（2026-10-14 Andrew 採用，11/02 再確認）：** slot ≤ now − 30 分鐘就算過期，等號包含在內；14:30 的 slot 從 15:00 起過期。產品寫的是 `if DateTime.now(timezone.utc) >= expire_at:`。
- **為什麼不能改成 `>`：** 產品對齊 slot 的算法已經把 15:00:00 算成 15:00 那一格；用 `>` 時那一刻 14:30 還沒過期，同一刻就同時屬於兩格，抓回來的 15:00 資料會被存成 14:30。

#### 名字對照

| 位置 | 名字 |
|---|---|
| 測試用 SQL 取出 | `slot` |
| 傳進產品 | `scrape_time=slot.isoformat()` |
| 產品轉成 UTC 後 | `request_time` |
| 產品算的到期時間 | `expire_at = request_time + timedelta(minutes=30)` |
| 測試凍結的現在 | `expire_time = slot + timedelta(minutes=30)` |

`expire_at` 是 `extract_youbike` 裡的區域變數，要執行到那一行才算出來，測試拿不到；所以測試用同樣的算法自己算一次，兩邊才會剛好相等。

#### `now` 停在哪裡，結果差在哪

| `now` 的位置 | `>=`（現行） | `>`（寫錯） | 用處 |
|---|---|---|---|
| 比 expire 早 | 沒過期 | 沒過期 | 分不出 |
| 剛好等於 expire | 過期 | 沒過期 | 只有這裡分得出 |
| 比 expire 晚 | 過期 | 過期 | 分不出 |

#### 範例 1：剛好到期 vs 很久以後

```python
from datetime import datetime, timedelta, timezone

slot = datetime(2026, 9, 24, 23, 0, tzinfo=timezone.utc)
expire_at = slot + timedelta(minutes=30)
for now in (expire_at, datetime(2026, 11, 2, tzinfo=timezone.utc)):
    print(now >= expire_at, now > expire_at)
```

```text
True False
True True
```

第一行剛好到期，`>=` 和 `>` 結果不同；第二行很久以後，兩種寫法都說過期。所以只用過去的 slot，產品被寫成 `>` 也測不出來。

#### 範例 2：真實時鐘一直在走

```python
slot = datetime.now(timezone.utc) - timedelta(minutes=30)
expire_at = slot + timedelta(minutes=30)
now = datetime.now(timezone.utc)      # 產品稍後才讀時鐘
print(now == expire_at, now > expire_at, now - expire_at)
```

```text
False True 0:00:00.000208
```

從算 slot 到讀時鐘已經過了 0.000208 秒，永遠等不到「剛好相等」。這就是要凍結時鐘，而不是用真實時間加減的原因。

#### 範例 3：凍結時鐘（繼承＋monkeypatch）

```python
import sys
from datetime import datetime, timedelta, timezone

import pytest

DateTime = datetime


def is_expired(slot):
    return DateTime.now(timezone.utc) >= slot + timedelta(minutes=30)


slot = datetime(2026, 9, 24, 23, 0, tzinfo=timezone.utc)
fixed_now = slot + timedelta(minutes=30)


class FixedDateTime(datetime):
    @staticmethod
    def now(tz=None):
        return fixed_now.astimezone(tz) if tz else fixed_now


print(DateTime.now(timezone.utc) > fixed_now)

with pytest.MonkeyPatch.context() as monkeypatch:
    monkeypatch.setattr(sys.modules[__name__], "DateTime", FixedDateTime)
    print(DateTime.now(timezone.utc))
    print(is_expired(slot))
    print(is_expired(slot + timedelta(minutes=1)))

print(DateTime.now(timezone.utc) == fixed_now)
```

```text
True
2026-09-24 23:30:00+00:00
True
False
False
```

- `DateTime = datetime`、`is_expired`：模仿產品檔頭 `from datetime import datetime as DateTime` 與過期判斷；`is_expired` 執行時才用名字 `DateTime` 去找。
- `FixedDateTime(datetime)`：其他功能都和 `datetime` 一樣，只有 `now()` 固定回傳；`@staticmethod` 讓 `tz` 直接收呼叫者給的時區，和 worker 的寫法相同。
- 換掉之後，剛好到期的 slot 判成過期（`True`），晚 1 分鐘的 slot 判成沒過期（`False`）；離開 `with` 就還原（最後一行 `False`）。測試裡 `monkeypatch` 是參數，結束時自動還原；`with` 只是讓範例能在 pytest 外跑。

#### 範例 4：類別寫在測試函式裡，讀同一個函式的變數

```python
from datetime import datetime, timedelta, timezone

def test_like():
    slot = datetime(2026, 9, 24, 23, 0, tzinfo=timezone.utc)
    fixed_now = slot + timedelta(minutes=30)

    class FixedDateTime(datetime):
        @staticmethod
        def now(tz=None):
            return fixed_now.astimezone(tz) if tz else fixed_now

    print(FixedDateTime.now(timezone.utc))

test_like()
```

```text
2026-09-24 23:30:00+00:00
```

`fixed_now` 是 `test_like` 的區域變數，寫在同一個函式裡的類別讀得到（closure）；worker 的 `WorkerDateTime` 讀 `set_worker_clock` 裡的 `new_now` 也是同一個機制。

#### 對照本專案

依 2026-11-02 18:15 的存檔。這一段是 Andrew 明確要求後由助理依他的寫法修正：slot 改用 SQL、補上 `monkeypatch.setattr`、入口改傳 `slot.isoformat()`；他寫的 GET0 與 raw0 兩個 assert 保留。

```python
def test_expired_without_raw_is_missing(youbike_test_env,controlled_raw_http_server,monkeypatch):
    control = controlled_raw_http_server
    conn = youbike_test_env
    with conn.cursor() as cursor:
        slot = cursor.execute("SELECT date_trunc('hour', COALESCE(MIN(fetched_start_at),NOW()),'UTC') - INTERVAL '60 minutes' FROM raw_bytes").fetchone()[0]
        # 產品呼叫 DateTime.now(...) 時固定回傳 expire_time（slot 剛好到期的那一刻）
        expire_time = slot + timedelta(minutes=30)
        class NewDateTime(datetime):
            @staticmethod
            def now(tz=None):
                return expire_time.astimezone(tz) if tz else expire_time

        monkeypatch.setattr(youbike_module, "DateTime", NewDateTime)
        youbike_module.extract_youbike(url=control["url"],scrape_time=slot.isoformat())
        count = cursor.execute("SELECT count(*) FROM raw_bytes WHERE fetched_start_at = %s", (slot,)).fetchone()[0]
        assert control["get_count"] == 0
        assert count == 0
```

結果：第三個測試 1 passed；把 `>=` 改成 `>` 的產品副本失敗在 `assert 1 == 0`（到期那一刻去發了 HTTP），代表等號邊界測得到；整個測試檔 3 passed，沒有殘留 worker。

#### 容易混淆的地方

1. **改 `now` 不是做「現在−30」：** 是把產品讀到的現在固定在 slot＋30 分鐘，不管測試哪天跑都一樣。
2. **−60 和 +30 不是互相抵消：** 兩者算的是兩個不同的值。−60 是 SQL 挑一個沒有 raw 的 slot，改成 −30 也可以，一樣對齊、一樣早於最早的 raw；+30 是算凍結的現在，不能省。只用一個值時，`now = slot` 得到 `False`（沒過期，產品會去抓），`now = slot + 30` 才是 `True`。
3. **`monkeypatch.setattr(youbike_module, "DateTime", NewDateTime)` 換的是模組上的名字：** 不是覆蓋整個模組，也不是直接改 `now`。內建型別的方法本來就改不了：`TypeError: can't set attributes of built-in/extension type 'datetime.datetime'`。測試結束自動換回。
4. **類別放在測試函式裡：** `now()` 被呼叫時才讀外層的 `expire_time`。VS Code 標「未定義」，是因為還沒寫賦值那一行。放在函式外或包成 fixture，都得另外想辦法把 slot 傳進去，反而更繞。
5. **slot 要保持 datetime：** `.isoformat()` 只在傳進產品時用。先轉字串再加時間會出錯：`TypeError: can only concatenate str (not "datetime.timedelta") to str`。
6. **`from datetime import datetime as timezone` 的 `timezone` 其實是 `datetime`：** `timezone.now()` 沒有時區（`tzinfo` 是 `None`），產品會拒絕；「現在−30 分鐘」也不是對齊整點或半點的 slot。
7. **不要把 now 設成 slot 本身：** 那代表「還在時段內」，產品會去抓；第一個測試的 worker 正是用 `--now` 等於 slot 讓產品去抓。
8. **只測「過期」可以不改時鐘：** 用過去的 slot 也會走 missing，但測不到等號邊界；HTML 現行驗收要邊界，Andrew 11/02 選擇維持。

一句話記法：讓產品看到「剛好到期」的那一刻——時間由測試凍結，名字換在產品模組上，類別寫在測試函式裡。

核對依據：範例都在本機 Youbike/.venv（Python 3.9.6）獨立執行；專案結果依 2026-11-02 18:15 的存檔，第三個測試與 `>` 副本對照都在 youbike_test 實跑（副本對照會在該 slot 寫入一組測試資料）。第三個情境還差用 caplog 核對 missing 紀錄，正式情境仍 2/3；本筆記不增加 D11 驗收完成數。

## 5. Airflow 重試與排程對帳

### 主題重點

- 重試由 Airflow 負責：`retries=4`（最多 5 次），退避約 66、171、324、600 秒，600 秒上限實際生效；Python 只做單次。
- `retry_count` 用模板 `{{ ti.try_number - 1 }}` 傳進產品，模板算完是字串，寫入前用 `int()`；`op_kwargs` 的 key 要和函式參數名稱對上，對不上的會被默默丟掉。
- 排程對帳：`generate_series` 列出應該有的 slot，再用 `NOT EXISTS` 找出缺的；缺口記成 missing（2026-11-10 起由 `record_missing` 寫入）。

### 2026-10-08 D10：Airflow有限重試的實際證據

- DAG省略url參數，官方網址僅由產品函式預設值提供。故障入口用一次性Airflow程序代理指向本機拒絕連線端點，沒有修改系統代理或.env，也沒有要求增加source_url功能。
- 同一故障run首次加4次重試，共5次；前四次觀察到up_for_retry，第五次task／DagRun最終failed。五份原生attempt log均記錄ProxyError，沒有第六次；這是ConnectionError驗證，不宣稱收到503。
- 框架允許等待66、171、324、600秒；實際間隔約66.750、171.824、325.120、600.202秒。退避含jitter，scheduler延遲另計；600秒上限實際生效。
- 正常環境恢復後，14:30 slot首次成功：raw 1列／949673 bytes、來源1813站／response1813列。catchup=False未補昨天缺失時段。本次相關既有pytest回歸8 passed（1既有LibreSSL warning）。
- D10完成，核心1/8、驗收7/36、Phase2 2/4。D11待處理跨程序slot排他與入口raw重播；已採用下一個30分鐘slot開始即過期，過期無raw記missing、不可抓現在snapshot假回補，已有raw仍可重播。

限制：此證據證明實際重試上限／退避／原生日誌，不等於所有HTTP狀態都經過真實scheduler故障；分類另有既有policy方向檢查。完整ops run觀測留在D12，未宣稱exactly-once。

### 2026-11-04：retry_count 怎麼從 Airflow 傳進產品，為什麼要傳、為什麼加 int()

問題：DAG 的 `"retry_count": "{{ ti.try_number - 1 }}"` 是什麼？重試不是看 Airflow 就好，為什麼要把變數抓進來？參數預設是 `retry_count=0`，為什麼還要寫 `int(retry_count)`？

結論：**這一行請 Airflow 在每次執行前算出「這是第幾次重試」，當成參數交給 `extract_youbike`。** 傳進來不是為了控制重試，重試仍由 Airflow 決定；要傳是因為 D12-B 要求 `run_status` 自己記 `retry_count`。Airflow 傳來的是字串 `"0"`，不是 int；`int()` 不是必要的，但能把型別統一成數字。

#### 這一行怎麼拆

| 片段 | 意思 |
|---|---|
| `op_kwargs` | Airflow 呼叫 `python_callable` 時要帶的具名參數 |
| `"{{ ... }}"` | Jinja 模板；DAG 檔被讀取時只是字串，任務要跑時 Airflow 才算出裡面的值 |
| `ti` | task instance，代表現在這次執行的任務；和 `data_interval_end` 一樣由 Airflow 提供，不用 import |
| `ti.try_number` | 現在是第幾次嘗試，第一次是 1 |
| `- 1` | `retry_count` 記的是重試幾次，第一次還沒重試，所以要是 0 |

`retries=4` 代表最多跑 5 次，傳進去的值依序是 `"0"` 到 `"4"`。

#### 為什麼不是只看 Airflow

只想知道有沒有重試，Airflow 的畫面和 log 就看得到。要傳進來有兩個原因：

- **契約要求：** [dashboard](de_transition_daily_dashboard.html) 的 D12-B 要 `run_status` 記 `retry_count`。
- **函式自己不知道：** `extract_youbike` 是普通 Python 函式，命令列和測試也直接呼叫它，所以數字要由外面傳進來。不傳的話欄位一直是預設值 0，真的重試過的那筆也顯示 0。

這個欄位和 Airflow 確實重複：每次嘗試都會新增一筆 run，同一個 `scheduled_at` 有幾筆，大致就看得出跑了幾次。`retry_count` 多給的是兩件事：

- **分得出重試和手動重跑：** 手動重跑也會多一筆，但它的 `retry_count` 是 0。
- **查詢方便：** 用 SQL 查 `run_status` 就看得到，不用再去對 Airflow。

決定（2026-11-04）：Andrew 選擇保留這個欄位。HTML 原本只要求「記 retry_count」；「DAG 用 `ti.try_number - 1` 傳進來」是助理補的做法，同日由 Andrew 確認採用。

#### 範例 1：模板算出來是字串

```python
from jinja2 import Template

class FakeTI:
    try_number = 3

rendered = Template("{{ ti.try_number - 1 }}").render(ti=FakeTI())
print(repr(rendered), type(rendered).__name__)
print(int(rendered))
```

```text
'2' str
2
```

`FakeTI` 只是假裝成 Airflow 的 `ti`，讓範例不用開 Airflow 也能跑。算出來的 `'2'` 有引號，是字串；`int()` 才把它變成數字。這段不放進專案，Airflow 會自己處理模板。

#### 範例 2：沒傳 vs 有傳

```python
def save_order(log, retry_count=0):
    log.append(retry_count)

no_pass = []
for try_number in [1, 2]:
    save_order(no_pass)

passed = []
for try_number in [1, 2]:
    save_order(passed, retry_count=try_number - 1)

print('沒傳：', no_pass)
print('有傳：', passed)
```

```text
沒傳： [0, 0]
有傳： [0, 1]
```

迴圈代表 Airflow，只有它知道第幾次；`save_order` 代表產品函式。第 2 次明明是重試，沒傳就記成 0。

#### 範例 3：字串也寫得進 integer 欄位

在 `Youbike/` 底下執行，用暫存表，連線結束就消失：

```python
from dotenv import dotenv_values
import psycopg

dsn = dotenv_values(".env")["YOUBIKE_TEST_DATABASE_URL"]
with psycopg.connect(dsn, autocommit=True) as conn:
    conn.execute("CREATE TEMP TABLE runs (retry_count integer NOT NULL DEFAULT 0)")
    conn.execute("INSERT INTO runs (retry_count) VALUES (%s)", ("2",))
    row = conn.execute("SELECT retry_count, pg_typeof(retry_count)::text FROM runs").fetchone()
    print(row)
```

```text
(2, 'integer')
```

傳進去的是字串 `"2"`，PostgreSQL 自己轉成了整數，所以不加 `int()` 也寫得進去。

#### 範例 4：字串在 Python 裡不能和數字比

```python
retry_count = "2"
print(int(retry_count) > 0)
try:
    print(retry_count > 0)
except TypeError as error:
    print(error)
```

```text
True
'>' not supported between instances of 'str' and 'int'
```

這就是建議加 `int()` 的原因：同一個參數可能是 int 也可能是 str，先統一成數字，之後在 Python 裡比較或計算才不會出錯。

#### 對照本專案

依 2026-11-04 16:09 的存檔。

| 位置 | 寫法 |
|---|---|
| `src/extract/youbike.py` 的參數 | `retry_count=0` |
| `src/extract/youbike.py` 寫 running 的 INSERT | 多寫 `retry_count` 欄位，值是 `int(retry_count)` |
| `dags/youbike_realtime.py` 的 `op_kwargs` | `"retry_count":"{{ti.try_number-1}}"` |

| 誰呼叫 | 傳進來的值 | 型別 |
|---|---|---|
| 命令列、測試（沒傳） | `0` | int |
| Airflow | `"0"` | str |

真實 Airflow 的 11/04 16:00 那次：

| 看哪裡 | 值 |
|---|---|
| Airflow 算出的 `op_kwargs` | `{'retry_count': '0', 'scrape_time': '2026-11-04 08:00:00+00:00'}` |
| Airflow 的 `try_number` | 1 |
| 正式庫的 `run_status.retry_count` | 0 |

`scrape_time` 走同一個模板機制，也是字串，所以產品才有 `isinstance(scrape_time, str)` 那段轉換。

如果來源第一次回 503，依程式推演會是這樣（這個情況還沒真的發生過）：

```text
第一次：extract_youbike(scrape_time=這個 slot, retry_count="0")
        丟出 HTTPError，run_status 新增一筆 failed，retry_count = 0

重試：  extract_youbike(scrape_time=同一個 slot, retry_count="1")
        這次成功，run_status 再新增一筆 succeeded，retry_count = 1
```

#### 容易混淆的地方

1. **`retry_count=0` 不代表傳進來的是 int：** 0 只是沒人傳值時的預設值。
2. **傳值不是控制重試：** 要不要重試、等多久，還是 `retries` 和 `Retry_Policy` 決定。
3. **`- 1` 不能拿掉：** `try_number` 從 1 開始，拿掉的話第一次執行就記成重試 1 次。
4. **不用在專案裡 import jinja2：** Airflow 自己處理模板，範例 1 只是示範。`{{ti.try_number-1}}` 和 `{{ ti.try_number - 1 }}` 一樣，空格不影響。
5. **寫得進去是 PostgreSQL 在轉型：** 不是 Python 幫忙。字串 `"abc"` 會被 PostgreSQL 拒絕（`InvalidTextRepresentation`）。
6. **DAG 和函式的參數名要對上：** DAG 多了這一項而函式沒有這個參數時，不會報錯。PythonOperator 會依函式的參數過濾 `op_kwargs`，對不上的 key 直接丟掉，欄位就一直是預設值 0，所以不能只看到 0 就當作有傳進來。自己直接呼叫函式才會報 `TypeError`。（2026-11-04 更正：原本寫 DAG 先上線會報 `TypeError`，Airflow 3.3.2 實跑不會。）
7. **參數放第一個目前沒有影響：** 現有呼叫都用名字傳。如果有人直接寫 `extract_youbike("http://...")`，網址會被當成 `retry_count`。

一句話記法：Airflow 知道第幾次，函式不知道，所以要傳；模板算完是字串，寫進資料庫前用 `int()` 統一。

核對依據：範例 2、3、4 在本機 Youbike/.venv（Python 3.9.6）獨立執行，範例 3 連 youbike_test 但只用暫存表；範例 1 在 Youbike/.venv-airflow（Python 3.12.13）執行，因為 .venv 沒有 jinja2。16:00 的 `op_kwargs` 與 `try_number` 查自 Airflow metadata，`retry_count` 查自正式庫。那次跑的是 16:09 之前的存檔，16:09 的存檔要到下一次排程才上線。只驗證到第一次嘗試；`retry_count` 大於 0 的情況還沒實際發生過。本筆記不增加 D12 驗收完成數。

### 2026-11-04：generate_series 和 expect.slot，先列出應該有的時間，再找缺少的

問題：`generate_series(...) AS expect(slot)` 是什麼？`expect.slot` 是怎麼來的，要怎麼用？

結論：**`generate_series(開始, 結束, 間隔)` 會產生一串值，一個值一列，不用先有資料表。`AS expect(slot)` 替這串值取名字：整組叫 `expect`，裡面那一欄叫 `slot`，後面用 `expect.slot` 拿到這一列的值。** 它只負責列出「應該有的」，要知道缺哪些，還要用 `NOT EXISTS` 去比對別的表。

`expect` 和 `slot` 都是自己取的。聊天裡的範例叫 `expected`，這裡照 Andrew 11/04 18:30 的存檔寫 `expect`，效果一樣。

#### 這段怎麼拆

| 片段 | 意思 |
|---|---|
| `generate_series(開始, 結束, 間隔)` | PostgreSQL 內建函式，從開始每次加一個間隔，超過結束就停；寫在 `FROM` 裡，用起來像一張表 |
| `TIMESTAMPTZ '2026-01-01 09:00+00'` | 告訴 PostgreSQL 這段文字是含時區的時間；`+00` 是 UTC，`+08` 是台北 |
| `INTERVAL '1 hour'` | 一段時間長度 |
| `AS expect(slot)` | 括號外是這組資料的名字，括號內是欄位的名字 |
| `expect.slot` | `expect` 這組資料的 `slot` 欄，和 `d.due_at` 是同一種寫法 |

#### 範例 1：不用資料表就能產生資料

```python
from dotenv import dotenv_values
import psycopg

dsn = dotenv_values(".env")["YOUBIKE_TEST_DATABASE_URL"]

with psycopg.connect(dsn, autocommit=True) as conn:
    print(conn.execute("SELECT n FROM generate_series(1, 3) AS nums(n)").fetchall())
    print(conn.execute("SELECT n FROM generate_series(1, 7, 2) AS nums(n)").fetchall())

    rows = conn.execute(
        """
        SELECT t.slot
        FROM generate_series(
            TIMESTAMPTZ '2026-01-01 09:00+08',
            TIMESTAMPTZ '2026-01-01 10:45+08',
            INTERVAL '30 minutes'
        ) AS t(slot)
        """
    ).fetchall()
    print([r[0].strftime("%H:%M") for r in rows])
```

```text
[(1,), (2,), (3,)]
[(1,), (3,), (5,), (7,)]
['09:00', '09:30', '10:00', '10:30']
```

數字省略間隔時是 1。結束點剛好落在格子上才會出現，所以第二行有 7；時間那行的下一格是 11:00，超過 10:45，所以停在 10:30。

#### 範例 2：`AS expect(slot)` 取的兩個名字

```python
from dotenv import dotenv_values
import psycopg

dsn = dotenv_values(".env")["YOUBIKE_TEST_DATABASE_URL"]

with psycopg.connect(dsn, autocommit=True) as conn:
    for sql in [
        "SELECT * FROM generate_series(1, 2)",
        "SELECT * FROM generate_series(1, 2) AS expect",
        "SELECT * FROM generate_series(1, 2) AS expect(slot)",
    ]:
        cursor = conn.execute(sql)
        print([column.name for column in cursor.description], cursor.fetchall())

    try:
        conn.execute("SELECT expected.slot FROM generate_series(1, 2) AS expect(slot)")
    except psycopg.Error as error:
        print(type(error).__name__, str(error).splitlines()[0])
```

```text
['generate_series'] [(1,), (2,)]
['expect'] [(1,), (2,)]
['slot'] [(1,), (2,)]
UndefinedTable missing FROM-clause entry for table "expected"
```

前三行是欄位名和資料：

- **不取名：** 欄位叫 `generate_series`。
- **只寫 `AS expect`：** 欄位也跟著叫 `expect`，沒有 `slot`。
- **寫 `AS expect(slot)`：** 欄位才叫 `slot`。

最後一行是名字對不上：`AS` 後面叫 `expect`，卻去拿 `expected.slot`，PostgreSQL 找不到這個名字。

#### 範例 3：用 `expect.slot` 找出兩張表都沒有的時間點

```python
from dotenv import dotenv_values
import psycopg

dsn = dotenv_values(".env")["YOUBIKE_TEST_DATABASE_URL"]

with psycopg.connect(dsn, autocommit=True) as conn:
    conn.execute("CREATE TEMP TABLE deliveries (due_at timestamptz PRIMARY KEY)")
    conn.execute("CREATE TEMP TABLE receipts (due_at timestamptz PRIMARY KEY)")
    conn.execute("INSERT INTO deliveries VALUES ('2026-01-01 09:00+00'), ('2026-01-01 10:00+00')")
    conn.execute("INSERT INTO receipts VALUES ('2026-01-01 11:00+00')")
    rows = conn.execute(
        """
        SELECT expect.slot
        FROM generate_series(
            TIMESTAMPTZ '2026-01-01 09:00+00',
            TIMESTAMPTZ '2026-01-01 12:00+00',
            INTERVAL '1 hour'
        ) AS expect(slot)
        WHERE NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.due_at = expect.slot)
          AND NOT EXISTS (SELECT 1 FROM receipts r WHERE r.due_at = expect.slot)
        ORDER BY expect.slot
        """
    ).fetchall()
    print(len(rows), [r[0].strftime("%H:%M %Z") for r in rows])
```

```text
1 ['20:00 CST']
```

可以想成一列一列比對：

| `expect.slot`（UTC） | deliveries | receipts | 結果 |
|---|---|---|---|
| 09:00 | 有 | 沒有 | 不留 |
| 10:00 | 有 | 沒有 | 不留 |
| 11:00 | 沒有 | 有 | 不留 |
| 12:00 | 沒有 | 沒有 | 留下 |

`expect.slot` 在這段有三種用法：

- **`SELECT expect.slot`：** 把這個時間印出來。
- **`d.due_at = expect.slot`：** 拿這一列的時間去另一張表查。輪到 09:00 時，這句就是在問「deliveries 有沒有 09:00」。
- **`ORDER BY expect.slot`：** 照時間排序。

`SELECT 1` 的 1 沒有特別意思，`EXISTS` 只看查不查得到列。留下的 12:00 UTC 就是台北 20:00；連線的時區是台北，所以印成 `20:00 CST`。

#### 範例 4：為什麼要寫 `expect.slot`，不要只寫 `slot`

這裡故意把欄位取成和 deliveries 一樣的 `due_at`。

```python
from dotenv import dotenv_values
import psycopg

dsn = dotenv_values(".env")["YOUBIKE_TEST_DATABASE_URL"]

with psycopg.connect(dsn, autocommit=True) as conn:
    conn.execute("CREATE TEMP TABLE deliveries (due_at timestamptz PRIMARY KEY)")
    conn.execute("INSERT INTO deliveries VALUES ('2026-01-01 09:00+00'), ('2026-01-01 10:00+00')")
    sql = """
        SELECT count(*)
        FROM generate_series(
            TIMESTAMPTZ '2026-01-01 09:00+00',
            TIMESTAMPTZ '2026-01-01 12:00+00',
            INTERVAL '1 hour'
        ) AS expect(due_at)
        WHERE NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.due_at = {right_side})
    """
    print("expect.due_at:", conn.execute(sql.format(right_side="expect.due_at")).fetchone()[0])
    print("due_at:", conn.execute(sql.format(right_side="due_at")).fetchone()[0])
```

```text
expect.due_at: 2
due_at: 0
```

11:00、12:00 明明沒有，只寫 `due_at` 卻查出 0 個，而且不會報錯。子查詢會先找自己這層的表，所以這句變成 `d.due_at = d.due_at`，只要 deliveries 有資料就成立。前面加上 `expect.` 才是外面這一列的時間。

#### 範例 5：起點決定查到什麼

deliveries 有 09:00、10:00、11:00，真正缺的只有 12:00，所以正確答案是 1。

```python
from dotenv import dotenv_values
import psycopg

dsn = dotenv_values(".env")["YOUBIKE_TEST_DATABASE_URL"]

with psycopg.connect(dsn, autocommit=True) as conn:
    conn.execute("CREATE TEMP TABLE deliveries (due_at timestamptz PRIMARY KEY)")
    conn.execute("INSERT INTO deliveries VALUES ('2026-01-01 09:00+00'), ('2026-01-01 10:00+00'), ('2026-01-01 11:00+00')")
    sql = """
        SELECT count(*)
        FROM generate_series({start}, TIMESTAMPTZ '2026-01-01 12:00+00', INTERVAL '1 hour') AS expect(slot)
        WHERE NOT EXISTS (SELECT 1 FROM deliveries d WHERE d.due_at = expect.slot)
    """
    starts = {
        "對齊": "date_trunc('hour', TIMESTAMPTZ '2026-01-01 09:17+00')",
        "沒對齊": "TIMESTAMPTZ '2026-01-01 09:17+00'",
        "太早": "TIMESTAMPTZ '2025-12-31 09:00+00'",
    }
    for name, start in starts.items():
        print(name, conn.execute(sql.format(start=start)).fetchone()[0])
```

```text
對齊 1
沒對齊 3
太早 25
```

- **對齊：** `date_trunc('hour', ...)` 把 09:17 切回 09:00，結果正確。
- **沒對齊：** 產生的是 09:17、10:17、11:17，每個都比不到資料，全被算成缺少；真正缺的 12:00 反而沒列出來。
- **太早：** 從前一天 09:00 開始，資料開始之前的 24 個時間也被算成缺少。

#### 對照本專案

| 範例 | 專案 |
|---|---|
| `deliveries.due_at` | `raw_bytes.fetched_start_at` |
| `receipts.due_at` | `run_status.scheduled_at` |
| `INTERVAL '1 hour'` | `INTERVAL '30 minutes'`，和排程一樣每 30 分鐘一個 slot |
| 寫死的開始和結束 | 最近 7 天，起點對齊整點，終點 `now() - INTERVAL '30 minutes'`，避開還在跑的 slot |

起點要對齊，是因為正式排程寫入的時間都在 :00 或 :30，差一分鐘就比不到。

[dashboard](de_transition_daily_dashboard.html) 的 D12-D 要的是「查得出應有卻沒有 run 的 slot」。最近 7 天和同時查 `raw_bytes` 是助理的建議，不是 HTML 的字句：11/03 18:30 之前還沒有 run 紀錄，只看 `run_status` 的話，舊 slot 全會被算成缺口。

2026-11-04 查正式庫時，最近 7 天兩張表都沒有的是 11/03 17:30、18:00 兩個 slot。

#### 容易混淆的地方

1. **名字不是關鍵字：** `expect`、`slot` 換成別的也可以，只要 `AS` 後面和使用的地方一致。
2. **`INTERVAL` 的數字和單位都放在引號裡：** `INTERVAL 30 'minutes'` 會報 `syntax error at or near "30"`，要寫 `INTERVAL '30 minutes'`。
3. **時間一定要給間隔：** 少了第三個參數會報 `function generate_series(timestamp with time zone, timestamp with time zone) does not exist`。
4. **三個參數不能全是沒標型別的字串：** 會報 `function generate_series(unknown, unknown, unknown) is not unique`，PostgreSQL 分不出要用哪個版本。其中一個有明確型別就可以，例如第二個參數是 `NOW() - INTERVAL '30 minutes'` 時，前後用字串也跑得動。
5. **開始比結束晚不會報錯：** 只會回 0 列，看起來像「沒有缺口」。查到 0 列時要先確認範圍對不對。

一句話記法：`generate_series` 列出應該有的時間，`AS expect(slot)` 替它取名，`expect.slot` 拿這個時間去別的表比對。

核對依據：範例都在本機 Youbike/.venv（Python 3.9.6）獨立執行，要在 `Youbike/` 底下跑才讀得到 `.env`；連 youbike_test（PostgreSQL 16.13），只用暫存表。第 2～5 點的訊息和結果也是同一環境實跑。兩個缺口來自 2026-11-04 下午的正式庫查詢，這次沒有重查。本筆記不增加 D12 驗收完成數。

## 6. Pydantic 來源模型

### 主題重點

- 角色：繼承 `BaseModel` 的類別寫規則；`模型.model_validate(dict)` 檢查一筆，回傳模型物件或丟 `ValidationError`；JSON 文字用 `model_validate_json`；整批 list 用 `TypeAdapter(List[模型])`。沒呼叫就沒檢查。
- `model_config = ConfigDict(...)` 管整個模型。YouBike 用 `strict=True`：`"300"`、`True` 不算 int，int 給 float 欄位可以（會變成 float）。
- `extra` 維持預設的 ignore：官方每列有 18 個 key，模型只宣告 10 個，設成 `forbid` 會讓每一列都被擋下。不用 `str_strip_whitespace`，它會改到原值；目前模型用 `pattern=r"\S"` 擋只有空白的文字。
- `YoubikeStations = TypeAdapter(Annotated[List[YoubikeStation], Field(min_length=1)])` 一次驗整批：不是 list 報 `list_type`，空的報 `too_short`，某列不是 object 報 `model_type`；錯誤的 `loc` 寫出第幾列、哪個欄位；1,824 站約 4 毫秒。
- `ValidationError` 是 `ValueError` 的子類：`extract_youbike` 照樣記 failed 再往外丟，Airflow 照舊不重試。
- alias：API 的名字只留在模型（`Field(alias="sno")`），程式和資料庫一律用 `station_id` 這類名字（2026-11-10 起）。
- 現況：2026-11-09 已接進產品（`check_json` 移除，`load_youbike` 入口整批驗）；2026-11-10 起屬性改用資料庫名字。下面 11/09 的範例保留當時的 API 名字寫法。

### 2026-11-09：Pydantic 和 model_validate 的關係：類別寫規則，model_validate 執行檢查

問題：Pydantic 和 `model_validate` 是什麼關係？

結論：**Pydantic 是套件；繼承 `BaseModel` 的類別把規則寫下來；`model_validate` 是拿一筆資料去照這些規則檢查的入口。** 合格就回傳模型物件，不合格就丟出 `ValidationError`。類別本身只是規則，沒有呼叫 `model_validate` 或其他驗證入口之前，什麼都不會被檢查。

#### 三者的分工

| 角色 | 是什麼 | 誰寫 |
|---|---|---|
| Pydantic | 套件，提供 `BaseModel`、`Field`、`ConfigDict`、`field_validator` 等工具 | 現成的 |
| 模型類別（繼承 `BaseModel`） | 寫規則：有哪些欄位、什麼型別、什麼限制 | 你 |
| `模型.model_validate(資料)` | 照類別的規則檢查一筆資料，回傳物件或丟錯 | 你在程式裡呼叫 |

`model_validate` 是 `BaseModel` 內建的 classmethod。類別只要繼承 `BaseModel`，就能直接用 `類別名.model_validate(...)`，不用自己定義。

#### 呼叫 model_validate 時發生什麼

1. 照欄位宣告檢查型別和限制，例如 `ConfigDict(strict=True)`、`Field(ge=0)`。
2. 跑 `@field_validator`：單一欄位的自訂檢查。
3. 所有欄位都過了，才跑 `@model_validator(mode="after")`：拿整筆資料一起檢查。
4. 全部通過就回傳物件；只要有一關沒過，就把所有錯誤收集起來，一次丟出 `ValidationError`。

#### 範例：五種寫法實跑

```python
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class Ticket(BaseModel):
    model_config = ConfigDict(strict=True)

    seat: str
    price: int = Field(ge=0)

    @field_validator("seat")
    @classmethod
    def seat_not_blank(cls, value):
        print("  field_validator seat:", repr(value))
        if not value.strip():
            raise ValueError("seat cannot be empty")
        return value

    @model_validator(mode="after")
    def whole_ticket(self):
        print("  model_validator after:", self.seat, self.price)
        return self


print("-- 1. model_validate(dict)")
ticket = Ticket.model_validate({"seat": "A1", "price": 300})
print(type(ticket).__name__, ticket.seat, ticket.price)

print("-- 2. Ticket(...) runs the same checks")
print(Ticket(seat="B2", price=100).model_dump())

print("-- 3. bad data")
try:
    Ticket.model_validate({"seat": "  ", "price": -1})
except ValidationError as error:
    print([(e["loc"], e["type"]) for e in error.errors()])

print("-- 4. model_validate_json")
print(Ticket.model_validate_json('{"seat": "C3", "price": 50}').model_dump())

print("-- 5. model_construct skips validation")
print(Ticket.model_construct(seat="  ", price=-1).model_dump())
```

```text
-- 1. model_validate(dict)
  field_validator seat: 'A1'
  model_validator after: A1 300
Ticket A1 300
-- 2. Ticket(...) runs the same checks
  field_validator seat: 'B2'
  model_validator after: B2 100
{'seat': 'B2', 'price': 100}
-- 3. bad data
  field_validator seat: '  '
[(('seat',), 'value_error'), (('price',), 'greater_than_equal')]
-- 4. model_validate_json
  field_validator seat: 'C3'
  model_validator after: C3 50
{'seat': 'C3', 'price': 50}
-- 5. model_construct skips validation
{'seat': '  ', 'price': -1}
```

1. **`model_validate(dict)`：** 先跑欄位檢查，再跑整筆檢查，回傳 `Ticket` 物件。
2. **`Ticket(...)` 也會檢查：** 直接用類別建立物件，跑的是同一套檢查。差別只在輸入寫法：`model_validate` 收一個 dict，`Ticket(...)` 收具名參數。從 JSON 解出來的 dict 用 `model_validate` 比較直接。
3. **不合格：** `seat` 和 `price` 兩個錯誤一次回報；欄位沒過，`model_validator` 就不會執行。
4. **`model_validate_json`：** 直接收 JSON 字串，解析和檢查一起做。
5. **`model_construct` 不檢查：** 空白座位和負價格都照收。它是給已經確定合法的資料用的，來源資料不要用它。

#### 容易搞混的名字

| 名字 | 是什麼 |
|---|---|
| `model_validate` | classmethod，呼叫它去檢查一筆資料 |
| `model_validator` | 裝飾器，寫在類別裡的整筆資料自訂檢查，在 `model_validate` 執行過程中被呼叫 |
| `field_validator` | 裝飾器，單一欄位的自訂檢查，也在 `model_validate` 執行過程中被呼叫 |
| `TypeAdapter(...).validate_python(...)` | 要檢查的不是模型、而是 list 這類型別時用的入口，例如一次檢查整批 |

（YouBike 的用法整合在本主題的重點。）

一句話記法：類別寫規則，`model_validate` 執行規則；沒呼叫就沒檢查。

核對依據：範例在本機 Youbike/.venv（Python 3.9.6、pydantic 2.13.5）實跑一次；`ValidationError` 是 `ValueError` 子類，是 2026-11-04 在同一環境實測的結果。本筆記不增加驗收完成數。

### 2026-11-09：model_validate 接收什麼、回傳什麼

問題：Pydantic 的 `model_validate` 接收什麼參數、什麼型別？回傳什麼？出錯會怎樣？

結論：**`模型.model_validate(obj)` 是類別方法，第一個參數 `obj` 通常是一個 dict（key 對應欄位名稱）。檢查通過就回傳一個模型物件，不通過就丟 `ValidationError`。** 它不接受 JSON 文字，也不接受 list：JSON 文字用 `model_validate_json`，整批 list 用 `TypeAdapter(List[模型])`。

#### 參數

| 參數 | 型別 | 用途 |
|---|---|---|
| `obj`（第一個，照位置傳） | 通常是 `dict`；搭配 `from_attributes=True` 時可以是有屬性的物件 | 要檢查的資料 |
| `strict` | `bool` 或 `None` | 這次呼叫要不要用嚴格模式；`None` 時照類別的 `model_config` |
| `extra` | `"ignore"`、`"allow"`、`"forbid"` 或 `None` | 這次呼叫怎麼處理多出來的 key；`None` 時照 `model_config` |
| `from_attributes` | `bool` 或 `None` | 允許從物件的屬性讀值，例如 dataclass |
| `context` | 任意 | 傳額外資訊給自訂的 validator 用 |
| `by_alias`、`by_name` | `bool` 或 `None` | 欄位有 alias 時，要用 alias 還是欄位名稱去對 key |

簽名裡的 `*` 表示後面的參數只能用關鍵字傳，例如 `strict=True`。

#### 範例：不同輸入、回傳值與錯誤

```python
import inspect
from dataclasses import dataclass
from typing import List

import pydantic
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError


class Item(BaseModel):
    name: str
    count: int


def show(label, call):
    try:
        result = call()
        print(f"{label:22} -> {result!r} ({type(result).__name__})")
    except ValidationError as error:
        print(f"{label:22} -> {[(e['loc'], e['type']) for e in error.errors()]}")


print("pydantic", pydantic.VERSION)
print("signature:", inspect.signature(Item.model_validate))
show("dict", lambda: Item.model_validate({"name": "pen", "count": 2}))
show("dict, extra key", lambda: Item.model_validate({"name": "pen", "count": 2, "color": "red"}))
show("JSON text", lambda: Item.model_validate('{"name": "pen", "count": 2}'))
show("model_validate_json", lambda: Item.model_validate_json('{"name": "pen", "count": 2}'))
show("list of dicts", lambda: Item.model_validate([{"name": "pen", "count": 2}]))
show("TypeAdapter list", lambda: TypeAdapter(List[Item]).validate_python([{"name": "pen", "count": 2}]))


@dataclass
class Row:
    name: str
    count: int


show("object", lambda: Item.model_validate(Row("cup", 5)))
show("object, from_attributes", lambda: Item.model_validate(Row("cup", 5), from_attributes=True))
show("'5', default", lambda: Item.model_validate({"name": "pen", "count": "5"}))
show("'5', strict=True", lambda: Item.model_validate({"name": "pen", "count": "5"}, strict=True))

item = Item.model_validate({"name": "pen", "count": 2})
print("attribute access:", item.name, item.count, "| model_dump:", item.model_dump())
try:
    Item.model_validate({"name": "pen", "count": "two"})
except ValidationError as error:
    first = error.errors()[0]
    print("isinstance ValueError:", isinstance(error, ValueError), "| error count:", error.error_count())
    print("one error dict keys:", sorted(first))
    print("type/loc/msg/input:", first["type"], first["loc"], first["msg"], repr(first["input"]))
```

```text
pydantic 2.13.5
signature: (obj: 'Any', *, strict: 'bool | None' = None, extra: 'ExtraValues | None' = None, from_attributes: 'bool | None' = None, context: 'Any | None' = None, by_alias: 'bool | None' = None, by_name: 'bool | None' = None) -> 'Self'
dict                   -> Item(name='pen', count=2) (Item)
dict, extra key        -> Item(name='pen', count=2) (Item)
JSON text              -> [((), 'model_type')]
model_validate_json    -> Item(name='pen', count=2) (Item)
list of dicts          -> [((), 'model_type')]
TypeAdapter list       -> [Item(name='pen', count=2)] (list)
object                 -> [((), 'model_type')]
object, from_attributes -> Item(name='cup', count=5) (Item)
'5', default           -> Item(name='pen', count=5) (Item)
'5', strict=True       -> [(('count',), 'int_type')]
attribute access: pen 2 | model_dump: {'name': 'pen', 'count': 2}
isinstance ValueError: True | error count: 1
one error dict keys: ['input', 'loc', 'msg', 'type', 'url']
type/loc/msg/input: int_parsing ('count',) Input should be a valid integer, unable to parse string as an integer 'two'
```

- **dict：** 回傳 `Item` 物件。多出來的 key（`color`）預設會被忽略。
- **JSON 文字：** 報 `model_type`，因為它要的是 dict。同一段文字改用 `model_validate_json` 就可以。
- **list：** 同樣報 `model_type`。整批要用 `TypeAdapter(List[Item]).validate_python(...)`，回傳的是 list。
- **一般物件：** 預設不接受，加 `from_attributes=True` 才會從屬性讀值。
- **嚴格模式：** 預設會把 `'5'` 轉成 `5`；這次呼叫傳 `strict=True` 就會擋下（`int_type`）。寫在類別的 `model_config = ConfigDict(strict=True)`，就是每次呼叫都嚴格。
- **回傳值：** 用 `.name`、`.count` 取值；`model_dump()` 轉回 dict。
- **錯誤：** `ValidationError` 是 `ValueError` 的子類。`error.errors()` 是一個 list，每個錯誤是一個 dict，`type` 是錯誤種類、`loc` 是位置、`msg` 是說明、`input` 是收到的值；`error.error_count()` 是錯誤數量。

（YouBike 的用法整合在本主題的重點。）

一句話記法：`model_validate` 吃 dict、回傳模型物件、錯了丟 `ValidationError`；JSON 文字用 `model_validate_json`，list 用 `TypeAdapter`。

核對依據：範例在本機 Youbike/.venv（Python 3.9.6、pydantic 2.13.5）實跑，簽名取自 `inspect.signature`。18 個 key 的實測用 youbike_test 裡一列真實資料。本筆記不增加驗收完成數。

### 2026-11-09：Pydantic 的 ConfigDict：寫在哪裡、有什麼用

問題：`model_config = ConfigDict(strict=True)` 是什麼？除了 `strict` 還能設定什麼？

結論：**`ConfigDict` 是整個模型的共同設定，寫在類別裡，名字固定叫 `model_config`。** 欄位宣告管「每個欄位是什麼型別、有什麼限制」，`ConfigDict` 管「整個模型怎麼驗證」，例如要不要自動轉型、遇到沒宣告的 key 怎麼辦。

#### 寫法

```python
from pydantic import BaseModel, ConfigDict

class StrictBook(BaseModel):
    model_config = ConfigDict(strict=True)

    pages: int
    price: float
```

- **名字固定：** `model_config` 是 Pydantic 規定的名字，寫成別的名字只是普通的類別屬性，不會生效。
- **它就是 dict：** `ConfigDict(strict=True)` 在執行時等於 `{'strict': True}`，可以用 `StrictBook.model_config` 讀回來。
- **不寫就用預設值。**
- **版本：** 舊版 Pydantic v1 是在類別裡寫 `class Config:`；專案用的是 v2（2.13.5），要用 `ConfigDict`。

#### 常用設定

| 設定 | 預設 | 作用 |
|---|---|---|
| `strict=True` | `False` | 不自動轉型：`"300"` 不算 int、`True` 不算 int、`"9.5"` 不算 float；int 給 float 欄位可以 |
| `extra="ignore"` | 預設就是這個 | 沒宣告的 key 直接丟掉 |
| `extra="forbid"` | — | 有沒宣告的 key 就報 `extra_forbidden` |
| `extra="allow"` | — | 沒宣告的 key 也保留下來 |
| `str_strip_whitespace=True` | `False` | 文字欄位自動去掉前後空白，會改到值 |

#### 範例：五種情況實跑

```python
import warnings

from pydantic import BaseModel, ConfigDict, ValidationError


def check(model, data):
    try:
        print(model.__name__, "accepted", model.model_validate(data).model_dump())
    except ValidationError as error:
        print(model.__name__, "rejected", [(e["loc"], e["type"]) for e in error.errors()])


print("-- 1. strict")


class LaxBook(BaseModel):
    pages: int
    price: float


class StrictBook(BaseModel):
    model_config = ConfigDict(strict=True)

    pages: int
    price: float


for data in ({"pages": "300", "price": "9.5"}, {"pages": True, "price": 10}):
    check(LaxBook, data)
    check(StrictBook, data)

print("-- 2. extra")


class IgnoreExtra(BaseModel):
    title: str


class ForbidExtra(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


class AllowExtra(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str


for model in (IgnoreExtra, ForbidExtra, AllowExtra):
    check(model, {"title": "Data", "shelf": "A3"})

print("-- 3. str_strip_whitespace")


class Stripped(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str


check(IgnoreExtra, {"title": "  Data  "})
check(Stripped, {"title": "  Data  "})

print("-- 4. misspelled key")
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")

    class Typo(BaseModel):
        model_config = ConfigDict(strick=True)

        pages: int

check(Typo, {"pages": "300"})
print("warnings:", [str(w.message)[:70] for w in caught])

print("-- 5. read the settings back")
print(StrictBook.model_config)
print(type(ConfigDict(strict=True)).__name__)
```

```text
-- 1. strict
LaxBook accepted {'pages': 300, 'price': 9.5}
StrictBook rejected [(('pages',), 'int_type'), (('price',), 'float_type')]
LaxBook accepted {'pages': 1, 'price': 10.0}
StrictBook rejected [(('pages',), 'int_type')]
-- 2. extra
IgnoreExtra accepted {'title': 'Data'}
ForbidExtra rejected [(('shelf',), 'extra_forbidden')]
AllowExtra accepted {'title': 'Data', 'shelf': 'A3'}
-- 3. str_strip_whitespace
IgnoreExtra accepted {'title': '  Data  '}
Stripped accepted {'title': 'Data'}
-- 4. misspelled key
Typo accepted {'pages': 300}
warnings: []
-- 5. read the settings back
{'strict': True}
dict
```

1. **strict：** 沒設時，`"300"` 被轉成 300、`True` 被轉成 1，資料默默變了；設了 strict 就報 `int_type`、`float_type`。第二組的 `price: 10` 在 strict 下也接受，會變成 `10.0`。
2. **extra：** 同一筆多了 `shelf`，預設丟掉，`forbid` 報錯，`allow` 保留。
3. **str_strip_whitespace：** 沒設時保留原本的空白；設了以後值被改成 `'Data'`。
4. **拼錯不會報錯：** `strick=True` 沒有任何警告，也沒有生效，`"300"` 照樣被轉成 300。寫完可以用 `model_config` 讀回來確認，或拿一筆應該被擋的資料試一次。
5. **讀回設定：** `StrictBook.model_config` 印出 `{'strict': True}`，`ConfigDict(...)` 的型別就是 `dict`。

（YouBike 的用法整合在本主題的重點。）

一句話記法：欄位宣告管單一欄位，`model_config = ConfigDict(...)` 管整個模型；YouBike 用 `strict=True`，其餘保持預設。

核對依據：範例在本機 Youbike/.venv（Python 3.9.6、pydantic 2.13.5）實跑一次。8 個欄位名來自 2026-11-04 對正式庫最新 raw 的唯讀檢查。本筆記不增加驗收完成數。

### 2026-11-09：TypeAdapter 整批驗證：YoubikeStations 怎麼組成、做了什麼、怎麼接進產品

問題：`YoubikeStations = TypeAdapter(...)` 這一行在做什麼？已經有 `YoubikeStation`（BaseModel）的欄位了，為什麼還要它？實際要怎麼接進 `youbike.py`？

結論：**`YoubikeStation` 一次只驗「一個站」，官方回傳的是「一整個 list 的站」。`TypeAdapter` 把「list、至少 1 筆、每一筆都照 `YoubikeStation` 驗」包成一個驗證器，一次呼叫就把整批驗完，錯誤會寫出第幾列、哪個欄位。** 它不是必要的：只用 BaseModel 加迴圈也行，但「批次不能空、要是 list」就得保留手寫判斷。HTML 的 E3-2 要把「非空批次、逐列 object」也集中到模型，所以建議用 TypeAdapter。

現行寫法（`src/extract/youbike_model.py`，2026-11-09 存檔）：

```python
YoubikeStations = TypeAdapter(Annotated[List[YoubikeStation], Field(min_length=1)])
```

#### 為什麼不能只靠 BaseModel

- **整個 list 直接丟給 `YoubikeStation.model_validate`：** 不行。它只收一個 dict，收到 list 就報 `model_type`。
- **用迴圈一列一列丟：** 可以，但整批的規則會漏掉。

```python
import sys

sys.path.insert(0, ".")
from pydantic import ValidationError
from src.extract.youbike_model import YoubikeStation

good = {"sno": "1", "sna": "model check", "sarea": "fixture", "latitude": 25.03, "longitude": 121.56, "Quantity": 6,
        "available_rent_bikes": 2, "available_return_bikes": 4, "act": "1", "srcUpdateTime": "2023-08-01 00:00:00"}


def loop_validate(batch):
    return [YoubikeStation.model_validate(row) for row in batch]


for label, batch in (("list of rows", [good]), ("empty list", []), ("one dict, no list", good)):
    try:
        print(f"{label:18} -> {loop_validate(batch)!r}")
    except ValidationError as error:
        print(f"{label:18} -> {[(e['loc'], e['type'], e['input']) for e in error.errors()]}")
try:
    YoubikeStation.model_validate([good])
except ValidationError as error:
    print(f"{'whole list at once':18} -> {[(e['loc'], e['type']) for e in error.errors()]}")
```

```text
list of rows       -> [YoubikeStation(sno='1', sna='model check', ..., srcUpdateTime='2023-08-01 00:00:00')]
empty list         -> []
one dict, no list  -> [((), 'model_type', 'sno')]
whole list at once -> [((), 'model_type')]
```

（第一行太長，中間以 `...` 省略。）

- **空 list：** 迴圈一次都沒跑，回傳 `[]`、不報錯，空資料會被當成成功。
- **不是 list 而是一個 dict：** 迴圈會去跑 dict 的 key，拿字串 `'sno'` 去驗、報 `model_type`。有擋下，但錯誤看不出真正的問題是「這不是 list」。

| 做法 | 單列規則 | 「批次不能空、要是 list」 |
|---|---|---|
| 只用 `YoubikeStation`＋迴圈 | 模型負責 | 留著 `load_youbike` 原本的手寫判斷 |
| 再加 `YoubikeStations`（TypeAdapter） | 模型負責 | 也由它負責，錯誤寫出第幾列 |

#### TypeAdapter 是什麼

`BaseModel` 只能驗「有欄位的物件」；`TypeAdapter` 可以替任何型別產生驗證器，例如 list、int，或加了限制的型別。常用的兩個方法：

- **`validate_python(資料)`：** 驗 Python 物件，例如 `loads(body)` 得到的 list。
- **`validate_json(文字或 bytes)`：** 直接驗 JSON 原文，解析和驗證一起做。

#### 這一行怎麼組起來（由內往外）

| 片段 | 意思 |
|---|---|
| `YoubikeStation` | 一個站的規則 |
| `List[YoubikeStation]` | 一個 list，裡面每個元素都照上面的規則驗 |
| `Field(min_length=1)` | 這個 list 至少要有 1 個元素 |
| `Annotated[型別, 限制]` | 把限制貼在型別上；不在 BaseModel 類別裡，沒辦法寫 `欄位: 型別 = Field(...)`，所以用這種寫法 |
| `TypeAdapter(...)` | 把整個型別變成驗證器；放在模組最上層，import 時建一次，之後重複使用 |

`List` 和 `Annotated` 從 `typing` 匯入，Python 3.9 可以用；不要用 3.9 不支援的 `int | None` 寫法。

#### validate_python 依序做的事

1. **確認最外層是 list：** 不是就報 `list_type`。
2. **每個元素用 `YoubikeStation` 驗：** 不是 dict 就報 `model_type`，欄位不合規則就報對應的錯。
3. **確認至少 1 筆：** 空的就報 `too_short`。
4. **錯誤全部收集：** 不會遇到第一個錯就停；最後一次丟出 `ValidationError`，每個錯誤的 `loc` 是「第幾列（從 0 開始）、哪個欄位」。
5. **全部通過：** 回傳一個 list，裡面是 `YoubikeStation` 物件；傳進去的原始 dict 不會被改動。

#### validate_python 回傳什麼

全部通過時才有回傳值；只要有一個錯，就不回傳，直接丟 `ValidationError`。回傳值的內容：

| 項目 | 內容 |
|---|---|
| 型別 | 一般的 Python `list` |
| 長度與順序 | 和傳進去的 list 一樣；第幾個站就在第幾個位置 |
| 每個元素 | 一個 `YoubikeStation` 物件，用 `.sno`、`.Quantity` 這種寫法取值 |
| 欄位 | 只有模型宣告的 10 個；官方多給的 8 個 key（`mday`、`infoTime` 等）不會出現在物件裡 |
| 值 | 和原始 dict 相同；只有 float 欄位收到 int 時會變成 float（`25` 變 `25.0`） |
| 原始資料 | 回傳的是新物件，傳進去的 dict 不會被改動，還是 18 個 key |
| 轉回 dict | `物件.model_dump()`，得到只含這 10 個欄位的 dict |

```python
"""Read-only: what validate_python returns, using one real raw body from youbike_test."""
import sys
from json import loads

sys.path.insert(0, ".")
import psycopg
from config import get_env_variable
from src.extract.youbike_model import YoubikeStations

with psycopg.connect(get_env_variable("YOUBIKE_TEST_DATABASE_URL")) as conn:
    conn.read_only = True
    body = bytes(conn.execute("SELECT body FROM raw_bytes WHERE octet_length(body) > 100000 ORDER BY fetched_start_at DESC LIMIT 1").fetchone()[0])
rows = loads(body)
stations = YoubikeStations.validate_python(rows)

print("type:", type(stations).__name__, "| length:", len(stations), "(input", len(rows), ")")
print("same order:", [s.sno for s in stations[:3]] == [r["sno"] for r in rows[:3]])
first = stations[0]
print("element type:", type(first).__name__)
print("attribute access:", first.sno, first.Quantity, first.srcUpdateTime)
dumped = first.model_dump()
print("model_dump keys:", len(dumped), list(dumped))
print("original dict keys:", len(rows[0]), "| dropped:", sorted(set(rows[0]) - set(dumped)))
print("values equal for the 10 fields:", all(dumped[k] == rows[0][k] for k in dumped))
print("new objects, not the input dicts:", first is not rows[0], "| input dict unchanged:", type(rows[0]).__name__, len(rows[0]))

int_lat = dict(rows[0], latitude=25)
converted = YoubikeStations.validate_python([int_lat])[0]
print("int latitude in:", repr(int_lat["latitude"]), "-> out:", repr(converted.latitude))
```

```text
type: list | length: 1824 (input 1824 )
same order: True
element type: YoubikeStation
attribute access: 500101001 28 2026-11-09 15:12:52
model_dump keys: 10 ['sno', 'sna', 'sarea', 'latitude', 'longitude', 'Quantity', 'available_rent_bikes', 'available_return_bikes', 'act', 'srcUpdateTime']
original dict keys: 18 | dropped: ['ar', 'aren', 'infoDate', 'infoTime', 'mday', 'sareaen', 'snaen', 'updateTime']
values equal for the 10 fields: True
new objects, not the input dicts: True | input dict unchanged: dict 18
int latitude in: 25 -> out: 25.0
```

- **只當關卡時：** 回傳值可以不用，原本的 dict 完全沒變，照舊拿去跑 `parse_station`。
- **改用回傳的物件時：** 取值要改成 `.sno` 這種寫法；物件裡只剩 10 個欄位，`parse_station` 用到的也正好是這 10 個，所以不會缺。
- **正式資料的經緯度本來就是 float**，`25` 變 `25.0` 這種轉換實際上不會發生；範例是刻意把一筆改成 int 才看得到。

#### 範例 1：小批次

`good` 是測試裡 `VALID_STATION` 那一筆，`bad_row` 是把它的 `Quantity` 改成 `-1`。

```python
import sys

sys.path.insert(0, ".")
from pydantic import ValidationError
from src.extract.youbike_model import YoubikeStations

good = {"sno": "1", "sna": "model check", "sarea": "fixture", "latitude": 25.03, "longitude": 121.56, "Quantity": 6,
        "available_rent_bikes": 2, "available_return_bikes": 4, "act": "1", "srcUpdateTime": "2023-08-01 00:00:00"}
bad_row = dict(good, Quantity=-1)

result = YoubikeStations.validate_python([good, good])
print("two good rows ->", type(result).__name__, len(result), type(result[0]).__name__, result[0].Quantity)
for label, batch in (("empty list", []), ("one dict, no list", good), ("2nd row is text", [good, "x"]), ("2nd row Quantity -1", [good, bad_row])):
    try:
        YoubikeStations.validate_python(batch)
        print(f"{label:20} -> accepted")
    except ValidationError as error:
        print(f"{label:20} -> {[(e['loc'], e['type']) for e in error.errors()]}")
```

```text
two good rows -> list 2 YoubikeStation 6
empty list           -> [((), 'too_short')]
one dict, no list    -> [((), 'list_type')]
2nd row is text      -> [((1,), 'model_type')]
2nd row Quantity -1  -> [((1, 'Quantity'), 'greater_than_equal')]
```

| 情況 | 錯誤 | 取代 `load_youbike` 的哪個手寫判斷 |
|---|---|---|
| 空 list | `too_short` | `json==[]` |
| 不是 list | `list_type` | `isinstance(json,list)==False` |
| 某一列不是 object | `model_type`，`loc` 是第幾列 | `isinstance(row,dict)` |
| 某一列欄位不合法 | `loc` 同時寫出第幾列、哪個欄位 | `parse_station` 裡的 `check_json` |

#### 範例 2：真實一批（youbike_test 裡最新的一份完整 raw）

```python
"""Read-only: run the saved YoubikeStations adapter on one real raw body from youbike_test."""
import sys
from json import loads
from time import perf_counter
from typing import List

sys.path.insert(0, ".")
import psycopg
from pydantic import Field, TypeAdapter, ValidationError
from typing_extensions import Annotated
from config import get_env_variable
from src.extract.youbike_model import YoubikeStation, YoubikeStations

with psycopg.connect(get_env_variable("YOUBIKE_TEST_DATABASE_URL")) as conn:
    conn.read_only = True
    body = bytes(conn.execute("SELECT body FROM raw_bytes WHERE octet_length(body) > 100000 ORDER BY fetched_start_at DESC LIMIT 1").fetchone()[0])
rows = loads(body)

t = perf_counter()
stations = YoubikeStations.validate_python(rows)
print(f"validate_python: {len(rows)} rows -> {type(stations).__name__} of {type(stations[0]).__name__}, {1000 * (perf_counter() - t):.1f} ms")
t = perf_counter()
stations_json = YoubikeStations.validate_json(body)
print(f"validate_json:   bytes -> {len(stations_json)} stations, {1000 * (perf_counter() - t):.1f} ms")
print("first station:", stations[0].sno, stations[0].Quantity, "| original dict untouched:", type(rows[0]).__name__)

two_bad = [dict(r) for r in rows]
two_bad[3]["Quantity"] = -1
two_bad[7]["sno"] = "   "
try:
    YoubikeStations.validate_python(two_bad)
except ValidationError as error:
    print("two bad rows ->", error.error_count(), "errors:", [(e["loc"], e["type"]) for e in error.errors()])

all_bad = [dict(r, Quantity=-1) for r in rows]
try:
    YoubikeStations.validate_python(all_bad)
except ValidationError as error:
    text = str(error)
    print("every row bad ->", error.error_count(), "errors; str(error) is", len(text), "characters; first line:", text.splitlines()[0])

t = perf_counter()
TypeAdapter(Annotated[List[YoubikeStation], Field(min_length=1)])
print(f"building a new TypeAdapter: {1000 * (perf_counter() - t):.1f} ms")
```

```text
validate_python: 1824 rows -> list of YoubikeStation, 4.4 ms
validate_json:   bytes -> 1824 stations, 6.0 ms
first station: 500101001 28 | original dict untouched: dict
two bad rows -> 2 errors: [((3, 'Quantity'), 'greater_than_equal'), ((7, 'sno'), 'string_pattern_mismatch')]
every row bad -> 1824 errors; str(error) is 372857 characters; first line: 1824 validation errors for list[YoubikeStation]
building a new TypeAdapter: 0.5 ms
```

- **速度：** 1,824 站驗一次 4.4 毫秒，每 30 分鐘跑一次不用擔心。
- **同時有兩列壞掉：** 兩個錯都列出來（第 3 列的 `Quantity`、第 7 列的 `sno`），一次就知道要修哪裡。
- **整批都壞：** 例如官方改了格式，會有 1,824 個錯誤，`str(error)` 長達 37 萬字。
- **建立驗證器：** 0.5 毫秒；放在最上層建一次就好。

#### 接進 youbike.py 時要注意的事

（2026-11-09 已照這裡接上：`check_json` 已移除，`parse_station` 改收模型物件；2026-11-10 起屬性改用資料庫的名字，見 alias 一節。）

1. **放的位置：** 在 `load_youbike` 拿到 `loads(body)` 之後、逐列處理之前，整批先驗一次。原本「空批次、不是 list、某列不是 dict」的手寫判斷可以拿掉；`parse_station` 裡那 10 行 `check_json` 也可以拿掉，之後 `parse_station` 只負責改名和時間轉換。`check_json` 函式本身先留著，`test_check_json` 還在測它。
2. **回傳值怎麼用，二選一：**
   - **只當關卡（改動最小）：** 驗過之後照舊拿原本的 dict 跑 `parse_station`，回傳值不用。
   - **改用回傳的物件：** `parse_station` 要把 `row["sno"]` 這種寫法改成 `row.sno`，改動比較多。
3. **順序不變：** raw 還是先存、先 commit，再驗證。`ValidationError` 是 `ValueError` 的子類，`extract_youbike` 的 except 照樣記 `failed` 和 `error_code` 再往外丟，Airflow 也照舊不重試。
4. **`error_code` 可能很長（建議，不是驗收要求）：** 整批都壞時，37 萬字會整段寫進 `run_status.error_code`。存得進去，只是很肥；如果在意，可以只記 `error.error_count()` 加前幾筆 `error.errors()`。
5. **`validate_json` 可以省掉 `loads`：** 但後面還要用 dict 跑 `parse_station`，所以用 `validate_python(loads(body))` 比較順。
6. **存檔就上線：** `youbike.py` 存檔後下一個 :00 或 :30 就會用到。模型先寫完、測過再接；存檔挑 :01 到 :25 之間，存完馬上跑 `tests/unit`（2026-11-08 12:00–13:00 就因為存到中間版本漏掉 3 個 slot）。

一句話記法：`BaseModel` 驗一個站，`TypeAdapter(List[...])` 驗一整批；錯誤的 `loc` 會告訴你第幾列、哪個欄位。

核對依據：三段範例都在本機 Youbike/.venv（Python 3.9.6、pydantic 2.13.5）用 2026-11-09 存檔的 `youbike_model.py` 實跑；範例 2 讀 youbike_test 的 raw，只讀不寫。毫秒數是單次量測，會隨機器狀態變動。本筆記不增加驗收完成數。

### 2026-11-10：Pydantic alias：API 的名字只留在模型，程式一律用資料庫的名字

問題：`youbike_model.py` 裡加的 `alias` 是做什麼的？

結論：**`alias` 是「這個欄位在輸入資料裡叫什麼名字」。** 官方 API 的欄位名改不了（`sno`、`sna`、`Quantity`、`act`、`srcUpdateTime`），但程式和資料庫想用同一套名字。把對照寫成 `Field(alias="sno")`，讀資料時去 JSON 找 `"sno"`，讀進來之後一律用 `station.station_id`。API 的名字只出現在模型這一個地方，`parse_station`、`load_youbike` 都不再看到它們。

#### YouBike 的對照

| 官方 JSON（alias） | 程式與資料庫 |
|---|---|
| `sno` | `station_id` |
| `sna` | `station_name` |
| `sarea` | `station_area` |
| `Quantity` | `quantity` |
| `act` | `station_active` |
| `srcUpdateTime` | `source_update_time` |
| `latitude`、`longitude`、`available_rent_bikes`、`available_return_bikes` | 兩邊同名，不用 alias |

#### 範例：氣象資料的 tmp、stn

```python
from pydantic import BaseModel, ConfigDict, Field, ValidationError

class Reading(BaseModel):
    model_config = ConfigDict(strict=True)
    temperature: float = Field(alias="tmp")
    station_code: str = Field(alias="stn")

r = Reading.model_validate({"tmp": 21.5, "stn": "A01", "extra": 1})
print(r.temperature, r.station_code)
print(r.model_dump())
print(r.model_dump(by_alias=True))
try:
    Reading.model_validate({"temperature": 21.5, "station_code": "A01"})
except ValidationError as e:
    print([(x["loc"], x["type"]) for x in e.errors()])
```

```text
21.5 A01
{'temperature': 21.5, 'station_code': 'A01'}
{'tmp': 21.5, 'stn': 'A01'}
[(('tmp',), 'missing'), (('stn',), 'missing')]
```

- **第 1 行：** 輸入用 `tmp`、`stn`，讀進來後用 `r.temperature`、`r.station_code` 取值；多出來的 `extra` 預設忽略。
- **第 2、3 行：** 轉回 dict 時預設用程式裡的名字；加 `by_alias=True` 就換回原始名字。
- **第 4 行：** 直接拿程式名字當輸入會被當成缺欄位。輸入一定要用 alias 的名字，錯誤訊息也用 alias 指出是哪一欄。

#### 注意

1. **規則不受影響：** `strict=True`、`pattern=r"\S"`（不能空白）、`ge=0`（不能負數）照樣作用在欄位上，加 alias 只改「去哪裡找值」和「之後叫什麼」。
2. **測試資料照舊用 API 名字：** `test_station_model_quantity` 的 `VALID_STATION` 還是寫 `Quantity`，因為它模擬的是官方 JSON。
3. **和命名統一同一個原則：** 同一個值在程式、資料庫、dbt 只用一個名字；外部來源的名字改不了，就在進門的地方（模型）對照一次。

一句話記法：`Field(alias="外面的名字")`，外面怎麼叫都只寫在模型，裡面一律用自己的名字。

核對依據：範例在本機 Youbike/.venv（Python 3.9.6、pydantic 2.13.5）實跑。專案的模型在 2026-11-10 命名統一時改成 alias 寫法，`tests/unit` 同半小時連跑兩次 16 passed，16:00、16:30 正式擷取都 succeeded。本筆記不增加驗收完成數。

### 2026-11-09：test_station_model_quantity 在測什麼，為什麼這樣寫

問題：`tests/unit/test_youbike_extract.py` 的 `test_station_model_quantity` 在做什麼？為什麼是這 5 個值？

結論：**它證明新的 `YoubikeStation` 模型對 `Quantity` 的規則，和原本 `check_json` 一樣嚴格。** 5 個案例就是原本 `test_check_json` 測 `Quantity` 用的那 5 個值，只是檢查的對象從 `check_json` 換成模型；這正是 E3-2「先用既有測試證明行為一樣，再替換」的做法。

#### 測試本體（2026-11-09 15:11 存檔，函式在第 82 行）

```python
VALID_STATION = {"sno":"1","sna":"model check","sarea":"fixture","latitude":25.03,"longitude":121.56,"Quantity":6,
                 "available_rent_bikes":2,"available_return_bikes":4,"act":"1","srcUpdateTime":"2023-08-01 00:00:00"}
@pytest.mark.parametrize("quantity,should_raise",
    [
        (0,False),
        (10,False),
        (-1,True),
        (True,True),
        (1.5,True)
    ]
)
def test_station_model_quantity(quantity,should_raise):
    row = dict(VALID_STATION, Quantity=quantity)
    if should_raise:
        with pytest.raises(ValidationError):
            YoubikeStation.model_validate(row)
    else:
        YoubikeStation.model_validate(row)
```

#### 怎麼跑

1. **`VALID_STATION`：** 一筆 10 個欄位都合法的站，是基準，單獨丟進模型一定會通過。
2. **`@pytest.mark.parametrize`：** 同一個測試跑 5 次，每次帶一組 `(quantity, should_raise)`。
3. **`row = dict(VALID_STATION, Quantity=quantity)`：** 複製一份基準，只把 `Quantity` 換掉。每個案例只有 `Quantity` 不同，失敗就一定是 `Quantity` 造成的；而且是新的 dict，5 個案例之間不會互相污染。
4. **檢查結果：** `should_raise` 是 `True` 時放在 `pytest.raises(ValidationError)` 裡，模型有丟錯才算過；是 `False` 時直接呼叫，沒丟錯就算過。

#### 範例：`dict(基準, 欄位=新值)` 會複製，不會改到基準

```python
base = {"name": "pen", "Count": 2}
row = dict(base, Count=-1)
print("row: ", row)
print("base:", base)
print("same object:", row is base)
```

```text
row:  {'name': 'pen', 'Count': -1}
base: {'name': 'pen', 'Count': 2}
same object: False
```

#### 為什麼是這 5 個值

| 值 | 預期 | 被哪條規則擋 |
|---|---|---|
| `0` | 通過 | 邊界值，`ge=0` 包含 0 |
| `10` | 通過 | 一般值 |
| `-1` | 擋下 | `Field(ge=0)` |
| `True` | 擋下 | `strict=True`；不開嚴格會被當成 `1` 通過 |
| `1.5` | 擋下 | `strict=True`，int 欄位不收 float |

#### 為什麼只測 Quantity

另外兩個車位數欄位（`available_rent_bikes`、`available_return_bikes`）用的是同一條 `Field(ge=0)`。依 2026-10-14 的去重原則，同一個機制沒有新的失敗方式，就不再各測一遍。

一句話記法：基準一筆合法資料，每次只改一個值，看模型有沒有在該擋的時候丟 `ValidationError`。

核對依據：測試本體逐字取自 2026-11-09 15:11 的存檔；`dict` 範例在本機 Youbike/.venv（Python 3.9.6）實跑；`True` 在不嚴格時會被當成 `1`，依同日 LaxBox／StrictBox 範例的實跑結果。這次沒有重跑這支測試，本筆記不增加驗收完成數。

## 7. dbt

### 主題重點

- 讀表：原始表用 `{{ source('群組名', '表名') }}`，在 `sources.yml` 登記，`schema: public` 要明寫；dbt 自己建的 model 用 `{{ ref('檔名') }}`。`{{ }}` 讓 dbt 記下誰讀誰，才能擋壞資料、排順序、只跑受影響的部分、畫 lineage。
- 名字三層：資料庫（`profiles.yml` 的 `dbname`）→ schema（原始表在 `public`，model 放 `profiles.yml` 寫的 `dbt`）→ 表。schema 有兩個意思：表的結構，或資料庫裡的資料夾；設定檔裡的 `schema:` 一律是資料夾。
- 分層看用途：staging 清理每張來源表，是翻譯層；intermediate 是可重用的零件；mart 依需求組出給人用的表。需求來了先用零件組 mart，組不出來才補零件。
- view 存的是查詢，不是資料；要像快取一樣存結果用 `materialized='table'`，任務 4 的 incremental 是只把新資料加進表。
- 檢查三種：unit test（建之前，驗 SQL 邏輯）、contract（建的當下，驗欄位名稱與型別）、data test（建之後，驗真實資料）。檢查放在會出錯的那層；失敗會擋下游，但不刪資料。
- 目前的決定：`coverage` 與 `sample_count` 於 2026-11-13 拿掉（漏抓看 `run_status`）；mart 用 `ref` 讀 intermediate、不重算；新鮮度要不要放 mart 待 Andrew 決定。

### 2026-11-10：sources.yml 是做什麼的，以及資料庫、schema、表三層名字

問題：`sources.yml` 要幹嘛？應該寫什麼？為什麼 `schema` 寫 `public`，不是 `profiles.yml` 裡那個 schema，也不是 `youbike_test`？`raw_bytes`、`response` 對應的 schema 在哪？

結論：**`sources.yml` 是一本登記簿：替資料庫裡本來就有的表取短名字。model 用短名字讀表，dbt 把它換成完整表名，並記下「這個 model 的資料從這張表來」。** 你的既有表在 `youbike_test` 資料庫的 `public` schema 裡，所以 `schema` 寫 `public`，`tables` 底下寫 `response`（要用時再加 `raw_bytes`）。

#### 「schema」有兩種意思

| 意思 | 指什麼 | `raw_bytes` 的例子 |
|---|---|---|
| ① 表的結構 | 一張表有哪些欄位、什麼型別 | `sql/practice/raw_response.sql` 的 `CREATE TABLE raw_bytes (...)` |
| ② PostgreSQL 的 schema | 資料庫裡放表的「資料夾」 | `public` |

`.yml` 裡的 `schema:` 一律是意思 ②。表的結構（意思 ①）寫在 `columns:` 底下；HTML D14 的「來源 schema／型別」指的是意思 ①。這裡的「資料夾」是資料庫裡的分區，Finder 看不到。

#### 三層名字：資料庫.schema.表

```text
youbike_test（資料庫）
└── public（意思②的 schema）
    ├── raw_bytes（表）── 欄位 id、body、batch_id、fetched_start_at（意思①的結構）
    ├── response（表）
    └── run_status（表）
```

| 層 | 你的實際值 | 寫在哪 |
|---|---|---|
| 資料庫 | 測試 `youbike_test`、正式 `youbike` | `profiles.yml` 的 `dbname`（`YOUBIKE_TEST_DB_NAME`） |
| schema | `public` | `sources.yml` 的 `schema` |
| 表 | `response`、`raw_bytes` | `sources.yml` 的 `tables` 底下的 `name` |

在測試庫實跑三種寫法：

```text
connected to: youbike_test
schemas here: ['public']
SELECT count(*) FROM public.response                 -> 36327 rows
SELECT count(*) FROM youbike_test.response           -> UndefinedTable: relation "youbike_test.response" does not exist
SELECT count(*) FROM youbike_test.public.response    -> 36327 rows
```

兩段式名字的第一段會被當成 schema；`youbike_test` 是資料庫名，不是 schema，所以第 2 種找不到表。

#### public 是哪來的

PostgreSQL 建資料庫時就會自動建一個叫 `public` 的 schema。建表時沒寫 schema（例如 `CREATE TABLE response (...)`），表就放進 `public`。兩個資料庫實查：

```text
youbike_test: search_path = "$user", public | tables: ['public.raw_bytes', 'public.response', 'public.run_status']
youbike: search_path = "$user", public | tables: ['public.raw_bytes', 'public.response', 'public.run_status']
```

`search_path` 是沒寫 schema 時 PostgreSQL 依序去找的地方：先找和帳號同名的 schema（沒有建），再用 `public`。所以平常寫 `response`，其實是在用 `public.response`。

`sources.yml` 不寫 `schema` 時，dbt 不會用這個預設，而是把來源的 `name` 當成 schema 名（例如取名 `youbike`，就會去找 `youbike.response`，找不到）。所以要明確寫 `schema: public`。來源的 `name` 只是自己取的標籤，和資料庫名無關；怕和 `youbike` 資料庫混淆，可以取 `raw` 之類的名字。

#### 範例：有沒有登記的差別（商店訂單，獨立小專案）

```yaml
# models/sources.yml
sources:
  - name: shop          # 分類名，自己取
    schema: public      # 表在哪個 schema（資料夾）
    tables:
      - name: orders    # 表的真名
```

```sql
-- models/stg_orders.sql
select * from {{ source('shop', 'orders') }}
```

```text
-- 拿掉 sources.yml 時
Compilation Error
Model 'model.no_version_demo.stg_orders' (models/stg_orders.sql) depends on a source named 'shop.orders' which was not found
-- 放回 sources.yml，dbt compile 的結果
select * from "none"."public"."orders"
```

`"none"` 是範例 profile 填的資料庫名，`"public"` 來自 `sources.yml` 的 `schema`，`"orders"` 來自 `tables`。換成你的專案，連測試庫時會編譯成 `"youbike_test"."public"."response"`。

跑 dbt 時：先讀所有 `.yml` 建好登記簿；讀到 `{{ source(...) }}` 時查登記簿換成完整表名；同時記下依賴，所以 `dbt ls --select +模型` 能一路列到 `source:...`，這就是 lineage。直接在 SQL 寫 `public.response` 也能跑，但 lineage 會斷在 staging，之後的新鮮度檢查也是掛在 source 上，表改名時還得每個 model 都改。

#### profiles.yml 的 schema 和 sources.yml 的 schema

| 寫在哪 | 意思 | 方向 |
|---|---|---|
| `profiles.yml` 的 `schema` | dbt 把自己建的 staging、mart 放在哪 | 寫出去 |
| `sources.yml` 的 `schema` | 要讀的既有表放在哪 | 讀進來 |

圖書館範例裡 `profiles.yml` 寫 `demo_library`、`sources.yml` 寫 `demo_library_src`，dbt 從 `demo_library_src.loans` 讀，建出來的放進 `demo_library`：

```text
OK created sql view model demo_library.stg_loans
```

要分開的原因：dbt 每次會砍掉重建自己的 model；和原始表放在同一個 schema，萬一 model 和原始表撞名，原始資料會被蓋掉。`profiles.yml` 的 schema 取新名字（例如 `analytics`），不存在 dbt 會自己建。

#### 為什麼先接測試庫

任務 3 在開發：會反覆建、砍、重建 view 或表，正反測試要故意放不合格資料，寫錯的 SQL 也可能掃整張大表。正式庫每 30 分鐘就有 Airflow 寫入，而且在 USB 2.0 的硬碟上；測試庫帳號已確認能建 schema，正式庫權限還沒開；dbt 接 DAG 和正式庫排在任務 5（D20）。測試庫的 `response` 有 36,327 列，夠開發；其中有測試留下的未來時間 slot（例如 2098、2099 年），算小時資料時看到是正常的。

#### version: 2

`.yml` 開頭的 `version: 2` 是 dbt 這類設定檔的格式版本，不是專案版本（專案版本是 `dbt_project.yml` 的 `version: "1.0"`）。官方文件說 dbt 1.5 起可以省略；用 dbt 1.12.6 實測，沒寫 `version: 2` 的 `sources.yml` 照樣能讀：

```text
no_version_demo.stg_orders
source:no_version_demo.shop.orders
```

#### 你的 sources.yml 要寫什麼

- `sources` 底下的 `name`：分類名，自己取。
- `schema`：`public`。
- `tables` 底下每張表一個 `- name:`：`response`；要用 `raw_bytes` 時再加。
- `columns`：想記錄表的結構就加，照 `CREATE TABLE` 寫欄位與 `data_type`；只是紀錄，不會擋錯（source 不能用 contract）。
- source tests：不用加。`response` 的 NOT NULL、站點＋採樣時間不重複、數量不為負、`station_active` 只能 0／1 都已經由資料庫約束（D3）擋住，在 dbt 再驗一次抓不到新的錯；正反測試放在 staging。

#### 2026-11-13 補充：怎麼分辨兩種 schema、DDL、dbt 的 schema 何時建立

- **怎麼分辨：** 出現在設定檔或 SQL 關鍵字裡的 schema（`schema: public`、`CREATE SCHEMA`、`public.response`）一律是意思 ②；講設計或結構時（「schema 設計」「schema 變更」「這張表的 schema」）通常是意思 ①。
- **DDL：** 定義結構的 SQL（`CREATE TABLE`、`ALTER TABLE`）統稱 DDL（Data Definition Language），寫的就是意思 ①。dbt 社群慣例常把描述 model 欄位的 yml 命名成 `schema.yml`，那也是意思 ①。
- **`dbt` 這個 schema 何時出現：** `profiles.yml` 寫的 `schema: dbt` 要等第一次成功 build 出 model，dbt 才會建立。2026-11-13 查測試庫時只有 `public`，原始表 `raw_bytes`、`response`、`run_status` 都在裡面，`search_path` 是 `"$user", public`。
- **分開放的好處：** Python 和 Airflow 寫的原始表在 `public`，dbt 算出來的表在 `dbt`；dbt 的表可以整批重建，不會碰到原始資料。

一句話記法：`.yml` 的 `schema` 是資料夾，`public` 就是你既有表所在的資料夾；資料庫名交給 `profiles.yml`，表名寫在 `tables` 底下。

核對依據：2026-11-10 在本機 Youbike/.venv（Python 3.9.6）連 youbike_test 與 youbike 唯讀實查；商店範例用 Youbike/.venv-dbt 的 dbt-core 1.12.6 實跑（只 parse／compile，不連資料庫建東西）；圖書館範例是 2026-11-09 在 youbike_test 另開 schema 實跑、跑完已刪除。本筆記不增加驗收完成數。

### 2026-11-11：dbt 為什麼用 source() 讀表，不直接寫表名

問題：staging 的 SQL 可以直接寫 `from public.response`，為什麼要寫 `{{ source('youbike', 'response') }}`？只是換個寫法，dbt 能多知道什麼？有什麼好處？

結論：**`{{ }}` 裡的東西是 dbt 在 compile 時自己執行的；直接寫的表名只是一段文字，dbt 不會去讀懂它。** `source()` 執行時做兩件事：去 `sources.yml` 查出這張表真正的位置，換進 SQL；同時把「這個 model 讀了這張表」記進 `target/manifest.json`。有了這份依賴紀錄，dbt 才能在來源檢查失敗時自動停下下游、自動排執行順序、只跑受影響的部分，並畫出 lineage。model 之間互相讀用 `ref()`，道理相同。

#### 範例 1：compile 之後長怎樣

同一個專案裡，`stg_product_snapshot` 用 `source()`，`stg_hardcoded` 直接寫表名。跑 `dbt compile` 後：

```text
-- compiled stg_product_snapshot.sql
select
    product_id,
    captured_at,
    price,
    stock,
    discontinued,
    import_batch
from "youbike_test"."demo_store_src"."product_snapshot"
-- compiled stg_hardcoded.sql
select product_id, captured_at, stock
from demo_store_src.product_snapshot
-- manifest.json depends_on
stg_product_snapshot -> ['source.store_demo.store.product_snapshot']
stg_hardcoded -> []
```

- **用 `source()` 的：** 被換成完整的 `"資料庫"."schema"."表"`，manifest 也記下它依賴 `product_snapshot`。
- **直接寫的：** 送出去的 SQL 原封不動，依賴是空的 `[]`。

#### 範例 2：dbt 看得到的依賴（lineage）

```text
-- dbt ls --select +stg_product_snapshot
    store_demo.stg_product_snapshot
    source:store_demo.store.product_snapshot
-- dbt ls --select +stg_hardcoded
    store_demo.stg_hardcoded
-- dbt ls --select source:store+
    store_demo.stg_product_snapshot
    source:store_demo.store.product_snapshot
```

`+model` 列出往上游依賴的東西，`source:store+` 列出這個來源往下游影響到的東西。直接寫表名的 `stg_hardcoded` 兩邊都看不到它和來源的關係。

#### 範例 3：來源有問題，下游自動停下來

來源表放一列 `product_id` 是 NULL，`sources.yml` 對它設 `not_null`，跑 `dbt build`：

```text
    1 of 3 OK created sql view model demo_store.stg_hardcoded ...................... [CREATE VIEW in 0.15s]
    2 of 3 FAIL 1 source_not_null_store_product_snapshot_product_id ................ [FAIL 1 in 0.08s]
    3 of 3 SKIP relation demo_store.stg_product_snapshot ........................... [SKIP]
    Done. PASS=1 WARN=0 ERROR=1 SKIP=1 NO-OP=0 REUSED=0 TOTAL=3
```

用 `source()` 的 model 因為來源檢查失敗被 `SKIP`；直接寫表名的照樣建出來，壞資料就流下去了。

#### 放到任務 3 的好處

1. **擋壞資料：** `response` 的 source tests 失敗時，staging、小時統計、mart 都會停下來，不會算出錯的數字。
2. **順序不用自己排：** 三層用 `ref()` 串起來，`dbt build` 自動照 staging、小時統計、mart 的順序跑；以後加 weather、calendar 也一樣。
3. **只跑受影響的部分：** `--select stg_youbike_snapshot+` 只重建它和所有下游。任務 4（增量）和任務 5（接排程）會用到。
4. **往上追問題：** mart 數字怪時，用 `dbt ls --select +mart_station_hourly` 看它從哪幾張表算出來。D14 要的 lineage 就是這個。
5. **位置只寫一次：** schema 只寫在 `sources.yml`。用 `var` 切到壞資料做反測時，所有 model 跟著換，不用改每支 SQL。

#### 同一串問答的其他觀念

- **staging 是新建的 view：** `stg_youbike_snapshot` 是 dbt 用 `.sql` 檔名新建的 view。`.sql` 決定內容；`.yml` 是它的說明書（contract 型別、tests），描述的是 model 的輸出，不是來源表。來源表的欄位寫在 `sources.yml`，靠縮排分哪張表。
- **`.yml` 怎麼對到 model：** 靠 `- name: stg_youbike_snapshot` 這一行，不是靠檔名；一個 model 一個 `.yml` 只是習慣。
- **兩張表都有 `id`：** 在 SQL 用別名指定來源（`o.id`），再用 `as` 改成不同名字。`.yml` 寫 `as` 之後的名字；寫錯時 contract 會列出 `missing in definition`（yml 有、SQL 沒有）和 `missing in contract`（SQL 有、yml 沒有）。
- **先寫 SQL 再寫 `.yml`：** 比較順。型別不確定可以先猜，contract 失敗時 `definition_type` 就是實際型別；欄位沒寫齊前先不要開 contract。`dbt show --select 模型 --limit 5` 可以預覽輸出。
- **staging 只選欄位：** 一列仍是一站一個 slot；不分組、不 join、不刪資料、不補值。`station_active` 可以是 NULL（9/24、9/29 定案），`ingested_at` 舊資料是 NULL 代表不知道（9/29 定案）。
- **反測怎麼做：** `response` 有 DB 約束，壞資料寫不進去，所以要另開沒有約束的 fixture 放壞資料，讓 `sources.yml` 的 schema 用 `var` 讀，執行時用 `--vars` 指過去。`accepted_values` 不把 NULL 算失敗。

#### ref 和 source 的寫法（2026-11-13 補）

| 用途 | 寫法 | 幾個名字 |
|---|---|---|
| 讀 dbt 外面的原始表（入口） | `{{ source('youbike', 'response') }}` | 兩個：來源群組名＋表名 |
| 讀 dbt 自己建的 model（之後全部） | `{{ ref('int_station_hourly_availability') }}` | 一個：檔名，不含 `.sql` |

- **一定要有 `{{ }}`：** 這是 dbt 的 Jinja 語法，dbt 先把它換成真正的表名，再交給 PostgreSQL。沒有大括號時，PostgreSQL 會把 `ref(...)` 當成一個叫 `ref` 的函式，執行就報錯。
- **source 的第一個名字不是資料庫名稱：** `'youbike'` 是 `sources.yml` 裡 `- name: youbike` 取的群組名，對應 `schema: public`；連哪個資料庫由 `profiles.yml` 決定。dbt 專案名稱剛好也叫 `youbike`，但那是另一個名字。
- **ref 只寫檔名、不寫資料夾：** 檔案放在 staging、intermediate 還是 marts 都一樣，所以整個專案的 model 檔名不能重複。

```text
-- 圖書館範例的 dbt ls 輸出
library_demo.marts.latest_loan
library_demo.staging.stg_loans
source:library_demo.library.loans
```

model 會列出所在資料夾，但 `ref` 只需要 `stg_loans`；source 要兩段（`library` 群組裡的 `loans` 表）。兩種寫法最後都會換成真正的表名：source 換成 `public.response`，ref 換成 `profiles.yml` 設的 `dbt` schema 底下 dbt 建出來的表。

一句話記法：`source()`／`ref()` 是讓 dbt 記下「誰讀誰」；有了這份紀錄，dbt 才能幫你擋壞資料、排順序、挑範圍、畫 lineage。

核對依據：三個範例在 2026-11-11 用本機 Youbike/.venv-dbt（dbt-core 1.12.6、dbt-postgres 1.11.0）連 youbike_test 實跑，用的是暫時的示範 schema，跑完已刪除。本筆記不增加驗收完成數。

### 2026-11-12：view、staging 和資料庫上下游的關係

問題：staging（`stg_youbike_snapshot`）只是原樣 select，為什麼要有它？下游不是一樣要改？DB 約束不是已經會抓錯？view 是不是 cache？是不是為了資安？大家要資料是不是去敲 staging，再由它連 DB？

結論：**staging 是原始表和所有下游 model 之間唯一的一道門，像翻譯層：左邊接來源的名字，右邊輸出固定的名字和型別。** 它建成 view，而 view 存的是「查詢」不是「資料」：本身在 DB 裡、佔 0 bytes，每次被查都由 PostgreSQL 當場展開去讀原表，所以永遠是最新資料。dbt 只在 `dbt run` 時建立或更新這些 view，查資料時不參與。

#### 整條上下游

```text
查 mart_station_hourly（一般人或 Metabase 查這層）
  → PostgreSQL 展開 mart 的 SELECT，讀小時統計那層
  → 展開小時統計的 SELECT，讀 stg_youbike_snapshot
  → 展開 staging 的 SELECT，讀 public.response 的實際資料
```

全部在同一個 PostgreSQL 裡一次跑完。staging 不是另一個「去連 DB」的服務，它就是 `dbt` schema 裡的一個 view。

#### staging 為什麼存在

1. **來源變了只改一處：** 來源表的欄位名稱只出現在 staging。11/10 的改名如果發生在下游都寫好之後，只要把 staging 從 `select fetched_start_at as slot_time` 改成 `select slot_time`；小時統計和 mart 讀的是 staging 給的 `slot_time`，一個字都不用改。下游從第一天就寫 `ref('stg_youbike_snapshot')`，所以「把 response 換成 stg」只在寫 model 時做一次。
2. **型別在門口擋下：** `.yml` 的 contract 鎖住欄位型別，來源型別被改掉時 staging build 就失敗，不會一路流到 mart。
3. **只給下游需要的欄位：** 例如 `id` 不選。
4. **lineage 和自動停止的起點：** `response` → staging → 小時統計 → mart。
5. **之後每個來源都照這個模式：** weather、calendar 各有自己的 `stg_`，跨來源 join 在小時統計或 mart 層做。

#### DB 約束和 contract 擋的東西不一樣

- **DB 約束擋「寫進來的資料值」：** NOT NULL、UNIQUE、CHECK、FK。所以 2026-11-11 Andrew 決定 staging 不寫 tests，正反測試移到小時統計層。
- **contract 擋「來源結構被改掉」：** 改欄位型別在 DB 是合法操作，不會報錯，下游結果卻會悄悄變掉。

```text
before: stock / 2 = 2
ALTER TABLE ... TYPE numeric: no error
after:  stock / 2 = 2.5000000000000000
```

同一句 `stock / 2`，欄位從 integer 改成 numeric 後，從整數除法的 2 變成 2.5，NOT NULL 和 CHECK 都照樣通過，沒有任何錯誤。staging 有 contract 的話，build 時就會出現 `data type mismatch`。

#### view 不是 cache

10 萬列的表和讀它的 view：

```text
table size: 4608 kB | view size: 0 bytes
what the view stores: SELECT id, value FROM readings WHERE (value > (10)::numeric);
querying the view runs: ->  Seq Scan on readings  (cost=0.00..1490.40 rows=24384 width=0)
```

view 佔 0 bytes，存的是那句 SELECT；查 view 時執行計畫掃的是原表。像 cache 的是 dbt 的 `materialized='table'`：

```text
right after dbt run (source has 1 row): view 1 | table 1
after inserting 1 more row       : view 2 | table 1
after the second dbt run          : view 2 | table 2
```

view 馬上看到新資料；table 停在舊結果，要再跑一次 `dbt run` 才更新。table 要在 model 最上面寫 `{{ config(materialized='table') }}`；任務 4 的 incremental 是只把新資料加進表裡。

#### view 的用處和代價

- **把查詢取名字：** 下游像讀表一樣讀它，查詢邏輯只寫一次。
- **翻譯層：** 隱藏來源細節，讀的人只認 view 給的欄位。
- **永遠最新、不佔空間。**
- **控制權限：** 只開 view 不開原表，Phase 9 讓 Metabase 唯讀時會用到。
- **代價：** 每次查都要重算。很重又常被讀的查詢（之後的小時統計、mart）可能改用 table 或 incremental，任務 4 評估。

view 最核心的目的是讓「看到的資料樣子」和「實際怎麼存」分開（資料庫裡叫邏輯資料獨立性），資安是同一個特性延伸出來的用法。view 也不一定是原表的子集：可以只挑部分欄位或列，也可以算出原表沒有的值，例如每小時平均和 coverage（coverage 已於 2026-11-13 拿掉）。

一句話記法：view 是存起來的查詢，不是存起來的資料；staging 這個 view 是來源和下游之間的翻譯層，來源怎麼變都只改它。

核對依據：範例在 2026-11-12 用本機 Youbike/.venv（psycopg）與 .venv-dbt（dbt-core 1.12.6、dbt-postgres 1.11.0）連 youbike_test 實跑，用的是暫存表與暫時的示範 schema，跑完已刪除。staging 不寫 tests 的決定見 HTML 的 D14、D15 列。本筆記不增加驗收完成數。

### 2026-11-13：staging、intermediate、mart 怎麼分工，需求來了改哪一層

問題：`mart_station_hourly` 看起來和 `int_station_hourly_availability` 一模一樣，為什麼還要 mart？intermediate 是不是一個來源一張、mart 才整合多來源？一張 intermediate 該放多少、事先怎麼知道要做哪些、新需求來了改哪一層？

結論：**分層看用途，不看來源數。** staging 清理每張來源表；intermediate 是事先備好、可重用的中間零件（計算步驟）；mart 是依需求從零件組出來、給人直接用的答案。平常接到需求，就用既有零件組 mart（Andrew 的說法）；零件組不出來時，才新增或修改 intermediate。

#### 三層各做什麼

```text
staging（一張來源表一個）      intermediate（計算步驟）              marts（給人用的最終表）
stg_youbike_snapshot   ──→  int_station_hourly_availability  ──┐
stg_weather            ──→  int_station_weather_mapping  ──────┼──→  mart_station_hourly
calendar 來源          ──→  dim_date  ─────────────────────────┘
```

- **staging：** 每張來源表一個，只清理、改名、統一型別，不做商業邏輯。
- **intermediate：** 一個計算步驟一張。它還不是答案，但答案一定要先算它，例如「每站每小時平均可借車」。像 Excel 的小計工作表，帶業務意義，不是＋－×÷ 那種通用運算。
- **mart：** 依分析問題和 grain 組出的最終表，給分析的人和 Metabase 直接讀。

分辨看用途，不看來源數，兩個反例：`int_station_weather_mapping` 用到 YouBike 和氣象兩個來源，但它是零件，所以在 intermediate；Phase 6 的 `mart_daily_usage` 只用租借一個來源，但它是給人用的最終表，所以是 mart。

#### 現在 mart 和 intermediate 一樣，為什麼還要 mart

1. **對外的固定介面：** 規格寫「BI 角色唯讀 marts」，D56 的 Metabase 也只讀 marts。intermediate 可以隨時重構，只要 mart 欄位不變，報表就不會壞。
2. **發布邊界（D18，任務 4）：** 新結果先放候選，品質通過才替換 mart；失敗時 mart 保留舊的、仍可查的結果。
3. **後面會長大：** 任務 7 接天氣，任務 8 接台北日期、假日與尖峰（`is_rush_hour` 在 station-hour 推導）。到時 intermediate 仍只算 YouBike 的可借車，mart 負責把三個來源組起來。

現在的寫法有兩種選擇：A. 兩層都留，mart 先照搬 intermediate（業界常見的 dbt 寫法）；B. 先只做 mart，等組合變複雜再拆。另外，intermediate 照規範應讀 `ref('stg_youbike_snapshot')`，不直接讀 `source(...)`。

#### mart_station_hourly 的內容（依現行文件）

- **grain：** 一站 × 一個 UTC 小時，和 intermediate 相同。
- **可借狀況：** avg／min／max 可借車、avg 可還位。
- **不放 `sample_count`、`coverage`：** 2026-11-13 Andrew 定案拿掉。漏抓與站數變化看 `run_status`（例如 `inserted_count` 從 1,824 變 1,823），跨小時彙總直接從 staging 算。
- **新鮮度：** 指官方的 `source_update_time` 落後 `slot_time` 多久，擷取每次都成功時，官方資料仍可能是舊的。要不要放進 mart 還待 Andrew 決定，規格 4.3 那列的「quality／freshness」也待同步。
- **不放 `rental_count`：** snapshot 推不出借車次數。10:00 有 8 台、10:30 剩 5 台，可能是借走 3 台、借 6 還 3，或調度車載走 3 台，三種在 snapshot 裡長得一樣。借車次數要等 Phase 6 的租借資料。

技術細節：計數只能在做 GROUP BY 的那一層算。彙總成「一組一列」之後再數，每組永遠只剩 1 列。

```text
count in the same GROUP BY: [('amy', 20, 3), ('ben', 50, 1)]
count after aggregating:     [('amy', 1), ('ben', 1)]
```

#### 一張 intermediate 放多少

- **一個 grain：** 說得出「一列代表什麼」，並對它加 unique test。
- **一件事：** 名字一句話說得清楚；需要寫成「可借車和天氣和假日」就是做太多。
- **欄位：** 只放這一步算得出來、下游會用到的。
- **拆出新的一張的時機：** grain 不同、兩個以上下游要用、邏輯複雜到值得單獨寫 unit test。只用一次又簡單的，直接寫在 mart 的 CTE 裡。

#### 事先怎麼知道要做哪些

1. **從已知需求倒推：** 本專案的需求寫在課表：D57 要 2–3 張可借狀況加天氣、日曆的圖，倒推出規格 4.3 的那幾個 model。
2. **資料最自然的彙總：** 每 30 分鐘一筆的站點快照，幾乎每個問題都從「每站每段時間」開始。
3. **重構時才拆：** 新問題先寫在 mart，重複或變複雜時再拆成 intermediate。

前提是 raw 和 staging 完整保留，之後出現沒料到的問題，隨時能從底層重算。

需求從哪來：問使用者、看他們現有的報表、看資料本身的形狀、看上線後實際被查哪些欄位。

#### 日常的循環（Andrew 的說法）

```text
① 先建共用的重要零件（intermediate），依資料的 grain、核心實體與已知主要問題
② 使用者提出需求
③ 用既有零件組出 mart 回給使用者        ← 日常大多在這裡
④ 組不出來 → 新增或修改 intermediate，回到 ①；新零件之後也能給別的需求用
```

#### 新需求來了改哪一層

| 變更 | 改哪層 | 例子 |
|---|---|---|
| 新問題、新欄位組合 | mart | 想看下雨時的可借車，就在 mart 接天氣 |
| 計算規則改了 | intermediate | 天氣對應從 20 公里改成 10 公里 |
| 來源格式改了 | staging | 官方 API 改欄位名，只改 staging 的對應 |
| 新來源 | staging 新增，必要時加 intermediate，再接進 mart | Phase 4 加入 Weather |
| 效能或處理方式改了 | intermediate | 任務 4 把每小時這層改成增量處理 |

越下游越常改、波及越小；越上游越少動、一改影響所有下游。改了 intermediate，下游要一起重跑重驗：`dbt build --select <model>+`。mart 加欄位通常安全，改名或刪欄位會讓報表壞掉，contract 會讓這種改動在 build 時直接失敗。

#### 業界參考與 SOP

- **dbt 官方的專案結構指南：** 分三層；intermediate 命名 `int_<實體>_<動作>`，只讀 staging 或其他 intermediate，不直接給終端使用者。
- **Kimball：** 先保留最細的粒度（atomic grain），彙總從最細的往上算。本專案的 `response`（一站一次採樣）就是最細粒度。
- **intermediate 常見類型：** 改粒度（彙總）、對應或橋接、去重取最新、時間骨架（D12 對帳腳本的 `generate_series`）、轉置。

#### 面試可能的問法

- 「需求還不清楚時，你怎麼設計資料模型？」用這個專案回答：raw 和 staging 完整保留，先定 station-hour 這個最常用的 grain，其他依需求從既有零件組 mart，組不出來才補 intermediate。
- 「staging、intermediate、mart 怎麼分？」答用途，不答來源數，並用天氣對應和 `mart_daily_usage` 兩個反例說明。

一句話記法：staging 清理來源，intermediate 備零件，mart 組答案；需求來了先用零件組，組不出來才補零件。

核對依據：規格 4.3、D15／D18／D56／D57 的現行內容與 2026-11-13 拿掉 sample_count、coverage 的定案；計數範例在 youbike_test 用暫存表實跑一次；dbt 指南與 Kimball 是業界一般做法的整理，不是本專案文件。本筆記不增加驗收完成數。

### 2026-11-13：mart 怎麼寫、mart.yml 放什麼、ref 和 source 怎麼寫

問題：現在 intermediate 和 mart 會不會完全一樣，是不是 copy & paste？那 mart.yml 是不是就不需要了？`from ref('int_station_hourly_availability')` 這樣寫對嗎？dbt 裡是不是 source 兩層、之後就直接找檔名？

結論：**mart 用 `ref` 讀 intermediate，不重算一次。** 欄位可能幾乎一樣，但計算只留在 intermediate 一份。mart.yml 不寫重複的檢查，但 contract 和欄位描述要寫。`ref` 要包在 `{{ }}` 裡；source 用兩個名字，ref 只用檔名。

（ref 與 source 的寫法併到〈dbt 為什麼用 source() 讀表〉一節；mart.yml 放什麼併到〈dbt 的 yml 怎麼對上 SQL〉一節。）

#### mart 不是 copy & paste

- **不要做的：** 把 intermediate 的 `GROUP BY` 和 `min()`、`max()`、`avg()` 整段複製到 mart。分組規則會有兩份，改一邊漏一邊就對不上。
- **還會直接出錯：** intermediate 輸出的欄位是 `slot_hour`、`min_rent_bikes`、`avg_rent_bikes` 這些，已經沒有 `slot_time`、`available_rent_bikes`。mart 如果照抄原本的計算，會報「欄位不存在」（2026-11-13 14:10 的存檔就是這樣）。
- **該做的：** mart 直接選 intermediate 算好的欄位，不需要彙總函式，也不需要 `group by`。

```sql
-- 換個情境的寫法（學校成績，示意）：不重算平均，直接讀已算好的零件
select
    class,
    avg_score
from {{ ref('int_class_avg') }}
```

#### 現在 mart 可以和 intermediate 不一樣的地方

1. **台北時間的顯示欄位：** 規格寫「小時區間為 UTC `[hour,hour+1h)`，台北顯示轉 Asia/Taipei」。intermediate 照 UTC 分小時；mart 是給人看的那層，可以多一欄台北時間。

```text
-- SELECT TIMESTAMPTZ '2026-11-13 02:00:00+00' AT TIME ZONE 'Asia/Taipei'
hour_utc   : 2026-11-13 10:00:00+08:00 datetime tz-aware
hour_taipei: 2026-11-13 10:00:00 datetime naive
```

結果不帶時區，適合直接顯示。第一行顯示成 `+08:00`，只是 psycopg 照連線時區印出來；同一個時間點換算成 UTC 就是 02:00。

2. **新鮮度（待 Andrew 決定要不要放）：** 「這小時官方最新的 `source_update_time`」要在 intermediate 的 `GROUP BY` 裡用 `max()` 取，彙總之後就取不到了；mart 再算它落後 `slot_time` 幾分鐘。

一句話記法：mart 用 `{{ ref() }}` 讀零件、不重算；mart.yml 寫 contract 和描述，檢查放在會出錯的那層；source 兩個名字進 dbt，之後全部用檔名 ref。

核對依據：規格 4.3 與 availability 段、D56、規格風險表的 weather fanout；台北時間範例在 youbike_test 實跑一次；`dbt ls` 輸出取自 2026-11-09 的圖書館範例實跑。本筆記不增加驗收完成數。

### 2026-11-12：dbt 的 yml 怎麼對上 SQL、檢查在哪一層發生、衍生欄位怎麼驗

問題：yml 怎麼知道 SQL 的輸出？資料是不是一層一層從 DB 過濾下來、每層都被 yml 擋一次？一個欄位拆成 min、max、avg 三欄，yml 要寫幾個 name？三欄都來自同一個變數，一個對不就全對？

結論：**yml 靠名字掛到同名的 model 上；它描述和檢查的是「這一層的輸出」。檢查會讓下游停下，但不會刪資料。一個輸入變成幾個輸出欄，yml 就列幾個 name；同一個來源算出來的欄位不保證一起對，但不用一欄一欄驗，用一個 unit test 加一個欄位間的關係檢查就能一起驗。**

#### 1. yml 和 SQL 用名字配對

- `int_station_hourly_availability.sql` 的檔名就是 model 名字。yml 寫 `models:`，底下 `- name: int_station_hourly_availability`，dbt 就把說明、tests、contract、欄位設定掛到這個 model。不用 import，也沒有另外的介面。
- 頂層一定要是 `models:`（複數），底下是清單。寫成 `model:` 時 dbt 不報錯，直接略過：2026-11-12 跑 `dbt parse` 後查 manifest，兩個 model 都是 contract 沒開、沒有欄位、沒有對應的 yml。

```yaml
models:
  - name: int_station_hourly_availability
    config:
      contract:
        enforced: true
    columns:
      - name: station_id
        data_type: text
```

#### 2. 資料流：每層讀上一層，也會改變資料

`response` → `stg_youbike_snapshot` → `int_station_hourly_availability` → `mart_station_hourly`。每個 model 用 `ref()`／`source()` 讀上一層。建成 view 時只存查詢、不存資料，查下游時才一路往上讀到 `response`。每一層不只過濾：staging 改名、統一型別，intermediate 把一站一次的採樣彙總成一站一小時。

#### 3. 三種檢查，時間點不同

| 檢查 | 什麼時候跑 | 驗什麼 |
|---|---|---|
| unit test | model 建好之前 | 用手寫的假資料驗 SQL 邏輯 |
| contract | 建 model 的當下 | 輸出的欄位名稱、型別、欄數要和 yml 一致，不一致就建不起來 |
| data test | model 建好之後 | 查真實資料有沒有違反規則 |

每層的 yml 驗的是自己那層的輸出：staging 驗一站一個 slot 不重複，intermediate 驗一站一小時不重複、coverage 在 0 到 1 之間（coverage 已於 2026-11-13 拿掉），內容不同，不是同一個檢查做兩次。

#### 4. test 失敗會擋下游，但不會刪資料

圖書館範例在 source 放一筆重複的 `loan_id`，跑 `dbt build`：

```text
-- dbt build with a duplicate loan_id in the source
    5 of 9 FAIL 1 unique_stg_loans_loan_id ......................................... [FAIL 1 in 0.08s]
    6 of 9 SKIP unit_test latest_loan_picks_newest_time ............................ [SKIP]
    7 of 9 SKIP relation demo_library.latest_loan .................................. [SKIP]
    8 of 9 SKIP unit_test member_fees_adds_up_each_member .......................... [SKIP]
    9 of 9 SKIP relation demo_library.member_fees .................................. [SKIP]
    Done. PASS=4 WARN=0 ERROR=1 SKIP=4 NO-OP=0 REUSED=0 TOTAL=9
-- rows still in the staging view: 3
```

staging 的 test 失敗，下游的 model 和 unit test 全部 SKIP；但 staging 自己已經建好，壞的那列還在。test 只負責發現問題、讓這次執行失敗。要剔除壞資料，得在 SQL 裡寫，或交給之後的 quarantine。

#### 5. 一個輸入變成三欄，yml 就列三個 name

yml 描述的是輸出。intermediate 的輸出沒有 `available_rent_bikes`，只有 `min_rent_bikes`、`max_rent_bikes`、`avg_rent_bikes`，所以列三個 name，各寫各的型別。開了 contract 時每一個輸出欄都要列。原本的 `available_rent_bikes` 寫在 staging 的 yml。

同一個來源算出來，型別也可能不同（2026-11-12 在測試庫查）：

```text
date_trunc(...)          -> timestamp with time zone
min(integer)             -> integer
max(integer)             -> integer
avg(integer)             -> numeric
count(*)                 -> bigint
count(*)::numeric / 2    -> numeric
```

min、max 一定是出現過的值，所以還是 integer；平均可能有小數，所以是 numeric。

#### 6. 同一個來源，不代表一個對就全對

三欄是三個不同的計算，可以只錯一個。範例故意把 `max_fee` 寫成 `min(fee)`：

```sql
select member_id, min(fee) as min_fee, min(fee) as max_fee, avg(fee) as avg_fee
from {{ ref('stg_loans') }}
group by member_id
```

```sql
-- tests/fee_stats_in_order.sql：一個 singular test，回傳任何一列就算失敗
select * from {{ ref('fee_stats') }}
where not (min_fee <= avg_fee and avg_fee <= max_fee)
```

```text
    6 of 7 OK created sql view model demo_library.fee_stats ........................ [CREATE VIEW in 0.03s]
    7 of 7 FAIL 1 fee_stats_in_order ............................................... [FAIL 1 in 0.04s]
-- fee_stats rows: member 7 -> min 1.5, max 1.5, avg 1.75；member 9 -> 0.5, 0.5, 0.5
```

`min_fee` 和 `avg_fee` 都對，只有 `max_fee` 錯；一個「min ≤ avg ≤ max」的檢查就抓到了。只有一筆資料的會員 9 三個值相同，這個檢查抓不到，所以 data test 要搭配 unit test：在 fixture 裡放有高有低的資料，手算 min、max、avg，一次驗三欄。

不必一欄一欄驗：contract 列出每一欄是在宣告輸出的形狀（必要）；數值正確性用一個 unit test（一次驗多欄）加一個欄位間的關係檢查就夠。

#### mart.yml 放什麼（2026-11-13 補）

| 內容 | 現在需要嗎 | 原因 |
|---|---|---|
| 和 intermediate 一樣的值檢查 | 不用 | mart 只是照搬，重跑抓不到新錯誤；重複的測試要刪 |
| contract（欄位名稱和型別） | 要 | mart 是對外介面；之後重構 intermediate 不小心改了欄位，build 會直接失敗，不會悄悄弄壞 Metabase 報表 |
| 欄位描述 | 要 | D56 要給 Metabase 一份指標字典：來源、grain、null 的意思、新鮮度 |
| station-hour 不重複 | 現在可省，接天氣後一定要 | 任務 7 接天氣時，一站對到兩個測站，一列會變兩列（規格風險表叫 weather fanout），join 發生在 mart，所以檢查放 mart |

原則：**檢查放在可能出錯的那一層。** 值算錯只會發生在做計算的 intermediate；欄位被改壞、join 讓列數變多，發生在 mart。

一句話記法：yml 用名字掛上 model，描述這一層的輸出；檢查擋下游、不刪資料；每個輸出欄各列一個 name，數值用一個 unit test 加一個關係檢查一起驗。

核對依據：範例都在 Youbike/.venv-dbt（dbt-core 1.12.6、dbt-postgres 1.11.0）對 youbike_test 另開 schema 實跑，跑完已刪除；manifest 檢查是 2026-11-12 對 Andrew 當時的 yml 執行 `dbt parse`。本筆記不增加驗收完成數。

## 2026-11-13：dbt unit test 的 yml 每個欄位怎麼寫

問題：寫任務 3 的手算對帳時，`unit_tests` 底下的 `name`、`model`、`given`、`expect` 各是什麼？`.yml` 是不是都用 `models:` 開頭？`expect` 要寫幾筆？

結論：**`.yml` 最上層的 key 決定這一段在描述什麼，檔名不重要。unit test 寫在 `unit_tests:` 底下，每個測試由 `name`、`model`、`given`、`expect` 四塊組成：dbt 用 `given` 的假資料取代被測 model 讀的上游，跑那個 model 的 SQL，再和 `expect` 裡你手算的答案比對，一樣就 PASS。**

### 最上層的 key

依本機 dbt 1.12.6 原始碼（`dbt/parser/schemas.py`），除了可省略的 `version`，共有 14 個：

| 熟悉程度 | key | 用途 |
|---|---|---|
| 要熟（任務 3 在用） | `models`、`sources`、`unit_tests` | model 的欄位與 tests；原始資料表；手寫輸入＋預期輸出 |
| 知道有、用到再查 | `data_tests`、`seeds`、`snapshots`、`macros`、`exposures` | 自訂 SQL 測試的說明；專案內的小 CSV；記錄資料隨時間的變化（SCD2）；可重用的 SQL 片段；誰在用這些資料（例如儀表板） |
| 聽過就好 | `analyses`、`groups`、`functions`、`metrics`、`semantic_models`、`saved_queries` | 這個專案用不到 |

- `version: 2` 只是格式版本標記，dbt 1.5 之後可以省略；寫或不寫都能跑，全專案統一一種就好。
- 一個檔可以同時放好幾個 key，例如上面 `models:`、下面 `unit_tests:`。
- `dbt_project.yml`（專案設定）和 `profiles.yml`（連線設定）不在這套規則裡。

### unit test 的四個欄位

| 欄位 | 寫什麼 | 注意 |
|---|---|---|
| `name` | 這個測試自己的名字，用英文加底線，描述在驗什麼情況 | 同一個 model 可以有好幾個 unit test，`name` 各自不同；dbt 輸出顯示成 `model::name` |
| `model` | 被測的 model 名稱，也就是 `.sql` 的檔名 | 不是測試名字，和 `name` 是兩件事 |
| `given` | 一個清單；每一項有 `input`（被測 model 直接讀的 `ref(...)` 或 `source(...)`）和 `rows`（手寫的假資料） | `input` 不一定是最源頭，是被測 model 的 SQL 裡寫的那個；`rows` 只寫 model 有用到的欄位，其他欄位 dbt 自動補 NULL；時間要帶時區，例如 `"2026-11-13 09:00:00+00"` |
| `expect` | `rows`：你預期 model 輸出的每一列 | 一筆＝輸出的一列；欄位名稱要和 SQL 輸出一樣；可以只寫要比對的欄位；順序不用和輸出一樣；值要從 `given` 手算 |

### 範例（圖書館情境，2026-11-09 在 youbike_test 實跑）

```yaml
version: 2
unit_tests:
  - name: latest_loan_picks_newest_time
    model: latest_loan
    given:
      - input: ref('stg_loans')
        rows:
          - {loan_id: 1, member_id: 7, borrowed_at: "2026-01-01 08:00:00+00"}
          - {loan_id: 2, member_id: 7, borrowed_at: "2026-01-03 09:30:00+00"}
          - {loan_id: 3, member_id: 9, borrowed_at: "2026-01-02 10:00:00+00"}
    expect:
      rows:
        - {member_id: 7, last_borrowed_at: "2026-01-03 09:30:00+00"}
        - {member_id: 9, last_borrowed_at: "2026-01-02 10:00:00+00"}
```

```text
PASS latest_loan::latest_loan_picks_newest_time
```

`latest_loan` 的 SQL 讀的是 `ref('stg_loans')`，所以 `input` 寫 `ref('stg_loans')`，不是最源頭的 `loans` 表。

2026-11-13 另跑了一次：`expect` 兩筆的順序和輸出相反，而且少寫一個輸出欄位 `loan_count`，結果還是 `PASS member_fees::member_fees_reversed_rows_partial_columns`。所以順序不影響，沒寫的欄位不比對。

### expect 要寫幾筆

`expect` 是測資的正確答案。它的筆數不用自己決定，由 `given` 決定：`given` 裡有幾個「一站×一小時」的組合，`expect` 就有幾筆。

`given` 不用多，夠手算、又能把三種錯誤都抓出來就好。例如 4 筆：

| 站 | slot_time（UTC） | 可借車 |
|---|---|---|
| A | 09:00 | 3 |
| A | 09:30 | 6 |
| A | 10:00 | 2 |
| B | 09:00 | 7 |

可以分成 3 組，所以 `expect` 寫 3 筆：A 的 09 時（min 3、max 6、avg 4.5）、A 的 10 時（2、2、2）、B 的 09 時（7、7、7）。

這 4 筆分別在驗：
- 同站同小時兩筆：min、max、avg 有沒有算對。
- 同站下一個小時：分小時有沒有切對，10:00 不能算進 09 時。
- 另一站：分站有沒有分開。

### 常見錯誤

1. **先跑 SQL 再把輸出抄進 `expect`。** 這樣不管 SQL 對錯都會過，等於沒測。答案一定要從 `given` 手算。
2. **時間沒帶時區。** 照 UTC 分小時時，可能整整差 8 小時。
3. **contract 把 avg 寫成 integer。** 手算 4.5，輸出被當成整數就對不起來。
4. **`input` 寫錯。** model 讀 `ref(...)` 卻在 `given` 寫 `source(...)`，或反過來。

### 相關問答

- **model 是什麼：** model 是一支 SELECT，加上 dbt 幫你把結果存成表或 view。你只寫 SELECT，dbt 送進資料庫時會包成 `create view ... as (select ...)`，名稱就是檔名，並把 `{{ source(...) }}`、`{{ ref(...) }}` 換成真實表名。
- **分層：** staging 跟原始表一對一，只整理欄位；intermediate 放計算邏輯；mart 給使用者查。照分層，intermediate 應該讀 `ref('stg_...')` 而不是直接讀原始表，這樣原始表變動只改 staging，staging 的 tests 也才保護得到下游。

一句話記法：`given` 是假的輸入，`expect` 是手算的答案；dbt 只測一個 model，用假輸入取代它直接讀的上游。

核對依據：最上層 key 依本機 dbt 1.12.6 的 `dbt/parser/schemas.py`；`latest_loan` 範例 2026-11-09 在 youbike_test 實跑 PASS；順序與部分欄位那次是 2026-11-13 另跑的，也是 PASS；兩次都用暫存 schema，跑完已刪除。本筆記不增加驗收完成數。

## 2026-11-13：YAML 的 `-` 代表清單裡的一項

問題：unit test 的 `given` 只有一個 input，為什麼前面還要加 `-`？

結論：**`-` 在 YAML 裡代表「清單裡的一項」。dbt 規定某些欄位一定要是清單，因為那裡可能有好幾個；就算只有一個，也要寫成「只有一項的清單」。少了 `-`，dbt 讀不懂，`dbt parse` 會直接報錯。**

### 有沒有 `-`，讀出來差在哪

同一段 YAML，用 dbt 環境裡的 YAML 讀法實跑：

```yaml
given:
  - input: ref('stg_loans')
    rows: []
```

```yaml
given:
  input: ref('stg_loans')
  rows: []
```

```text
with -   : {'given': [{'input': "ref('stg_loans')", 'rows': []}]}
without -: {'given': {'input': "ref('stg_loans')", 'rows': []}}
```

- 有 `-`：`given` 是清單 `[...]`，裡面放一個 input，這是 dbt 要的格式。
- 沒有 `-`：`given` 變成單一的 `{...}`，不是清單。

把範例的 `given` 改成沒有 `-` 再跑 `dbt parse`，結果是：

```text
Parsing Error
  Invalid unit_tests config given in ... member_open_fees.yml
```

### unit test 裡出現三次

| 位置 | 為什麼是清單 |
|---|---|
| `unit_tests:` 底下的 `- name:` | 一個檔可以放好幾個測試 |
| `given:` 底下的 `- input:` | 一個 model 可以讀好幾張表 |
| `rows:` 底下的 `- {...}` | 迷你表有好幾列 |

`models:` 底下的 `- name:`、`columns:` 底下的 `- name:`、`sources:` 底下的 `- name:` 也是同一個規則。

### 縮排

`-` 後面那一項的其他 key 要和 `-` 後的第一個 key 對齊，例如：

```yaml
given:
  - input: ref('stg_loans')
    rows:
      - {loan_id: 1, fee: 1.5}
```

`rows` 和 `input` 對齊，表示兩個都屬於同一項；`rows` 底下的每一列再用 `-` 開頭。

一句話記法：看到「這裡可能有好幾個」的地方就用 `-` 開頭，只有一個也一樣。

核對依據：兩種寫法的讀法用 `.venv-dbt` 的 PyYAML 實跑；少了 `-` 的錯誤訊息是 2026-11-13 在暫存範例專案跑 `dbt parse` 得到的（dbt 1.12.6），跑完已還原。本筆記不增加驗收完成數。
