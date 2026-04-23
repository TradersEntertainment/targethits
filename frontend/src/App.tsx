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
    <div className="min-h-screen p-8 md:p-12 max-w-7xl mx-auto flex flex-col gap-10 font-sans">
      
      {/* Header section with rich aesthetics */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6 pb-6 border-b border-white/5">
        <div>
          <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-primaryGlow via-primary to-accent mb-2 drop-shadow-sm">
            Quantum Pyth Tracker
          </h1>
          <p className="text-gray-400 flex items-center gap-2 font-medium text-sm md:text-base">
            <Activity size={18} className="text-accent animate-pulse" />
            Kesintisiz Fiyat Takibi ve Akıllı Telegram Bildirimleri
          </p>
        </div>
        
        <div className="flex flex-col md:flex-row gap-4">
          {marketInfo && (
            <motion.div 
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-3 px-5 py-2.5 bg-glass-gradient border border-accent/30 rounded-2xl text-xs shadow-glow-accent"
            >
              <div className="flex flex-col">
                <span className="text-[10px] text-accent/80 uppercase font-bold tracking-widest">WTI Rollover Uyarı Tarihi</span>
                <span className="text-white font-mono font-bold text-sm tracking-widest">{marketInfo.wti_alert_date}</span>
              </div>
              <div className="w-px h-8 bg-white/10 mx-2"></div>
              <Activity size={16} className="text-accent drop-shadow-[0_0_8px_rgba(139,92,246,0.8)]" />
            </motion.div>
          )}

          <motion.button 
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => setIsModalOpen(true)}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-primary to-blue-600 rounded-full font-bold shadow-glow-primary hover:shadow-[0_0_30px_rgba(59,130,246,0.6)] text-white transition-all border border-blue-400/30"
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
            <Target size={48} className="opacity-30" />
            <p className="text-lg font-medium">Henüz takip edilen bir varlık yok.</p>
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
                  whileHover={{ y: -5 }}
                  layout
                  className={`glass-panel rounded-3xl p-7 relative overflow-hidden group transition-all duration-300 ${tracker.status === 'triggered' ? 'border-success/50 bg-success/5 shadow-[0_0_30px_rgba(16,185,129,0.15)]' : 'hover:border-white/20 hover:shadow-2xl hover:bg-cardHover/40'}`}
                >
                  {/* Decorative background glow */}
                  <div className={`absolute -top-24 -right-24 w-48 h-48 blur-3xl opacity-[0.15] rounded-full pointer-events-none transition-all duration-500 group-hover:opacity-30 group-hover:scale-110 ${tracker.status === 'triggered' ? 'bg-success' : 'bg-primaryGlow'}`}></div>
                  
                  <div className="flex justify-between items-start mb-6 relative z-10">
                    <div>
                      <h3 className="text-xl font-extrabold text-white mb-2 flex items-center gap-2 tracking-tight">
                        {tracker.symbol}
                        {tracker.source === 'polymarket' && <span title="Polymarket Botu Ekledi" className="text-lg drop-shadow-md">🤖</span>}
                      </h3>
                      <div className="flex items-center gap-2">
                        {tracker.status === 'triggered' ? (
                          <span className="text-[10px] uppercase tracking-wider bg-success/20 border border-success/30 text-success px-2.5 py-1 rounded-full font-bold shadow-[0_0_10px_rgba(16,185,129,0.2)]">Tetiklendi</span>
                        ) : (
                          <span className="text-[10px] uppercase tracking-wider bg-primary/20 border border-primary/30 text-primaryGlow px-2.5 py-1 rounded-full font-bold flex items-center gap-1.5 shadow-[0_0_10px_rgba(59,130,246,0.2)]">
                            <span className="w-1.5 h-1.5 rounded-full bg-primaryGlow animate-ping"></span> Aktif
                          </span>
                        )}
                      </div>
                    </div>
                    <button 
                      onClick={() => handleDelete(tracker.id)}
                      className="text-gray-500 hover:text-danger hover:bg-danger/10 p-2 rounded-full transition-colors"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>

                  <div className="space-y-4 relative z-10 bg-black/20 p-4 rounded-2xl border border-white/5">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Hedef Fiyat</span>
                      <span className="font-mono text-lg font-bold tracking-tight flex items-center gap-1">
                        <span className="text-gray-500">$</span>
                        {tracker.target_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
                        {tracker.condition === 'above' ? <TrendingUp size={16} className="text-success ml-1 drop-shadow-[0_0_5px_rgba(16,185,129,0.5)]" /> : <TrendingDown size={16} className="text-danger ml-1 drop-shadow-[0_0_5px_rgba(239,68,68,0.5)]" />}
                      </span>
                    </div>
                    
                    <div className="h-px w-full bg-gradient-to-r from-transparent via-white/10 to-transparent"></div>

                    <div className="flex justify-between items-center">
                      <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Canlı Fiyat</span>
                      <span className="font-mono text-2xl font-black text-white tracking-tight drop-shadow-md">
                        {tracker.current_price ? (
                          <span className="flex items-center gap-1">
                            <span className="text-gray-500 text-lg">$</span>
                            {tracker.current_price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
                          </span>
                        ) : (
                          <span className="text-gray-500 text-sm font-medium animate-pulse">Bekleniyor...</span>
                        )}
                      </span>
                    </div>
                  </div>

                  <div className="mt-6 flex flex-col gap-2.5 relative z-10">
                    <a 
                      href={`https://pythdata.app/explore/${tracker.symbol.replace('/', '%2F')}`}
                      target="_blank" 
                      rel="noreferrer"
                      className="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 hover:border-white/20 text-sm font-semibold text-gray-200 transition-all group/btn"
                    >
                      Pyth'de İncele <ExternalLink size={14} className="group-hover/btn:translate-x-0.5 group-hover/btn:-translate-y-0.5 transition-transform" />
                    </a>
                    
                    {tracker.source === 'polymarket' && (
                      <a 
                        href={tracker.url}
                        target="_blank" 
                        rel="noreferrer"
                        className="flex items-center justify-center gap-2 w-full py-3 rounded-xl bg-blue-500/10 hover:bg-blue-500/20 text-sm text-blue-400 font-bold transition-all border border-blue-500/20 hover:border-blue-500/40 hover:shadow-[0_0_15px_rgba(59,130,246,0.2)] group/btn2"
                      >
                        Bet Al <ExternalLink size={14} className="group-hover/btn2:translate-x-0.5 group-hover/btn2:-translate-y-0.5 transition-transform" />
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
              className="absolute inset-0 bg-background/80 backdrop-blur-md"
              onClick={() => setIsModalOpen(false)}
            />
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-lg glass-panel rounded-[2rem] p-8 md:p-10 shadow-2xl border-white/10"
            >
              <h2 className="text-3xl font-extrabold mb-6 tracking-tight text-white">Yeni Takip Ekle</h2>
              
              {error && (
                <div className="mb-6 p-4 bg-danger/10 border border-danger/20 rounded-2xl text-danger text-sm font-medium">
                  {error}
                </div>
              )}

              <form onSubmit={handleAddTracker} className="space-y-6">
                <div className="space-y-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 ml-1">Pyth URL'si</label>
                  <input 
                    type="url" 
                    required
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    placeholder="https://pythdata.app/explore/Metal.XAU%2FUSD"
                    className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all font-mono text-sm shadow-inner"
                  />
                </div>
                
                <div className="space-y-2">
                  <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 ml-1">İğne Hedef Fiyatı ($)</label>
                  <input 
                    type="number" 
                    step="any"
                    required
                    value={newPrice}
                    onChange={(e) => setNewPrice(e.target.value)}
                    placeholder="Örn: 90.50"
                    className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-white placeholder:text-gray-600 focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-all font-mono text-lg shadow-inner"
                  />
                  <p className="text-[11px] text-gray-500 ml-1 font-medium mt-1">Aralıksız anlık veri çekilir, fiyata değdiği an bildirim atılır.</p>
                </div>

                <div className="pt-6 flex gap-4">
                  <button 
                    type="button"
                    onClick={() => setIsModalOpen(false)}
                    className="flex-1 py-4 rounded-2xl bg-white/5 hover:bg-white/10 border border-transparent hover:border-white/10 transition-all font-bold text-gray-300"
                  >
                    Vazgeç
                  </button>
                  <button 
                    type="submit"
                    disabled={loading}
                    className="flex-1 py-4 rounded-2xl bg-gradient-to-r from-primary to-blue-600 hover:from-primaryGlow hover:to-primary shadow-glow-primary transition-all font-bold text-white flex items-center justify-center gap-2 border border-blue-400/20"
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
