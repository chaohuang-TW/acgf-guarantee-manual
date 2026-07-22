# 查閱工具重點 UI/UX 改善與驗收說明

本文件記錄「農業信用保證業務作業手冊數位閱讀版」針對承辦放款人員實際查閱情境所進行的五項關鍵 UI/UX 優化。

---

## 🎯 五項重點改善說明

### 1. 簡潔 Sticky 頂端導覽 (Clean Sticky Header)
- **理念**：移除不必要的過度動畫與毛玻璃模糊效果，維持純色色塊（`--navy-950`）與細微下陰影。
- **行動版優化**：手機寬度下壓縮選單內距並隱藏標題副文字，確保 Sticky Header 占用最少直向空間。
- **無障礙**：設定 `z-index: 100`，避免遮擋跳轉錨點與跳至主要內容（Skip Link）。

### 2. 錨點遮蔽防護 (`scroll-margin-top`)
- **理念**：修正固定導覽列遮擋目標頁卡標題的問題。
- **適用選擇器**：`.page-card`, `[id]`, `section`, `h1`, `h2`, `h3`, `.toc-group`。
- **效益**：當使用者開啟含有 `#pdf-page-21` 錨點的 URL 或點擊搜尋結果時，頁面平滑定位且卡片標題完全露出於 Header 下方。

### 3. 長頁面「回頂部」按鈕 (Back-to-Top Button)
- **獨立架構**：位於獨立的前端腳本 `assets/js/site.js` 中。
- **顯示條件**：當頁面縱向滾動超過 400px 時顯現。
- **鍵盤與無障礙防護**：
  - 隱藏狀態下自動設定 `button.hidden = true`，防範鍵盤 Tab 鍵選取無效元素。
  - 點擊時依據 `prefers-reduced-motion: reduce` 自動選擇平滑或瞬間滾動。
  - 獨立單一實體按鈕，不重複建立 DOM。

### 4. 頁卡「複製本頁連結」 (Copy PDF Page Link)
- **理念**：提供方便承辦人員於通訊軟體或公文中分享確切 PDF 實體頁錨點的簡易操作。
- **錯誤防護機制**：
  - 使用 `async / await` 呼叫 `navigator.clipboard.writeText()`。
  - 複製成功顯示「已複製連結！」，2 秒後恢復。
  - 若遭到瀏覽器安全性限制或拒絕，顯示「無法自動複製，請手動複製網址列」，堅決不誤報假成功。

### 5. 專用乾淨列印樣式 (`@media print`)
- **列印時隱藏**：Header 導覽、搜尋面板、按鈕（複製連結、回頂部、開啟預覽）、Footer。
- **列印時保留**：麵包屑、頁碼標示、正文與「本網站為公開資料數位閱讀版，內容以正式發布 PDF 為準」身分警語。
- **分頁防護**：`.page-card` 設定 `break-inside: avoid;`，防止頁碼與內文遭不合理斷頁裁切。

---

## 🛠️ 架構拆分 (JS Architecture)

全站前端 JavaScript 已實現權責分離：
- `assets/js/search.js`：專責本機全文檢索、詞彙擴充與意圖比對。
- `assets/js/site.js`：專責全站閱讀互動（回頂部按鈕、複製本頁連結）。

`templates/base.html` 確保全站 291 個網頁皆載入 `site.js` 與 `site.css`。

---

## 🧪 驗收與構建指令

```bash
# 1. 重新建置全站 HTML
.venv/bin/python scripts/build_site.py

# 2. 執行全套驗證與稽核腳本
.venv/bin/python scripts/validate_site.py
.venv/bin/python scripts/validate_page_rendering.py
.venv/bin/python scripts/audit_content.py
PYTHONIOENCODING=utf-8 LC_ALL=en_US.UTF-8 .venv/bin/python scripts/audit_search_quality.py
```
