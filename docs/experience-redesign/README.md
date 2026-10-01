# Experience Redesign 1.0 — 設計驗收候選版交接

正式基準：`212a9e79a2779296c45e6f6907c90e7d8dc0d4f2`。
本機分支：`codex/manual-experience-redesign`。不是正式上線版本；不push、merge、deploy、tag或Release。

## 先看與操作

交付包包含可直接由HTTP靜態伺服器開啟的完整候選站。入口：

- `/`：首頁與全文搜尋；輸入25a、格式 ２５ Ａ、代位清嘗或不予保證，按Enter。
- `/review/`：首頁、搜尋、正文、書表的390／1440同尺寸前後比較。
- `/design/experience-redesign/components.html`：實際共用CSS的元件與狀態展示。
- `/versions/115-04/chapters/part-2/overdue-guarantee.html`：長閱讀、相關書表與來源工具。
- `/versions/115-04/forms/form-25a.html`：正式原頁預覽；不是重設書表。

不要用file://測fetch或Worker。解壓候選站後在該資料夾執行：

```sh
python3 -m http.server 8765 --bind 127.0.0.1
```

開啟 `http://127.0.0.1:8765/`。HTTP伺服器不需要後端業務程式、外部API或網路字型。原始下載PDF仍含於候選站；本機伺服器由使用者自行停止。

## 改善的任務路徑

| 任務 | 舊版的額外負擔 | 候選版 |
| --- | --- | --- |
| 找規定／書表 | 搜尋結果先承擔大量前導狀態 | 送出後緊湊工作區、相同排名、原查詢與命中理由 |
| 閱讀完整主題 | 來源與目錄占首屏，正文較小 | 20px主柱，目錄按需展開，手機先看主題與正文 |
| 回查原文 | 桌機跳實體頁再返回，難同時比對 | 來源並看／手機modal；普通來源href仍可直接跳轉 |
| 開相關書表 | 須辨認既有Related Forms區 | 本頁工具直接列既有確定關係；返回規定及瀏覽器Back不變 |
| 查來源失败 | 圖片／fetch失敗缺少工作區替代狀態 | 明確錯誤，保留正常原PDF新分頁入口，不造新書表檔 |

搜尋至正文至書表仍保留原正常鏈結，沒有把真實目標換成JS事件。新來源工作區減少頁面往返，但按需工具多一次開啟動作；不宣稱所有任務都減少點擊。十項任務是工程模擬，不是真人使用者研究。

## 設計與研究

[設計方向、字級與三層IA](DESIGN.md) · [官方評選與七個作品研究](RESEARCH.md) · [實際迭代](ITERATIONS.md) · [舊測試契約遷移](TEST_MIGRATION.md)。

採編輯式閱讀工作台：紙白與墨綠、中文襯線章題、系統正文、限寬閱讀柱、原生收合。`design-taste-frontend`用於方向選擇、去模板化與反覆視覺審查；框架、照片與外部字型預設均服從本專案的原生靜態／真實來源限制。

## 建置與驗證

沿用現有Python／Node環境，不升級依賴；範例中的node若不在PATH，設定`NODE_BINARY`為既有完整路徑。

```sh
python scripts/build_site.py
python scripts/ci_validate.py
python scripts/validate_experience_contracts.py
python tests/e2e_experience_redesign.py
git diff --check
```

新E2E使用現有Playwright。可及性驗證工具axe-core僅供測試，透過`AXE_PATH`指定本機檔；不加入網站依賴。`EXPERIENCE_EVIDENCE_DIR`可指定外部輸出資料夾。正式完整矩陣不得用僅選寬度／瀏覽器的開發設定替代。

`validate_experience_contracts.py`獨立建置基準，核對103個不可變檔案、291條舊路由／錨點，以及66組**完整**搜尋結果的排序、分數、格式目標、理由、來源與摘要。新E2E增加真實操作的IME模擬、快速查詢／清空狀態、無Worker回退、字級、modal、焦點位置、影像比例、故障替代與列印。

最終完整CI會自行build並跑全部既有驗證／E2E。重導經tee時使用Bash pipefail，不能將tee成功當CI成功。最後manifest包含所有新檔；必須與CI後source／test／文件內容一致。

## 呈現改動的程式邊界

`templates/base.html`、`templates/home.html`與`assets/css/site.css`是共用呈現；`scripts/build_site.py`只加語意／工具hooks、不增新來源模型。`site.js`是導覽、字級與來源工作區。`search.js`原純函式保持基準，只調整UI排程／狀態／安全呈現；`search-worker.js`import同一份核心。

集中搜尋仍只有首頁與完整目錄。196筆完整索引與所有權威data、PDF、預覽、Related Forms、16單元與四個continuous單元邊界不變。來源工具fetch的是既有實體HTML，不生成新正文。未處理`GENERATED-SITE-SNAPSHOT-001`或`SEARCH-DISCOVERY-001`。

tracked `site/`建置產物不提交。清理前以`preview_experience_redesign.py`複製完整新建置與比較頁；因此交付預覽不會回到舊snapshot。重建下一個候選時仍應用新資料夾，不覆寫未知工作。

## 尚需外部驗收

Chromium／WebKit等桌面瀏覽器的模擬視窗不等於實機。本環境Firefox安裝檔啟動失敗（macOS sandbox extension／software framebuffer錯誤），未進入測試頁，不列為PASS；原錯誤保留在證據包。未做實體iOS／Android、螢幕閱讀器人工測試、真人承辦人研究、正式站UI smoke或field p75 INP。自動axe／Lighthouse不是WCAG認證或獎項保證。

來源圖片較多的書表仍需要滾動；PDF檢視與新分頁行為受瀏覽器設定影響。舊模式閱讀仍保留原來源分頁模型，沒有為了統一外觀擴張continuous來源邊界。沒有字型下載，Windows等平台的中文行寬／斷行需日後實機觀察。

下一步僅為使用者檢視此候選版並決定是否採用。不自動進入正式發布或其他搜尋／內容專案。
