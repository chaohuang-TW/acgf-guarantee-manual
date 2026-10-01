# 呈現契約遷移

不刪除、放寬或跳過既有內容／排名斷言；沒有保留不可見的舊介面專門騙測試。

| 舊斷言／selector | 新介面／selector | 保留的行為 |
| --- | --- | --- |
| `get_by_role("searchbox", name="全文搜尋")` | `get_by_role("combobox", name="全文搜尋")` | 同一個type=search輸入、原查詢、Enter、建議方向鍵、q/type與Back；修復aria-expanded不合法角色 |
| 首頁大題名是手冊名稱 | `.brand span`手冊身份＋`#home-title`可見 | 名稱不變、身份在首屏；新h1是介面引導文字，不是改寫正式手冊 |
| 手機可直接點主要導覽 | 先開`.global-menu > summary`再點同一普通連結 | 同一目錄URL、網址改變、可鍵盤展開；不以JS假點擊代替href |
| 手機篇目錄直接展開 | 先開`.section-nav > details > summary` | 原章名、href與當前頁aria-current皆不變 |
| 直接讀取本規定目錄的可見文字 | 鍵盤Enter展開`.topic-toc-disclosure > summary`後讀同一連結 | 原條款逐字相等、唯一錨點與keyboard-focusable斷言全保留 |
| Tab直接走入來源連結 | 聚焦來源details summary、Enter展開，再保留原Tab/Enter/Back斷言 | 全部正常`.source-page-link`與實體頁hash不變；不是換成按鈕冒充來源跳轉 |
| 來源arialabel固定為「查看手冊第X頁原始頁面」 | 可見文字與無障礙名稱皆精確為資料推導的「手冊頁 X (PDF Y)」 | 正確手冊頁／PDF頁仍逐筆精確核對，實體href與anchor原斷言全部保留；修復可見名稱與aria-label不一致，未取消名稱驗證 |

`h3`搜尋結果、`.match-reason`、`mark.search-hit`、`.reading-hit-nav/current`、`.return-to-search`與原來源selector保持。
條款仍是原始`p`字元序列，額外`role=heading`/`aria-level=2`提供輔助科技章內導航。
原始來源、Related Forms與四主題正文不移出既有article，以避免破壞片段邊界與來源忠實性。

第一個完整CI嘗試在此15筆舊ARIA字串斷言停止，失敗記錄與前一manifest保留。完成上述呈現契約遷移後重新凍結並重跑完整CI；不能將第一個嘗試列為PASS。

第二個完整CI在手機收合導覽內先計算可見連結數而停止；將「展開summary」移至原本的唯一連結、點擊與目標URL斷言之前。橫式WebKit對content-visibility下的搜尋結果，先捲動真正第一筆結果至可見區，再執行原本精確標題／網址／命中理由檢查。兩者保留實際UI操作，沒有改成只讀DOM或降低斷言。

第三個完整CI在讀取收合的本規定目錄文字時停止；新增鍵盤展開前置操作，再保留全部原文字與錨點斷言。三次失敗記錄皆保留，最終結果只取重新凍結後完整CI的真正退出碼。

新增測試不取代原CI：`tests/e2e_experience_redesign.py`、`scripts/validate_experience_contracts.py`與`tests/experience_search_contract.cjs`。
後者對完整66組查詢逐欄比對排序、分數、exactForm、命中理由、來源段落、URL、頁碼與摘要；不是只測前幾名。
