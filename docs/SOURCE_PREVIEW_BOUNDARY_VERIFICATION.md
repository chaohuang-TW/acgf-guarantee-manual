# Source Preview Boundary Verification

## 稽核目的
為了徹底排除「上一個 logical item 其實延伸到下一個 item 的起始 physical page，但因 `nextPrintedPage - 1` 推導方式而未被發現」的盲點，我們針對所有 `source-preview` 類型的文件（附錄、一般書表、專用書表）進行了全人工視覺驗證。

## 稽核方法
本機制禁止使用 OCR 或是基於 PDF 文字層的順序猜測，而是：
1. 提取出所有 `source-preview` 類型的相鄰項目邊界 (共 46 個邊界)。
2. 自動將上一個項目的推斷結束頁 (`previousEndPdfPage`) 與下一個項目的起始頁 (`currentStartPdfPage`) 截圖並並列。
3. 由人工 (或 AI 視覺能力) 進行肉眼查核，判斷實體頁面上是否發生多個單元共用 (shared-page) 的情況。
4. 驗證結果被鎖定在 `data/source-preview-boundaries.json` 中，包含 `version: 1` 及其所屬的 `sourcePdfSha256`。

## 稽核結果
經過 46 個邊界的逐一肉眼檢視：
- **全部 46 個邊界均為 `clean-new-page`**。
- 不存在任何 `source-preview` 項目與上/下一項目共用實體頁面 (`shared-page`) 的情況。
- 每個項目的內容均被明確的換頁或是空白分隔頁所隔開。

## CI 自動化防護
新增了 `scripts/audit_source_preview_boundaries.py` 腳本，加入 CI 流程。
- 若未來 PDF 版本 (`sha256`) 變更，腳本將自動拋出錯誤，強制要求重新進行人工視覺驗證並更新 manifest。
- 若 `data/toc.json` 被更動導致邊界對應不上，腳本也會自動拋出錯誤，確保 `source-preview` 的邊界定義絕對安全，再也不受制於 `nextPrintedPage - 1` 的盲點。
