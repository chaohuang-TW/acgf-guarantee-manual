# Experience Redesign 1.0 — 官方獎項與作品研究

檢視日期：2026-10-01。研究範圍僅為唯讀；未修改專案或提交外部表單。桌面視窗 1440 × 1000，手機視窗 390 × 844，Chromium / Playwright。這是瀏覽器模擬視窗，不是實體手機測試。獲獎紀錄與今日實站分開確認；今日頁面可能已非當年獲獎版本。

## 官方評選資料

- [Awwwards Evaluation System](https://www.awwwards.com/about-evaluation/)：官方頁實際讀取並截圖，確認 Design 40%、Usability 30%、Creativity 20%、Content 10%。這是平台評審機制，不能拿本專案內部自評替代。Developer Award 另有工程面評選；視覺獎項不等於 WCAG 合規證明。證據：`aw-criteria.json`、`aw-criteria-1440.png`。
- [Webby Judging Criteria](https://www.webbyawards.com/judging-criteria/)：已讀官方 2026/2027 Websites and Mobile Sites 七面向：內容、結構導覽、視覺、功能、互動、創新、整体體驗。此處不宣稱其有與 Awwwards 相同的權重。其視覺與功能文字包含對使用者需求及可近性的考量，並非要求所有網站使用 AI。
- [FWA](https://thefwa.com/)：透過官方案例頁實際確認 FWA of the Day 名稱、日期與類型；本次不援引第三方整理的門檻或權重。`/about/` 在本次瀏覽雖 HTTP 200，body 無可讀資料，因此未宣稱已讀到完整 FWA 評選規則。
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/) 與 [Core Web Vitals](https://web.dev/articles/vitals)：是另行驗收依據，不是獎項。Web Vitals 官方頁確認目前 LCP ≤ 2.5 秒、INP ≤ 200 毫秒、CLS ≤ 0.1 為 good thresholds，實際合規還需以行動／桌面真實使用者的第 75 百分位判斷。單次 lab 或 Lighthouse TBT 不能冒稱真實 INP。

## 七個選定案例

### 1. Rijksmuseum Collection Online

- 官方紀錄：[Webby 2025 Best User Interface](https://winners.webbyawards.com/2025/websites-and-mobile-sites/features-design/best-user-interface/333807/rijksmuseum-collection-online)，Webby Winner + People's Voice Winner。
- 實際檢視：[Collection](https://www.rijksmuseum.nl/en/collection)、以 UI 輸入 `Milkmaid` 後 Enter 送出的搜尋結果。1440 與 390 都截圖並看過；拒絕非必要 Cookie 後再截圖。URL 真正改為 `/en/collection/search?query=Milkmaid&collectionSearchContext=Art&page=1&sortingType=Popularity&view=gallery`。
- 可借鏡：搜尋字串在搜尋結果中仍保留；作品／圖書館／訪客故事分群與數量緊靠搜尋；Filter 以獨立入口漸進揭露。查詢與分類屬同一任務，而不是幾套搜尋。
- 不適合：全屏畫作、瀑布流、固定底部搜尋覆蓋內容。手機查詢 bar 可見，但横向類型項目在右邊截斷；不照搬這個完成度缺口。
- 轉化：手冊用安定的文字結果清單、保留 query 和結果數；篩選放進階面板；一般規定、書表、查索表以可讀標籤區分。不複製圖像或配色。
- 證據：`webby-rijksmuseum.json`、`rijks-1440-content.png`、`rijks-390-clear.png`、`rijks-search-1440.png`、`rijks-search-390.png`、`rijks-search.json`。

### 2. Nordiska Museet

- 官方紀錄：[Webby 2025 Cultural Institutions](https://winners.webbyawards.com/2025/websites-and-mobile-sites/general-desktop-mobile-sites/cultural-institutions/324196/nordiska-museet)，Webby Winner。
- 實際檢視：[首頁](https://www.nordiskamuseet.se/)、[Utforska 內容分類](https://www.nordiskamuseet.se/utforska/)、[Talesätt och ordspråk 文章](https://www.nordiskamuseet.se/utforska/livet-i-norden/talesatt-och-ordsprak/)，桌面與手機均已截圖並看過；關閉 Cookie 遮擋。
- 可借鏡：標題、導言、正文使用不同但一致的字體角色；麵包屑與內容分群有明確層級；手機將雙欄分類收成單列，標題依容器自然換行。
- 不適合：首頁 giant welcome、篇幅很長的置中導言、鮮豔橘色，以及首屏把主要工具推走。本案承辦人不需要先讀形象宣言。
- 轉化：短、直接的頁首＋可立即操作的搜尋；閱讀頁保留清楚的章名、source metadata 與中文正文角色，縮減導言和頭部空白；不借用其文案與品牌色。
- 證據：`project-nordiska.json`、`nordiska-1440-clear.png`、`nordiska-390-clear.png`、`nordiska-reading-1440.png`、`nordiska-reading-390.png`。

### 3. Elektra Virtual Museum

- 官方紀錄：[Awwwards 案例](https://www.awwwards.com/sites/elektra-virtual-museum)，SOTD 2022-08-01、Developer Award。官方案例頁已實際讀取（不是搜尋摘要）。
- 實際檢視：原站 `https://evm.elektramontreal.ca/en` 回傳 Cloudflare **522**，未宣稱看過運作中的網站。另實際開啟官方封存的 [Exhibition Page](https://www.awwwards.com/inspiration/exhibition-page)，1440／390，檢視其中的展覽畫面（390 是官方影片縮放顯示，不是原網站手機驗證）。
- 可借鏡：在封存畫面可確認網站身份、有限全域入口、下載动作與主題層次分開；以排字完成視覺辨識，而不需裝飾性 icon 卡片。
- 不適合：極端 giant headline 與 WebGL 展示；既有封存畫面不能证明其今日互動、載入效能或無障礙。不能借 Developer Award 作今日可近性結論。
- 轉化：本案採清楚但適度的章節標題、正常文字導覽與單一 source 工具區；不採 giant 字、動態藝術或沉浸轉場。
- 證據：`aw-elektra.json`、`project-elektra.json`（522）、`elektra-archive-1440.png`、`elektra-archive-390.png`。

### 4. The Museum of the World

- 官方紀錄：[Awwwards](https://www.awwwards.com/sites/the-museum-of-the-world)：SOTD **2015-12-25**；[FWA](https://thefwa.com/cases/the-museum-of-the-world)：FOTD **2016-01-13**。兩個平台不同日期不可混寫。
- 實際檢視：官方兩個案例頁均已讀。獲獎作品入口 `https://britishmuseum.withgoogle.com/` 目前 **轉到 Google Arts & Culture 的 British Museum 頁**；桌面、手機已截圖並看過，不能當原获獎互動畫面的验收。
- 可借鏡（限今日轉址頁）：館藏主體身份、簡短介紹、Stories／Virtual visits，與 Medium／Event／Place 等內容導覽分層，沒有把所有入口混為同一層。
- 不適合：原獲獎 3D 時間線今日未可用，不採其空間式跳躍、音訊、進場負擔；今日轉址頁不能证明當年作品操作。
- 轉化：手冊的全域「查規定／找書表／附錄與查索／版本來源」與主題、頁內小節分層；用原有目錄和正式 metadata，不建立猜測性關聯。
- 證據：`fwa-museumworld.json`（日期與官方 Launch URL）、`project-museumworld.json`、`project-museumworld-1440.png`、`project-museumworld-390.png`。

### 5. NASA's Visual Universe

- 官方紀錄：[FWA 案例](https://thefwa.com/cases/nasas-visual-universe)，FOTD **2019-11-21**，Website。
- 實際檢視：[作品](https://artsexperiments.withgoogle.com/nasasvisualuniverse)，1440 與 390；進場畫面、滚動後內容畫面已看。另使用獨立 390 初始視窗再測，避免只改視窗尺寸造成狀態差異。
- 可借鏡：視覺內容與說明側欄分區，界面可讓原資料與解說保持上下文；DOM 可確認有 Search 輸入入口。但本次未完成圖片選取與搜尋結果工作流，沒有宣稱全功能驗證。
- 不適合：初始畫面出現長時間空白／動畫進場；手機縮放後側欄與大畫布状态不理想。本案不得用模擬宇宙、強制動畫或機器學習改寫原文。
- 轉化：閱讀正文仍是主體，source 以按需侧面板出现；不用雙欄永久擠壓手機。保留正式 source 與文字同一工作空間是借鏡目的，不是採其資料演算法。
- 證據：`fwa-nasa.json`、`nasa-1440-content.png`、`nasa-390-clear.png`、`nasa-390-fresh.png`、`nasa-mobile-fresh.json`。

### 6. Ceramic Beats

- 官方紀錄：[FWA 案例](https://thefwa.com/cases/ceramicbeats)，FOTD **2026-09-22**，Website。
- 實際檢視：[作品](https://ceramic-beats.zui.ooo/)，1440／390，已截图并看過；另独立手機初始窗口复查。
- 可借鏡：九種材料的分類身份、物件格與 collection 來源同框，來源不是整站頁尾一個模糊链接。內容物件與來源總體有可見連結。
- 不適合：這是聲音互動工具，不是正式閱讀工具；390 下盤面旋轉，細小手寫 labels 及工具要求橫向理解；官方說明的生成音訊也不属于本案允许范围。
- 轉化：書表頁在完整比例 preview 旁邊／下方顯示格式號、正式名稱、頁碼、原 PDF 與確定的相关規定；不做節拍／生成聲音／強制旋轉／細小文字。
- 證據：`fwa-ceramic.json`、`project-ceramic-1440.png`、`project-ceramic-390.png`、`ceramic-390-fresh.png`。

### 7. National Gallery Imaginarium

- 官方紀錄：[Webby Cultural Institutions 2026](https://winners.webbyawards.com/winners/websites-and-mobile-sites/general-desktop-mobile-sites/cultural-institutions)，Webby Winner；[National Gallery 官方作品介紹](https://www.nationalgallery.org.uk/visiting/virtual-gallery/national-gallery-imaginarium) 亦确认该奖。
- 實際檢視：[作品](https://imaginarium.nationalgallery.org.uk/)，1440／390；初始截圖是 Cookie gate 和空畫面，另以獨立 390 初始視窗拒絕 Cookie 後再記錄，已看到完整比例的館內背景、清楚身份、單一 Start 按鈕和音效提示。沒有把未出現的內頁當成已看過。
- 可借鏡：新開手機畫面有明確的一個首要动作，身份與操作層次分開；內部導覽未充分可見，故不依它提出具體內容布局結論。官方介紹證明其以內容、聲景與引導進行體驗，但並非本案需要的方式。
- 不適合：進入閱讀前需先通過 Cookie 與沉浸載入。本案不新增 tracking／Cookie gate，不將直接查詢改成虛擬導覽。
- 轉化：反向驗證本案該採直接內容、無阻擋首屏、低動態，並明确把獲獎不等於本業任務相容寫入決策。
- 證據：`imaginarium.json`、`imaginarium-1440.png`、`imaginarium-390.png`、`imaginarium-390-fresh.png`、`imaginarium-mobile-fresh.json`。

## 額外嘗試但不列入七個主要案例

- Smithsonian's National Museum of Asian Art：官方 Webby 類別列表確認 **2024 People's Voice Winner / Cultural Institutions**；`https://asia.si.edu/` 本次 HTTP **403** request verification，未检视到網站设计，故没有拿它当视觉参照。
- National Gallery of Art Website：同一 Webby 官方類別列表確認 **2026 People's Voice Winner / Cultural Institutions**；`https://www.nga.gov/` 本次 HTTP **403**，未看网站画面。
- CANALS：`https://www.awwwards.com/sites/canals` 本次 HTTP 200 但 body 無可讀資料，官方獲獎記錄未完成核实；不以第三方转述计入本次案例。
- 猜測的 Rijksmuseum `/en/collection/artworks` 路徑實測404；已排除，實際研究使用 UI 自己產出的 `/collection/search?...`，不把404路徑当成合理页面。

## 轉化決定（本專案，而非他站原文）

1. **主動查詢優先**：首頁第一屏就是全文搜尋和少量任務入口；不讓形象大圖、引言、動態片頭占據工具位置。
2. **三級導覽**：全域任務 → 當前主題與相關主題 → 主題內小節／命中／書表／source。全站一致但不重複傾倒相同連結。
3. **編輯型閱讀工作區**：限寬中文正文、大而清楚的字、低噪音 metadata；桌面按需並看來源，手機用可關閉工具抽屜。
4. **內容自身是視覺素材**：正式 source preview、格式號、章節結構構成辨識，不借用他站照片、商標或聲音。
5. **任務狀態清楚**：保留 query、類型與返回狀態；loading、no-result、error、篩選為空分開，不用 animation 替代回饋。
6. **適用性與獲獎分開**：FWA 作品能啟發完成度，但強制旋轉、極小文字、source 未載入與 Cookie gate 都不得照搬。此研究不宣稱本案獲獎或已獲評審認可。

## 證據讀取說明

此目錄所有 `*.json` 包含本次實際 browser response status、最終 URL、title、body 與連結清單；截圖為本次實際執行所得。頁面 unavailable / redirected / archived 都已明確區分。檔名 `-clear` 表示拒絕非必要 Cookie 後、`-content` 表示捲動後，`-fresh` 表示 390 初始 viewport。只改 viewport 的截圖不能當成實機驗收。研究未使用新帳戶、付費、素材下載、資料提交或第三方分析寫入。
