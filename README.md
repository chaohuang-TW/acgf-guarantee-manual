# 農業信用保證業務作業手冊

農漁會版，中華民國115年4月公開資料數位閱讀版。

本專案將原始 PDF 忠實整理為可全文搜尋的靜態網站，方便依篇章、附錄、書表與 PDF 實體頁碼查閱。本網站不是農業信用保證基金官方網站，內容如與正式 PDF、後續函釋或公告不一致，以正式發布文件為準。

## 資料版本與來源

- 資料版本：中華民國115年4月
- 來源文件：財團法人農業信用保證基金《保證業務作業手冊（農漁會版）》
- PDF 實體頁數：203頁
- 原始檔保存位置：`source/acgf-guarantee-manual-115-04.pdf`
- 公開下載位置：`site/downloads/acgf-guarantee-manual-115-04.pdf`

兩份 PDF 必須保持位元完全相同，建置與驗證腳本會檢查 SHA-256。

## 正式發布資料

- 目前正式 Release：`v115.04.0`
- [版本紀錄頁](https://chaohuang-tw.github.io/acgf-guarantee-manual/versions/)
- [CHANGELOG](CHANGELOG.md)
- [新版更新檢核清單](docs/UPDATE_CHECKLIST.md)
- [本版 Release Notes](docs/releases/115-04.md)
- [SHA-256 驗證檔](SHA256SUMS.txt)

## 專案結構

```text
source/       原始 PDF，不修改、不重新壓縮
data/         版本、目錄與逐頁文字層資料
scripts/      擷取、建置與驗證腳本
templates/    靜態 HTML 樣板
assets/       本機 CSS 與原生 JavaScript
site/         GitHub Pages 唯一部署內容
.github/      GitHub Pages Actions workflow
```

## 本機建置

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/extract_manual.py
python scripts/build_site.py
python scripts/audit_content.py
python scripts/validate_site.py
python3 -m http.server 8000 --directory site
```

在瀏覽器開啟 `http://localhost:8000/`。網站使用相對路徑，可在 GitHub Project Pages 子路徑運作。

## 更新新版手冊

1. 先閱讀並逐項執行 [`docs/UPDATE_CHECKLIST.md`](docs/UPDATE_CHECKLIST.md)。
2. 保留既有 `source/`、`data/` 與 `site/versions/` 版本，不覆蓋舊版本或舊版 PDF。
3. 不移動既有 tag，不刪除既有 GitHub Release。
4. 將新版原始 PDF 以新的版本 ID 命名，例如 `115-10`。
5. 重新確認實體頁數、SHA-256、印刷頁碼映射與無文字層頁面，不沿用舊版頁碼映射。
6. 依新版正式目錄建立資料，依序擷取、建置、驗證並抽查原文、數字、日期、金額及百分比。
7. 將根目錄首頁指向新版，舊版標示為非最新版並繼續保留。

## 擷取原則

`scripts/extract_manual.py` 使用 PDF 既有文字層，不使用 OCR。它驗證來源檔、頁數與 SHA-256，逐頁保存 PDF 頁碼、可辨識的印刷頁碼、原始文字及僅供搜尋的空白正規化文字。

不使用 OCR 的原因是避免在法規、金額、年限、成數、日期與格式編號上產生誤辨。沒有文字層的頁面會標記為「原頁影像／表單版面」，並連回原始 PDF 實體頁。

## 複雜表格與正式書表

- 只有欄列順序能可靠確認時，才適合轉成 HTML 表格。
- 查索表若無法百分之百確認文字順序，不猜測重建，版面以原始 PDF 為準。
- 正式書表不重新設計為可填寫或可送出的線上表單。
- 擷取文字只用於搜尋與輔助查閱，正式填表版面仍以 PDF 為準。

## 全文搜尋與隱私

搜尋索引位於 `site/assets/data/search-index.json`，由原生 JavaScript 在使用者瀏覽器內比對完整子字串。沒有後端、資料庫、模型 API、向量搜尋、分析服務、Cookie 或使用者資料蒐集。

本網站不使用 AI，因為用途是忠實呈現來源文件與關鍵字檢索，不提供摘要、問答、推論、資格判斷或個案建議。

## 驗證

`scripts/validate_site.py` 會檢查：

- PDF 203頁與兩份 PDF 的 SHA-256
- HTML title、單一 H1、版本與免責說明
- 內部連結、資產與搜尋結果 URL
- 重複 ID、PDF 頁碼範圍與空白主章節
- 四大篇、附錄一至十八及重要搜尋關鍵字
- 外部資源、追蹤服務、AI 服務與網域根目錄絕對路徑

`scripts/audit_content.py` 會重新讀取至少20個代表位置，逐字比對 `pages.json` 與 PDF 當下擷取結果，涵蓋前言、目錄、四大篇、附錄、查索表、一般書表及專用書表。

部署前仍須以瀏覽器實測 390、768、1024、1440 像素版面、搜尋互動、深層頁面、PDF 下載、列印樣式、Console 與 Network。

## GitHub Pages 部署

`.github/workflows/pages.yml` 在 `main` 有新 push 時執行，也支援手動觸發。流程先執行驗證，只將 `site/` 上傳為 Pages artifact，再使用 GitHub 官方 Pages Actions 部署；不需要自訂 secret。

## 版本保存原則

每個版本使用獨立的 `site/versions/<版本ID>/` 路徑。新版只能新增，不能覆蓋或刪除舊版。根目錄首頁顯示目前版本，歷史版本則清楚標示已非最新版。

## 免責聲明

本網站為公開資料數位閱讀版，非農業信用保證基金官方網站。內容如與正式PDF、後續函釋或公告不一致，以正式發布文件為準。本網站內容不能取代正式規定，也不作為授信決策依據。
