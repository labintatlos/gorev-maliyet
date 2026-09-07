// localStorage ile offline hesaplamaları yönet

const DB = {
  STORAGE_KEY: 'gorev_calculations_pending',
  SYNC_KEY: 'gorev_last_sync',

  // Yeni hesaplamayı localStorage'a kaydet
  savePendingCalculation(calculationData) {
    try {
      const pending = this.getPendingCalculations();
      const id = Date.now();

      pending.push({
        id,
        data: calculationData,
        timestamp: new Date().toISOString(),
        synced: false
      });

      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(pending));
      return id;
    } catch (error) {
      console.error('Hesaplama kaydedilemedi:', error);
      return null;
    }
  },

  // Pending hesaplamaları al
  getPendingCalculations() {
    try {
      const data = localStorage.getItem(this.STORAGE_KEY);
      return data ? JSON.parse(data) : [];
    } catch (error) {
      console.error('Pending hesaplamalar okunamadı:', error);
      return [];
    }
  },

  // Senkronize edilmemiş hesaplamaları al
  getUnsyncedCalculations() {
    const pending = this.getPendingCalculations();
    return pending.filter(calc => !calc.synced);
  },

  // Hesaplamayı senkronize edildi olarak işaretle
  markAsSynced(id) {
    try {
      const pending = this.getPendingCalculations();
      const index = pending.findIndex(c => c.id === id);

      if (index !== -1) {
        pending[index].synced = true;
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(pending));
      }
    } catch (error) {
      console.error('Senkronizasyon işaretlenemedi:', error);
    }
  },

  // Senkronize edilen hesaplamaları temizle
  clearSyncedCalculations() {
    try {
      const pending = this.getPendingCalculations();
      const remaining = pending.filter(calc => !calc.synced);
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(remaining));
    } catch (error) {
      console.error('Temizleme başarısız:', error);
    }
  },

  // Son senkronizasyon zamanını al
  getLastSyncTime() {
    try {
      return localStorage.getItem(this.SYNC_KEY);
    } catch (error) {
      console.error('Son sinkron saati okunamadı:', error);
      return null;
    }
  },

  // Son senkronizasyon zamanını güncelle
  setLastSyncTime() {
    try {
      localStorage.setItem(this.SYNC_KEY, new Date().toISOString());
    } catch (error) {
      console.error('Son sinkron saati yazılamadı:', error);
    }
  },

  // Tüm verileri temizle
  clearAll() {
    try {
      localStorage.removeItem(this.STORAGE_KEY);
      localStorage.removeItem(this.SYNC_KEY);
    } catch (error) {
      console.error('Veriler silinmedi:', error);
    }
  }
};

// Service Worker kayıt et
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./service-worker.js')
      .then(registration => {
        console.log('Service Worker başarıyla kayıtlandı:', registration);
      })
      .catch(error => {
        console.log('Service Worker kaydı başarısız:', error);
      });
  });
}
