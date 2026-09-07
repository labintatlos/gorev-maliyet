// Senkronizasyon sistemi - Offline hesaplamaları bota gönder

const SYNC = {
  // Online/Offline durumunu kontrol et
  async checkConnection() {
    try {
      const response = await fetch('.');
      return response.ok;
    } catch {
      return false;
    }
  },

  // Senkronizasyonu başlat
  async start() {
    const isOnline = await this.checkConnection();

    if (!isOnline) {
      this.showOfflineIndicator();
      return;
    }

    this.hideOfflineIndicator();
    await this.syncPendingCalculations();
  },

  // Pending hesaplamaları bota gönder
  async syncPendingCalculations() {
    const unsyncedCalcs = DB.getUnsyncedCalculations();

    if (unsyncedCalcs.length === 0) {
      this.showSyncStatus('Tüm hesaplamalar senkronize edildi ✓');
      return;
    }

    this.showSyncStatus(`Senkronize ediliyor... (${unsyncedCalcs.length} bekleyen)`);

    try {
      for (const calc of unsyncedCalcs) {
        const success = await this.sendToBot(calc.data);

        if (success) {
          DB.markAsSynced(calc.id);
          this.showSyncStatus(`Hesaplama #${calc.id} gönderildi ✓`);
        } else {
          this.showSyncStatus(`Gönderme başarısız. Daha sonra tekrar deneyin.`);
          break;
        }
      }

      DB.clearSyncedCalculations();
      DB.setLastSyncTime();
      this.showSyncStatus('Tüm hesaplamalar senkronize edildi ✓');
    } catch (error) {
      console.error('Senkronizasyon hatası:', error);
      this.showSyncStatus('Senkronizasyon hatası. Lütfen daha sonra tekrar deneyin.');
    }
  },

  // Hesaplamayı bota gönder (Telegram WebApp SDK üzerinden)
  async sendToBot(calculationData) {
    try {
      // Telegram WebApp SDK'sı kullanarak bota veri gönder
      if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.sendData(JSON.stringify({
          action: 'save_calculation',
          data: calculationData
        }));
        return true;
      }

      // Fallback: WebApp SDK yoksa, genel POST isteği gönder
      const response = await fetch('./api/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(calculationData),
        timeout: 10000
      });

      return response.ok;
    } catch (error) {
      console.error('Bota gönderme hatası:', error);
      return false;
    }
  },

  // Offline göstergesi göster
  showOfflineIndicator() {
    const indicator = document.getElementById('offline-indicator');
    if (!indicator) {
      const div = document.createElement('div');
      div.id = 'offline-indicator';
      div.innerHTML = '📡 <strong>Çevrimdışı Mod</strong><br><small>Hesaplamalar otomatik kaydedilecek ve bağlanıldığında gönderilecek</small>';
      div.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: #ff9800;
        color: white;
        padding: 12px;
        text-align: center;
        font-size: 12px;
        z-index: 9999;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      `;
      document.body.prepend(div);
    } else {
      indicator.style.display = 'block';
    }
  },

  // Offline göstergesi gizle
  hideOfflineIndicator() {
    const indicator = document.getElementById('offline-indicator');
    if (indicator) {
      indicator.style.display = 'none';
    }
  },

  // Senkronizasyon durumu göster
  showSyncStatus(message) {
    const status = document.getElementById('sync-status');
    if (!status) {
      const div = document.createElement('div');
      div.id = 'sync-status';
      div.style.cssText = `
        position: fixed;
        bottom: 20px;
        left: 20px;
        right: 20px;
        background: #4caf50;
        color: white;
        padding: 12px;
        border-radius: 8px;
        font-size: 13px;
        z-index: 9998;
        max-width: 300px;
      `;
      document.body.appendChild(div);
    }

    status.textContent = message;
    status.style.display = 'block';

    // 5 saniye sonra gizle
    setTimeout(() => {
      status.style.display = 'none';
    }, 5000);
  }
};

// Online/Offline dinleyicileri ayarla
window.addEventListener('online', () => {
  console.log('İnternet bağlantısı sağlandı');
  SYNC.start();
});

window.addEventListener('offline', () => {
  console.log('İnternet bağlantısı kesildi');
  SYNC.showOfflineIndicator();
});

// Sayfa yüklendiğinde senkronizasyonu başlat
window.addEventListener('load', () => {
  SYNC.start();
});
