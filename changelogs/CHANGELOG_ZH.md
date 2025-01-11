# Hoyo Buddy 更新日誌

## v1.15.7  

### 新增功能  

- (`/web-events`) 新增命令來查看正在進行中的網頁活動，並設置通知器以提醒您有新活動。  
- (`/notes`) 為《絕區零》（ZZZ）新增懸賞委託和 Ridu 每週點數通知器。  
- (`/about`) 新增更新日誌按鈕。  

### 優化  

- (`/gacha-log view`) 修復緩存問題，提升祈願記錄頁面的性能。  
- (`/about`) 移除最新 Git 變更的顯示。  
- (`/mimo`) 在自動購買時，將旅行夥伴 Mimo 商店物品按照價格從高到低排序。  
- 改進其他語言的本地化。

### 問題修復  

- (`/characters genshin`) 修復因無屬性旅行者導致的 `KeyError` 問題。  
- (`/characters genshin`) 修復神里綾華天賦等級顯示錯誤的問題。  
- (`/stats`) 修復 ZZZ 中「未找到記錄卡片」的錯誤。  
- (`/build genshin`) 修復「沒有可繪製的阻止列表」的錯誤。  
- (`/gacha-log view`) 修復錯誤的 50/50 勝率計算。  
- (`/gacha-log view`) 修復 Web 應用中的 422 驗證錯誤。  
- (`/gacha-log view`) 處理無效的大小輸入。  
- (`/gacha-log import`) 處理匯入祈願記錄時的無效卡池類型問題。  
- (`/gacha-log import`) 修復 UIGF 匯入功能。  
- (`/mimo`) 在發送通知前確認任務完成狀態。  
- (`/mimo`) 在完成任務之間新增休眠間隔以避免觸發限速。  
- (`/mimo`) 移除任務名稱中的 HTML 標籤。  
- (`/mimo`) 修復購買物品後的錯誤。  
- (`/profile`) 修復不同遊戲的卡片設置混合的問題。  
- (`/profile genshin`) 修復隊伍卡片中顯示多餘天賦的問題。  
- (`/profile genshin`) 修復與 Mavuika 相關的驗證錯誤。  
- (`/search`) 修復 W-engine 精煉選擇器未更新所選值的問題。  
- (`/notes`) 修復《崩壞3》中的驗證錯誤。  
- (`/challenge zzz assault`) 修復增益圖標未顯示的問題。  

## v1.15.6

### 新增功能

- (`/mimo`) 新增旅行 Mimo 對於原神的支持（活動在撰寫時已經結束）。
- (`/mimo`) 新增自動抽獎功能。
- (`/challenge zzz`) 新增對於「危局強襲戰」遊戲模式的支持。
- (`/profile hsr`) 新增卡片樣式 2。
- (`/notes`) 新增對於絕區零懸賞委託及麗都週記任務資訊的顯示。

## 優化

- (`/check-in`) 減少重複的簽到 API 請求。

## 問題修復

- (`/mimo`) 修復當沒有完成任何任務或獲取任何積分時仍發送通知的問題。
- (`/mimo`) 修復有價值物品判斷方式的問題。
- (`/mimo`) 處理 -510001 錯誤。
- (`/mimo`) 修復在星穹鐵道中，有價值物品被誤認為裝飾品的問題。
- (`/mimo`) 當達到上限時禁用抽獎按鈕。
- (`/challenge zzz`) 修復卡片中錯誤的邦布圖片。
- (`/events`) 修復螺旋深淵進度錯誤的問題。
- (`/gacha-log view`) 修復錯誤的「距離上一稀有度的抽取次數」。
- 修復靜態圖片文件夾創建邏輯。

## v1.15.5  

### 新增功能  

- (`/mimo`) 自動完成需要在帖子下留言的任務。  
- (`/mimo`) 自動完成需要關注主題的任務。  
- (`/mimo`) 新增抽獎功能。  
- (`/mimo`) 新增通知設置。  
- (`/profile zzz`) 新增圖片設置，允許在構建卡中使用「Mindscape 3」的美術圖。  
- (`/profile zzz`) 新增春政 (Harumasa) 和雅 (Miyabi) 卡片數據。  
- (`/search`) 在某些公會中隱藏「未釋出內容」分類。  

### 優化  

- (`/mimo`) 在某些任務中顯示任務進度。  
- (`/mimo`) 在通知中顯示已完成任務的名稱。  
- (`/mimo`) 提升自動任務執行性能。  
- (`/challenge zzz shiyu`) 更新卡片佈局。  
- (`/challenge zzz shiyu`) 避免重複抓取代理人數據。  
- 在錯誤嵌入的頁腳顯示 Discord 伺服器邀請鏈接。  
- 在錯誤情況下解除項目加載狀態。  
- 在切換按鈕上新增開/關標籤。  
- 改進代理 API 請求邏輯。  
- 改善自動任務的錯誤處理邏輯。  

### 問題修復  

- (`/mimo`) 在兌換 Mimo 獎勵禮品碼後新增休眠間隔。  
- (`/mimo`) 修復任務清單中遺漏的任務。  
- (`/mimo`) 修復留言任務未被完成的問題。  
- (`/mimo`) 修復當沒有完成任何任務時仍發送通知的問題。  
- (`/mimo`) 自動完成中僅顯示 HoYoLAB 賬號。  
- (`/mimo`) 修復自動任務中的 `QuerySetError` 問題。  
- (`/mimo`) 修復帖子留言未被刪除的問題。  
- (`/mimo`) 處理旅行夥伴 Mimo 不可用於某些遊戲的情況。  
- (`/profile zzz`) 修復副屬性高亮未顯示在卡片上的問題。  
- (`/profile zzz`) 修復代理人被誤認為已緩存的問題。  
- (`/characters zzz`) 修復代理人總數顯示錯誤的問題。  
- (`/gacha-log upload`) 修復 zzz.rng.moe 導入時的問題。  
- (`/redeem`) 修復 Miyoushe 賬號出現在賬號自動完成選項中的問題。  
- (`/build genshin`) 處理某些角色缺失使用率的情況。  
- (`/events`) 修復 HSR 未來卡池未顯示為「尚未釋出」的問題。  
- 適配新的 ZenlessData 鍵值。  
- 修復 Hakushin API 的相關問題。  
- 捕獲 `dm_user` 方法中的一般異常情況。  

## v1.15.4  

### 新增功能  

- (`/build genshin`) 顯示角色隊伍配置的相關信息。  
- (`/mimo`) 新增指令來管理旅行 Mimo。  

### 優化  

- (`/build genshin`) 改善卡片設計。  
- (`/notes`) 使用事件日曆 API 檢查位面分裂事件。  

### 問題修復  

- (`/build genshin`) 修復一些 UI 問題。  
- (`/events`) 修復導致指令無法使用的問題。  
- (`/gacha-log upload`) 修復使用 UIGF 數據時的 `ValidationError` 問題。  
- (`/gacha-log upload`) 修復 UIGF 版本低於 3.0 時的 `KeyError` 問題。  
- (`/search`) 修復重複的自動完成選項問題。  

## v1.15.3  

先前版本中的錯誤程式碼導致部分使用者在登入時看到「請求次數過多」錯誤，請參閱[本文](https://link.seria.moe/kky283) 以了解更多資訊。

### 新增功能  

- (`/profile zzz`) 新增選擇器，可選擇想要突出的副屬性。  
- (`/profile hsr`) 新增 Fugue 和 Sunday 卡片數據。  

### 優化  

- (`/redeem`) 使用禮品碼本身掩蓋兌換鏈接。  
- (`/challenge genshin theater`, `/challenge genshin abyss`) 在卡片中顯示旅行者的元素屬性。  
- (`/accounts`) 對「請求過多」錯誤顯示自定義錯誤信息。  

### 問題修復  

- 修復指令未被翻譯為其他語言的問題。  
- 修復超時的模態未正確關閉的問題。  
- 修復 API 重試邏輯與錯誤處理邏輯。  
- 修復某些指令的 `ValueError` 問題。  
- 修復模態超時時間過短的問題。  
- 處理 Web 服務器重定向端點的 `KeyError` 問題。  
- (`/profile`) 處理從 Enka Network API 獲取數據時的 `EnkaAPIError` 問題。  
- (`/profile`) 更優雅地處理 Enka Network API 網關超時錯誤。  
- (`/profile`) 修復生成 AI 圖像時的 `BadRequestError` 問題。  
- (`/upload`) 修復上傳圖片時的 `BadRequestError` 問題。  

## v1.15.2 及以下

先前版本的更新日誌寫在 [Discord 伺服器](https://link.seria.moe/hb-dc) 內的 #更新 頻道中。  
