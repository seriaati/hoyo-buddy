# Hoyo Buddy 更新日誌

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
