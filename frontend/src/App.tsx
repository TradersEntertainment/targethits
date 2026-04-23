import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Activity, ExternalLink, Trash2, TrendingUp, TrendingDown, Target } from 'lucide-react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

interface Tracker {
  id: number;
  url: string;
  symbol: string;
  target_price: number;
  condition: string;
  status: string;
  source?: string;
  current_price?: number;
}

export default function App() {
  const [trackers, setTrackers] = useState<Tracker[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newUrl, setNewUrl] = useState('');
  const [newPrice, setNewPrice] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [marketInfo, setMarketInfo] = useState<{wti_alert_date: string, current_month: string, instruction: string} | null>(null);

  const fetchMarketInfo = async () => {
    try {
      const res = await axios.get(`${API_URL}/market-info`);
      setMarketInfo(res.data);
    } catch (err) {
      console.error("Failed to fetch market info", err);
    }
  };

  const fetchTrackers = async () => {
    try {
      const res = await axios.get(`${API_URL}/trackers`);
      setTrackers(res.data);
    } catch (err) {
      console.error("Failed to fetch trackers", err);
    }
  };

  useEffect(() => {
    fetchTrackers();
    fetchMarketInfo();
    const interval = setInterval(() => {
      fetchTrackers();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleAddTracker = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    
    try {
      await axios.post(`${API_URL}/trackers`, {
        url: newUrl,
        target_price: parseFloat(newPrice)
      });
      setIsModalOpen(false);
      setNewUrl('');
      setNewPrice('');
      fetchTrackers();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Bir hata oluştu');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if(!confirm("Bu takibi silmek istediğinize emin misiniz?")) return;
    try {
      await axios.delete(`${API_URL}/trackers/${id}`);
      fetchTrackers();
    } catch (err) {
      console.error("Delete failed", err);
    }
  };

  return (
    <div className="min-h-screen p-8 md:p-12 max-w-7xl mx-auto flex flex-col gap-10">
      
      {/* Header section with rich aesthetics */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-6 border-b border-white/10">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-primary to-accent mb-2">
            Quantum Pyth Tracker
          </h1>
          <p className="text-gray-400 flex items-center gap-2">
            <Activity size={18} className="text-accent animate-pulse" />
            Kesintisiz Fiyat Takibi ve Telegram Bildirimleri (İğneler dahil)
          </p>
        </div>
        
        <div className="flex flex-col md:flex-row gap-4">
          {marketInfo && (
            <motion.div 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-3 px-5 py-2.5 bg-accent/10 border border-accent/20 rounded-2xl text-xs"
            >
              <div className="flex flex-col">
                <span className="text-[10px] text-accent/60 uppercase font-bold tracking-widest">WTI Rollover Uyarı Tarihi</span>
                <span className="text-accent font-mono font-bold text-sm tracking-widest">{marketInfo.wti_alert_date}</span>
              </div>
              <div className="w-px h-8 bg-white/5 mx-2"></div>
              <Activity size={16} className="text-accent" />
            </motion.div>
          )}

          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-primary to-blue-600 rounded-full font-medium shadow-[0_0_20px_rgba(59,130,246,0.3)] hover:shadow-[0_0_30px_rgba(59,130,246,0.5)] transition-all"
          >
            <Plus size={20} />
            Yeni Takip Ekle
          </motion.button>
        </div>
      </header>

      {/* Grid Layout with Spaces */}
      <main className="flex-1">
        {trackers.length === 0 ? (
          <div className="h-64 flex flex-col items-center justify-center text-gray-500 gap-4 glass-panel rounded-2xl">
            <Target size={48} className="opacity-50" />
            <p className="text-lg">Henüz takip edilen bir varlık yok.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            <AnimatePresence>
              {trackers.map((tracker) => (
                <motion.div
                  key={tracker.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  layout
                  className={`glass-panel rounded-2xl p-6 relative overflow-hidden group ${tracker.status === 'triggered' ? 'border-success/50 bg-success/5' : ''}`}
                >
                  {/* Decorative background glow */}
                  <div className={`absolute -top-20 -right-20 w-40 h-40 blur-3xl opacity-20 rounded-full pointer-events-none ${tracker.status === 'triggered' ? 'bg-success' : 'bg-primary'}`}></div>
                  
                  <div className="flex justify-between items-start mb-4 relative z-10">
                    <div>
                      <h3 className="text-xl font-bold text-white mb-1 flex items-center gap-2">
                        {tracker.symbol}
                        {tracker.source === 'polymarket' && <span title="Polymarket Botu Ekledi" className="text-lg">🤖</span>}
                        {tracker.status === 'triggered' && <span className="text-[10px] uppercase tracking-wider bg-success/20 text-success px-2 py-1 rounded-full font-semibold">Tetiklendi</span>}
                        {tracker.status === 'active' && <span className="text-[10px] uppercase tracking-wider bg-primary/20 text-primary px-2 py-1 rounded-full font-semibold flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-primary animate-ping"></span> Aktif</span>}
                      </h3>
                    </div>
                    <button 
                      onClick={() => handleDelete(tracker.id)}
                      className="text-gray-500 hover:text-danger hover:bg-danger/10 p-2 rounded-full transition-colors"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>

                  <div className="space-y-4 relative z-10">
                    <div className="flex justify-between items-center py-2 border-b border-white/5">
                      <span className="text-sm text-gray-400">Hedef Fiyat</span>
                      <span className="font-mono text-lg font-medium tracking-tight">
                        ${tracker.target_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
                        {tracker.condition === 'above' ? <TrendingUp size={16} className="inline ml-1 text-success" /> : <TrendingDown size={16} className="inline ml-1 text-danger" />}
                      </span>
                    </div>
                    
                    <div className="flex justify-between items-center py-2">
                      <span className="text-sm text-gray-400">Canlı Fiyat</span>
                      <span className="font-mono text-xl font-bold text-white">
                        {tracker.current_price ? `$${tracker.current_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}` : <span className="text-gray-500 text-sm">Bekleniyor...</span>}
                      </span>
                    </div>
                  </div>

                  <div className="mt-6 flex flex-col gap-2 relative z-10">
                    <a 
                      href={`https://pythdata.app/explore/${tracker.symbol.replace('/', '%2F')}`}
                      target="_blank" 
                      rel="noreferrer"
                      className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-sm text-gray-300 transition-colors"
                    >
                      Pyth'de İncele <ExternalLink size={14} />
                    </a>
                    
                    {tracker.source === 'polymarket' && (
                      <a 
                        href={tracker.url}
                        target="_blank" 
                        rel="noreferrer"
                        className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-blue-500/10 hover:bg-blue-500/20 text-sm text-blue-400 font-medium transition-colors border border-blue-500/20"
                      >
                        Bet Al <ExternalLink size={14} />
                      </a>
                    )}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </main>

      {/* Add Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setIsModalOpen(false)}
            />
            <motion.div 
              initial={{ opacity: 0, scale: 0.9, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.9, y: 20 }}
              className="relative w-full max-w-lg glass-panel rounded-3xl p-8 shadow-2xl border-white/20"
            >
              <h2 className="text-2xl font-bold mb-6">Yeni Takip Ekle</h2>
              
              {error && (
                <div className="mb-4 p-3 bg-danger/10 border border-danger/20 rounded-xl text-danger text-sm">
                  {error}
                </div>
              )}

              <form onSubmit={handleAddTracker} className="space-y-5">
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Pyth URL'si</label>
                  <input 
                    type="url" 
                    required
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    placeholder="https://pythdata.app/explore/Metal.XAU%2FUSD"
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all font-mono text-sm"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-gray-400 mb-2">Iğne Hedef Fiyatı ($)</label>
                  <input 
                    type="number" 
                    step="any"
                    required
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    placeholder="Aralıksız anlık veri çekilir, dokunduğu an yazılır"
                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 text-white placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all font-mono text-lg"
                  />
                </div>

                <div className="pt-4 flex gap-3">
                  <button 
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="flex-1 py-3 rounded-xl bg-white/5 hover:bg-white/10 transition-colors font-medium text-gray-300"
                  >
                    Vazgeç
                  </button>
                  <button 
                    type="submit"
                    disabled={loading}
                    className="flex-1 py-3 rounded-xl bg-primary hover:bg-blue-600 shadow-[0_0_20px_rgba(59,130,246,0.3)] transition-all font-medium flex items-center justify-center gap-2"
                  >
                    {loading ? <span className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin"></span> : 'Takibi Başlat'}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}
